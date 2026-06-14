"""
Thread pentru citirea si procesarea cadrelor video (fisier sau RTSP).

Arhitectura producer-consumer:
  - ThreadCititor (threading.Thread intern): citeste cadre la FPS nativ, pune in coada
  - ThreadVideo   (QThread, consumator):     ia cadre din coada, ruleaza inferenta, emite semnale

Avantaj: video ruleaza la FPS nativ indiferent de viteza modelului.
Coada (maxsize=4) absoarbe diferenta; cand e plina, cititorul arunca cadrul cel mai vechi.
"""

import os
import queue
import threading
import time
import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from nuclee.clase_semne import nume_semn

# Valori sentinela puse in coada pentru comunicare intre thread-uri
_SFARSIT = None   # stream terminat normal
_EROARE  = "ERR"  # primul element al unui tuplu de eroare

# Prag minim de incredere ca sa afisam numele semnului clasificat (two-stage)
PRAG_CLASIFICATOR = 0.5

# Cadre de pastrare a ultimei cutii in tracking (anti-flicker)
COASTING_MAX_CADRE = 10


class ThreadVideo(QThread):
    """QThread consumator: inferenta YOLO + emitere semnale catre UI."""

    semnal_cadru    = pyqtSignal(QImage)
    semnal_fps      = pyqtSignal(float)
    semnal_latenta  = pyqtSignal(float)   # latenta medie de inferenta (ms) - reflecta imgsz
    semnal_detectii = pyqtSignal(list)
    semnal_progres  = pyqtSignal(int, int)   # (cadru_curent, total_cadre)
    semnal_eroare   = pyqtSignal(str)
    semnal_gata     = pyqtSignal()

    def __init__(self, sursa=None, model=None, config=None):
        super().__init__()
        self.sursa           = sursa
        self.model           = model
        self.config          = config or {}
        self._rulare         = False
        self._pauza          = False
        self._seek_to        = -1
        self._velocitate     = 1.0
        self._reset_tracker  = False
        self._clasificator   = None   # clasificatorul de semne (incarcat lazy, two-stage)
        self._cache_semne    = {}     # cache rezultate clasificare pe ID de tracking
        self._track_persist  = {}     # anti-flicker: ultima cutie cunoscuta per ID de tracking
        self._coada          = queue.Queue(maxsize=4)
        self._tracking_anterior = False   # mod tracking la cadrul precedent (pt reload la track->detect)

    # ------------------------------------------------------------------ #
    # API public
    # ------------------------------------------------------------------ #

    @property
    def velocitate(self):
        return self._velocitate

    @velocitate.setter
    def velocitate(self, val):
        self._velocitate = max(0.1, float(val))

    def seteaza_model(self, model):
        self.model = model
        self._tracking_anterior = False   # model proaspat din afara e curat (fara stare de tracking)
        self._track_persist.clear()       # cutii fantoma vechi nu mai sunt valide pe noul model

    def opreste(self):
        self._rulare = False

    def toggle_pauza(self):
        self._pauza = not self._pauza

    @property
    def in_pauza(self):
        return self._pauza

    def seek(self, cadru_index):
        """Sare la cadrul specificat (thread-safe)."""
        self._seek_to = max(0, int(cadru_index))
        self._cache_semne.clear()   # ID-urile de tracking reincep dupa seek -> golim cache-ul

    # ------------------------------------------------------------------ #
    # Thread cititor (producer) - ruleaza in threading.Thread, nu QThread
    # ------------------------------------------------------------------ #

    def _citeste_cadre(self):
        """
        Deschide sursa video, citeste cadre la FPS nativ si le pune in coada.
        Cand coada e plina (inferenta lenta), arunca cadrul cel mai vechi
        si pune cadrul nou - video ramine in sync cu timpul real.
        """
        cap = cv2.VideoCapture(self.sursa)
        if not cap.isOpened():
            self._coada.put((_EROARE, f"Nu pot deschide: {self.sursa}"))
            return

        total_cadre  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_sursa    = cap.get(cv2.CAP_PROP_FPS) or 30.0
        interval_ref = 1.0 / fps_sursa
        cadru_index  = 0

        while self._rulare:
            # --- Seek ---
            if self._seek_to >= 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, self._seek_to)
                cadru_index      = self._seek_to
                self._seek_to    = -1
                self._reset_tracker = True
                # Golim coada - cadrele vechi nu mai sunt relevante dupa seek
                _goleste_coada(self._coada)

            # --- Pauza ---
            if self._pauza:
                time.sleep(0.03)
                continue

            t_start = time.perf_counter()

            ret, cadru = cap.read()
            if not ret:
                self._coada.put(_SFARSIT)
                break

            cadru_index += 1

            # Incercam sa punem cadrul in coada fara sa blocam
            try:
                self._coada.put_nowait((cadru, cadru_index, total_cadre))
            except queue.Full:
                # Coada plina = inferenta mai lenta decat FPS-ul video.
                # Aruncam cadrul cel mai vechi si punem cadrul curent.
                try:
                    self._coada.get_nowait()
                    self._coada.put_nowait((cadru, cadru_index, total_cadre))
                except Exception:
                    pass

            # Timing: cititorul respecta FPS-ul nativ al videoclipului
            elapsed = time.perf_counter() - t_start
            sleep_t = (interval_ref / self._velocitate) - elapsed
            if sleep_t > 0.001:
                time.sleep(sleep_t)

        cap.release()

    # ------------------------------------------------------------------ #
    # Thread inferenta (consumator, QThread)
    # ------------------------------------------------------------------ #

    def run(self):
        if not self.sursa:
            self.semnal_eroare.emit("Nicio sursa video specificata.")
            return

        self._rulare = True

        # Pornim thread-ul cititor
        cititor = threading.Thread(target=self._citeste_cadre, daemon=True)
        cititor.start()

        contor_fps     = 0
        suma_lat       = 0.0
        n_lat          = 0
        timp_start_fps = time.perf_counter()

        while self._rulare:
            # Asteptam urmatorul cadru din coada (timeout ca sa putem verifica _rulare)
            try:
                item = self._coada.get(timeout=0.5)
            except queue.Empty:
                continue

            # --- Semnale speciale din cititor ---
            if item is _SFARSIT:
                break
            if isinstance(item, tuple) and item[0] is _EROARE:
                self.semnal_eroare.emit(item[1])
                break

            cadru, cadru_index, total_cadre = item
            detectii = []

            # --- Inferenta YOLO ---
            if self.model is not None:
                try:
                    conf_global  = self.config.get("confidence", 0.45)
                    iou          = self.config.get("iou", 0.45)
                    imgsz        = self.config.get("imgsz", 640)
                    use_tracking = self.config.get("show_tracks", False)
                    # La iesirea din tracking reincarcam modelul (track() lasa stare reziduala care incetineste detectia)
                    if self._tracking_anterior and not use_tracking:
                        cale_m = self.config.get("model_path")
                        if cale_m and os.path.exists(cale_m):
                            try:
                                from ultralytics import YOLO
                                self.model = YOLO(cale_m)
                            except Exception:
                                pass
                    self._tracking_anterior = use_tracking
                    clase        = self.config.get("classes", None)
                    if isinstance(clase, list) and len(clase) == 0:
                        clase = None

                    # Praguri per clasa (live din config; cheile pot fi str din JSON)
                    praguri = self.config.get("praguri_clase") or {}
                    praguri = {int(k): float(v) for k, v in praguri.items()}
                    # Rulam la cel mai mic prag necesar, apoi filtram per clasa la afisare,
                    # ca pragurile mai mici decat global-ul sa aiba efect real.
                    conf_floor = min([conf_global, *praguri.values()]) if praguri else conf_global

                    t_inf0 = time.perf_counter()
                    if use_tracking:
                        persist = not self._reset_tracker
                        if self._reset_tracker:
                            self._track_persist.clear()   # tracker resetat -> ID-urile reincep
                        self._reset_tracker = False
                        rezultate = self.model.track(
                            cadru, conf=conf_floor, iou=iou, imgsz=imgsz, classes=clase,
                            persist=persist, verbose=False
                        )
                    else:
                        self._reset_tracker = False
                        self._track_persist.clear()   # in afara modului tracking nu coasting
                        rezultate = self.model(
                            cadru, conf=conf_floor, iou=iou, imgsz=imgsz, classes=clase, verbose=False
                        )
                    suma_lat += (time.perf_counter() - t_inf0) * 1000.0
                    n_lat    += 1

                    # Filtrare per clasa: pastram cutiile cu conf >= pragul clasei (sau global).
                    # Filtram REZULTATUL, deci si lista de detectii SI cadrul desenat (plot).
                    if praguri:
                        rezultate = [self._filtreaza_praguri(r, praguri, conf_global) for r in rezultate]

                    for r in rezultate:
                        for box in r.boxes:
                            d = {
                                "cls":  int(box.cls[0]),
                                "conf": float(box.conf[0]),
                                "xyxy": box.xyxy[0].tolist(),
                            }
                            if use_tracking and box.id is not None:
                                d["id"] = int(box.id[0])
                            detectii.append(d)

                    # Etapa 2 optionala: clasificam semnele din cadrul original, inainte de plot()
                    if self.config.get("clasificare_semne"):
                        self._clasifica_semne(detectii, cadru)

                    show_labels = self.config.get("show_labels", True)
                    show_conf   = self.config.get("show_confidence", True)
                    cadru = rezultate[0].plot(labels=show_labels, conf=show_conf)

                    # Anti-flicker: redeseneaza cutiile track-urilor ratate temporar
                    if use_tracking:
                        self._aplica_coasting(detectii, cadru)

                    if self.config.get("clasificare_semne"):
                        self._deseneaza_semne(detectii, cadru)
                except Exception:
                    pass

            # --- Conversie si emitere cadru ---
            cadru_rgb = cv2.cvtColor(cadru, cv2.COLOR_BGR2RGB)
            h, w, ch  = cadru_rgb.shape
            qimg = QImage(cadru_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.semnal_cadru.emit(qimg.copy())
            self.semnal_detectii.emit(detectii)

            if total_cadre > 0:
                self.semnal_progres.emit(cadru_index, total_cadre)

            # --- FPS masurat (viteza reala a inferentei) ---
            contor_fps += 1
            acum = time.perf_counter()
            if acum - timp_start_fps >= 1.0:
                self.semnal_fps.emit(contor_fps / (acum - timp_start_fps))
                if n_lat > 0:
                    self.semnal_latenta.emit(suma_lat / n_lat)
                contor_fps     = 0
                suma_lat       = 0.0
                n_lat          = 0
                timp_start_fps = acum

        # Semnalam cititorului sa se opreasca si asteptam terminarea
        self._rulare = False
        cititor.join(timeout=2.0)
        self.semnal_gata.emit()

    # ------------------------------------------------------------------ #
    # Filtrare praguri per clasa
    # ------------------------------------------------------------------ #

    def _filtreaza_praguri(self, r, praguri, conf_global):
        """Pastreaza doar cutiile cu conf >= pragul clasei lor (fallback: pragul global).
        Filtreaza obiectul Results, deci efectul se vede si in plot, nu doar in lista."""
        boxes = getattr(r, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return r
        try:
            import torch
            cls_t  = boxes.cls.int()
            conf_t = boxes.conf
            thr = torch.full_like(conf_t, float(conf_global))
            for c, p in praguri.items():
                thr[cls_t == c] = float(p)
            keep = torch.nonzero(conf_t >= thr, as_tuple=True)[0]
            if int(keep.numel()) == len(boxes):
                return r   # nimic de taiat
            return r[keep]
        except Exception:
            return r

    # ------------------------------------------------------------------ #
    # Etapa 2: clasificare semne (two-stage)
    # ------------------------------------------------------------------ #

    def _incarca_clasificator(self):
        """Incarca o singura data clasificatorul de semne din modele/clasificator_semne.pt."""
        if self._clasificator is not None:
            return self._clasificator
        base = os.environ.get(
            "ADAS_BASE_DIR",
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        cale = os.path.join(base, "modele", "clasificator_semne.pt")
        if not os.path.exists(cale):
            return None
        try:
            from ultralytics import YOLO
            self._clasificator = YOLO(cale)
        except Exception:
            self._clasificator = None
        return self._clasificator

    def _clasifica_semne(self, detectii, cadru):
        """Clasifica semnele detectate (clasa 9). Optimizat:
        (B) cache pe ID de tracking - un semn deja clasificat NU se re-clasifica;
        (A) batch - toate decupajele neclasificate intr-UN SINGUR apel de inferenta.
        """
        cls_semn = int(self.config.get("cls_semn", 9))
        if cls_semn < 0:
            return   # modelul curent nu are clasa de semn -> two-stage dezactivat
        clf = self._incarca_clasificator()
        if clf is None:
            return
        h, w = cadru.shape[:2]

        crops, refs = [], []
        for d in detectii:
            if d["cls"] != cls_semn:   # clasa de semn (din model.names, nu hardcodat 9)
                continue
            tid = d.get("id")
            # (B) refoloseste rezultatul din cache daca semnul (ID) e deja clasificat
            if tid is not None and tid in self._cache_semne:
                semn, cf = self._cache_semne[tid]
                if semn:
                    d["semn"] = semn
                    d["semn_conf"] = cf
                continue
            x1, y1, x2, y2 = (int(v) for v in d["xyxy"])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            crops.append(cadru[y1:y2, x1:x2])
            refs.append(d)

        if not crops:
            return

        # (A) UN SINGUR apel batch pentru toate decupajele neclasificate
        try:
            rezultate = clf(crops, verbose=False)
        except Exception:
            return

        # Limitam cache-ul ca sa nu creasca la infinit pe stream-uri foarte lungi
        if len(self._cache_semne) > 4000:
            self._cache_semne.clear()

        for d, rez in zip(refs, rezultate):
            try:
                idx  = int(rez.probs.top1)
                cf   = float(rez.probs.top1conf)
                nume = nume_semn(clf.names, idx)
                semn = nume if (nume and cf >= PRAG_CLASIFICATOR) else None
                if semn:
                    d["semn"] = semn
                    d["semn_conf"] = cf
                tid = d.get("id")
                if tid is not None:
                    self._cache_semne[tid] = (semn, cf if semn else 0.0)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Anti-flicker (coasting) pentru modul tracking
    # ------------------------------------------------------------------ #

    def _culoare_clasa(self, cls):
        """Culoarea (BGR) folosita de YOLO plot() pentru o clasa, ca fantomele
        sa arate la fel ca cutiile reale. Fallback verde daca nu e disponibila."""
        try:
            from ultralytics.utils.plotting import colors
            return colors(int(cls), True)   # bgr=True -> potriveste cadrul BGR
        except Exception:
            return (0, 255, 0)

    def _aplica_coasting(self, detectii, cadru):
        """Redeseneaza ultima cutie a track-urilor ratate temporar (max COASTING_MAX_CADRE
        cadre) si le adauga ca detectii 'coasted'. Sare cutiile lipite de marginea
        cadrului (obiecte iesite din scena)."""
        h, w = cadru.shape[:2]
        margine = int(0.02 * max(h, w)) + 2   # ~2% din latura -> "atinge marginea"
        prezenti = set()
        for d in detectii:
            tid = d.get("id")
            if tid is None:
                continue
            prezenti.add(tid)
            self._track_persist[tid] = {
                "xyxy": list(d["xyxy"]),
                "cls":  d["cls"],
                "conf": d["conf"],
                "semn": d.get("semn"),
                "semn_conf": d.get("semn_conf"),
                "lipsa": 0,
            }

        for tid in list(self._track_persist.keys()):
            if tid in prezenti:
                continue
            info = self._track_persist[tid]
            info["lipsa"] += 1
            x1, y1, x2, y2 = (int(v) for v in info["xyxy"])
            la_margine = (x1 <= margine or y1 <= margine
                          or x2 >= w - margine or y2 >= h - margine)
            if info["lipsa"] > COASTING_MAX_CADRE or la_margine:
                del self._track_persist[tid]   # prea vechi sau a iesit din scena
                continue
            cv2.rectangle(cadru, (x1, y1), (x2, y2), self._culoare_clasa(info["cls"]), 2)
            d = {
                "cls": info["cls"], "conf": info["conf"],
                "xyxy": list(info["xyxy"]), "id": tid, "coasted": True,
            }
            if info["semn"]:
                d["semn"] = info["semn"]
                d["semn_conf"] = info["semn_conf"]
            detectii.append(d)

    def _deseneaza_semne(self, detectii, cadru):
        """Scrie numele semnului clasificat deasupra cutiei, pe cadrul desenat."""
        for d in detectii:
            if "semn" not in d:
                continue
            x1, y1 = int(d["xyxy"][0]), int(d["xyxy"][1])
            txt = f"{d['semn']} {d['semn_conf']:.0%}"
            cv2.putText(cadru, txt, (x1, max(14, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 230, 90), 2, cv2.LINE_AA)


def _goleste_coada(q):
    """Goleste o coada fara sa blocheze."""
    while not q.empty():
        try:
            q.get_nowait()
        except queue.Empty:
            break
