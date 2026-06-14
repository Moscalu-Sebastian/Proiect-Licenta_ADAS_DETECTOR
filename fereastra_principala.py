"""
Fereastra principala a aplicatiei ADAS Detector.
Contine: menu bar, sidebar de navigare, zona de continut, status bar.
"""

import json
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStackedWidget, QLabel, QFrame,
    QFileDialog, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence

from panouri.panou_video     import PanouVideo
from panouri.panou_rtsp      import PanouRTSP
from panouri.panou_benchmark import PanouBenchmark
from panouri.panou_setari    import PanouSetari
from nuclee import baza_date
from nuclee.traduceri import tr, seteaza_limba
from nuclee.optimizare_praguri import ThreadOptimizare, gaseste_resurse_val
from nuclee.clase_model import normalizeaza_names, gaseste_clasa_semn, clase_compatibile


class FereastaPrincipala(QMainWindow):
    """Fereastra principala cu sidebar de navigare si panou de continut schimbabil."""

    def __init__(self):
        super().__init__()
        self.config = self._incarca_config()
        # Limba se fixeaza inainte de a construi UI-ul (textele se traduc la creare)
        seteaza_limba(self.config.get("limba", "en"))
        self._index_anterior = 0   # ultimul panou non-Setari (pentru butonul Inapoi)
        self._thread_optim   = None   # thread-ul de optimizare praguri (cand ruleaza)
        self._model_names    = None   # numele claselor modelului curent (din model.names)
        self._initUI()

    # --- Config ---

    def _get_dir_app(self):
        """Returneaza directorul aplicatiei - functioneaza si in .exe bundled."""
        return os.environ.get('ADAS_BASE_DIR', os.path.dirname(os.path.abspath(__file__)))

    def _incarca_config(self):
        dir_app = self._get_dir_app()
        implicit = {
            "model_path": "", "confidence": 0.45, "iou": 0.45, "imgsz": 640,
            "show_labels": True, "show_confidence": True, "show_tracks": False,
            "clasificare_semne": False,
            "rtsp_url": "rtsp://", "rtsp_timeout": 5,
            "snapshot_folder": "snapshots", "theme": "dark",
            "limba": "en",
            "praguri_clase": {},        # {id_clasa: prag} - gol = foloseste confidence global
            "modele_intrebate": [],     # caile modelelor pt care s-a oferit deja optimizarea
            "cls_semn": 9               # id-ul clasei de semn pt two-stage (-1 = modelul nu are)
        }
        baza_date.init_db()
        # Migram automat un eventual config.json vechi in DB (o singura data)
        baza_date.migreaza_din_json(os.path.join(dir_app, "config.json"))
        date = baza_date.incarca_setari()
        # Rezolva model_path relativ la folderul aplicatiei
        mp = date.get("model_path", "")
        if mp and not os.path.isabs(mp):
            date["model_path"] = os.path.join(dir_app, mp)
        return {**implicit, **date}

    def salveaza_config(self):
        dir_app = self._get_dir_app()
        date = self.config.copy()
        # Istoricul video sta in tabelul lui (videoclipuri), nu in setari
        date.pop("istoric_video", None)
        date.pop("istoric_migrat", None)
        # Salveaza model_path relativ la folderul aplicatiei (portabil)
        mp = date.get("model_path", "")
        if mp and os.path.isabs(mp):
            try:
                rel = os.path.relpath(mp, dir_app)
                if not rel.startswith(".."):
                    date["model_path"] = rel.replace("\\", "/")
            except ValueError:
                pass  # drive-uri diferite pe Windows - pastram absolut
        baza_date.salveaza_setari(date)

    # --- UI ---

    def _initUI(self):
        self.setWindowTitle(tr("app_title"))
        self.setMinimumSize(1280, 720)
        self.resize(1440, 860)

        self._creeaza_meniu()
        self._creeaza_layout_principal()
        self._creeaza_status_bar()

        # Navigam implicit pe primul panou
        self._naviga(0)

    def _creeaza_meniu(self):
        bara = self.menuBar()

        # Fisier
        m_fisier = bara.addMenu(tr("menu_file"))

        a_video = QAction(tr("menu_open_video"), self)
        a_video.setShortcut(QKeySequence("Ctrl+O"))
        a_video.triggered.connect(self._meniu_deschide_video)
        m_fisier.addAction(a_video)

        a_snap = QAction(tr("menu_snapshot"), self)
        a_snap.setShortcut(QKeySequence("Ctrl+S"))
        a_snap.triggered.connect(self._snapshot_curent)
        m_fisier.addAction(a_snap)

        m_fisier.addSeparator()

        a_exit = QAction(tr("menu_exit"), self)
        a_exit.setShortcut(QKeySequence("Ctrl+Q"))
        a_exit.triggered.connect(self.close)
        m_fisier.addAction(a_exit)

        # Vizualizare
        m_view = bara.addMenu(tr("menu_view"))

        self.a_fullscreen = QAction(tr("menu_fullscreen"), self)
        self.a_fullscreen.setShortcut(QKeySequence("F11"))
        self.a_fullscreen.setCheckable(True)
        self.a_fullscreen.triggered.connect(self._toggle_fullscreen)
        m_view.addAction(self.a_fullscreen)

        a_sidebar = QAction(tr("menu_toggle_sidebar"), self)
        a_sidebar.setShortcut(QKeySequence("Ctrl+B"))
        a_sidebar.triggered.connect(self._toggle_sidebar)
        m_view.addAction(a_sidebar)

        m_view.addSeparator()

        a_setari = QAction(tr("menu_settings"), self)
        a_setari.triggered.connect(lambda: self._naviga(3))
        m_view.addAction(a_setari)

        # Model
        m_model = bara.addMenu(tr("menu_model"))

        a_incarca = QAction(tr("menu_load_model"), self)
        a_incarca.triggered.connect(self._meniu_incarca_model)
        m_model.addAction(a_incarca)

        m_model.addSeparator()

        a_benchmark = QAction(tr("menu_run_benchmark"), self)
        a_benchmark.triggered.connect(lambda: self._naviga(2))
        m_model.addAction(a_benchmark)

        # Ajutor
        m_help = bara.addMenu(tr("menu_help"))

        a_despre = QAction(tr("menu_about"), self)
        a_despre.triggered.connect(self._arata_despre)
        m_help.addAction(a_despre)

    def _creeaza_layout_principal(self):
        widget_central = QWidget()
        widget_central.setObjectName("widgetCentral")
        self.setCentralWidget(widget_central)

        layout = QHBoxLayout(widget_central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._creeaza_sidebar())
        layout.addWidget(self._creeaza_zona_continut())

    def _creeaza_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Logo area ---
        logo_widget = QWidget()
        logo_widget.setObjectName("logoArea")
        logo_layout = QVBoxLayout(logo_widget)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(0)

        lbl_icon = QLabel("◈")
        lbl_icon.setObjectName("logoIcon")
        logo_layout.addWidget(lbl_icon)

        lbl_titlu = QLabel("ADAS")
        lbl_titlu.setObjectName("titluApp")
        logo_layout.addWidget(lbl_titlu)

        lbl_ver = QLabel(tr("logo_subtitle"))
        lbl_ver.setObjectName("versiuneApp")
        logo_layout.addWidget(lbl_ver)

        layout.addWidget(logo_widget)

        # Mic spatiu
        layout.addSpacing(8)

        # --- Butoane de navigare ---
        self.butoane_nav = []
        nav_items = [
            ("▶   " + tr("nav_video"),    tr("nav_video_tip")),
            ("◉   " + tr("nav_rtsp"),     tr("nav_rtsp_tip")),
            ("⚡  " + tr("nav_benchmark"), tr("nav_benchmark_tip")),
        ]

        for i, (text, _tooltip) in enumerate(nav_items):
            btn = QPushButton(f"  {text}")
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setToolTip(_tooltip)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(50)
            btn.clicked.connect(lambda checked, idx=i: self._naviga(idx))
            layout.addWidget(btn)
            self.butoane_nav.append(btn)

        layout.addStretch()

        # "Setari" nu mai e aici - a devenit "Setari avansate" in panoul din dreapta
        # (si ramane accesibil din meniul de sus: Vizualizare -> Setari).

        return self.sidebar

    def _creeaza_zona_continut(self):
        self.stacked = QStackedWidget()
        self.stacked.setObjectName("stackedWidget")

        self.panou_video     = PanouVideo(self.config, self)
        self.panou_rtsp      = PanouRTSP(self.config, self)
        self.panou_benchmark = PanouBenchmark(self.config, self)
        self.panou_setari    = PanouSetari(self.config, self)

        self.stacked.addWidget(self.panou_video)      # 0
        self.stacked.addWidget(self.panou_rtsp)       # 1
        self.stacked.addWidget(self.panou_benchmark)  # 2
        self.stacked.addWidget(self.panou_setari)     # 3

        # Cand se selecteaza un model din Benchmark, il propagam la Video si RTSP
        # (intreaba=True -> ofera optimizarea pragurilor la primul model nou)
        self.panou_benchmark.semnal_model_selectat.connect(
            lambda c: self._propagare_model(c, intreaba=True)
        )

        # Auto-incarca modelul implicit la pornire
        mp = self.config.get("model_path", "")
        if mp and os.path.exists(mp):
            self._propagare_model(mp)

        return self.stacked

    def _creeaza_status_bar(self):
        sb = self.statusBar()
        sb.showMessage(tr("status_ready"), 8000)

        self.label_model_activ = QLabel(tr("status_model_none"))
        self.label_model_activ.setStyleSheet("padding: 0 12px;")
        sb.addPermanentWidget(self.label_model_activ)

    # --- Navigare ---

    def _naviga(self, index):
        if index != 3:                       # 3 = pagina Setari
            self._index_anterior = index     # retinem ultimul panou non-Setari
        self.stacked.setCurrentIndex(index)
        for i, btn in enumerate(self.butoane_nav):
            btn.setChecked(i == index)
        # Re-aliniem controalele panoului la config (evita desincronizarea
        # intre Video si RTSP, care editeaza acelasi config partajat)
        panou = self.stacked.widget(index)
        if hasattr(panou, "reincarca_din_config"):
            panou.reincarca_din_config()

    def _inapoi(self):
        """Revine la panoul anterior (folosit de butonul Inapoi din Setari avansate)."""
        self._naviga(self._index_anterior)

    def _snapshot_curent(self):
        """Snapshot pe panoul activ (Video sau RTSP)."""
        idx = self.stacked.currentIndex()
        if idx == 0:
            self.panou_video._snapshot()
        elif idx == 1:
            self.panou_rtsp._snapshot()

    # --- Actiuni meniu ---

    def _meniu_deschide_video(self):
        self._naviga(0)
        self.panou_video._deschide_video()

    def _meniu_incarca_model(self):
        cale, _ = QFileDialog.getOpenFileName(
            self, tr("dlg_select_model"),
            "", tr("filter_model")
        )
        if cale:
            self._propagare_model(cale, intreaba=True)

    def _toggle_fullscreen(self, checked):
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()

    def _toggle_sidebar(self):
        # Colapsare doar din meniul Vizualizare (Ctrl+B); nu mai exista buton-handle.
        self.sidebar.setVisible(self.sidebar.isHidden())

    def _arata_despre(self):
        QMessageBox.about(self, tr("about_title"), tr("about_body"))

    def reporneste_aplicatia(self):
        """Relanseaza aplicatia (folosit dupa schimbarea limbii din Setari)."""
        import sys
        from PyQt6.QtCore import QProcess
        from PyQt6.QtWidgets import QApplication
        # Salvam intai ca noua instanta sa porneasca cu setarile curente
        self.salveaza_config()
        program = sys.executable
        # In dev: python main.py ...  | In .exe bundled: doar executabilul
        argumente = [] if getattr(sys, "frozen", False) else sys.argv
        QProcess.startDetached(program, argumente)
        QApplication.quit()

    # --- Propagare model catre toate panourile ---

    def _propagare_model(self, cale_model, intreaba=False):
        if not cale_model or not os.path.exists(cale_model):
            return
        try:
            from ultralytics import YOLO
            model = YOLO(cale_model)
            self.panou_video.seteaza_model(model)   # actualizeaza LIVE thread-ul daca ruleaza
            self.panou_video.adauga_model_in_lista(cale_model)
            self.panou_rtsp.seteaza_model(model, cale_model)
            self.config["model_path"] = cale_model
            self._aplica_clase_model(model)   # propaga clasele (din model.names) la tot UI-ul
            self.label_model_activ.setText(tr("status_model_label", nume=os.path.basename(cale_model)))
            self.statusBar().showMessage(tr("status_model_propagated", nume=os.path.basename(cale_model)), 5000)
            self.salveaza_config()
        except Exception as e:
            self.statusBar().showMessage(tr("status_model_error", err=e), 8000)
            return

        # La PRIMA incarcare (initiata de user) a unui model nou, oferim optimizarea pragurilor
        # - doar daca clasele modelului sunt compatibile cu setul de validare.
        if intreaba:
            intrebate = self.config.setdefault("modele_intrebate", [])
            if cale_model not in intrebate:
                intrebate.append(cale_model)
                self.salveaza_config()
                if self._optimizare_disponibila():
                    self._prompt_optimizare(cale_model)

    def _aplica_clase_model(self, model):
        """Deriva clasele din model.names si le propaga la tot UI-ul (agnostic la dataset)."""
        names = normalizeaza_names(getattr(model, "names", None))
        # Comparam cu setul de clase SALVAT (nu cu runtime-ul), ca sa NU stergem
        # filtrele/pragurile la fiecare pornire cand se reincarca acelasi model.
        salvate = self.config.get("model_names")
        anterioare = normalizeaza_names(salvate) if salvate else None
        if anterioare is not None and names != anterioare:
            # alt set de clase -> filtrele/pragurile vechi nu mai au sens
            self.config["classes"] = None
            self.config["praguri_clase"] = {}
        self.config["model_names"] = names
        self._model_names = names

        # Clasa de semn pentru clasificatorul two-stage (None -> modelul n-are semne)
        cls_semn = gaseste_clasa_semn(names)
        self.config["cls_semn"] = cls_semn if cls_semn is not None else -1

        # Propagam clasele la barele laterale si la sliderele de praguri din Setari
        self.panou_video.bara.seteaza_clase(names)
        self.panou_rtsp.bara.seteaza_clase(names)
        self.panou_setari.seteaza_clase(names)

        # Clasificatorul de semne: blocat daca modelul n-are clasa de semn
        are_semn = cls_semn is not None
        self.panou_setari.check_clasificare.setEnabled(are_semn)
        if not are_semn:
            self.panou_setari.check_clasificare.setChecked(False)
            self.config["clasificare_semne"] = False
            self.panou_setari.check_clasificare.setToolTip(tr("classifier_no_sign"))
        else:
            self.panou_setari.check_clasificare.setToolTip("")

    def _optimizare_disponibila(self):
        """True daca exista set de validare SI clasele modelului sunt compatibile cu el."""
        val_dir, names = gaseste_resurse_val(self._get_dir_app())
        if not val_dir:
            return False
        return clase_compatibile(self._model_names, names)

    # --- Optimizare praguri per clasa ---

    def _prompt_optimizare(self, cale_model):
        """Dialog la primul model nou: optimizezi acum sau mai tarziu."""
        cutie = QMessageBox(self)
        cutie.setIcon(QMessageBox.Icon.Question)
        cutie.setWindowTitle(tr("opt_prompt_title"))
        cutie.setText(tr("opt_prompt_body", nume=os.path.basename(cale_model)))
        btn_acum = cutie.addButton(tr("opt_btn_now"), QMessageBox.ButtonRole.AcceptRole)
        cutie.addButton(tr("opt_btn_later"), QMessageBox.ButtonRole.RejectRole)
        cutie.exec()
        if cutie.clickedButton() is btn_acum:
            self.lanseaza_optimizare()

    def lanseaza_optimizare(self):
        """Porneste thread-ul de optimizare a pragurilor per clasa (o singura metoda)."""
        if self._thread_optim is not None and self._thread_optim.isRunning():
            self.statusBar().showMessage(tr("opt_busy"), 4000)
            return
        cale_model = self.config.get("model_path", "")
        if not cale_model or not os.path.exists(cale_model):
            self.statusBar().showMessage(tr("status_model_none"), 5000)
            return
        val_dir, names = gaseste_resurse_val(self._get_dir_app())
        if not val_dir:
            self.statusBar().showMessage(tr("opt_no_dataset"), 8000)
            return
        # Optimizarea are sens doar daca clasele modelului = clasele setului de validare
        if not clase_compatibile(self._model_names, names):
            self.statusBar().showMessage(tr("opt_incompatibil"), 9000)
            return

        self._thread_optim = ThreadOptimizare(cale_model, val_dir, names)
        self._thread_optim.semnal_status.connect(self._optim_status)
        self._thread_optim.semnal_gata.connect(self._optim_gata)
        self._thread_optim.semnal_eroare.connect(self._optim_eroare)
        self._thread_optim.start()

    def _optim_status(self, sentinela):
        # sentinela e o cheie de traducere ('optim_loading' / 'optim_running')
        self.statusBar().showMessage(tr(sentinela), 0)

    def _optim_gata(self, praguri):
        self.config["praguri_clase"] = praguri
        self.salveaza_config()
        # Reflectam pragurile in sliderele din Setari avansate
        if hasattr(self.panou_setari, "actualizeaza_praguri"):
            self.panou_setari.actualizeaza_praguri()
        # Confirmare vizibila in panou (auto-save: pragurile s-au salvat deja in DB)
        if hasattr(self.panou_setari, "marcheaza_optimizat"):
            self.panou_setari.marcheaza_optimizat(len(praguri))
        self.statusBar().showMessage(tr("opt_done", n=len(praguri)), 8000)

    def _optim_eroare(self, mesaj):
        self.statusBar().showMessage(tr("opt_error", err=mesaj), 10000)

    def closeEvent(self, event):
        # Oprim thread-urile active la inchidere
        for thread_attr in ["thread_video", "thread_rtsp"]:
            for panou in [self.panou_video, self.panou_rtsp]:
                t = getattr(panou, thread_attr, None)
                if t and t.isRunning():
                    t.opreste()
                    t.wait(1500)
        self.salveaza_config()
        event.accept()
