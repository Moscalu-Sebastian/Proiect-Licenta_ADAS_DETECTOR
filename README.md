# ADAS Detector

Aplicatie desktop (PyQt6) pentru detectie ADAS in trafic, bazata pe modele YOLO.
Ruleaza detectie pe fisiere video sau pe stream live de la o camera de bord (dashcam),
cu tracking, clasificare de semne in doua etape, benchmark de hardware si interfata
in engleza/romana.

## Functii

- **Mod Video** - incarcare fisier, redare cu play/pauza/seek/viteza, detectie cadru cu cadru
- **Mod RTSP/Dashcam** - conectare la stream-ul camerei (auto-descoperire sau URL manual)
- **Tracking** - ID stabil per obiect, cu anti-flicker (coasting)
- **Clasificare semne (two-stage)** - detectorul gaseste semnul, un clasificator spune ce semn e
- **Praguri per clasa** - optimizare automata Best-F1 + reglaj manual
- **Benchmark** - masoara FPS-ul real per model/rezolutie si recomanda setari
- **Interfata EN/RO** + tema dark

## Cerinte

- Python 3.10+
- Pachetele din `requirements.txt`
- PyTorch cu suportul CUDA potrivit placii video (pentru rulare pe GPU);
  vezi https://pytorch.org pentru comanda de instalare corecta

## Instalare si rulare

```bash
python -m venv venv
venv\Scripts\activate        # Windows  (sau: source venv/bin/activate)
pip install -r requirements.txt

python main.py
```

## Structura

```
main.py                 punct de intrare
fereastra_principala.py fereastra principala + navigare
nuclee/                 logica: thread video, clasificare semne, baza de date, optimizare praguri, traduceri
panouri/                interfata: video, RTSP, benchmark, setari, bara de control
modele/                 modele YOLO (.pt): detectoare + clasificator de semne
stil/                   tema (QSS)
```

Setarile si istoricul se salveaza local in `adas.db` (creat automat la prima rulare).
