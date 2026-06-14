"""
Optimizare automata a pragurilor de incredere PER CLASA.

Ruleaza model.val si, din curba F1-Confidence per clasa, alege pragul Best-F1 pentru
fiecare clasa. Rezultat: dict {id_clasa: prag(0..1)}. Valideaza pe setul stratificat
din aplicatie/date_validare/ la 1280px, cu yaml construit dinamic (cai absolute,
portabil). Ruleaza intr-un QThread; nu porni in timpul unei antrenari pe GPU.
"""

import os
import random
import shutil
import tempfile
from collections import defaultdict

import yaml
from PyQt6.QtCore import QThread, pyqtSignal

# Prag F1 minim ca sa consideram o clasa "optimizabila". Clasele degenerate
# (ex. 'train' in BDD100K, cvasi-absenta) au F1 ~0 -> raman pe pragul global.
_F1_MINIM = 0.05

# Rezolutia de validare (= rezolutia de antrenare, cele mai reprezentative praguri)
IMGSZ_VAL = 1280

# Cate imagini per clasa in subsetul stratificat (folosit la CONSTRUIREA folderului)
CAP_PER_CLASA = 400

# Numele claselor BDD100K (fallback daca nu gasim un yaml cu names)
NUME_IMPLICITE = {
    0: "pedestrian", 1: "rider", 2: "car", 3: "truck", 4: "bus",
    5: "train", 6: "motorcycle", 7: "bicycle", 8: "traffic light", 9: "traffic sign",
}

_EXT_IMG = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


class ThreadOptimizare(QThread):
    """Ruleaza validarea pe setul curatat si extrage pragul Best-F1 per clasa."""

    semnal_status = pyqtSignal(str)     # cheie de traducere pentru status
    semnal_gata   = pyqtSignal(dict)    # {id_clasa(int): prag(float)}
    semnal_eroare = pyqtSignal(str)

    def __init__(self, cale_model, val_dir, names, device=None, parent=None):
        super().__init__(parent)
        self.cale_model = cale_model
        self.val_dir    = os.path.normpath(val_dir)   # folderul absolut cu imaginile de validare
        self.names      = names or NUME_IMPLICITE
        self.device     = device                       # None = auto (GPU daca exista)

    def run(self):
        try:
            from ultralytics import YOLO

            self.semnal_status.emit("optim_loading")
            model = YOLO(self.cale_model)

            data = self._construieste_yaml()
            self.semnal_status.emit("optim_running")
            kwargs = dict(data=data, imgsz=IMGSZ_VAL, batch=4, conf=0.001,
                          verbose=False, plots=False, save_json=False)
            if self.device is not None:
                kwargs["device"] = self.device
            metrics = model.val(**kwargs)

            praguri = self._extrage_praguri(metrics)
            if not praguri:
                self.semnal_eroare.emit("Nu am putut extrage praguri (val fara rezultate per clasa).")
                return
            self.semnal_gata.emit(praguri)

        except Exception as e:
            self.semnal_eroare.emit(str(e))

    def _extrage_praguri(self, metrics):
        """Din metrics.box: pentru fiecare clasa prezenta, ia confidence-ul cu F1 maxim."""
        box = getattr(metrics, "box", None)
        if box is None:
            return {}
        try:
            px  = list(getattr(box, "px"))           # axa de confidence (0..1)
            f1c = getattr(box, "f1_curve")           # (nc_prezent, len(px))
            idx = list(getattr(box, "ap_class_index"))
        except Exception:
            return {}

        praguri = {}
        for rand, cls_id in enumerate(idx):
            try:
                curba = f1c[rand]
                bi = int(curba.argmax())
                if float(curba[bi]) < _F1_MINIM:
                    continue   # clasa degenerata -> ramane pe global
                # Limitam la intervalul sliderelor (5..95%) ca valoarea stocata (folosita
                # si la inferenta) sa coincida cu pozitia afisata in Setari.
                praguri[int(cls_id)] = max(0.05, min(0.95, round(float(px[bi]), 3)))
            except Exception:
                continue
        return praguri

    def _construieste_yaml(self):
        """Yaml temporar cu cai ABSOLUTE catre tot folderul de validare (portabil)."""
        radacina = os.path.dirname(os.path.dirname(self.val_dir))   # parintele lui 'images'
        tmp = os.path.join(tempfile.gettempdir(), "adas_optim")
        os.makedirs(tmp, exist_ok=True)
        cale_yaml = os.path.join(tmp, "val_optim.yaml")
        with open(cale_yaml, "w", encoding="utf-8") as f:
            # Ultralytics cere OBLIGATORIU si 'train' in yaml, chiar daca rulam doar 'val'
            # (altfel: SyntaxError "'train:' key missing"). Punem train = val (nu se scaneaza).
            yaml.safe_dump(
                {"path": radacina, "train": self.val_dir, "val": self.val_dir, "names": dict(self.names)},
                f, allow_unicode=True, sort_keys=False
            )
        return cale_yaml


def gaseste_resurse_val(dir_app):
    """Localizeaza folderul de validare (imagini) si numele claselor.
    Cauta INTAI in folderul aplicatiei (date_validare/), apoi in radacina proiectului.
    Returneaza (val_dir_absolut, names) sau (None, None) daca nu exista."""
    radacina_proiect = os.path.dirname(dir_app)

    candidati_val = [
        os.path.join(dir_app, "date_validare", "images", "val"),          # in-app (standalone)
        os.path.join(radacina_proiect, "dataset_bdd100k_yolo", "images", "val"),
        os.path.join(dir_app, "dataset_bdd100k_yolo", "images", "val"),
    ]
    candidati_yaml = [
        os.path.join(radacina_proiect, "bdd100k.yaml"),
        os.path.join(dir_app, "bdd100k.yaml"),
        os.path.join(radacina_proiect, "dataset_bdd100k_yolo", "bdd100k.yaml"),
    ]

    names = dict(NUME_IMPLICITE)
    for cy in candidati_yaml:
        if os.path.exists(cy):
            try:
                with open(cy, "r", encoding="utf-8") as f:
                    d = yaml.safe_load(f) or {}
                if d.get("names"):
                    names = d["names"]
                    break
            except Exception:
                continue

    for vd in candidati_val:
        if os.path.isdir(vd):
            return os.path.normpath(vd), names
    return None, None


# --------------------------------------------------------------------------- #
# Utilitar offline: construieste folderul de validare stratificat (subset).
# Nu e folosit la runtime; ruleaza-l manual cand vrei sa (re)generezi date_validare.
# --------------------------------------------------------------------------- #

def selecteaza_stratificat(val_dir_complet, cap=CAP_PER_CLASA, seed=0):
    """Returneaza lista de NUME de fisiere imagine (esantion stratificat) din val_dir_complet:
    pana la `cap` imagini per clasa, max disponibil pentru clasele rare."""
    val_dir_complet = os.path.normpath(val_dir_complet)
    labels_dir = val_dir_complet.replace(os.sep + "images" + os.sep, os.sep + "labels" + os.sep)
    imgs = [f for f in os.listdir(val_dir_complet) if f.lower().endswith(_EXT_IMG)]

    per_clasa = defaultdict(list)
    for f in imgs:
        lp = os.path.join(labels_dir, os.path.splitext(f)[0] + ".txt")
        if not os.path.exists(lp):
            continue
        clase = set()
        try:
            with open(lp, "r", encoding="utf-8") as fh:
                for linie in fh:
                    linie = linie.strip()
                    if linie:
                        clase.add(int(float(linie.split()[0])))
        except Exception:
            continue
        for c in clase:
            per_clasa[c].append(f)

    random.seed(seed)
    sel = set()
    for c in sorted(per_clasa, key=lambda k: len(per_clasa[k])):   # clasele rare primele
        lst = per_clasa[c]
        sel.update(random.sample(lst, min(cap, len(lst))))
    return sorted(sel)


def construieste_date_validare(val_dir_complet, dest_dir, cap=CAP_PER_CLASA):
    """Copiaza esantionul stratificat (imagini + etichete) in `dest_dir`/{images,labels}/val.
    Returneaza numarul de imagini copiate."""
    nume = selecteaza_stratificat(val_dir_complet, cap)
    labels_src = val_dir_complet.replace(os.sep + "images" + os.sep, os.sep + "labels" + os.sep)
    img_dst = os.path.join(dest_dir, "images", "val")
    lbl_dst = os.path.join(dest_dir, "labels", "val")
    os.makedirs(img_dst, exist_ok=True)
    os.makedirs(lbl_dst, exist_ok=True)
    for f in nume:
        shutil.copy2(os.path.join(val_dir_complet, f), os.path.join(img_dst, f))
        lp = os.path.splitext(f)[0] + ".txt"
        src_lp = os.path.join(labels_src, lp)
        if os.path.exists(src_lp):
            shutil.copy2(src_lp, os.path.join(lbl_dst, lp))
    return len(nume)
