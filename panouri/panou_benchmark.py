"""
Panoul de benchmark hardware si selectie model.

Detecteaza automat GPU/CPU/RAM, listeaza modelele reale din folderul `modele/`
(plus optiunea de a incarca unul custom) si masoara FPS-ul real pe hardware-ul
curent. Modelul aplicat se propaga la modul Video si RTSP prin fereastra principala.
"""

import os
import glob
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QButtonGroup, QFileDialog, QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from nuclee.traduceri import tr
from panouri.bara_control import REZOLUTII


class ThreadAutoBenchmark(QThread):
    """Benchmark automat: masoara FPS de inferenta pentru fiecare combinatie
    (model x rezolutie) pe cadre sintetice 720p, cu cateva rulari de incalzire
    inainte (init CUDA) ca prima inferenta sa nu falsifice rezultatul."""

    semnal_progres  = pyqtSignal(int, str)   # procent, eticheta configuratiei curente
    semnal_rezultat = pyqtSignal(list)       # [{model_path, model_nume, size, imgsz, fps}]
    semnal_eroare   = pyqtSignal(str)

    def __init__(self, combinatii):
        super().__init__()
        self.combinatii = combinatii   # [(cale_model, nume, size, imgsz)], deja ordonate

    def run(self):
        try:
            import time
            import numpy as np
            from ultralytics import YOLO

            cadru = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
            cache = {}
            rezultate = []
            total = max(1, len(self.combinatii))

            for i, (cale, nume, size, imgsz) in enumerate(self.combinatii):
                self.semnal_progres.emit(int(i * 100 / total), f"{nume} @ {imgsz}px")
                model = cache.get(cale)
                if model is None:
                    model = YOLO(cale)
                    cache[cale] = model

                for _ in range(3):   # incalzire (necronometrata)
                    model(cadru, imgsz=imgsz, conf=0.45, verbose=False)

                n  = 25
                t0 = time.perf_counter()
                for _ in range(n):
                    model(cadru, imgsz=imgsz, conf=0.45, verbose=False)
                dt  = time.perf_counter() - t0
                fps = n / dt if dt > 0 else 0.0

                rezultate.append({"model_path": cale, "model_nume": nume,
                                  "size": size, "imgsz": imgsz, "fps": fps})

            self.semnal_progres.emit(100, "")
            self.semnal_rezultat.emit(rezultate)

        except Exception as e:
            self.semnal_eroare.emit(str(e))


class PanouBenchmark(QWidget):
    """Panou cu info hardware, selectie model real si benchmark."""

    # Emis cand userul aplica un model (pentru a-l propaga la celelalte panouri)
    semnal_model_selectat = pyqtSignal(str)

    def __init__(self, config, fereastra_parinte=None):
        super().__init__()
        self.config              = config
        self.fereastra_parinte   = fereastra_parinte
        self.cale_model_selectat = None
        self.thread_benchmark    = None
        self._carduri_model      = []
        self._initUI()
        self._detecteaza_hardware()

    def _initUI(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        continut = QWidget()
        layout = QVBoxLayout(continut)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(20)

        lbl_titlu = QLabel(tr("bm_title"))
        lbl_titlu.setObjectName("titluPanou")
        lbl_sub = QLabel(tr("bm_subtitle"))
        lbl_sub.setObjectName("subtitluPanou")
        layout.addWidget(lbl_titlu)
        layout.addWidget(lbl_sub)

        layout.addWidget(self._sectiune_hardware())
        layout.addWidget(self._sectiune_modele())
        layout.addWidget(self._sectiune_benchmark())
        layout.addStretch()

        scroll.setWidget(continut)

        layout_root = QVBoxLayout(self)
        layout_root.setContentsMargins(0, 0, 0, 0)
        layout_root.addWidget(scroll)

    # ------------------------------------------------------------------ #
    # Hardware
    # ------------------------------------------------------------------ #

    def _sectiune_hardware(self):
        grup = QFrame()
        grup.setObjectName("cardSectiune")
        layout = QVBoxLayout(grup)
        layout.setSpacing(12)

        lbl_hw = QLabel(tr("bm_hw_info"))
        lbl_hw.setObjectName("labelSectiuneCard")
        layout.addWidget(lbl_hw)

        grid = QHBoxLayout()
        grid.setSpacing(12)
        self.card_gpu  = self._card_hw("GPU", tr("bm_detecting"))
        self.card_vram = self._card_hw("VRAM", tr("bm_detecting"))
        self.card_cpu  = self._card_hw("CPU", tr("bm_detecting"))
        self.card_ram  = self._card_hw(tr("bm_ram_system"), tr("bm_detecting"))
        for c in (self.card_gpu, self.card_vram, self.card_cpu, self.card_ram):
            grid.addWidget(c)
        layout.addLayout(grid)

        return grup

    def _card_hw(self, titlu, valoare):
        card = QFrame()
        card.setObjectName("cardHwMini")
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        lbl_t = QLabel(titlu)
        lbl_t.setObjectName("labelHwTitluMic")
        lbl_v = QLabel(valoare)
        lbl_v.setObjectName("labelHwValoare")
        lbl_v.setWordWrap(True)
        layout.addWidget(lbl_t)
        layout.addWidget(lbl_v)
        card._lbl_valoare = lbl_v
        return card

    # ------------------------------------------------------------------ #
    # Selectie model (din folderul modele/)
    # ------------------------------------------------------------------ #

    def _sectiune_modele(self):
        grup = QFrame()
        grup.setObjectName("cardSectiune")
        layout = QVBoxLayout(grup)
        layout.setSpacing(12)

        lbl_t = QLabel(tr("bm_model_select"))
        lbl_t.setObjectName("labelSectiuneCard")
        layout.addWidget(lbl_t)

        lbl_sub = QLabel(tr("bm_model_sub"))
        lbl_sub.setObjectName("labelDesc")
        layout.addWidget(lbl_sub)

        # Carduri pentru modelele reale din folder
        self.grup_butoane = QButtonGroup(self)
        self.grup_butoane.setExclusive(True)

        self.zona_carduri = QHBoxLayout()
        self.zona_carduri.setSpacing(12)
        layout.addLayout(self.zona_carduri)
        self._populeaza_carduri_model()

        # Incarca model custom
        layout_custom = QHBoxLayout()
        self.btn_incarca_custom = QPushButton(tr("bm_load_custom"))
        self.btn_incarca_custom.setObjectName("btnSecundar")
        self.btn_incarca_custom.setFixedHeight(38)   # acelasi cu Aplica model / Ruleaza Benchmark
        self.btn_incarca_custom.clicked.connect(self._incarca_model_custom)
        layout_custom.addWidget(self.btn_incarca_custom)
        self.label_model_custom = QLabel("")
        self.label_model_custom.setObjectName("labelDesc")
        layout_custom.addWidget(self.label_model_custom)
        layout_custom.addStretch()
        layout.addLayout(layout_custom)

        # Aplica + status
        layout_confirmare = QHBoxLayout()
        self.btn_aplica_model = QPushButton(tr("bm_apply_model"))
        self.btn_aplica_model.setFixedHeight(38)
        self.btn_aplica_model.setEnabled(False)
        self.btn_aplica_model.clicked.connect(self._aplica_model)
        layout_confirmare.addWidget(self.btn_aplica_model)
        layout_confirmare.addStretch()
        self.label_model_activ = QLabel(tr("bm_model_none"))
        self.label_model_activ.setObjectName("labelSucces")
        layout_confirmare.addWidget(self.label_model_activ)
        layout.addLayout(layout_confirmare)

        return grup

    def _dir_modele(self):
        base = os.environ.get(
            "ADAS_BASE_DIR",
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        return os.path.join(base, "modele")

    def _eticheta_model(self, nume_fisier):
        """Returneaza o descriere scurta pe baza numelui fisierului."""
        n = nume_fisier.lower()
        if "26n" in n or "yolov8n" in n or "nano" in n:
            return tr("bm_tag_nano")
        if "26s" in n or "small" in n:
            return tr("bm_tag_small")
        if "26m" in n or "medium" in n:
            return tr("bm_tag_medium")
        return tr("bm_tag_generic")

    def _populeaza_carduri_model(self):
        # Curatam cardurile existente
        for c in self._carduri_model:
            self.grup_butoane.removeButton(c)
            c.deleteLater()
        self._carduri_model = []

        dir_modele = self._dir_modele()
        fisiere = sorted(glob.glob(os.path.join(dir_modele, "*.pt"))) if os.path.isdir(dir_modele) else []
        # Excludem clasificatorul de semne - e model de clasificare (two-stage), NU detector
        fisiere = [f for f in fisiere if "clasificator" not in os.path.basename(f).lower()]

        if not fisiere:
            lbl = QLabel(tr("bm_no_models"))
            lbl.setObjectName("labelDesc")
            self.zona_carduri.addWidget(lbl)
            self._lbl_gol = lbl
            return

        for cale in fisiere:
            nume = os.path.basename(cale)
            try:
                mb = os.path.getsize(cale) / (1024 ** 2)
                marime = f"{mb:.1f} MB"
            except OSError:
                marime = "?"
            card = self._card_model(nume, self._eticheta_model(nume), marime, cale)
            self.zona_carduri.addWidget(card)
            self._carduri_model.append(card)

    def _card_model(self, nume, descriere, marime, cale):
        card = QPushButton()
        card.setObjectName("cardModel")
        card.setCheckable(True)
        card.setText(f"{nume}\n\n{descriere}\n{marime}")
        card.setToolTip(cale)
        card.clicked.connect(lambda _checked, c=cale: self._selecteaza_model_card(c))
        self.grup_butoane.addButton(card)
        return card

    def _selecteaza_model_card(self, cale):
        self.cale_model_selectat = cale
        self.label_model_custom.setText("")
        self.btn_aplica_model.setEnabled(True)

    def _incarca_model_custom(self):
        cale, _ = QFileDialog.getOpenFileName(
            self, tr("dlg_select_model"),
            "", tr("filter_model")
        )
        if not cale:
            return
        self.cale_model_selectat = cale
        self.label_model_custom.setText(tr("bm_custom_prefix", nume=os.path.basename(cale)))
        # Deselectam cardurile
        self.grup_butoane.setExclusive(False)
        for btn in self.grup_butoane.buttons():
            btn.setChecked(False)
        self.grup_butoane.setExclusive(True)
        self.btn_aplica_model.setEnabled(True)

    def _aplica_model(self):
        cale = self.cale_model_selectat or self.config.get("model_path", "")
        if not cale or not os.path.exists(cale):
            self._actualizeaza_status(tr("bm_select_valid"))
            return

        self.label_model_activ.setText(tr("bm_active_prefix", nume=os.path.basename(cale)))
        # Propagarea efectiva (incarcare + salvare config) o face fereastra principala
        self.semnal_model_selectat.emit(cale)
        self._actualizeaza_status(tr("bm_model_applied", nume=os.path.basename(cale)))

    # ------------------------------------------------------------------ #
    # Benchmark
    # ------------------------------------------------------------------ #

    def _sectiune_benchmark(self):
        grup = QFrame()
        grup.setObjectName("cardSectiune")
        layout = QVBoxLayout(grup)
        layout.setSpacing(10)

        lbl_t = QLabel(tr("bm_section"))
        lbl_t.setObjectName("labelSectiuneCard")
        layout.addWidget(lbl_t)

        lbl_sub = QLabel(tr("bm_section_sub"))
        lbl_sub.setObjectName("labelDesc")
        lbl_sub.setWordWrap(True)
        layout.addWidget(lbl_sub)

        layout_btn = QHBoxLayout()
        self.btn_benchmark = QPushButton(tr("bm_run"))
        self.btn_benchmark.setFixedHeight(38)
        self.btn_benchmark.clicked.connect(self._ruleaza_auto)
        layout_btn.addWidget(self.btn_benchmark)
        layout_btn.addStretch()
        layout.addLayout(layout_btn)

        self.bara_benchmark = QProgressBar()
        self.bara_benchmark.setRange(0, 100)
        self.bara_benchmark.setValue(0)
        self.bara_benchmark.setFixedHeight(8)
        self.bara_benchmark.setVisible(False)
        layout.addWidget(self.bara_benchmark)

        self.label_rezultat_bm = QLabel("")
        self.label_rezultat_bm.setObjectName("labelRezultatBm")
        self.label_rezultat_bm.setWordWrap(True)
        layout.addWidget(self.label_rezultat_bm)

        # Containerul celor 4 carduri-optiune (apar dupa sweep)
        self.zona_optiuni = QHBoxLayout()
        self.zona_optiuni.setSpacing(12)
        layout.addLayout(self.zona_optiuni)
        self._carduri_optiuni = []

        return grup

    # ------------------------------------------------------------------ #
    # Benchmark automat: sweep (model x rezolutie) -> 4 optiuni pe paliere FPS
    # ------------------------------------------------------------------ #

    def _detectoare(self):
        """Lista detectoarelor reale din modele/ ca (cale, nume, dimensiune_bytes).
        Clasificatorul de semne e exclus (nu e detector)."""
        dir_modele = self._dir_modele()
        fisiere = sorted(glob.glob(os.path.join(dir_modele, "*.pt"))) if os.path.isdir(dir_modele) else []
        fisiere = [f for f in fisiere if "clasificator" not in os.path.basename(f).lower()]
        out = []
        for f in fisiere:
            try:
                size = os.path.getsize(f)
            except OSError:
                size = 0
            out.append((f, os.path.basename(f), size))
        return out

    def _ruleaza_auto(self):
        if self.thread_benchmark is not None and self.thread_benchmark.isRunning():
            return
        detectoare = self._detectoare()
        if not detectoare:
            self._actualizeaza_status(tr("bm_no_models"))
            return

        # Nano = cel mai mic detector (proxy dupa dimensiunea fisierului).
        # Incepem cu nano @ 1280 (cerinta), apoi maturam restul combinatiilor.
        nano = min(detectoare, key=lambda d: d[2])
        combinatii = [(nano[0], nano[1], nano[2], 1280)]
        for cale, nume, size in detectoare:
            for r in REZOLUTII:
                if cale == nano[0] and r == 1280:
                    continue
                combinatii.append((cale, nume, size, r))

        # Curatam optiunile precedente
        self._curata_optiuni()
        self.bara_benchmark.setVisible(True)
        self.bara_benchmark.setValue(0)
        self.btn_benchmark.setEnabled(False)
        self.label_rezultat_bm.setText(tr("bm_smart_start"))
        self._actualizeaza_status(tr("bm_in_progress"))

        self.thread_benchmark = ThreadAutoBenchmark(combinatii)
        self.thread_benchmark.semnal_progres.connect(self._progres_auto)
        self.thread_benchmark.semnal_rezultat.connect(self._rezultat_auto)
        self.thread_benchmark.semnal_eroare.connect(self._eroare_auto)
        self.thread_benchmark.start()

    def _progres_auto(self, procent, eticheta):
        self.bara_benchmark.setValue(procent)
        if eticheta:
            self.label_rezultat_bm.setText(tr("bm_smart_testing", config=eticheta))

    def _rezultat_auto(self, rezultate):
        self.bara_benchmark.setValue(100)
        self.btn_benchmark.setEnabled(True)
        if not rezultate:
            self.label_rezultat_bm.setText(tr("bm_smart_empty"))
            return
        optiuni = self._alege_4_optiuni(rezultate)
        self._afiseaza_optiuni(optiuni)
        self.label_rezultat_bm.setText(tr("bm_smart_done"))
        self._actualizeaza_status(tr("bm_smart_done"))

    def _eroare_auto(self, mesaj):
        self.bara_benchmark.setVisible(False)
        self.btn_benchmark.setEnabled(True)
        self.label_rezultat_bm.setText(tr("bm_error", mesaj=mesaj))

    # Definitia palierelor: (cheie titlu, fps_min, fps_max sau None=fara plafon)
    _PALIERE = [
        ("bm_opt_quality",  10, None),   # >=10 FPS, calitate maxima (mai lent dar mai bun)
        ("bm_opt_balanced", 15, 20),     # 15-20 FPS
        ("bm_opt_fluid",    20, 25),     # 20-25 FPS
        ("bm_opt_fast",     30, None),   # >30 FPS, cea mai buna calitate care ramane foarte fluida
    ]

    def _alege_4_optiuni(self, rez):
        """Alege 4 configuratii, una per palier FPS. In fiecare palier ia configuratia cu
        CEA MAI BUNA calitate (model mai mare > rezolutie mai mare), preferand optiuni
        distincte. Daca un palier e gol pe hardware-ul curent, ia cea mai apropiata ca FPS."""
        def calitate(r):
            return (r["size"], r["imgsz"], r["fps"])   # model mai mare, apoi rezolutie, apoi fps

        alese = []
        folosite = set()
        for cheie, lo, hi in self._PALIERE:
            if hi is None:
                in_palier = [r for r in rez if r["fps"] >= lo]
            else:
                in_palier = [r for r in rez if lo <= r["fps"] < hi]
            noi = [r for r in in_palier if id(r) not in folosite]
            pool = noi or in_palier
            if pool:
                ales = max(pool, key=calitate)
                aprox = False
            else:
                # niciun rezultat in interval -> cel mai apropiat ca FPS de tinta palierului
                tinta = lo if hi is None else (lo + hi) / 2
                rest = [r for r in rez if id(r) not in folosite] or rez
                ales = min(rest, key=lambda r: abs(r["fps"] - tinta))
                aprox = True
            folosite.add(id(ales))
            alese.append({**ales, "cheie": cheie, "aprox": aprox})
        return alese

    def _curata_optiuni(self):
        for c in self._carduri_optiuni:
            c.deleteLater()
        self._carduri_optiuni = []

    def _afiseaza_optiuni(self, optiuni):
        self._curata_optiuni()
        for opt in optiuni:
            titlu = tr(opt["cheie"])
            aprox = "  " + tr("bm_opt_approx") if opt["aprox"] else ""
            card = QPushButton()
            card.setObjectName("cardOptiune")
            card.setCheckable(False)
            card.setText(tr("bm_opt_card", titlu=titlu, model=opt["model_nume"],
                            imgsz=opt["imgsz"], fps=opt["fps"]) + aprox)
            card.setToolTip(tr("bm_opt_apply_tip"))
            card.clicked.connect(lambda _checked, o=opt: self._aplica_optiune(o))
            self.zona_optiuni.addWidget(card)
            self._carduri_optiuni.append(card)

    def _aplica_optiune(self, opt):
        """Aplica configuratia aleasa: model + rezolutie. Propaga modelul si salveaza."""
        self.config["imgsz"] = opt["imgsz"]
        if self.fereastra_parinte:
            self.fereastra_parinte._propagare_model(opt["model_path"])
            # Aliniem combo-urile de rezolutie din barele laterale la noul imgsz
            self.fereastra_parinte.panou_video.bara.reincarca_din_config()
            self.fereastra_parinte.panou_rtsp.bara.reincarca_din_config()
        self.label_model_activ.setText(tr("bm_active_prefix", nume=opt["model_nume"]))
        self._actualizeaza_status(
            tr("bm_applied_cfg", model=opt["model_nume"], imgsz=opt["imgsz"], fps=opt["fps"])
        )

    # ------------------------------------------------------------------ #
    # Utilitare
    # ------------------------------------------------------------------ #

    def _detecteaza_hardware(self):
        try:
            import torch
            import platform

            if torch.cuda.is_available():
                gpu = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                self.card_gpu._lbl_valoare.setText(gpu)
                self.card_vram._lbl_valoare.setText(f"{vram:.1f} GB")
            else:
                self.card_gpu._lbl_valoare.setText(tr("bm_no_gpu"))
                self.card_vram._lbl_valoare.setText("N/A")

            self.card_cpu._lbl_valoare.setText(platform.processor() or "N/A")

            try:
                import psutil
                ram = psutil.virtual_memory().total / (1024 ** 3)
                self.card_ram._lbl_valoare.setText(f"{ram:.1f} GB")
            except ImportError:
                self.card_ram._lbl_valoare.setText(tr("bm_psutil_missing"))

        except Exception as e:
            self.card_gpu._lbl_valoare.setText(tr("bm_hw_error", err=e))

    def reincarca_din_config(self):
        """Re-scaneaza folderul de modele cand panoul devine vizibil."""
        self._populeaza_carduri_model()

    def _actualizeaza_status(self, mesaj):
        if self.fereastra_parinte:
            self.fereastra_parinte.statusBar().showMessage(mesaj, 5000)
