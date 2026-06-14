"""
Logica de clase a modelului - centralizata, ca aplicatia sa fie AGNOSTICA la dataset.

Tot ce tine de clase (nume, culori, ordine, alerte, clasa de semne) se deriva din
`model.names` (dict {id: nume}) al modelului incarcat, nu din valori hardcodate.
Pana la incarcarea unui model se folosesc clasele BDD100K ca implicit.
"""

# Clasele BDD100K (implicit, pana se incarca un model)
CLASE_BDD = [
    "pedestrian", "rider", "car", "truck", "bus",
    "train", "motorcycle", "bicycle", "traffic light", "traffic sign",
]
NUME_BDD = {i: n for i, n in enumerate(CLASE_BDD)}

# Culori "frumoase" pentru clasele BDD (continuitate vizuala cu raportul)
CULORI_BDD = {
    0: "#EF4444", 1: "#F97316", 2: "#818CF8", 3: "#A78BFA", 4: "#22D3EE",
    5: "#38BDF8", 6: "#F59E0B", 7: "#A3E635", 8: "#34D399", 9: "#6EE7B7",
}

# Paleta de rezerva pentru clase peste cele 10 BDD (orice model custom)
PALETA = [
    "#818CF8", "#A78BFA", "#22D3EE", "#38BDF8", "#F59E0B",
    "#A3E635", "#34D399", "#6EE7B7", "#EF4444", "#F97316",
    "#FB7185", "#C084FC", "#2DD4BF", "#FBBF24", "#4ADE80",
    "#60A5FA", "#E879F9", "#FCA5A5", "#FCD34D", "#5EEAD4",
]


def normalizeaza_names(names):
    """Transforma model.names (dict sau list) intr-un dict {int: str} curat."""
    if names is None:
        return dict(NUME_BDD)
    if isinstance(names, dict):
        return {int(k): str(v) for k, v in names.items()}
    # lista / tuple -> indexam
    return {int(i): str(v) for i, v in enumerate(names)}


def culoare_clasa(cls_id):
    """Culoarea pentru o clasa: BDD daca e in primele 10, altfel din paleta (ciclic)."""
    if cls_id in CULORI_BDD:
        return CULORI_BDD[cls_id]
    return PALETA[int(cls_id) % len(PALETA)]


def gaseste_clasa_semn(names):
    """Returneaza id-ul clasei de 'semn de circulatie' din names, sau None daca nu exista.
    Folosit de clasificatorul two-stage ca sa stie ce sa decupeze."""
    names = normalizeaza_names(names)
    for k, v in names.items():
        n = str(v).strip().lower()
        if "traffic sign" in n or n in ("sign", "signs") or "indicator" in n:
            return int(k)
    return None


def categorie_alerta(nume_clasa):
    """Mapeaza un nume de clasa la o categorie de alerta ADAS (sau None).
    Permite alertele sa mearga si pe modele cu nume diferite, prin potrivire pe nume."""
    n = str(nume_clasa).strip().lower()
    if "pedestrian" in n or "person" in n or "pieton" in n:
        return "pedestrian"
    if "traffic sign" in n or "indicator" in n:
        return "sign"
    if "traffic light" in n or "semafor" in n:
        return "light"
    return None


def clase_compatibile(model_names, ref_names):
    """True daca clasele modelului corespund EXACT (index + nume) cu cele de referinta
    (setul de validare). Necesara ca optimizarea pe baza de validare sa aiba sens."""
    if not model_names or not ref_names:
        return False
    m = normalizeaza_names(model_names)
    r = normalizeaza_names(ref_names)
    if set(m.keys()) != set(r.keys()):
        return False
    for k in r:
        if m.get(k, "").strip().lower() != r[k].strip().lower():
            return False
    return True
