"""
Bara laterala de control - componenta comuna pentru modul Video si RTSP.

Contine: FPS, alerte ADAS (doar RTSP), lista de detectii, parametri detectie
(Confidence, IoU, Rezolutie - LIVE), selectie clase, buton Snapshot.

Controalele scriu direct in dictionarul `config` partajat (acelasi dat thread-ului
de inferenta), deci schimbarile sunt vizibile imediat fara restart de stream.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QFrame, QListWidget, QListWidgetItem,
    QGridLayout, QCheckBox, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from nuclee.traduceri import tr, tr_clasa
from nuclee.clase_model import NUME_BDD, normalizeaza_names, culoare_clasa, categorie_alerta

# Rezolutii de inferenta disponibile. Toate sunt multipli de 32 (cerinta YOLO).
# Mai mare = mai precis pe obiecte mici (semne) dar mai lent.
REZOLUTII = [320, 480, 640, 960, 1280]


class BaraControlLateral(QWidget):
    """Bara laterala reutilizabila cu FPS, detectii si toti parametrii de detectie."""

    # Emis cand userul apasa Snapshot - parintele salveaza cadrul curent
    semnal_snapshot = pyqtSignal()
    # Emis cand userul apasa "Setari avansate" - parintele navigheaza la pagina Setari
    semnal_setari_avansate = pyqtSignal()

    def __init__(self, config, eticheta_fps=None, cu_alerte=False):
        super().__init__()
        self.config             = config
        # eticheta_fps se rezolva la runtime (nu la import) ca sa prinda limba curenta
        self.eticheta_fps       = eticheta_fps or tr("bar_fps_playback")
        self.cu_alerte          = cu_alerte
        self._reincarcare       = False   # guard impotriva buclelor la reload programatic
        self._checkboxuri_clase = {}
        # Clasele se deriva din model.names (dinamic). Pana se incarca un model: BDD.
        self._names             = dict(NUME_BDD)
        self._initUI()

    # ------------------------------------------------------------------ #
    # Constructie UI
    # ------------------------------------------------------------------ #

    def _initUI(self):
        self.setObjectName("panouInfo")
        self.setFixedWidth(300)        # latime fixa garantata (independent de QSS); ~1.5x
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sectiunile colapsabile stau intr-un scroll: cand expandezi mai multe decat
        # incape pe inaltime, apare scroll. Toate sectiunile sunt STRANSE implicit.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        continut_total = QWidget()
        continut_total.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(continut_total)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- FPS ---
        zona_fps = QWidget()
        zona_fps.setStyleSheet("background:transparent;")
        lf = QVBoxLayout(zona_fps)
        lf.setContentsMargins(12, 6, 12, 8)
        lf.setSpacing(0)
        self.label_fps = QLabel("--")
        self.label_fps.setObjectName("labelFps")
        lf.addWidget(self.label_fps)
        lbl_unit = QLabel(tr("bar_fps_unit"))
        lbl_unit.setObjectName("labelFpsUnit")
        lf.addWidget(lbl_unit)
        # Latenta de inferenta - SE schimba cu rezolutia (FPS-ul e plafonat de redare)
        self.label_latenta = QLabel("-- ms")
        self.label_latenta.setObjectName("labelLatenta")
        lf.addWidget(self.label_latenta)
        self._adauga_sectiune(layout, self.eticheta_fps, zona_fps)

        # --- Alerte ADAS (doar RTSP) ---
        if self.cu_alerte:
            zona_alerte = QWidget()
            zona_alerte.setStyleSheet("background:transparent;")
            self.layout_alerte = QVBoxLayout(zona_alerte)
            self.layout_alerte.setContentsMargins(8, 6, 8, 6)
            self.layout_alerte.setSpacing(4)
            self._afiseaza_fara_alerte()
            self._adauga_sectiune(layout, tr("bar_alerts"), zona_alerte)

        # --- Lista detectii (10 vizibile mereu, scroll, maxim 100 in actualizeaza) ---
        self.lista_detectii = QListWidget()
        self.lista_detectii.setObjectName("listaDetectii")
        self.lista_detectii.setFixedHeight(250)   # ~10 randuri vizibile; restul cu scroll
        self._adauga_sectiune(layout, tr("bar_active_det"), self.lista_detectii)

        # --- Parametri detectie (LIVE) ---
        zona_par = QWidget()
        zona_par.setStyleSheet("background:transparent;")
        lp = QVBoxLayout(zona_par)
        lp.setContentsMargins(12, 8, 12, 8)
        lp.setSpacing(10)
        lp.addLayout(self._rand_confidence())
        lp.addLayout(self._rand_iou())
        lp.addLayout(self._rand_rezolutie())
        self._adauga_sectiune(layout, tr("bar_det_params"), zona_par)

        # --- Clase detectie (continut reconstruibil cand se schimba modelul) ---
        self._zona_clase = QWidget()
        self._zona_clase.setStyleSheet("background:transparent;")
        self._grid_clase = QGridLayout(self._zona_clase)
        self._grid_clase.setContentsMargins(10, 6, 10, 6)
        self._grid_clase.setHorizontalSpacing(4)
        self._grid_clase.setVerticalSpacing(3)
        self._populeaza_clase()
        self._adauga_sectiune(layout, tr("bar_det_classes"), self._zona_clase)

        layout.addStretch()
        scroll.setWidget(continut_total)
        root.addWidget(scroll)

        # --- Snapshot + Setari avansate (mereu vizibile jos, NU colapsabile) ---
        zona_snap = QWidget()
        zona_snap.setObjectName("zonaActiuniBara")
        ls = QVBoxLayout(zona_snap)
        ls.setContentsMargins(12, 8, 12, 12)
        ls.setSpacing(6)

        self.btn_snapshot = QPushButton(tr("bar_snapshot"))
        self.btn_snapshot.setObjectName("btnSecundar")
        self.btn_snapshot.setFixedHeight(32)
        self.btn_snapshot.setToolTip(tr("bar_snapshot_tip"))
        self.btn_snapshot.setEnabled(False)
        self.btn_snapshot.clicked.connect(self.semnal_snapshot.emit)
        ls.addWidget(self.btn_snapshot)

        self.btn_setari_avansate = QPushButton("  ⚙" + tr("bar_adv_settings"))
        self.btn_setari_avansate.setObjectName("btnSecundar")
        self.btn_setari_avansate.setFixedHeight(32)
        self.btn_setari_avansate.setToolTip(tr("bar_adv_settings_tip"))
        self.btn_setari_avansate.clicked.connect(self.semnal_setari_avansate.emit)
        ls.addWidget(self.btn_setari_avansate)

        root.addWidget(zona_snap)

    def _adauga_sectiune(self, layout, titlu, continut, colapsat=True):
        """Sectiune colapsabila: header clickabil (cu sageata ▸/▾) + continut care se
        ascunde/arata la click. Implicit STRANS (colapsat=True)."""
        header = QPushButton(("▸  " if colapsat else "▾  ") + titlu)
        header.setObjectName("headerColaps")
        header.setCheckable(True)
        header.setChecked(not colapsat)
        continut.setVisible(not colapsat)

        def toggle(_checked=False, h=header, c=continut, t=titlu):
            vizibil = c.isHidden()
            c.setVisible(vizibil)
            h.setText(("▾  " if vizibil else "▸  ") + t)

        header.clicked.connect(toggle)
        layout.addWidget(header)
        layout.addWidget(continut)

    # --- Clase dinamice (din model.names) ---

    def _populeaza_clase(self):
        """(Re)construieste checkbox-urile de clase din self._names (sortate dupa id)."""
        prev = self._reincarcare
        self._reincarcare = True   # nu marca modificari in timpul (re)constructiei
        while self._grid_clase.count():
            w = self._grid_clase.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._checkboxuri_clase = {}
        clase_cfg = self.config.get("classes")
        clase_active = set(clase_cfg) if clase_cfg else set(self._names.keys())  # gol/None = toate
        for idx, cls_id in enumerate(sorted(self._names.keys())):
            cb = QCheckBox(tr_clasa(self._names[cls_id]))
            cb.setChecked(cls_id in clase_active)
            cb.setStyleSheet("font-size: 11px;")
            cb.stateChanged.connect(self._clase_schimbate)
            self._checkboxuri_clase[cls_id] = cb
            self._grid_clase.addWidget(cb, idx, 0)
        self._reincarcare = prev

    def seteaza_clase(self, names):
        """Schimba setul de clase (din model.names) si reconstruieste checkbox-urile."""
        self._names = normalizeaza_names(names)
        self._populeaza_clase()

    # --- Constructori de randuri pentru parametri ---

    def _rand_confidence(self):
        rand = QVBoxLayout()
        rand.setSpacing(3)

        cap = QHBoxLayout()
        lbl = QLabel(tr("param_confidence"))
        lbl.setObjectName("labelParam")
        self.label_conf_val = QLabel(f"{int(self.config.get('confidence', 0.45) * 100)}%")
        self.label_conf_val.setObjectName("labelConfVal")
        cap.addWidget(lbl)
        cap.addStretch()
        cap.addWidget(self.label_conf_val)
        rand.addLayout(cap)

        self.slider_conf = QSlider(Qt.Orientation.Horizontal)
        self.slider_conf.setRange(5, 95)
        self.slider_conf.setValue(int(self.config.get("confidence", 0.45) * 100))
        self.slider_conf.setToolTip(tr("param_confidence_tip"))
        self.slider_conf.valueChanged.connect(self._schimba_confidence)
        rand.addWidget(self.slider_conf)
        return rand

    def _rand_iou(self):
        rand = QVBoxLayout()
        rand.setSpacing(3)

        cap = QHBoxLayout()
        lbl = QLabel(tr("param_iou"))
        lbl.setObjectName("labelParam")
        self.label_iou_val = QLabel(f"{self.config.get('iou', 0.45):.2f}")
        self.label_iou_val.setObjectName("labelConfVal")
        cap.addWidget(lbl)
        cap.addStretch()
        cap.addWidget(self.label_iou_val)
        rand.addLayout(cap)

        self.slider_iou = QSlider(Qt.Orientation.Horizontal)
        self.slider_iou.setRange(10, 90)
        self.slider_iou.setValue(int(self.config.get("iou", 0.45) * 100))
        self.slider_iou.setToolTip(tr("param_iou_tip"))
        self.slider_iou.valueChanged.connect(self._schimba_iou)
        rand.addWidget(self.slider_iou)
        return rand

    def _rand_rezolutie(self):
        rand = QHBoxLayout()
        lbl = QLabel(tr("param_resolution"))
        lbl.setObjectName("labelParam")

        self.combo_imgsz = QComboBox()
        self.combo_imgsz.setObjectName("comboRezolutie")
        for dim in REZOLUTII:
            self.combo_imgsz.addItem(f"{dim} px", dim)
        idx = self.combo_imgsz.findData(self.config.get("imgsz", 640))
        if idx < 0:
            idx = self.combo_imgsz.findData(640)
        self.combo_imgsz.setCurrentIndex(max(0, idx))
        self.combo_imgsz.setToolTip(tr("param_resolution_tip"))
        self.combo_imgsz.currentIndexChanged.connect(self._schimba_imgsz)

        rand.addWidget(lbl)
        rand.addStretch()
        rand.addWidget(self.combo_imgsz)
        return rand

    def _sep(self, layout):
        linie = QFrame()
        linie.setObjectName("separatorInfo")
        linie.setFixedHeight(1)
        layout.addWidget(linie)

    # ------------------------------------------------------------------ #
    # Handlere controale (scriu in config-ul partajat)
    # ------------------------------------------------------------------ #

    def _schimba_confidence(self, valoare):
        if self._reincarcare:
            return
        self.label_conf_val.setText(f"{valoare}%")
        self.config["confidence"] = valoare / 100.0

    def _schimba_iou(self, valoare):
        if self._reincarcare:
            return
        self.label_iou_val.setText(f"{valoare / 100:.2f}")
        self.config["iou"] = valoare / 100.0

    def _schimba_imgsz(self, _index):
        if self._reincarcare:
            return
        self.config["imgsz"] = self.combo_imgsz.currentData()

    def _clase_schimbate(self):
        if self._reincarcare:
            return
        selectate = sorted(
            cls_id for cls_id, cb in self._checkboxuri_clase.items() if cb.isChecked()
        )
        # None = toate clasele (mai eficient decat lista completa)
        self.config["classes"] = selectate if len(selectate) < len(self._names) else None

    # ------------------------------------------------------------------ #
    # API public apelat de panoul parinte
    # ------------------------------------------------------------------ #

    def actualizeaza_fps(self, fps):
        self.label_fps.setText(f"{fps:.1f}")
        if fps >= 20:
            culoare = "#30D158"   # verde iOS  - real-time
        elif fps >= 10:
            culoare = "#FF9F0A"   # orange iOS - acceptabil
        else:
            culoare = "#FF453A"   # rosu iOS   - lent
        self.label_fps.setStyleSheet(
            f"font-size:40px; font-weight:bold; color:{culoare};"
            f"padding:10px 14px 0 14px; font-family:'Consolas',monospace;"
        )

    def actualizeaza_latenta(self, ms):
        """Latenta medie de inferenta. Legata de imgsz ca sa fie clar ce face rezolutia."""
        imgsz = self.config.get("imgsz", 640)
        self.label_latenta.setText(f"{ms:.0f} ms @ {imgsz}px")

    def actualizeaza_detectii(self, detectii):
        self.lista_detectii.clear()
        if self.cu_alerte:
            self._actualizeaza_alerte(detectii)
        for d in sorted(detectii, key=lambda x: x["conf"], reverse=True)[:100]:   # maxim 100
            cls_id   = d["cls"]
            nume     = self._names.get(cls_id)
            cls_name = tr_clasa(nume) if nume else f"cls{cls_id}"
            text     = f"  {cls_name}   {d['conf']:.0%}"
            if d.get("semn"):
                text += f"  →  {d['semn']}"
            track_id = d.get("id")
            if track_id is not None:
                text += f"  #{track_id}"
            item = QListWidgetItem(text)
            item.setForeground(QColor(culoare_clasa(cls_id)))
            self.lista_detectii.addItem(item)

    def activeaza_snapshot(self, activ):
        self.btn_snapshot.setEnabled(activ)

    def reset_fps(self):
        self.label_fps.setText("--")
        self.label_latenta.setText("-- ms")

    def goleste(self):
        """Reseteaza FPS si lista de detectii (la stop / deconectare)."""
        self.lista_detectii.clear()
        self.reset_fps()
        if self.cu_alerte:
            self._curata_alerte()
            self._afiseaza_fara_alerte()

    def reincarca_din_config(self):
        """Re-aliniaza toate controalele la valorile curente din config.
        Apelat cand panoul devine vizibil, ca sa nu existe desincronizare
        intre modul Video si modul RTSP (ambele editeaza acelasi config)."""
        self._reincarcare = True

        self.slider_conf.setValue(int(self.config.get("confidence", 0.45) * 100))
        self.label_conf_val.setText(f"{self.slider_conf.value()}%")

        self.slider_iou.setValue(int(self.config.get("iou", 0.45) * 100))
        self.label_iou_val.setText(f"{self.slider_iou.value() / 100:.2f}")

        idx = self.combo_imgsz.findData(self.config.get("imgsz", 640))
        if idx >= 0:
            self.combo_imgsz.setCurrentIndex(idx)

        clase_active = set(self.config.get("classes") or self._names.keys())
        for cls_id, cb in self._checkboxuri_clase.items():
            cb.setChecked(cls_id in clase_active)

        self._reincarcare = False

    # ------------------------------------------------------------------ #
    # Alerte ADAS (doar cand cu_alerte=True)
    # ------------------------------------------------------------------ #

    def _afiseaza_fara_alerte(self):
        lbl = QLabel(tr("alert_none"))
        lbl.setObjectName("labelFaraAlerte")
        self.layout_alerte.addWidget(lbl)

    def _curata_alerte(self):
        while self.layout_alerte.count():
            w = self.layout_alerte.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _actualizeaza_alerte(self, detectii):
        self._curata_alerte()

        # Categorii prezente, derivate din numele claselor modelului (agnostic la dataset)
        categorii = {categorie_alerta(self._names.get(d["cls"], "")) for d in detectii}
        alerte = []
        if "pedestrian" in categorii:
            alerte.append(("danger", tr("alert_pedestrian")))
        if "sign" in categorii:
            alerte.append(("info", tr("alert_sign")))
        if "light" in categorii:
            alerte.append(("info", tr("alert_light")))

        if not alerte:
            self._afiseaza_fara_alerte()
            return

        for tip, mesaj in alerte:
            card = QFrame()
            card.setObjectName("alertaActiva" if tip == "danger" else "alertaInfo")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(8, 5, 8, 5)
            lbl = QLabel(mesaj)
            lbl.setObjectName("textAlerta" if tip == "danger" else "textAlertaInfo")
            cl.addWidget(lbl)
            self.layout_alerte.addWidget(card)
