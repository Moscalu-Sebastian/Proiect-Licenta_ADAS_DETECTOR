"""
Panoul pentru modul RTSP (dashcam / stream Wi-Fi): bara de conectare
(auto-descoperire + URL manual) si zona de afisare. Parametrii de detectie si
alertele ADAS stau in bara laterala comuna BaraControlLateral.
"""

import os
import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from nuclee.thread_video import ThreadVideo
from nuclee.thread_descoperire import ThreadDescoperire
from nuclee.traduceri import tr
from panouri.bara_control import BaraControlLateral
from panouri.panou_video import EtichetaVideo


class PanouRTSP(QWidget):
    """Panou pentru conectare si afisare stream RTSP cu detectie ADAS."""

    def __init__(self, config, fereastra_parinte=None):
        super().__init__()
        self.config             = config
        self.fereastra_parinte  = fereastra_parinte
        self.thread_rtsp        = None
        self.thread_descoperire = None
        self.model_yolo         = None
        self._initUI()

    def _initUI(self):
        # Layout orizontal: [coloana stream pe toata inaltimea | maner | bara dreapta]
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Coloana stanga: bara de conectare (sus) + stream. Doar peste stream.
        col_stream = QWidget()
        cv = QVBoxLayout(col_stream)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(self._creeaza_bara_conectare())

        stream_container = QWidget()
        sl = QVBoxLayout(stream_container)
        sl.setContentsMargins(12, 8, 0, 8)
        sl.setSpacing(0)
        self.label_stream = EtichetaVideo(tr("rtsp_placeholder"))
        self.label_stream.setObjectName("displayVideo")
        self.label_stream.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_stream.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sl.addWidget(self.label_stream)
        cv.addWidget(stream_container)
        root.addWidget(col_stream)

        # Bara din dreapta pe TOATA inaltimea (ca sidebar-ul) + maner
        self.bara = BaraControlLateral(self.config, eticheta_fps=tr("bar_fps_stream"), cu_alerte=True)
        self.bara.semnal_snapshot.connect(self._snapshot)
        self.bara.semnal_setari_avansate.connect(self._deschide_setari)
        root.addWidget(self._creeaza_handle_bara())
        root.addWidget(self.bara)

    def _creeaza_handle_bara(self):
        """Maner subtire pe marginea stanga a panoului din dreapta (intre stream si panou)."""
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

    def _creeaza_bara_conectare(self):
        container = QFrame()
        container.setObjectName("baraConectare")
        layout_v = QVBoxLayout(container)
        layout_v.setContentsMargins(12, 8, 12, 8)
        layout_v.setSpacing(6)

        # --- Randul 1: auto-detectare ---
        rand1 = QHBoxLayout()
        rand1.setSpacing(10)

        self.btn_detecteaza = QPushButton(tr("rtsp_autodetect"))
        self.btn_detecteaza.setObjectName("btnSucces")
        self.btn_detecteaza.setFixedHeight(34)
        self.btn_detecteaza.setToolTip(tr("rtsp_autodetect_tip"))
        self.btn_detecteaza.clicked.connect(self._detecteaza_automat)
        rand1.addWidget(self.btn_detecteaza)

        self.label_scanare = QLabel(tr("rtsp_scan_hint"))
        self.label_scanare.setObjectName("labelHint")
        rand1.addWidget(self.label_scanare)
        rand1.addStretch()

        self.label_indicator = QLabel("● " + tr("rtsp_disconnected"))
        self.label_indicator.setObjectName("indicatorDeconectat")
        rand1.addWidget(self.label_indicator)

        layout_v.addLayout(rand1)

        # --- Randul 2: URL manual + butoane conectare ---
        rand2 = QHBoxLayout()
        rand2.setSpacing(10)

        lbl_url = QLabel(tr("rtsp_url_manual"))
        lbl_url.setObjectName("labelToolbar")
        lbl_url.setFixedWidth(80)
        rand2.addWidget(lbl_url)

        self.input_url = QLineEdit(self.config.get("rtsp_url", "rtsp://"))
        self.input_url.setPlaceholderText(tr("rtsp_url_placeholder"))
        self.input_url.setFixedHeight(30)
        self.input_url.returnPressed.connect(self._conecteaza)
        rand2.addWidget(self.input_url)

        self.btn_conecteaza = QPushButton(tr("rtsp_connect"))
        self.btn_conecteaza.setFixedHeight(30)
        self.btn_conecteaza.setFixedWidth(120)
        self.btn_conecteaza.clicked.connect(self._conecteaza)
        rand2.addWidget(self.btn_conecteaza)

        self.btn_deconecteaza = QPushButton(tr("rtsp_disconnect"))
        self.btn_deconecteaza.setObjectName("btnPericol")
        self.btn_deconecteaza.setFixedHeight(30)
        self.btn_deconecteaza.setFixedWidth(120)
        self.btn_deconecteaza.clicked.connect(self._deconecteaza)
        self.btn_deconecteaza.setEnabled(False)
        rand2.addWidget(self.btn_deconecteaza)

        rand2.addStretch()
        layout_v.addLayout(rand2)

        return container

    # ------------------------------------------------------------------ #
    # Auto-descoperire camera
    # ------------------------------------------------------------------ #

    def _detecteaza_automat(self):
        if self.thread_rtsp and self.thread_rtsp.isRunning():
            return

        self.btn_detecteaza.setEnabled(False)
        self.btn_conecteaza.setEnabled(False)
        self._seteaza_indicator("indicatorAsteptare", "● " + tr("rtsp_scanning"))
        self.label_scanare.setObjectName("labelHintActiv")
        self.label_scanare.setStyle(self.label_scanare.style())

        self.thread_descoperire = ThreadDescoperire()
        self.thread_descoperire.semnal_progres.connect(self._progres_scanare)
        self.thread_descoperire.semnal_gasit.connect(self._camera_gasita)
        self.thread_descoperire.semnal_esuat.connect(self._scanare_esuata)
        self.thread_descoperire.start()

    def _progres_scanare(self, mesaj):
        self.label_scanare.setText(mesaj)
        self._actualizeaza_status(mesaj)

    def _camera_gasita(self, url):
        self.input_url.setText(url)
        self.label_scanare.setObjectName("labelHintSucces")
        self.label_scanare.setStyle(self.label_scanare.style())
        self.label_scanare.setText(tr("rtsp_camera_found", url=url))
        self.btn_detecteaza.setEnabled(True)
        self.btn_conecteaza.setEnabled(True)
        self._actualizeaza_status(tr("status_rtsp_detected", url=url))
        self._conecteaza()

    def _scanare_esuata(self, motiv):
        self.label_scanare.setObjectName("labelHintEroare")
        self.label_scanare.setStyle(self.label_scanare.style())
        self.label_scanare.setText(tr("rtsp_detect_failed"))
        self._seteaza_indicator("indicatorDeconectat", "● " + tr("rtsp_disconnected"))
        self.btn_detecteaza.setEnabled(True)
        self.btn_conecteaza.setEnabled(True)
        self._actualizeaza_status(tr("status_rtsp_detect_failed", motiv=motiv.splitlines()[0]))

    # ------------------------------------------------------------------ #
    # Conectare / deconectare
    # ------------------------------------------------------------------ #

    def _conecteaza(self):
        url = self.input_url.text().strip()
        if not url or url == "rtsp://":
            self._actualizeaza_status(tr("status_rtsp_invalid"))
            return

        self.config["rtsp_url"] = url
        self._seteaza_indicator("indicatorAsteptare", "● " + tr("rtsp_connecting"))

        # Referinta directa la config: schimbarile din bara laterala sunt live.
        self.thread_rtsp = ThreadVideo(
            sursa=url,
            model=self.model_yolo,
            config=self.config
        )
        self.thread_rtsp.semnal_cadru.connect(self._actualizeaza_cadru)
        self.thread_rtsp.semnal_fps.connect(self.bara.actualizeaza_fps)
        self.thread_rtsp.semnal_latenta.connect(self.bara.actualizeaza_latenta)
        self.thread_rtsp.semnal_detectii.connect(self.bara.actualizeaza_detectii)
        self.thread_rtsp.semnal_eroare.connect(self._eroare_rtsp)
        self.thread_rtsp.semnal_gata.connect(self._stream_gata)
        self.thread_rtsp.start()

        self.btn_conecteaza.setEnabled(False)
        self.btn_deconecteaza.setEnabled(True)
        self.input_url.setEnabled(False)
        self.bara.activeaza_snapshot(True)
        self._actualizeaza_status(tr("status_rtsp_connecting", url=url))

    def _deconecteaza(self):
        if self.thread_rtsp and self.thread_rtsp.isRunning():
            self.thread_rtsp.opreste()
            self.thread_rtsp.wait(2000)
        self._resetare_ui()

    def _resetare_ui(self):
        self._seteaza_indicator("indicatorDeconectat", "● " + tr("rtsp_disconnected"))
        self.btn_conecteaza.setEnabled(True)
        self.btn_deconecteaza.setEnabled(False)
        self.input_url.setEnabled(True)
        self.bara.activeaza_snapshot(False)
        self.bara.goleste()
        self.label_stream.clear_cadru()
        self.label_stream.setText(tr("rtsp_disconnected_msg"))

    # ------------------------------------------------------------------ #
    # Sloturi thread
    # ------------------------------------------------------------------ #

    def _actualizeaza_cadru(self, qimage):
        # Marcam conectat la primul cadru primit
        if self.label_indicator.objectName() != "indicatorConectat":
            self._seteaza_indicator("indicatorConectat", "● " + tr("rtsp_connected"))

        self.label_stream.seteaza_cadru(QPixmap.fromImage(qimage))

    def _eroare_rtsp(self, mesaj):
        self._seteaza_indicator("indicatorDeconectat", "● " + tr("rtsp_indic_error"))
        self.label_stream.setText(tr("rtsp_conn_error", mesaj=mesaj))
        self._resetare_ui()
        self._actualizeaza_status(tr("status_rtsp_error", mesaj=mesaj))

    def _stream_gata(self):
        self._resetare_ui()

    # ------------------------------------------------------------------ #
    # Utilitare
    # ------------------------------------------------------------------ #

    def _seteaza_indicator(self, nume_obiect, text):
        """Schimba stilul + textul indicatorului de conexiune (forteaza re-stilizare)."""
        self.label_indicator.setObjectName(nume_obiect)
        self.label_indicator.setText(text)
        self.label_indicator.setStyle(self.label_indicator.style())

    def _snapshot(self):
        # Cadrul-sursa full-res; fallback la pixmap-ul afisat daca nu exista cadru
        pixmap = self.label_stream.cadru_sursa() or self.label_stream.pixmap()
        if pixmap and not pixmap.isNull():
            folder = self.config.get("snapshot_folder", "snapshots")
            os.makedirs(folder, exist_ok=True)
            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            cale = os.path.join(folder, f"rtsp_snapshot_{ts}.png")
            pixmap.save(cale)
            self._actualizeaza_status(f"Snapshot salvat: {cale}")

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

    def seteaza_model(self, model, cale_model=None):
        self.model_yolo = model
        if self.thread_rtsp:
            self.thread_rtsp.seteaza_model(model)
