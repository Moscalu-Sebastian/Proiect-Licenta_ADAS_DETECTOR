"""
Panoul pentru modul Video - incarcare fisier si detectie cadru cu cadru.

Panoul detine: toolbar (deschidere video + selectie model), zona de afisare,
bara de control jos (play/pauza/seek/viteza). Toti parametrii de detectie
(confidence, IoU, rezolutie, clase) si lista de detectii stau in bara laterala
comuna `BaraControlLateral`.
"""

import os
import datetime
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QFrame, QFileDialog, QSizePolicy,
    QDialog, QListWidget, QListWidgetItem, QMenu
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QPixmap, QImage

from nuclee.thread_video import ThreadVideo
from nuclee import baza_date
from nuclee.traduceri import tr
from panouri.bara_control import BaraControlLateral

# Viteze de redare disponibile
VITEZE = [
    ("0.25×", 0.25), ("0.5×", 0.5), ("0.75×", 0.75),
    ("1×",    1.0),  ("1.25×", 1.25), ("1.5×", 1.5),
    ("2×",    2.0),  ("4×", 4.0),   ("8×", 8.0),
]
INDEX_VITEZA_NORMAL = 3   # "1×"


class SliderSeeking(QSlider):
    """QSlider cu click-to-seek: un click oriunde sare direct la pozitie."""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            ratio = event.position().x() / max(self.width(), 1)
            val   = int(self.minimum() + ratio * (self.maximum() - self.minimum()))
            self.setValue(val)
            self.sliderMoved.emit(val)
        super().mousePressEvent(event)


class EtichetaVideo(QLabel):
    """QLabel care pastreaza cadrul-sursa si il re-scaleaza automat la redimensionare,
    ca imaginea sa se potriveasca mereu cand zona de afisare isi schimba latimea."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cadru_src = None

    def seteaza_cadru(self, pixmap):
        self._cadru_src = pixmap
        self._reaplica()

    def cadru_sursa(self):
        """Cadrul-sursa la rezolutie completa (inainte de scalarea pt display).
        Folosit la snapshot ca sa salvam imaginea full-res, nu varianta redimensionata."""
        return self._cadru_src

    def clear_cadru(self):
        self._cadru_src = None
        super().setPixmap(QPixmap())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reaplica()

    def _reaplica(self):
        if self._cadru_src and not self._cadru_src.isNull():
            super().setPixmap(self._cadru_src.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))


class DialogIstoric(QDialog):
    """Fereastra afisata la 'Deschide Video': alegi un video nou sau unul din istoric.
    Istoricul vine din baza de date (tabelul videoclipuri). Numerotat in stanga;
    click-dreapta pe o intrare -> sterge din istoric."""

    def __init__(self, istoric, parinte=None):
        super().__init__(parinte)
        self.parinte = parinte
        self.setWindowTitle(tr("hist_title"))
        self.setMinimumWidth(480)
        self.alegere = None        # "nou" | "istoric" | None
        self.cale_aleasa = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        btn_nou = QPushButton(tr("hist_new_video"))
        btn_nou.setObjectName("btnDeschide")
        btn_nou.setFixedHeight(40)
        btn_nou.clicked.connect(self._video_nou)
        layout.addWidget(btn_nou)

        lbl = QLabel(tr("hist_header"))
        lbl.setObjectName("labelSectiune")
        layout.addWidget(lbl)

        self.lista = QListWidget()
        self.lista.setMaximumHeight(300)
        self.lista.itemDoubleClicked.connect(self._alege_istoric)
        self.lista.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lista.customContextMenuRequested.connect(self._meniu_context)
        for i, rec in enumerate(istoric):
            self._adauga_item(i, rec)
        layout.addWidget(self.lista)

        nota = tr("hist_note") if istoric else tr("hist_empty")
        lbl_nota = QLabel(nota)
        lbl_nota.setObjectName("labelDesc")
        layout.addWidget(lbl_nota)

        rand = QHBoxLayout()
        rand.addStretch()
        btn_anuleaza = QPushButton(tr("hist_cancel"))
        btn_anuleaza.setObjectName("btnSecundar")
        btn_anuleaza.setFixedHeight(32)
        btn_anuleaza.clicked.connect(self.reject)
        rand.addWidget(btn_anuleaza)
        layout.addLayout(rand)

    def _adauga_item(self, i, rec):
        cale = rec["cale"] if isinstance(rec, dict) else rec
        item = QListWidgetItem(f"{i + 1}.   {os.path.basename(cale)}")
        if isinstance(rec, dict):
            item.setToolTip(tr("hist_tip", cale=cale,
                               ultima=rec.get('ultima_rulare', '?'),
                               nr=rec.get('nr_rulari', 1)))
        else:
            item.setToolTip(cale)
        item.setData(Qt.ItemDataRole.UserRole, cale)
        self.lista.addItem(item)

    def _video_nou(self):
        self.alegere = "nou"
        self.accept()

    def _alege_istoric(self, item):
        self.alegere = "istoric"
        self.cale_aleasa = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _meniu_context(self, pozitie):
        item = self.lista.itemAt(pozitie)
        if item is None:
            return
        meniu = QMenu(self)
        act_sterge = meniu.addAction(tr("hist_delete"))
        if meniu.exec(self.lista.viewport().mapToGlobal(pozitie)) is act_sterge:
            cale = item.data(Qt.ItemDataRole.UserRole)
            self.lista.takeItem(self.lista.row(item))
            if self.parinte is not None:
                self.parinte._sterge_din_istoric(cale)
            self._renumeroteaza()

    def _renumeroteaza(self):
        for i in range(self.lista.count()):
            it = self.lista.item(i)
            it.setText(f"{i + 1}.   {os.path.basename(it.data(Qt.ItemDataRole.UserRole))}")


class PanouVideo(QWidget):
    """Panou principal pentru modul Video cu redare la FPS nativ si tracking."""

    def __init__(self, config, fereastra_parinte=None):
        super().__init__()
        self.config            = config
        self.fereastra_parinte = fereastra_parinte
        self.thread_video      = None
        self.model_yolo        = None
        self.cale_video        = None
        self.fps_video         = 30.0
        self._ignore_slider    = False   # previne bucla la update programatic seekbar
        self._ignore_combo     = False   # previne bucla la setarea programatica a modelului
        self._cadru_curent     = 0
        self._total_cadre      = 0
        self._fps_jos_contor   = 0       # secunde consecutive cu FPS sub prag (recomandare benchmark)
        self._benchmark_sugerat = False  # banner-ul de benchmark s-a aratat deja pt videoclipul curent
        self._initUI()
        self.populeaza_modele_standard()   # listeaza modelele din modele/ in bara de sus

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #

    def _initUI(self):
        # Layout pe orizontala: [coloana video pe toata inaltimea | maner | bara dreapta]
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Coloana stanga: toolbar + video + bara de play. Astea stau DOAR peste video,
        # nu si peste panoul din dreapta.
        col_video = QWidget()
        cv = QVBoxLayout(col_video)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(self._creeaza_toolbar())
        cv.addWidget(self._creeaza_banner_benchmark())
        cv.addWidget(self._creeaza_display())
        cv.addWidget(self._creeaza_bara_control())
        root.addWidget(col_video)

        # Bara din dreapta pe TOATA inaltimea (la fel ca sidebar-ul din stanga) + maner
        self.bara = BaraControlLateral(self.config, eticheta_fps=tr("bar_fps_inference"), cu_alerte=False)
        self.bara.semnal_snapshot.connect(self._snapshot)
        self.bara.semnal_setari_avansate.connect(self._deschide_setari)
        root.addWidget(self._creeaza_handle_bara())
        root.addWidget(self.bara)

    def _creeaza_toolbar(self):
        bara = QFrame()
        bara.setObjectName("toolbarVideo")
        layout = QHBoxLayout(bara)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        vcenter = Qt.AlignmentFlag.AlignVCenter   # toate elementele centrate intre sus/jos

        self.btn_deschide = QPushButton(tr("video_open"))
        self.btn_deschide.setObjectName("btnDeschide")
        self.btn_deschide.setFixedHeight(32)
        self.btn_deschide.setFixedWidth(94)
        self.btn_deschide.setToolTip(tr("video_open_tip"))
        self.btn_deschide.clicked.connect(self._deschide_video)
        layout.addWidget(self.btn_deschide, alignment=vcenter)

        sep = QFrame()
        sep.setObjectName("separatorVertical")
        sep.setFixedWidth(1)
        layout.addWidget(sep)

        lbl_model = QLabel(tr("video_model_label"))
        lbl_model.setObjectName("labelToolbar")
        layout.addWidget(lbl_model, alignment=vcenter)

        self.combo_model = QComboBox()
        self.combo_model.setObjectName("comboModel")
        self.combo_model.addItem(tr("video_no_model"), None)
        self.combo_model.setFixedHeight(32)
        self.combo_model.setMinimumWidth(190)
        self.combo_model.setToolTip(tr("video_model_combo_tip"))
        self.combo_model.currentIndexChanged.connect(self._schimba_model)
        layout.addWidget(self.combo_model, alignment=vcenter)

        self.btn_incarca_model = QPushButton(tr("video_load_pt"))
        self.btn_incarca_model.setObjectName("btnSecundar")
        self.btn_incarca_model.setFixedHeight(32)
        self.btn_incarca_model.setFixedWidth(94)
        self.btn_incarca_model.setToolTip(tr("video_load_pt_tip"))
        self.btn_incarca_model.clicked.connect(self._incarca_model)
        layout.addWidget(self.btn_incarca_model, alignment=vcenter)

        layout.addStretch()

        self.label_fisier = QLabel(tr("video_no_file"))
        self.label_fisier.setObjectName("labelFisierVideo")
        layout.addWidget(self.label_fisier)

        return bara

    def _creeaza_handle_bara(self):
        """Maner subtire pe marginea stanga a panoului din dreapta (intre video si panou).
        Contine butonul de colapsare, care se muta odata cu panoul."""
        self.handle_bara = QFrame()
        self.handle_bara.setObjectName("handlePanou")
        l = QVBoxLayout(self.handle_bara)
        l.setContentsMargins(0, 8, 0, 0)
        l.setSpacing(0)
        self.btn_colaps_bara = QPushButton("▶")
        self.btn_colaps_bara.setObjectName("btnHandle")
        self.btn_colaps_bara.setFixedSize(18, 44)
        self.btn_colaps_bara.setToolTip(tr("panel_toggle_tip"))
        self.btn_colaps_bara.clicked.connect(self._toggle_bara)
        l.addWidget(self.btn_colaps_bara, alignment=Qt.AlignmentFlag.AlignHCenter)
        l.addSpacing(10)
        lbl_setari = QLabel(tr("vertical_settings"))
        lbl_setari.setObjectName("labelVertical")
        lbl_setari.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        l.addWidget(lbl_setari, alignment=Qt.AlignmentFlag.AlignHCenter)
        l.addStretch()
        return self.handle_bara

    def _creeaza_banner_benchmark(self):
        """Banner clickabil (ascuns implicit) care apare cand FPS-ul scade sub prag
        in timpul redarii, recomandand un benchmark pentru setari optime."""
        self.banner_benchmark = QPushButton("")
        self.banner_benchmark.setObjectName("bannerBenchmark")
        self.banner_benchmark.setVisible(False)
        self.banner_benchmark.setCursor(Qt.CursorShape.PointingHandCursor)
        self.banner_benchmark.setToolTip(tr("video_low_fps_tip"))
        self.banner_benchmark.clicked.connect(self._deschide_benchmark)
        return self.banner_benchmark

    def _deschide_benchmark(self):
        self.banner_benchmark.setVisible(False)
        if self.fereastra_parinte:
            self.fereastra_parinte._naviga(2)   # 2 = panoul Benchmark

    def _creeaza_display(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 0, 10)

        self.label_video = EtichetaVideo(tr("video_placeholder"))
        self.label_video.setObjectName("displayVideo")
        self.label_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.label_video.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label_video.installEventFilter(self)
        layout.addWidget(self.label_video)

        return container

    def _creeaza_bara_control(self):
        bara = QFrame()
        bara.setObjectName("baraControl")
        layout_v = QVBoxLayout(bara)
        layout_v.setContentsMargins(12, 6, 12, 8)
        layout_v.setSpacing(6)

        # --- Randul 1: butoane + timp + viteza ---
        rand_btn = QHBoxLayout()
        rand_btn.setSpacing(4)

        self.btn_inapoi = QPushButton("← 10s")
        self.btn_inapoi.setObjectName("btnPlayback")
        self.btn_inapoi.setFixedSize(56, 32)
        self.btn_inapoi.setToolTip(tr("play_back10_tip"))
        self.btn_inapoi.clicked.connect(lambda: self._sari_secunde(-10))
        self.btn_inapoi.setEnabled(False)
        rand_btn.addWidget(self.btn_inapoi)

        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setObjectName("btnPlay")
        self.btn_play_pause.setFixedSize(40, 32)
        self.btn_play_pause.setToolTip(tr("play_toggle_tip"))
        self.btn_play_pause.clicked.connect(self._toggle_play_pause)
        self.btn_play_pause.setEnabled(False)
        rand_btn.addWidget(self.btn_play_pause)

        self.btn_stop = QPushButton("■")
        self.btn_stop.setObjectName("btnPlayback")
        self.btn_stop.setFixedSize(32, 32)
        self.btn_stop.setToolTip(tr("play_stop_tip"))
        self.btn_stop.clicked.connect(self._stop)
        self.btn_stop.setEnabled(False)
        rand_btn.addWidget(self.btn_stop)

        self.btn_inainte = QPushButton("10s →")
        self.btn_inainte.setObjectName("btnPlayback")
        self.btn_inainte.setFixedSize(56, 32)
        self.btn_inainte.setToolTip(tr("play_fwd10_tip"))
        self.btn_inainte.clicked.connect(lambda: self._sari_secunde(10))
        self.btn_inainte.setEnabled(False)
        rand_btn.addWidget(self.btn_inainte)

        rand_btn.addSpacing(8)

        self.label_timp = QLabel("00:00 / 00:00")
        self.label_timp.setObjectName("labelTimp")
        rand_btn.addWidget(self.label_timp)

        rand_btn.addStretch()

        self.label_status_video = QLabel(tr("video_state_idle"))
        self.label_status_video.setObjectName("labelStatusMic")
        rand_btn.addWidget(self.label_status_video)

        rand_btn.addStretch()

        lbl_v = QLabel(tr("play_speed_label"))
        lbl_v.setObjectName("labelToolbar")
        rand_btn.addWidget(lbl_v)

        self.combo_viteza = QComboBox()
        self.combo_viteza.setObjectName("comboViteza")
        self.combo_viteza.setFixedHeight(32)   # aliniat cu butoanele play/stop din acelasi rand
        self.combo_viteza.setFixedWidth(70)
        self.combo_viteza.setToolTip(tr("play_speed_tip"))
        for eticheta, _ in VITEZE:
            self.combo_viteza.addItem(eticheta)
        self.combo_viteza.setCurrentIndex(INDEX_VITEZA_NORMAL)
        self.combo_viteza.currentIndexChanged.connect(self._schimba_viteza)
        rand_btn.addWidget(self.combo_viteza)

        layout_v.addLayout(rand_btn)

        # --- Randul 2: seekbar ---
        self.slider_seek = SliderSeeking(Qt.Orientation.Horizontal)
        self.slider_seek.setObjectName("seekBar")
        self.slider_seek.setRange(0, 1000)
        self.slider_seek.setValue(0)
        self.slider_seek.setFixedHeight(18)
        self.slider_seek.setEnabled(False)
        self.slider_seek.sliderMoved.connect(self._seek_din_slider)
        layout_v.addWidget(self.slider_seek)

        return bara

    # ------------------------------------------------------------------ #
    # Actiuni video
    # ------------------------------------------------------------------ #

    def _deschide_video(self):
        """Arata dialogul de alegere (video nou / istoric), apoi incarca fisierul ales."""
        istoric = baza_date.lista_videoclipuri(100)
        dlg = DialogIstoric(istoric, self)
        if not dlg.exec():
            return

        if dlg.alegere == "nou":
            cale, _ = QFileDialog.getOpenFileName(
                self, tr("dlg_open_video"),
                "", tr("filter_video")
            )
            if not cale:
                return
        elif dlg.alegere == "istoric" and dlg.cale_aleasa:
            cale = dlg.cale_aleasa
            if not os.path.exists(cale):
                self._actualizeaza_status(tr("status_file_gone", cale=cale))
                return
        else:
            return

        self._adauga_in_istoric(cale)
        self._incarca_fisier_video(cale)

    def _adauga_in_istoric(self, cale):
        """Adauga videoclipul in istoricul din baza de date (upsert: incrementeaza nr_rulari)."""
        baza_date.adauga_video(cale)

    def _sterge_din_istoric(self, cale):
        """Sterge un videoclip din istoricul din baza de date."""
        baza_date.sterge_video(cale)

    def _opreste_thread_video(self):
        """Opreste SI deconecteaza thread-ul video curent. Deconectarea e esentiala:
        altfel cadre/semnale 'fantoma' ramase in coada Qt de la thread-ul vechi sosesc
        dupa ce am pus preview-ul noului video si il suprascriu (noul cadru nu mai apare)."""
        t = self.thread_video
        if not t:
            return
        for semnal in (t.semnal_cadru, t.semnal_fps, t.semnal_latenta, t.semnal_detectii,
                       t.semnal_progres, t.semnal_eroare, t.semnal_gata):
            try:
                semnal.disconnect()
            except Exception:
                pass
        if t.isRunning():
            t.opreste()
            t.wait(2000)
        self.thread_video = None

    def seteaza_model(self, model):
        """Seteaza modelul YOLO. Daca un video ruleaza, il actualizeaza LIVE in thread
        (altfel modelul nou s-ar aplica abia la urmatoarea pornire / reincarcare video)."""
        self.model_yolo = model
        if self.thread_video and self.thread_video.isRunning():
            self.thread_video.seteaza_model(model)

    def _incarca_fisier_video(self, cale):
        """Opreste redarea curenta, incarca fisierul dat si afiseaza primul cadru ca preview."""
        # Oprim + DECONECTAM thread-ul curent (inlocuire video)
        self._opreste_thread_video()

        self.cale_video = cale

        import cv2
        cap = cv2.VideoCapture(cale)
        self.fps_video = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total          = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Afisam primul cadru ca preview imediat, fara sa fie nevoie de Play
        ret, frame_preview = cap.read()
        cap.release()
        if ret:
            frame_rgb = cv2.cvtColor(frame_preview, cv2.COLOR_BGR2RGB)
            h, w, ch  = frame_rgb.shape
            qimg = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.label_video.seteaza_cadru(QPixmap.fromImage(qimg))

        # Video nou -> reevaluam recomandarea de benchmark de la zero
        self._benchmark_sugerat = False
        self._fps_jos_contor    = 0
        self.banner_benchmark.setVisible(False)

        self.label_fisier.setText(os.path.basename(cale))
        self.label_status_video.setText(tr("video_state_loaded"))
        for btn in (self.btn_play_pause, self.btn_stop, self.btn_inapoi, self.btn_inainte):
            btn.setEnabled(True)
        self.slider_seek.setEnabled(True)
        self.bara.activeaza_snapshot(True)

        self._ignore_slider = True
        self.slider_seek.setValue(0)
        self._ignore_slider = False
        self.btn_play_pause.setText("▶")
        self.bara.reset_fps()
        self.bara.lista_detectii.clear()
        self._cadru_curent = 0
        self._total_cadre  = total

        durata = total / self.fps_video if self.fps_video > 0 else 0
        self.label_timp.setText(f"00:00 / {self._format_timp(durata)}")
        self._actualizeaza_status(tr("status_video_loaded", nume=os.path.basename(cale)))

    # --- Model (rutat prin fereastra principala = un singur drum de incarcare) ---

    def _incarca_model(self):
        if self.fereastra_parinte:
            self.fereastra_parinte._meniu_incarca_model()

    def _schimba_model(self, index):
        if self._ignore_combo:
            return
        cale = self.combo_model.itemData(index)
        if cale and self.fereastra_parinte:
            self.fereastra_parinte._propagare_model(cale)

    @staticmethod
    def _norm_cale(p):
        """Normalizeaza o cale pt comparatie robusta (absolut/relativ, slash/backslash)."""
        return os.path.normcase(os.path.abspath(p)) if p else None

    def populeaza_modele_standard(self):
        """Listeaza in bara de sus toate detectoarele standard din modele/ (exclus clasificatorul),
        ca sa poti comuta intre ele direct, fara sa le incarci manual."""
        import glob
        if self.fereastra_parinte and hasattr(self.fereastra_parinte, "_get_dir_app"):
            base = self.fereastra_parinte._get_dir_app()
        else:
            base = os.environ.get("ADAS_BASE_DIR",
                                  os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dir_modele = os.path.join(base, "modele")
        if not os.path.isdir(dir_modele):
            return
        fisiere = sorted(glob.glob(os.path.join(dir_modele, "*.pt")))
        fisiere = [f for f in fisiere if "clasificator" not in os.path.basename(f).lower()]
        self._ignore_combo = True
        existente = {self._norm_cale(self.combo_model.itemData(i))
                     for i in range(self.combo_model.count())}
        for cale in fisiere:
            if self._norm_cale(cale) in existente:
                continue
            self.combo_model.addItem(f"  {os.path.basename(cale)}", cale)
        self._ignore_combo = False

    def adauga_model_in_lista(self, cale_model):
        """Adauga modelul in combo si il selecteaza (fara sa re-declanseze incarcarea)."""
        if not cale_model:
            return
        self._ignore_combo = True
        cn = self._norm_cale(cale_model)
        for i in range(self.combo_model.count()):
            if self._norm_cale(self.combo_model.itemData(i)) == cn:
                self.combo_model.setCurrentIndex(i)
                self._ignore_combo = False
                return
        self.combo_model.addItem(f"  {os.path.basename(cale_model)}", cale_model)
        self.combo_model.setCurrentIndex(self.combo_model.count() - 1)
        self._ignore_combo = False

    # --- Redare ---

    def eventFilter(self, obj, event):
        """Click pe display video = toggle play/pause."""
        if (obj is self.label_video
                and event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and self.btn_play_pause.isEnabled()):
            self._toggle_play_pause()
            return True
        return super().eventFilter(obj, event)

    def _schimba_viteza(self, index):
        _, viteza = VITEZE[index]
        if self.thread_video:
            self.thread_video.velocitate = viteza

    def _toggle_play_pause(self):
        if self.thread_video and self.thread_video.isRunning():
            self.thread_video.toggle_pauza()
            if self.thread_video.in_pauza:
                self.btn_play_pause.setText("▶")
                self.label_status_video.setText(tr("video_state_paused"))
            else:
                self.btn_play_pause.setText("⏸")
                self.label_status_video.setText(tr("video_state_running"))
        else:
            self._porneste_video()

    def _porneste_video(self):
        if not self.cale_video:
            return

        _, viteza = VITEZE[self.combo_viteza.currentIndex()]

        # Pasam referinta directa la config (nu copie): schimbarile din bara
        # laterala (confidence, IoU, rezolutie, clase) sunt vizibile imediat.
        self.thread_video = ThreadVideo(
            sursa=self.cale_video,
            model=self.model_yolo,
            config=self.config
        )
        self._fps_jos_contor = 0
        self.thread_video.velocitate = viteza
        self.thread_video.semnal_cadru.connect(self._actualizeaza_cadru)
        self.thread_video.semnal_fps.connect(self.bara.actualizeaza_fps)
        self.thread_video.semnal_fps.connect(self._monitor_fps_jos)
        self.thread_video.semnal_latenta.connect(self.bara.actualizeaza_latenta)
        self.thread_video.semnal_detectii.connect(self.bara.actualizeaza_detectii)
        self.thread_video.semnal_progres.connect(self._actualizeaza_progres)
        self.thread_video.semnal_eroare.connect(self._eroare_video)
        self.thread_video.semnal_gata.connect(self._video_gata)
        self.thread_video.start()

        self.btn_play_pause.setText("⏸")
        self.label_status_video.setText(tr("video_state_running"))

    def _stop(self):
        self._opreste_thread_video()
        self.btn_play_pause.setText("▶")
        self._ignore_slider = True
        self.slider_seek.setValue(0)
        self._ignore_slider = False
        self.label_timp.setText(f"00:00 / {self._format_timp(0)}")
        self.bara.goleste()
        self.label_status_video.setText(tr("video_state_stopped"))
        self.label_video.clear_cadru()
        self.label_video.setText(tr("video_press_play"))
        self._fps_jos_contor = 0
        self.banner_benchmark.setVisible(False)

    def _sari_secunde(self, secunde):
        """Sare cu +/- N secunde fata de pozitia curenta."""
        if not self.thread_video:
            return
        delta_cadre = int(secunde * self.fps_video)
        self.thread_video.seek(max(0, self._cadru_curent + delta_cadre))

    def _seek_din_slider(self, valoare):
        """Apelat cand utilizatorul misca/apasa pe seekbar."""
        if self._ignore_slider or not self.thread_video:
            return
        if self._total_cadre > 0:
            cadru = int(valoare / 1000 * self._total_cadre)
            self.thread_video.seek(cadru)

    def _snapshot(self):
        # Cadrul-sursa full-res; fallback la pixmap-ul afisat daca nu exista cadru
        pixmap = self.label_video.cadru_sursa() or self.label_video.pixmap()
        if pixmap and not pixmap.isNull():
            folder = self.config.get("snapshot_folder", "snapshots")
            os.makedirs(folder, exist_ok=True)
            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            cale = os.path.join(folder, f"snapshot_{ts}.png")
            pixmap.save(cale)
            self._actualizeaza_status(tr("status_snapshot_saved", cale=cale))

    # ------------------------------------------------------------------ #
    # Sloturi thread
    # ------------------------------------------------------------------ #

    def _semnal_de_la_thread_curent(self):
        """True doar daca semnalul vine de la thread-ul video activ (nu unul vechi/oprit)."""
        return self.sender() is self.thread_video

    def _actualizeaza_cadru(self, qimage):
        if not self._semnal_de_la_thread_curent():
            return   # cadru 'fantoma' de la un thread vechi - ignoram
        self.label_video.seteaza_cadru(QPixmap.fromImage(qimage))

    def _monitor_fps_jos(self, fps):
        """Recomanda un benchmark daca redarea ramane in urma (FPS scazut sustinut).
        Doar la viteza >= 1x si doar cand chiar pierdem cadre fata de cadenta nativa
        (ca incetinirea intentionata 0.5x sa nu declanseze fals)."""
        if not self._semnal_de_la_thread_curent() or self._benchmark_sugerat:
            return
        _, viteza = VITEZE[self.combo_viteza.currentIndex()]
        prag_nativ = self.fps_video * 0.9 if self.fps_video else 15
        if viteza >= 1.0 and fps < 15 and fps < prag_nativ:
            self._fps_jos_contor += 1
        else:
            self._fps_jos_contor = 0
        if self._fps_jos_contor >= 3:   # ~3 secunde consecutive (FPS emis ~1/s)
            self._benchmark_sugerat = True
            self.banner_benchmark.setText(tr("video_low_fps_banner", fps=fps))
            self.banner_benchmark.setVisible(True)

    def _actualizeaza_progres(self, curent, total):
        if not self._semnal_de_la_thread_curent():
            return
        self._cadru_curent = curent
        self._total_cadre  = total
        if total > 0:
            self._ignore_slider = True
            self.slider_seek.setValue(int(curent * 1000 / total))
            self._ignore_slider = False

            sec_curent = curent / self.fps_video
            sec_total  = total  / self.fps_video
            self.label_timp.setText(
                f"{self._format_timp(sec_curent)} / {self._format_timp(sec_total)}"
            )

    def _eroare_video(self, mesaj):
        if not self._semnal_de_la_thread_curent():
            return
        self.label_status_video.setText(tr("video_state_error"))
        self._actualizeaza_status(tr("status_video_error", mesaj=mesaj))

    def _video_gata(self):
        if not self._semnal_de_la_thread_curent():
            return
        self.btn_play_pause.setText("▶")
        self.label_status_video.setText(tr("video_state_finished"))
        self._ignore_slider = True
        self.slider_seek.setValue(1000)
        self._ignore_slider = False

    def _actualizeaza_status(self, mesaj):
        if self.fereastra_parinte:
            self.fereastra_parinte.statusBar().showMessage(mesaj, 5000)

    def reincarca_din_config(self):
        """Re-aliniaza bara laterala cand panoul devine vizibil."""
        self.bara.reincarca_din_config()

    def _toggle_bara(self):
        """Ascunde / arata bara laterala din dreapta."""
        ascuns = self.bara.isHidden()      # True daca e ascuns acum
        self.bara.setVisible(ascuns)        # ascuns -> arata; vizibil -> ascunde
        self.btn_colaps_bara.setText("▶" if ascuns else "◀")

    def _deschide_setari(self):
        """Navigheaza la pagina de Setari avansate."""
        if self.fereastra_parinte:
            self.fereastra_parinte._naviga(3)

    # ------------------------------------------------------------------ #
    # Utilitare
    # ------------------------------------------------------------------ #

    def _format_timp(self, secunde):
        secunde = max(0, int(secunde))
        h = secunde // 3600
        m = (secunde % 3600) // 60
        s = secunde % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
