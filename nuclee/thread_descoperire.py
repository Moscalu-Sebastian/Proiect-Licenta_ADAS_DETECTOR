"""
Thread de auto-descoperire camera pe reteaua WiFi curenta.
Gaseste gateway-ul retelei si incearca URL-uri de stream cunoscute pentru dashcam-uri.
"""

import re
import socket
import subprocess
import threading
import cv2
from PyQt6.QtCore import QThread, pyqtSignal

from nuclee.traduceri import tr


# URL-uri de stream incercate in ordine de probabilitate
# {ip} este inlocuit cu IP-ul gateway-ului detectat
URLS_CANDIDAT = [
    # Dashcam Novatek (BlueLens): stream live HTTP pe port 8192
    "http://{ip}:8192",
    # RTSP standard
    "rtsp://{ip}/stream",
    "rtsp://{ip}/live",
    "rtsp://{ip}/video",
    "rtsp://{ip}:554/stream",
    "rtsp://{ip}:554/live",
    "rtsp://{ip}:554/video",
    # Dashcam-uri Ambarella (BlueLens, Viofo, Thinkware, etc.)
    "rtsp://{ip}/stream0",
    "rtsp://{ip}/live/ch00_0",
    "rtsp://{ip}:8554/stream",
    # MJPEG over HTTP (unele dashcam-uri mai vechi)
    "http://{ip}/video",
    "http://{ip}:8080/video",
    "http://{ip}/mjpeg",
    "http://{ip}:80/mjpeg.cgi",
    # Novatek / Rockchip
    "rtsp://{ip}:554/0",
    "rtsp://{ip}/ch0",
    "rtsp://{ip}/Streaming/Channels/101",
]

TIMEOUT_PORT  = 1.5   # secunde pentru TCP check
TIMEOUT_OPEN  = 3.0   # secunde pentru cv2.VideoCapture


def _get_gateway_ip():
    """Detecteaza IP-ul gateway-ului pe reteaua WiFi activa."""
    try:
        result = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, timeout=5
        )
        matches = re.findall(
            r"Default Gateway[.\s]+:\s+(\d+\.\d+\.\d+\.\d+)",
            result.stdout
        )
        for gw in matches:
            if not gw.startswith("0.") and gw != "0.0.0.0":
                return gw
    except Exception:
        pass
    return None


def _port_deschis(ip, port, timeout=TIMEOUT_PORT):
    """Verifica rapid daca un port TCP este deschis."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        rezultat = s.connect_ex((ip, port))
        s.close()
        return rezultat == 0
    except Exception:
        return False


def _testeaza_url_stream(url, timeout_s=TIMEOUT_OPEN):
    """
    Incearca sa deschida un stream video la URL-ul dat.
    Ruleaza in thread separat ca sa putem aplica un timeout real.
    """
    gasit = [False]
    cap_ref = [None]

    def _incearca():
        try:
            cap = cv2.VideoCapture(url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    gasit[0] = True
                    cap_ref[0] = cap
                    return
            cap.release()
        except Exception:
            pass

    t = threading.Thread(target=_incearca, daemon=True)
    t.start()
    t.join(timeout=timeout_s)

    if gasit[0]:
        if cap_ref[0]:
            cap_ref[0].release()
        return True
    return False


class ThreadDescoperire(QThread):
    """
    Scaneaza reteaua curenta pentru o camera dashcam.
    Emite semnal_gasit(url) cand gaseste un stream valid.
    """

    semnal_progres = pyqtSignal(str)   # mesaj de status pentru UI
    semnal_gasit   = pyqtSignal(str)   # URL-ul stream-ului descoperit
    semnal_esuat   = pyqtSignal(str)   # motiv esec

    def run(self):
        self.semnal_progres.emit(tr("disc_gateway"))

        ip = _get_gateway_ip()
        if not ip:
            self.semnal_esuat.emit(tr("disc_no_gateway"))
            return

        self.semnal_progres.emit(tr("disc_found_ip", ip=ip))

        # Verificam ce porturi sunt deschise (mai rapid decat sa incercam toate URL-urile)
        porturi_deschise = []
        for port in [80, 554, 8080, 8554, 7878, 8192]:
            if _port_deschis(ip, port):
                porturi_deschise.append(port)

        if not porturi_deschise:
            self.semnal_esuat.emit(tr("disc_no_ports", ip=ip))
            return

        self.semnal_progres.emit(tr("disc_active_ports", ip=ip, porturi=porturi_deschise))

        # Filtram URL-urile candidat in functie de porturile deschise
        urls_de_testat = []
        for url_tmpl in URLS_CANDIDAT:
            url = url_tmpl.format(ip=ip)
            # Extragem portul din URL
            port_url = 554 if url.startswith("rtsp://") else 80
            if ":8080" in url:
                port_url = 8080
            elif ":8554" in url:
                port_url = 8554
            elif ":7878" in url:
                port_url = 7878
            elif ":8192" in url:
                port_url = 8192
            if port_url in porturi_deschise:
                urls_de_testat.append(url)

        if not urls_de_testat:
            # Daca filtrarea a eliminat totul, incercam oricum primele 6
            urls_de_testat = [u.format(ip=ip) for u in URLS_CANDIDAT[:6]]

        for i, url in enumerate(urls_de_testat):
            self.semnal_progres.emit(tr("disc_testing", i=i + 1, n=len(urls_de_testat), url=url))
            if _testeaza_url_stream(url):
                self.semnal_gasit.emit(url)
                return

        self.semnal_esuat.emit(
            tr("disc_no_url", ip=ip, porturi=porturi_deschise)
        )
