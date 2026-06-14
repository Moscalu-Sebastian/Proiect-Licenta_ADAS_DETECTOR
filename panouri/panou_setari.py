"""
Panoul de setari persistente: limba, afisare, clasificare, praguri per clasa,
conexiune RTSP, snapshot. Parametrii de detectie LIVE (confidence, IoU, rezolutie,
clase) stau in bara laterala din Video/RTSP, nu aici.
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QLineEdit, QFrame, QGroupBox, QComboBox,
    QDoubleSpinBox, QScrollArea, QFileDialog, QMessageBox, QSlider
)
from PyQt6.QtCore import Qt

from nuclee.traduceri import tr, tr_clasa, LIMBI_DISPONIBILE, eticheta_limba, limba_curenta
from nuclee.clase_model import NUME_BDD, normalizeaza_names


class SliderFaraScroll(QSlider):
    """QSlider care IGNORA rotita mouse-ului, ca scroll-ul peste pagina sa nu modifice
    accidental pragul cand treci cu mouse-ul peste el."""
    def wheelEvent(self, event):
        event.ignore()


class PanouSetari(QWidget):
    """Panou cu setarile persistente ale aplicatiei (afisare, RTSP, snapshot)."""

    def __init__(self, config, fereastra_parinte=None):
        super().__init__()
        self.config            = config
        self.fereastra_parinte = fereastra_parinte
        self._incarcare        = False   # guard: nu marca 'modificat' in timpul incarcarii
        self._modificat        = False
        self._names            = dict(NUME_BDD)   # clase dinamice (din model.names)
        self._praguri_pending  = {}               # praguri editate, aplicate la Salvare
        self._initUI()
        self._incarca_valori()
        self._conecteaza_modificari()

    def _initUI(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        continut = QWidget()
        layout = QVBoxLayout(continut)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Buton Inapoi in coltul stanga-sus, deasupra titlului
        rand_sus = QHBoxLayout()
        self.btn_inapoi = QPushButton(tr("set_back"))
        self.btn_inapoi.setObjectName("btnSecundar")
        self.btn_inapoi.setFixedHeight(34)
        self.btn_inapoi.setFixedWidth(120)
        self.btn_inapoi.setToolTip(tr("set_back_tip"))
        self.btn_inapoi.clicked.connect(self._inapoi)
        rand_sus.addWidget(self.btn_inapoi)
        rand_sus.addStretch()
        layout.addLayout(rand_sus)

        lbl_titlu = QLabel(tr("set_title"))
        lbl_titlu.setObjectName("titluPanou")
        lbl_sub = QLabel(tr("set_subtitle"))
        lbl_sub.setObjectName("subtitluPanou")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_titlu)
        layout.addWidget(lbl_sub)

        layout.addWidget(self._grup_limba())
        layout.addWidget(self._grup_afisare())
        layout.addWidget(self._grup_clasificare())
        layout.addWidget(self._grup_praguri())
        layout.addWidget(self._grup_rtsp())
        layout.addWidget(self._grup_snapshot())
        layout.addStretch()

        scroll.setWidget(continut)

        layout_root = QVBoxLayout(self)
        layout_root.setContentsMargins(0, 0, 0, 0)
        layout_root.setSpacing(0)
        layout_root.addWidget(scroll)
        layout_root.addWidget(self._bara_actiuni())   # bara Save mereu vizibila, jos (sticky)

    def _grup_limba(self):
        grup = QGroupBox(tr("set_grp_language"))
        layout = QVBoxLayout(grup)
        layout.setSpacing(10)

        rand = QHBoxLayout()
        lbl = QLabel(tr("set_language_label"))
        lbl.setFixedWidth(160)
        self.combo_limba = QComboBox()
        self.combo_limba.setFixedWidth(180)
        for cod in LIMBI_DISPONIBILE:
            self.combo_limba.addItem(eticheta_limba(cod), cod)
        rand.addWidget(lbl)
        rand.addWidget(self.combo_limba)
        rand.addStretch()
        layout.addLayout(rand)

        lbl_hint = QLabel(tr("set_language_hint"))
        lbl_hint.setObjectName("labelDesc")
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)

        return grup

    def _grup_afisare(self):
        grup = QGroupBox(tr("set_grp_display"))
        layout = QVBoxLayout(grup)
        layout.setSpacing(10)

        self.check_etichete  = QCheckBox(tr("set_show_labels"))
        self.check_incredere = QCheckBox(tr("set_show_conf"))
        self.check_tracks    = QCheckBox(tr("set_show_tracks"))

        layout.addWidget(self.check_etichete)
        layout.addWidget(self.check_incredere)
        layout.addWidget(self.check_tracks)

        lbl_desc = QLabel(tr("set_tracks_desc"))
        lbl_desc.setObjectName("labelDesc")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        return grup

    def _grup_clasificare(self):
        grup = QGroupBox(tr("set_grp_classifier"))
        layout = QVBoxLayout(grup)
        layout.setSpacing(10)

        self.check_clasificare = QCheckBox(tr("set_enable_classifier"))
        layout.addWidget(self.check_clasificare)

        lbl = QLabel(tr("set_classifier_desc"))
        lbl.setObjectName("labelDesc")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        return grup

    def _grup_praguri(self):
        grup = QGroupBox(tr("set_grp_thresholds"))
        layout = QVBoxLayout(grup)
        layout.setSpacing(8)

        lbl_desc = QLabel(tr("set_thr_desc"))
        lbl_desc.setObjectName("labelDesc")
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        # Butoane: optimizare rapida / completa / reset la global
        rand_btn = QHBoxLayout()
        self.btn_opt = QPushButton(tr("set_thr_optimize"))
        self.btn_opt.setFixedHeight(32)
        self.btn_opt.clicked.connect(self._optimizeaza)
        self.btn_opt_reset = QPushButton(tr("set_thr_reset"))
        self.btn_opt_reset.setObjectName("btnSecundar")
        self.btn_opt_reset.setFixedHeight(32)
        self.btn_opt_reset.clicked.connect(self._reset_praguri)
        rand_btn.addWidget(self.btn_opt)
        rand_btn.addWidget(self.btn_opt_reset)
        rand_btn.addStretch()
        layout.addLayout(rand_btn)

        # Sliderele per clasa traiesc intr-un container reconstruibil (din model.names)
        self._slidere_praguri = {}
        self._labeluri_praguri = {}
        self._container_slidere = QVBoxLayout()
        self._container_slidere.setSpacing(6)
        layout.addLayout(self._container_slidere)
        self._populeaza_slidere_praguri()

        lbl_hint = QLabel(tr("set_thr_global_hint"))
        lbl_hint.setObjectName("labelDesc")
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)

        return grup

    def _populeaza_slidere_praguri(self):
        """(Re)construieste un slider per clasa din self._names (sortate dupa id)."""
        prev = self._incarcare
        self._incarcare = True   # nu marca modificari in timpul (re)constructiei
        # golim containerul
        while self._container_slidere.count():
            item = self._container_slidere.takeAt(0)
            sub = item.layout()
            if sub:
                while sub.count():
                    w = sub.takeAt(0).widget()
                    if w:
                        w.deleteLater()
            elif item.widget():
                item.widget().deleteLater()
        self._slidere_praguri = {}
        self._labeluri_praguri = {}

        global_pct = int(self.config.get("confidence", 0.45) * 100)
        for cls_id in sorted(self._names.keys()):
            rand = QHBoxLayout()
            lbl = QLabel(tr_clasa(self._names[cls_id]))
            lbl.setObjectName("labelParam")
            lbl.setFixedWidth(130)
            sl = SliderFaraScroll(Qt.Orientation.Horizontal)
            sl.setRange(5, 95)
            sl.setValue(global_pct)
            val = QLabel("--%")
            val.setObjectName("labelConfVal")
            val.setFixedWidth(42)
            sl.valueChanged.connect(lambda v, c=cls_id, lv=val: self._prag_schimbat(c, v, lv))
            # Buton mic de reset per clasa: o readuce la confidence-ul global (urmeaza globalul)
            btn_reset = QPushButton("↺")
            btn_reset.setObjectName("btnResetClasa")
            btn_reset.setFixedSize(26, 22)
            btn_reset.setToolTip(tr("set_thr_reset_class"))
            btn_reset.clicked.connect(lambda _=False, c=cls_id: self._reseteaza_clasa(c))
            rand.addWidget(lbl)
            rand.addWidget(sl)
            rand.addWidget(val)
            rand.addWidget(btn_reset)
            self._container_slidere.addLayout(rand)
            self._slidere_praguri[cls_id] = sl
            self._labeluri_praguri[cls_id] = val
            self._marcheaza_rand(cls_id, True)   # implicit: urmeaza globalul
        self._incarcare = prev

    def seteaza_clase(self, names):
        """Reconstruieste sliderele de praguri pentru noul set de clase (din model.names)."""
        self._names = normalizeaza_names(names)
        self._populeaza_slidere_praguri()
        self.actualizeaza_praguri()

    def _grup_rtsp(self):
        grup = QGroupBox(tr("set_grp_rtsp"))
        layout = QVBoxLayout(grup)
        layout.setSpacing(10)

        row_url = QHBoxLayout()
        lbl_url = QLabel(tr("set_rtsp_url"))
        lbl_url.setFixedWidth(130)
        self.input_rtsp_url = QLineEdit()
        self.input_rtsp_url.setPlaceholderText("rtsp://192.168.1.100:8554/dashcam")
        row_url.addWidget(lbl_url)
        row_url.addWidget(self.input_rtsp_url)
        layout.addLayout(row_url)

        row_timeout = QHBoxLayout()
        lbl_to = QLabel(tr("set_rtsp_timeout"))
        lbl_to.setFixedWidth(180)
        self.spin_timeout = QDoubleSpinBox()
        self.spin_timeout.setRange(1.0, 30.0)
        self.spin_timeout.setSingleStep(1.0)
        self.spin_timeout.setFixedWidth(80)
        row_timeout.addWidget(lbl_to)
        row_timeout.addWidget(self.spin_timeout)
        row_timeout.addStretch()
        layout.addLayout(row_timeout)

        lbl_hint = QLabel(tr("set_rtsp_hint"))
        lbl_hint.setObjectName("labelCod")
        layout.addWidget(lbl_hint)

        return grup

    def _grup_snapshot(self):
        grup = QGroupBox(tr("set_grp_snapshot"))
        layout = QVBoxLayout(grup)
        layout.setSpacing(10)

        row_folder = QHBoxLayout()
        lbl_folder = QLabel(tr("set_snap_folder"))
        lbl_folder.setFixedWidth(130)
        self.input_snap_folder = QLineEdit()
        self.input_snap_folder.setPlaceholderText("snapshots")
        btn_browse = QPushButton(tr("set_browse"))
        btn_browse.setObjectName("btnSecundar")
        btn_browse.setFixedHeight(30)
        btn_browse.setFixedWidth(90)
        btn_browse.clicked.connect(self._browse_folder)
        row_folder.addWidget(lbl_folder)
        row_folder.addWidget(self.input_snap_folder)
        row_folder.addWidget(btn_browse)
        layout.addLayout(row_folder)

        return grup

    def _bara_actiuni(self):
        bara = QFrame()
        bara.setObjectName("baraActiuniSetari")
        layout = QHBoxLayout(bara)
        layout.setContentsMargins(24, 10, 24, 10)

        self.btn_salveaza = QPushButton(tr("set_save"))
        self.btn_salveaza.setFixedHeight(38)
        self.btn_salveaza.setFixedWidth(190)
        self.btn_salveaza.clicked.connect(self._salveaza)

        self.btn_reset = QPushButton(tr("set_reset"))
        self.btn_reset.setObjectName("btnSecundar")
        self.btn_reset.setFixedHeight(38)
        self.btn_reset.setFixedWidth(190)
        self.btn_reset.clicked.connect(self._reseteaza)

        self.label_salvat = QLabel("")
        self.label_salvat.setObjectName("labelSucces")

        layout.addWidget(self.btn_salveaza)
        layout.addWidget(self.btn_reset)
        layout.addStretch()
        layout.addWidget(self.label_salvat)

        return bara

    # --- Logica ---

    def _incarca_valori(self):
        self._incarcare = True
        # Limba: selecteaza valoarea curenta din config (implicit limba activa)
        cod_limba = self.config.get("limba", limba_curenta())
        idx = self.combo_limba.findData(cod_limba)
        self.combo_limba.setCurrentIndex(idx if idx >= 0 else 0)
        self._limba_initiala = self.combo_limba.currentData()
        self.check_etichete.setChecked(self.config.get("show_labels", True))
        self.check_incredere.setChecked(self.config.get("show_confidence", True))
        self.check_tracks.setChecked(self.config.get("show_tracks", False))
        self.check_clasificare.setChecked(self.config.get("clasificare_semne", False))
        self.input_rtsp_url.setText(self.config.get("rtsp_url", "rtsp://"))
        self.spin_timeout.setValue(float(self.config.get("rtsp_timeout", 5)))
        self.input_snap_folder.setText(self.config.get("snapshot_folder", "snapshots"))
        self._incarcare = False
        self._seteaza_nesalvat(False)
        self.actualizeaza_praguri()

    # --- Praguri per clasa ---

    def _marcheaza_rand(self, cls_id, urmeaza_global):
        """Marcheaza vizual daca o clasa urmeaza globalul (label estompat + tooltip)
        sau are prag explicit (label normal). Sursa de adevar: prezenta in _praguri_pending."""
        lbl = self._labeluri_praguri.get(cls_id)
        if lbl is None:
            return
        lbl.setObjectName("labelConfValGlobal" if urmeaza_global else "labelConfVal")
        lbl.setToolTip(tr("set_thr_follows_global") if urmeaza_global else "")
        lbl.setStyle(lbl.style())   # forteaza re-aplicarea QSS dupa schimbarea objectName

    def _prag_schimbat(self, cls_id, valoare, lbl_val):
        lbl_val.setText(f"{valoare}%")
        if self._incarcare:
            return
        # Stageam modificarea (se aplica la Salvare) si marcam 'modificari nesalvate'
        self._praguri_pending[int(cls_id)] = round(valoare / 100.0, 3)
        self._marcheaza_rand(cls_id, False)   # mutare manuala -> prag explicit
        self._marcheaza_modificat()

    def _reseteaza_clasa(self, cls_id):
        """Readuce o singura clasa la confidence-ul global (urmeaza din nou globalul).
        Se aplica la Salvare."""
        self._praguri_pending.pop(int(cls_id), None)
        self._incarcare = True
        global_pct = max(5, min(95, int(self.config.get("confidence", 0.45) * 100)))
        sl = self._slidere_praguri.get(cls_id)
        if sl is not None:
            sl.setValue(global_pct)
            self._labeluri_praguri[cls_id].setText(f"{global_pct}%")
        self._incarcare = False
        self._marcheaza_rand(cls_id, True)
        self._marcheaza_modificat()

    def _optimizeaza(self):
        if self.fereastra_parinte:
            self.fereastra_parinte.lanseaza_optimizare()

    def _reset_praguri(self):
        """Aduce toate clasele inapoi la confidence-ul global (se aplica la Salvare)."""
        self._praguri_pending = {}
        self._incarcare = True
        global_pct = max(5, min(95, int(self.config.get("confidence", 0.45) * 100)))
        for cls_id, sl in self._slidere_praguri.items():
            sl.setValue(global_pct)
            self._labeluri_praguri[cls_id].setText(f"{global_pct}%")
            self._marcheaza_rand(cls_id, True)
        self._incarcare = False
        self._marcheaza_modificat()

    def actualizeaza_praguri(self):
        """Aliniaza sliderele la config['praguri_clase'] (clasele fara prag -> global)
        si sincronizeaza dict-ul 'pending'. Apelat la incarcare si dupa optimizarea automata."""
        if not hasattr(self, "_slidere_praguri"):
            return
        self._incarcare = True
        praguri = {int(k): float(v) for k, v in (self.config.get("praguri_clase") or {}).items()}
        self._praguri_pending = dict(praguri)
        global_pct = int(self.config.get("confidence", 0.45) * 100)
        for cls_id, sl in self._slidere_praguri.items():
            in_praguri = cls_id in praguri
            pct = int(round(praguri[cls_id] * 100)) if in_praguri else global_pct
            pct = max(5, min(95, pct))
            sl.setValue(pct)
            self._labeluri_praguri[cls_id].setText(f"{pct}%")
            self._marcheaza_rand(cls_id, not in_praguri)
        self._incarcare = False

    def _conecteaza_modificari(self):
        """Conecteaza schimbarile widget-urilor la indicatorul 'modificari nesalvate'."""
        for w in (self.check_etichete, self.check_incredere, self.check_tracks, self.check_clasificare):
            w.stateChanged.connect(self._marcheaza_modificat)
        self.combo_limba.currentIndexChanged.connect(self._marcheaza_modificat)
        self.input_rtsp_url.textChanged.connect(self._marcheaza_modificat)
        self.spin_timeout.valueChanged.connect(self._marcheaza_modificat)
        self.input_snap_folder.textChanged.connect(self._marcheaza_modificat)

    def _marcheaza_modificat(self, *args):
        if not self._incarcare:
            self._seteaza_nesalvat(True)

    def _seteaza_nesalvat(self, nesalvat):
        self._modificat = nesalvat
        if nesalvat:
            self.label_salvat.setObjectName("labelModificat")
            self.label_salvat.setText(tr("set_unsaved"))
        else:
            self.label_salvat.setObjectName("labelSucces")
            self.label_salvat.setText("")
        self.label_salvat.setStyle(self.label_salvat.style())

    def _salveaza(self):
        limba_noua = self.combo_limba.currentData()
        limba_schimbata = (limba_noua != self._limba_initiala)

        self.config["limba"]           = limba_noua
        self.config["show_labels"]     = self.check_etichete.isChecked()
        self.config["show_confidence"] = self.check_incredere.isChecked()
        self.config["show_tracks"]     = self.check_tracks.isChecked()
        self.config["clasificare_semne"] = self.check_clasificare.isChecked()
        self.config["rtsp_url"]        = self.input_rtsp_url.text().strip() or "rtsp://"
        self.config["rtsp_timeout"]    = self.spin_timeout.value()
        self.config["snapshot_folder"] = self.input_snap_folder.text().strip() or "snapshots"
        self.config["praguri_clase"]   = dict(self._praguri_pending)   # praguri per clasa stageate

        if self.fereastra_parinte:
            self.fereastra_parinte.salveaza_config()

        self._seteaza_nesalvat(False)
        self.label_salvat.setText(tr("set_saved"))
        self._actualizeaza_status(tr("set_saved_status"))
        self._limba_initiala = limba_noua

        # Daca limba s-a schimbat, propunem repornirea (textele se re-traduc la pornire)
        if limba_schimbata:
            self._propune_repornire()

    def _propune_repornire(self):
        cutie = QMessageBox(self)
        cutie.setIcon(QMessageBox.Icon.Information)
        cutie.setWindowTitle(tr("restart_title"))
        cutie.setText(tr("restart_body"))
        btn_acum = cutie.addButton(tr("restart_now"), QMessageBox.ButtonRole.AcceptRole)
        cutie.addButton(tr("restart_later"), QMessageBox.ButtonRole.RejectRole)
        cutie.exec()
        if cutie.clickedButton() is btn_acum and self.fereastra_parinte:
            self.fereastra_parinte.reporneste_aplicatia()

    def _reseteaza(self):
        # Reseteaza DOAR widget-urile la valorile implicite; se aplica DUPA Save.
        self._incarcare = True
        self.check_etichete.setChecked(True)
        self.check_incredere.setChecked(True)
        self.check_tracks.setChecked(False)
        self.check_clasificare.setChecked(False)
        self.input_rtsp_url.setText("rtsp://")
        self.spin_timeout.setValue(5.0)
        self.input_snap_folder.setText("snapshots")
        # Praguri per clasa -> inapoi la global (implicit)
        self._praguri_pending = {}
        global_pct = max(5, min(95, int(self.config.get("confidence", 0.45) * 100)))
        for cls_id, sl in self._slidere_praguri.items():
            sl.setValue(global_pct)
            self._labeluri_praguri[cls_id].setText(f"{global_pct}%")
            self._marcheaza_rand(cls_id, True)
        self._incarcare = False
        self._seteaza_nesalvat(True)
        self.label_salvat.setText(tr("set_defaults_note"))

    def marcheaza_optimizat(self, n):
        """Confirmare vizibila ca optimizarea automata s-a aplicat SI salvat (praguri in DB).
        Apelata de fereastra principala dupa ce thread-ul de optimizare termina."""
        self.label_salvat.setObjectName("labelSucces")
        self.label_salvat.setText(tr("set_thr_optimized", n=n))
        self.label_salvat.setStyle(self.label_salvat.style())

    def _inapoi(self):
        if self.fereastra_parinte:
            self.fereastra_parinte._inapoi()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("dlg_select_snap_folder"))
        if folder:
            self.input_snap_folder.setText(folder)

    def reincarca_din_config(self):
        self._incarca_valori()

    def _actualizeaza_status(self, mesaj):
        if self.fereastra_parinte:
            self.fereastra_parinte.statusBar().showMessage(mesaj, 5000)
