"""
Sistem minimal de traduceri (i18n) pentru aplicatia ADAS Detector.

Limba implicita este ENGLEZA; comutabila pe Romana din Setari (aplicat la repornire).
Textele se construiesc o singura data la pornire, cu limba curenta. tr(cheie, **kwargs)
intoarce textul tradus (sau cheia daca lipseste); suporta template-uri cu .format().
"""

LIMBI_DISPONIBILE = ("en", "ro")
_ETICHETE_LIMBA = {"en": "English", "ro": "Romana"}

_LIMBA = "en"   # implicit: engleza


def seteaza_limba(cod):
    """Seteaza limba globala. Accepta 'en' sau 'ro'; orice altceva -> 'en'."""
    global _LIMBA
    _LIMBA = cod if cod in LIMBI_DISPONIBILE else "en"


def limba_curenta():
    return _LIMBA


def eticheta_limba(cod):
    """Numele lizibil al unei limbi (pentru selectorul din Setari)."""
    return _ETICHETE_LIMBA.get(cod, cod)


def tr(cheie, **kwargs):
    """Returneaza textul tradus pentru cheia data, in limba curenta.
    Daca textul contine campuri {nume}, le completeaza din kwargs."""
    intrare = _TRADUCERI.get(cheie)
    if intrare is None:
        return cheie
    text = intrare.get(_LIMBA) or intrare.get("en") or cheie
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def tr_clasa(nume_en):
    """Traduce numele unei clase BDD100K (ex. 'car' -> 'Masina' in RO).
    Daca nu exista traducere, intoarce numele original."""
    intrare = _CLASE.get(nume_en)
    if intrare is None:
        return nume_en
    return intrare.get(_LIMBA) or intrare.get("en") or nume_en


# --------------------------------------------------------------------------- #
# Numele claselor BDD100K (folosite si in checkbox-uri si in lista de detectii)
# --------------------------------------------------------------------------- #
_CLASE = {
    "pedestrian":    {"en": "pedestrian",    "ro": "pieton"},
    "rider":         {"en": "rider",         "ro": "conducator (2 roti)"},
    "car":           {"en": "car",           "ro": "masina"},
    "truck":         {"en": "truck",         "ro": "camion"},
    "bus":           {"en": "bus",           "ro": "autobuz"},
    "train":         {"en": "train",         "ro": "tren"},
    "motorcycle":    {"en": "motorcycle",    "ro": "motocicleta"},
    "bicycle":       {"en": "bicycle",       "ro": "bicicleta"},
    "traffic light": {"en": "traffic light", "ro": "semafor"},
    "traffic sign":  {"en": "traffic sign",  "ro": "indicator"},
}


# --------------------------------------------------------------------------- #
# Catalog de traduceri. Cheie -> {en, ro}
# --------------------------------------------------------------------------- #
_TRADUCERI = {
    # ---- Fereastra principala: titlu, meniuri ----
    "app_title":            {"en": "ADAS Detector  v1.0", "ro": "ADAS Detector  v1.0"},
    "menu_file":            {"en": "File",            "ro": "Fisier"},
    "menu_open_video":      {"en": "Open Video...",   "ro": "Deschide Video..."},
    "menu_snapshot":        {"en": "Snapshot",        "ro": "Snapshot"},
    "menu_exit":            {"en": "Exit",            "ro": "Iesire"},
    "menu_view":            {"en": "View",            "ro": "Vizualizare"},
    "menu_fullscreen":      {"en": "Fullscreen",      "ro": "Ecran complet"},
    "menu_toggle_sidebar":  {"en": "Show/Hide sidebar", "ro": "Arata/Ascunde sidebar"},
    "menu_settings":        {"en": "Settings",        "ro": "Setari"},
    "menu_model":           {"en": "Model",           "ro": "Model"},
    "menu_load_model":      {"en": "Load model (.pt)...", "ro": "Incarca model (.pt)..."},
    "menu_run_benchmark":   {"en": "Run Benchmark",   "ro": "Ruleaza Benchmark"},
    "menu_help":            {"en": "Help",            "ro": "Ajutor"},
    "menu_about":           {"en": "About ADAS Detector...", "ro": "Despre ADAS Detector..."},

    # ---- Sidebar navigare ----
    "nav_video":            {"en": "Video Mode",  "ro": "Mod Video"},
    "nav_rtsp":             {"en": "RTSP Mode",   "ro": "Mod RTSP"},
    "nav_benchmark":        {"en": "Benchmark",   "ro": "Benchmark"},
    "nav_video_tip":        {"en": "Detection on a local video file",          "ro": "Detectie pe fisier video local"},
    "nav_rtsp_tip":         {"en": "Real-time dashcam or camera stream",       "ro": "Stream dashcam sau camera in timp real"},
    "nav_benchmark_tip":    {"en": "Test the model's speed on your hardware",  "ro": "Testeaza viteza modelului pe hardware-ul tau"},
    "logo_subtitle":        {"en": "Detector  -  v1.0", "ro": "Detector  -  v1.0"},

    # ---- Status bar ----
    "status_ready":         {"en": "Ready.  Load a model from Benchmark or directly from Video Mode.",
                             "ro": "Gata.  Incarca un model din Benchmark sau direct din Mod Video."},
    "status_model_none":    {"en": "Model: none active", "ro": "Model: niciun model activ"},
    "status_model_label":   {"en": "Model: {nume}",      "ro": "Model: {nume}"},
    "status_model_propagated": {"en": "Model propagated to all panels: {nume}",
                                "ro": "Model propagat catre toate panourile: {nume}"},
    "status_model_error":   {"en": "Error loading model: {err}", "ro": "Eroare la incarcarea modelului: {err}"},

    # ---- Dialog About ----
    "about_title":          {"en": "About ADAS Detector", "ro": "Despre ADAS Detector"},
    "about_body":           {"en": "<h3>ADAS Detector v1.0</h3>"
                                   "<p>Real-time detection of objects of interest in video "
                                   "sequences for driver assistance.</p>"
                                   "<p><b>Author:</b> Sebastian Moscalu<br>"
                                   "<b>Supervisor:</b> conf. dr. ing. Paul-Corneliu Herghelegiu<br>"
                                   "<b>Institution:</b> Gheorghe Asachi Technical University, Iasi<br>"
                                   "<b>Year:</b> 2026</p>"
                                   "<p><b>Model:</b> YOLO26n trained on BDD100K<br>"
                                   "<b>Framework:</b> PyTorch + Ultralytics + PyQt6</p>",
                             "ro": "<h3>ADAS Detector v1.0</h3>"
                                   "<p>Sistem de detectie in timp real a elementelor de interes "
                                   "in secvente video pentru asistenta conducerii auto.</p>"
                                   "<p><b>Autor:</b> Sebastian Moscalu<br>"
                                   "<b>Coordonator:</b> conf. dr. ing. Paul-Corneliu Herghelegiu<br>"
                                   "<b>Institutie:</b> Universitatea Tehnica Gheorghe Asachi, Iasi<br>"
                                   "<b>An:</b> 2026</p>"
                                   "<p><b>Model:</b> YOLO26n antrenat pe BDD100K<br>"
                                   "<b>Framework:</b> PyTorch + Ultralytics + PyQt6</p>"},

    # ---- Dialoguri de fisiere ----
    "dlg_select_model":     {"en": "Select YOLO model (.pt)", "ro": "Selecteaza model YOLO (.pt)"},
    "filter_model":         {"en": "PyTorch Model (*.pt);;All files (*)", "ro": "Model PyTorch (*.pt);;Toate fisierele (*)"},
    "dlg_open_video":       {"en": "Open video file", "ro": "Deschide fisier video"},
    "filter_video":         {"en": "Video (*.mp4 *.avi *.mkv *.mov *.wmv *.ts *.flv);;All files (*)",
                             "ro": "Video (*.mp4 *.avi *.mkv *.mov *.wmv *.ts *.flv);;Toate fisierele (*)"},
    "dlg_select_snap_folder": {"en": "Select the snapshots folder", "ro": "Selecteaza folderul pentru snapshot-uri"},

    # ---- Panou Video: toolbar ----
    "video_open":           {"en": "Open",        "ro": "Deschide"},
    "video_open_tip":       {"en": "Open a video file (Ctrl+O)", "ro": "Deschide un fisier video (Ctrl+O)"},
    "video_model_label":    {"en": "Model:",      "ro": "Model:"},
    "video_no_model":       {"en": "- No model -", "ro": "- Fara model -"},
    "video_model_combo_tip": {"en": "Switch between loaded models", "ro": "Comuta intre modelele incarcate"},
    "video_load_pt":        {"en": "Load .pt",    "ro": "Incarca .pt"},
    "video_load_pt_tip":    {"en": "Load a YOLO model from disk", "ro": "Incarca un model YOLO de pe disc"},
    "video_no_file":        {"en": "No file selected", "ro": "Niciun fisier selectat"},

    # ---- Panou Video: handle / vertical ----
    "panel_toggle_tip":     {"en": "Hide / show the right panel", "ro": "Ascunde / arata panoul din dreapta"},
    "vertical_settings":    {"en": "S\nE\nT\nT\nI\nN\nG\nS", "ro": "S\nE\nT\nA\nR\nI"},

    # ---- Panou Video: display ----
    "video_placeholder":    {"en": "No video loaded.\nPress  Open  to begin.",
                             "ro": "Niciun video incarcat.\nApasa  Deschide  pentru a incepe."},
    "video_press_play":     {"en": "Press Play to resume.", "ro": "Apasa Play pentru a relua."},
    "video_low_fps_banner": {"en": "  ⚠  Low FPS ({fps:.0f}). Click to find optimal settings (Benchmark)  →",
                             "ro": "  ⚠  FPS scazut ({fps:.0f}). Apasa pentru a gasi setarile optime (Benchmark)  →"},
    "video_low_fps_tip":    {"en": "Open the Smart Benchmark to pick a faster model/resolution",
                             "ro": "Deschide Benchmark-ul inteligent pentru un model/rezolutie mai rapide"},

    # ---- Panou Video: control redare ----
    "play_back10_tip":      {"en": "Rewind 10 seconds",  "ro": "Deruleaza inapoi 10 secunde"},
    "play_toggle_tip":      {"en": "Play / Pause (or click the video)", "ro": "Play / Pauza (sau click pe video)"},
    "play_stop_tip":        {"en": "Stop playback",      "ro": "Opreste redarea"},
    "play_fwd10_tip":       {"en": "Forward 10 seconds", "ro": "Deruleaza inainte 10 secunde"},
    "play_speed_label":     {"en": "Speed:",             "ro": "Viteza:"},
    "play_speed_tip":       {"en": "Playback speed",     "ro": "Viteza de redare"},
    "video_state_idle":     {"en": "Idle",       "ro": "Inactiv"},
    "video_state_loaded":   {"en": "Loaded - press Play", "ro": "Incarcat - apasa Play"},
    "video_state_paused":   {"en": "Paused",     "ro": "Pauza"},
    "video_state_running":  {"en": "Running...", "ro": "Ruleaza..."},
    "video_state_stopped":  {"en": "Stopped",    "ro": "Oprit"},
    "video_state_finished": {"en": "Finished",   "ro": "Finalizat"},
    "video_state_error":    {"en": "Error",      "ro": "Eroare"},

    # ---- Panou Video: statusuri ----
    "status_file_gone":     {"en": "File no longer exists: {cale}", "ro": "Fisierul nu mai exista: {cale}"},
    "status_video_loaded":  {"en": "Video loaded: {nume}", "ro": "Video incarcat: {nume}"},
    "status_video_error":   {"en": "Video error: {mesaj}", "ro": "Eroare video: {mesaj}"},
    "status_snapshot_saved": {"en": "Snapshot saved: {cale}", "ro": "Snapshot salvat: {cale}"},

    # ---- Dialog Istoric video ----
    "hist_title":           {"en": "Open Video",   "ro": "Deschide Video"},
    "hist_new_video":       {"en": "  New video...", "ro": "  Video nou..."},
    "hist_header":          {"en": "HISTORY  -  recently played videos", "ro": "ISTORIC  -  ultimele videoclipuri rulate"},
    "hist_note":            {"en": "Double-click = open.   Right-click = remove from history.",
                             "ro": "Dublu-click = deschide.   Click-dreapta = sterge din istoric."},
    "hist_empty":           {"en": "No videos in history yet.", "ro": "Niciun videoclip in istoric inca."},
    "hist_cancel":          {"en": "Cancel",       "ro": "Anuleaza"},
    "hist_delete":          {"en": "Remove from history", "ro": "Sterge din istoric"},
    "hist_tip":             {"en": "{cale}\nLast run: {ultima}   |   runs: {nr}",
                             "ro": "{cale}\nUltima rulare: {ultima}   |   rulari: {nr}"},

    # ---- Bara control laterala: sectiuni ----
    "bar_fps_playback":     {"en": "PLAYBACK FPS",  "ro": "FPS REDARE"},
    "bar_fps_inference":    {"en": "INFERENCE FPS", "ro": "FPS INFERENTA"},
    "bar_fps_stream":       {"en": "STREAM FPS",    "ro": "FPS STREAM"},
    "bar_fps_unit":         {"en": "FRAMES / SECOND", "ro": "CADRE / SECUNDA"},
    "bar_alerts":           {"en": "ADAS ALERTS",   "ro": "ALERTE ADAS"},
    "bar_active_det":       {"en": "ACTIVE DETECTIONS", "ro": "DETECTII ACTIVE"},
    "bar_det_params":       {"en": "DETECTION PARAMETERS", "ro": "PARAMETRI DETECTIE"},
    "bar_det_classes":      {"en": "DETECTION CLASSES", "ro": "CLASE DETECTIE"},

    # ---- Bara control: parametri ----
    "param_confidence":     {"en": "Confidence", "ro": "Confidence"},
    "param_confidence_tip": {"en": "Minimum confidence threshold for a detection",
                             "ro": "Prag minim de incredere pentru o detectie"},
    "param_iou":            {"en": "IoU (NMS)",  "ro": "IoU (NMS)"},
    "param_iou_tip":        {"en": "Overlap threshold for removing duplicate boxes",
                             "ro": "Prag de suprapunere pentru eliminarea cutiilor duplicate"},
    "param_resolution":     {"en": "Resolution", "ro": "Rezolutie"},
    "param_resolution_tip": {"en": "Resolution at which the model runs.\nHigher = more accurate on small objects (signs), but slower.",
                             "ro": "Rezolutia la care ruleaza modelul.\nMai mare = mai precis pe obiecte mici (semne), dar mai lent."},

    # ---- Bara control: actiuni ----
    "bar_snapshot":         {"en": "  Snapshot", "ro": "  Snapshot"},
    "bar_snapshot_tip":     {"en": "Save the current frame as a PNG image", "ro": "Salveaza cadrul curent ca imagine PNG"},
    "bar_adv_settings":     {"en": "  Advanced settings", "ro": "  Setari avansate"},
    "bar_adv_settings_tip": {"en": "Open the advanced settings page (display, RTSP, snapshot)",
                             "ro": "Deschide pagina de setari avansate (afisare, RTSP, snapshot)"},

    # ---- Bara control: alerte ----
    "alert_none":           {"en": "No active alert", "ro": "Nicio alerta activa"},
    "alert_pedestrian":     {"en": "Pedestrian detected in zone!", "ro": "Pieton detectat in zona!"},
    "alert_sign":           {"en": "Traffic sign detected", "ro": "Semn de circulatie detectat"},
    "alert_light":          {"en": "Traffic light in view", "ro": "Semafor in camp vizual"},

    # ---- Panou RTSP ----
    "rtsp_placeholder":     {"en": "Not connected.\nEnter the RTSP URL and press Connect.",
                             "ro": "Neconectat.\nIntroduci URL-ul RTSP si apasa Conecteaza."},
    "rtsp_autodetect":      {"en": "  Detect Camera Automatically", "ro": "  Detecteaza Camera Automat"},
    "rtsp_autodetect_tip":  {"en": "Connect to the camera's hotspot, then press this button.\nThe app finds the stream automatically without entering an IP.",
                             "ro": "Conecteaza-te la hotspot-ul camerei, apoi apasa acest buton.\nAplicatia gaseste automat stream-ul fara sa introduci IP."},
    "rtsp_scan_hint":       {"en": "Connect to the camera's WiFi, then press 'Detect'.",
                             "ro": "Conecteaza-te la WiFi-ul camerei, apoi apasa 'Detecteaza'."},
    "rtsp_url_manual":      {"en": "Manual URL:", "ro": "URL manual:"},
    "rtsp_url_placeholder": {"en": "auto-filled after detection, or enter manually",
                             "ro": "completat automat dupa detectare, sau introdu manual"},
    "rtsp_connect":         {"en": "Connect",    "ro": "Conecteaza"},
    "rtsp_disconnect":      {"en": "Disconnect", "ro": "Deconecteaza"},
    "rtsp_disconnected":    {"en": "DISCONNECTED", "ro": "DECONECTAT"},
    "rtsp_scanning":        {"en": "SCANNING...",  "ro": "SCANARE..."},
    "rtsp_connecting":      {"en": "CONNECTING...", "ro": "CONECTARE..."},
    "rtsp_connected":       {"en": "CONNECTED",  "ro": "CONECTAT"},
    "rtsp_indic_error":     {"en": "ERROR",      "ro": "EROARE"},
    "rtsp_camera_found":    {"en": "Camera found: {url}", "ro": "Camera gasita: {url}"},
    "rtsp_detect_failed":   {"en": "Detection failed - try a manual URL", "ro": "Detectare esuata - incearca URL manual"},
    "rtsp_disconnected_msg": {"en": "Disconnected.", "ro": "Deconectat."},
    "rtsp_conn_error":      {"en": "Connection error:\n{mesaj}", "ro": "Eroare conectare:\n{mesaj}"},
    "status_rtsp_invalid":  {"en": "Enter a valid RTSP URL.", "ro": "Introdu un URL RTSP valid."},
    "status_rtsp_detected": {"en": "Camera detected: {url}", "ro": "Camera detectata: {url}"},
    "status_rtsp_detect_failed": {"en": "Detection failed: {motiv}", "ro": "Detectare esuata: {motiv}"},
    "status_rtsp_connecting": {"en": "Connecting to: {url}", "ro": "Conectare la: {url}"},
    "status_rtsp_error":    {"en": "RTSP error: {mesaj}", "ro": "Eroare RTSP: {mesaj}"},

    # ---- Panou Benchmark ----
    "bm_title":             {"en": "Hardware & Model", "ro": "Hardware & Model"},
    "bm_subtitle":          {"en": "System info, YOLO model selection and real FPS measurement",
                             "ro": "Informatii sistem, selectie model YOLO si masurare FPS real"},
    "bm_hw_info":           {"en": "HARDWARE INFO", "ro": "INFORMATII HARDWARE"},
    "bm_detecting":         {"en": "Detecting...", "ro": "Se detecteaza..."},
    "bm_ram_system":        {"en": "System RAM", "ro": "RAM sistem"},
    "bm_no_gpu":            {"en": "No CUDA GPU", "ro": "Fara GPU CUDA"},
    "bm_psutil_missing":    {"en": "psutil missing", "ro": "psutil neinst."},
    "bm_hw_error":          {"en": "Error: {err}", "ro": "Eroare: {err}"},
    "bm_model_select":      {"en": "MODEL SELECTION", "ro": "SELECTIE MODEL"},
    "bm_model_sub":         {"en": "Pick a model from the modele/ folder or load a custom one (.pt):",
                             "ro": "Alege un model din folderul modele/ sau incarca unul custom (.pt):"},
    "bm_load_custom":       {"en": "  Load custom model (.pt)...", "ro": "  Incarca model custom (.pt)..."},
    "bm_no_models":         {"en": "No model in the modele/ folder. Use 'Load custom model'.",
                             "ro": "Niciun model in folderul modele/. Foloseste 'Incarca model custom'."},
    "bm_apply_model":       {"en": "  Apply selected model", "ro": "  Aplica model selectat"},
    "bm_model_none":        {"en": "No active model", "ro": "Niciun model activ"},
    "bm_custom_prefix":     {"en": "Custom: {nume}", "ro": "Custom: {nume}"},
    "bm_active_prefix":     {"en": "Active: {nume}", "ro": "Activ: {nume}"},
    "bm_tag_nano":          {"en": "Nano - fastest", "ro": "Nano - cel mai rapid"},
    "bm_tag_small":         {"en": "Small - balanced", "ro": "Small - echilibrat"},
    "bm_tag_medium":        {"en": "Medium - most accurate", "ro": "Medium - cel mai precis"},
    "bm_tag_generic":       {"en": "YOLO model", "ro": "Model YOLO"},
    "bm_section":           {"en": "SMART BENCHMARK", "ro": "BENCHMARK INTELIGENT"},
    "bm_section_sub":       {"en": "Automatically tests model x resolution combinations (starting with nano @ 1280px) "
                                   "and suggests 4 ready-to-apply configurations, from best quality to fastest.",
                             "ro": "Testeaza automat combinatii model x rezolutie (incepand cu nano @ 1280px) si "
                                   "propune 4 configuratii gata de aplicat, de la calitate maxima la cel mai rapid."},
    "bm_run":               {"en": "  Find optimal settings", "ro": "  Gaseste setarile optime"},
    "bm_smart_start":       {"en": "Starting with nano @ 1280px...", "ro": "Pornim cu nano @ 1280px..."},
    "bm_smart_testing":     {"en": "Testing {config}...", "ro": "Se testeaza {config}..."},
    "bm_smart_done":        {"en": "Done — pick a configuration to apply:", "ro": "Gata — alege o configuratie de aplicat:"},
    "bm_smart_empty":       {"en": "No result. Check that a detector model exists in modele/.",
                             "ro": "Niciun rezultat. Verifica daca exista un model detector in modele/."},
    "bm_opt_quality":       {"en": "Max quality", "ro": "Calitate maxima"},
    "bm_opt_balanced":      {"en": "Balanced", "ro": "Echilibrat"},
    "bm_opt_fluid":         {"en": "Smooth", "ro": "Fluid"},
    "bm_opt_fast":          {"en": "Very smooth", "ro": "Foarte fluid"},
    "bm_opt_card":          {"en": "{titlu}\n\n{model}\n{imgsz}px  ·  {fps:.0f} FPS",
                             "ro": "{titlu}\n\n{model}\n{imgsz}px  ·  {fps:.0f} FPS"},
    "bm_opt_approx":        {"en": "(closest)", "ro": "(cel mai apropiat)"},
    "bm_opt_apply_tip":     {"en": "Apply this model + resolution", "ro": "Aplica acest model + rezolutie"},
    "bm_applied_cfg":       {"en": "Applied: {model} @ {imgsz}px  (~{fps:.0f} FPS)",
                             "ro": "Aplicat: {model} @ {imgsz}px  (~{fps:.0f} FPS)"},
    "bm_running_at":        {"en": "Running benchmark at {imgsz}px...", "ro": "Se ruleaza benchmark la {imgsz}px..."},
    "bm_in_progress":       {"en": "Benchmark in progress...", "ro": "Benchmark in desfasurare..."},
    "bm_result":            {"en": "Result: {fps:.1f} FPS  ({perf})", "ro": "Rezultat: {fps:.1f} FPS  ({perf})"},
    "bm_done":              {"en": "Benchmark done: {fps:.1f} FPS", "ro": "Benchmark finalizat: {fps:.1f} FPS"},
    "bm_error":             {"en": "Error: {mesaj}", "ro": "Eroare: {mesaj}"},
    "bm_perf_excellent":    {"en": "Excellent", "ro": "Excelent"},
    "bm_perf_good":         {"en": "Good",       "ro": "Bun"},
    "bm_perf_ok":           {"en": "Acceptable", "ro": "Acceptabil"},
    "bm_select_valid":      {"en": "Select or load a valid model.", "ro": "Selecteaza sau incarca un model valid."},
    "bm_no_model_bench":    {"en": "No model selected for benchmark.", "ro": "Niciun model selectat pentru benchmark."},
    "bm_open_source_error": {"en": "Cannot open the video source for benchmark.", "ro": "Nu pot deschide sursa video pentru benchmark."},
    "bm_model_applied":     {"en": "Model applied: {nume}", "ro": "Model aplicat: {nume}"},

    # ---- Panou Setari ----
    "set_back":             {"en": "  <-  Back", "ro": "  <-  Inapoi"},
    "set_back_tip":         {"en": "Back to the previous panel (Video / RTSP / Benchmark)",
                             "ro": "Inapoi la panoul anterior (Video / RTSP / Benchmark)"},
    "set_title":            {"en": "Settings", "ro": "Setari"},
    "set_subtitle":         {"en": "Display, connectivity and snapshot. Confidence, IoU, resolution and "
                                   "classes are tuned live from the Video / RTSP panel.",
                             "ro": "Afisare, conectivitate si snapshot. Confidence, IoU, rezolutia "
                                   "si clasele se regleaza live din panoul Video / RTSP."},
    "set_grp_language":     {"en": "Language", "ro": "Limba"},
    "set_language_label":   {"en": "Interface language:", "ro": "Limba interfetei:"},
    "set_language_hint":    {"en": "Changing the language takes effect after restarting the application.",
                             "ro": "Schimbarea limbii se aplica dupa repornirea aplicatiei."},
    "set_grp_display":      {"en": "Display on detection boxes", "ro": "Afisare pe cutiile de detectie"},
    "set_show_labels":      {"en": "Show the class label on the box", "ro": "Afiseaza eticheta clasei pe cutie"},
    "set_show_conf":        {"en": "Show the confidence value on the box", "ro": "Afiseaza valoarea de incredere pe cutie"},
    "set_show_tracks":      {"en": "Show tracking IDs (ByteTrack)", "ro": "Afiseaza ID-uri de tracking (ByteTrack)"},
    "set_tracks_desc":      {"en": "Tracking (ByteTrack) reduces detection flicker between frames, but costs a little more.",
                             "ro": "Tracking-ul (ByteTrack) reduce flicker-ul detectiilor intre cadre, dar consuma putin mai mult."},
    "set_grp_classifier":   {"en": "Sign classification (two-stage)", "ro": "Clasificare semne (two-stage)"},
    "set_enable_classifier": {"en": "Enable the sign classifier (MTSD)", "ro": "Activeaza clasificatorul de semne (MTSD)"},
    "set_classifier_desc":  {"en": "When active, each sign detected by YOLO is classified (Stop, Yield, Limit 50, etc.) "
                                   "and the name appears on the frame and in the detection list. Adds a little latency per sign.",
                             "ro": "Cand e activ, fiecare semn detectat de YOLO e clasificat (Stop, Cedeaza trecerea, "
                                   "Limita 50, etc.) si numele apare pe cadru si in lista de detectii. Adauga putina latenta per semn."},
    "set_grp_rtsp":         {"en": "RTSP Connection", "ro": "Conexiune RTSP"},
    "set_rtsp_url":         {"en": "Default URL:", "ro": "URL implicit:"},
    "set_rtsp_timeout":     {"en": "Connection timeout (s):", "ro": "Timeout conectare (s):"},
    "set_rtsp_hint":        {"en": "Local RTSP simulation with ffmpeg:\n"
                                   "  mediamtx  (terminal 1)\n"
                                   "  ffmpeg -re -stream_loop -1 -i test.mp4 -c:v libx264 -f rtsp rtsp://localhost:8554/dashcam  (terminal 2)",
                             "ro": "Simulare RTSP local cu ffmpeg:\n"
                                   "  mediamtx  (terminal 1)\n"
                                   "  ffmpeg -re -stream_loop -1 -i test.mp4 -c:v libx264 -f rtsp rtsp://localhost:8554/dashcam  (terminal 2)"},
    "set_grp_snapshot":     {"en": "Snapshots", "ro": "Snapshot-uri"},
    "set_snap_folder":      {"en": "Save folder:", "ro": "Folder salvare:"},
    "set_browse":           {"en": "Browse...", "ro": "Browse..."},
    "set_save":             {"en": "  Save settings", "ro": "  Salveaza setarile"},
    "set_reset":            {"en": "  Reset to defaults", "ro": "  Reseteaza la implicit"},
    "set_unsaved":          {"en": "*  unsaved changes", "ro": "*  modificari nesalvate"},
    "set_saved":            {"en": "Settings saved.", "ro": "Setarile au fost salvate."},
    "set_saved_status":     {"en": "Settings saved to the database", "ro": "Setarile salvate in baza de date"},
    "set_defaults_note":    {"en": "*  default values (press Save)", "ro": "*  valori implicite (apasa Save)"},

    # ---- Auto-descoperire camera (thread_descoperire) ----
    "disc_gateway":         {"en": "Detecting the WiFi network gateway...", "ro": "Detectez gateway-ul retelei WiFi..."},
    "disc_no_gateway":      {"en": "Could not detect the gateway.\nMake sure you are connected to the camera's hotspot.",
                             "ro": "Nu am putut detecta gateway-ul.\nAsigura-te ca esti conectat la hotspot-ul camerei."},
    "disc_found_ip":        {"en": "Camera found at IP: {ip}  -  Checking ports...",
                             "ro": "Camera gasita la IP: {ip}  -  Verific porturi..."},
    "disc_no_ports":        {"en": "Detected IP: {ip}\nNo streaming port responds (80, 554, 8080, 8554, 7878).\n"
                                   "The camera may use an unknown protocol. Try manually from the Viidure app.",
                             "ro": "IP detectat: {ip}\nNiciun port de streaming nu raspunde (80, 554, 8080, 8554, 7878).\n"
                                   "Camera poate folosi un protocol necunoscut. Incearca manual din aplicatia Viidure."},
    "disc_active_ports":    {"en": "Active ports at {ip}: {porturi}  -  Searching for the stream...",
                             "ro": "Porturi active la {ip}: {porturi}  -  Caut stream-ul..."},
    "disc_testing":         {"en": "Testing ({i}/{n}): {url}", "ro": "Testez ({i}/{n}): {url}"},
    "disc_no_url":          {"en": "Detected IP: {ip}  -  Active ports: {porturi}\nNo standard URL worked.\n"
                                   "The camera may use a proprietary Viidure protocol.\n"
                                   "Try manually: connect with Wireshark active on the WiFi interface\n"
                                   "and see which URL the Viidure app requests.",
                             "ro": "IP detectat: {ip}  -  Porturi active: {porturi}\nNiciun URL standard nu a functionat.\n"
                                   "Camera poate folosi un protocol proprietar Viidure.\n"
                                   "Incearca manual: conecteaza-te cu Wireshark activ pe interfata WiFi\n"
                                   "si vezi ce URL cere aplicatia Viidure."},

    # ---- Optimizare praguri per clasa ----
    "opt_prompt_title":     {"en": "Optimize per-class thresholds?", "ro": "Optimizezi pragurile per clasa?"},
    "opt_prompt_body":      {"en": "A new model was loaded:\n{nume}\n\nDo you want to automatically optimize the per-class "
                                   "confidence thresholds now (runs a validation), or do it later from Advanced Settings?",
                             "ro": "A fost incarcat un model nou:\n{nume}\n\nVrei sa optimizezi automat acum pragurile de "
                                   "incredere per clasa (ruleaza o validare), sau mai tarziu din Setari avansate?"},
    "opt_btn_now":          {"en": "Optimize now (~1 min)", "ro": "Optimizeaza acum (~1 min)"},
    "opt_btn_later":        {"en": "Later", "ro": "Mai tarziu"},
    "optim_loading":        {"en": "Loading model for optimization...", "ro": "Incarc modelul pentru optimizare..."},
    "optim_running":        {"en": "Optimizing per-class thresholds (validation running, please wait)...",
                             "ro": "Optimizare praguri per clasa (validare in curs, asteapta)..."},
    "opt_done":             {"en": "Per-class thresholds optimized: {n} classes.", "ro": "Praguri per clasa optimizate: {n} clase."},
    "opt_error":            {"en": "Optimization error: {err}", "ro": "Eroare optimizare: {err}"},
    "opt_no_dataset":       {"en": "Validation set not found - cannot auto-optimize. Set thresholds manually in Advanced Settings.",
                             "ro": "Setul de validare nu a fost gasit - nu pot optimiza automat. Seteaza pragurile manual in Setari avansate."},
    "opt_busy":             {"en": "An optimization is already running.", "ro": "O optimizare deja ruleaza."},
    "opt_incompatibil":     {"en": "Auto-optimization unavailable: this model's classes don't match the validation set. Set thresholds manually.",
                             "ro": "Optimizare automata indisponibila: clasele acestui model nu corespund setului de validare. Seteaza pragurile manual."},
    "classifier_no_sign":   {"en": "Disabled: this model has no 'traffic sign' class.",
                             "ro": "Dezactivat: modelul nu are clasa de semn de circulatie."},

    # ---- Setari: praguri per clasa ----
    "set_grp_thresholds":   {"en": "Per-class confidence thresholds", "ro": "Praguri de incredere per clasa"},
    "set_thr_desc":         {"en": "Detections below a class's threshold are discarded. 'Auto-optimize' runs a validation and "
                                   "sets the best-F1 threshold per class. Manual changes apply when you press Save.",
                             "ro": "Detectiile sub pragul unei clase sunt eliminate. 'Optimizeaza auto' ruleaza o validare si "
                                   "seteaza pragul cu cel mai bun F1 per clasa. Modificarile manuale se aplica la Salvare."},
    "set_thr_optimize":     {"en": "  Auto-optimize thresholds", "ro": "  Optimizeaza pragurile auto"},
    "set_thr_reset":        {"en": "  Reset to global", "ro": "  Reseteaza la global"},
    "set_thr_global_hint":  {"en": "Empty / Reset = each class uses the global confidence from the live panel.",
                             "ro": "Gol / Reset = fiecare clasa foloseste confidence-ul global din panoul live."},
    "set_thr_optimized":    {"en": "Thresholds optimized & saved ({n} classes)",
                             "ro": "Praguri optimizate si salvate ({n} clase)"},
    "set_thr_follows_global": {"en": "This class follows the global confidence (no per-class threshold set).",
                               "ro": "Aceasta clasa urmeaza confidence-ul global (fara prag per-clasa)."},
    "set_thr_reset_class":  {"en": "Reset this class to the global confidence",
                             "ro": "Reseteaza aceasta clasa la confidence-ul global"},

    # ---- Dialog repornire (schimbare limba) ----
    "restart_title":        {"en": "Restart required", "ro": "Repornire necesara"},
    "restart_body":         {"en": "The language change will be applied after restarting the application.\n\n"
                                   "Do you want to restart now?",
                             "ro": "Schimbarea limbii se va aplica dupa repornirea aplicatiei.\n\n"
                                   "Vrei sa repornesti acum?"},
    "restart_now":          {"en": "Restart now", "ro": "Reporneste acum"},
    "restart_later":        {"en": "Later", "ro": "Mai tarziu"},
}
