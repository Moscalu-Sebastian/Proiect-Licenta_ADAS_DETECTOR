"""
Punct de intrare - ADAS Detector.
Lansare: python main.py  (din folderul aplicatie/, cu venv activat)
"""

import sys
import os

# Directorul de baza al aplicatiei - functioneaza atat in dev cat si in .exe (PyInstaller)
if getattr(sys, 'frozen', False):
    # Rulam ca .exe bundled (PyInstaller --onedir)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.environ['ADAS_BASE_DIR'] = BASE_DIR

# Adaugam folderul aplicatiei in PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from fereastra_principala import FereastaPrincipala


def main():
    # Support HiDPI / scalare automata
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("ADAS Detector")
    app.setOrganizationName("UTI Iasi")
    app.setApplicationVersion("1.0.0")

    # Incarcam tema dark
    cale_tema = os.path.join(BASE_DIR, "stil", "tema.qss")
    if os.path.exists(cale_tema):
        with open(cale_tema, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    fereastra = FereastaPrincipala()
    fereastra.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
