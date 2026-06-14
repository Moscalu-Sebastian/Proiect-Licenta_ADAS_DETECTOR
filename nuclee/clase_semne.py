"""
Maparea predictiei clasificatorului de semne (etapa a doua, two-stage: YOLO detecteaza
'traffic sign', clasificatorul spune CE semn e) -> nume romanesc afisat.

Suporta DOUA clasificatoare, detectat automat dupa forma numelor din model (model.names):
  - MTSD (Europa/RO): model.names sunt chei-folder ASCII ('stop', 'trecere_pietoni', 'limita_50'...).
    Se mapeaza direct prin NUME_RO_MTSD.
  - GTSRB (vechi): model.names sunt ID-uri numerice ca string ('0'..'42'). Se mapeaza prin DICT_GTSRB.

Asa aplicatia merge cu oricare model pus in modele/clasificator_semne.pt, fara alte modificari.
"""

# ---- Clasificator MTSD (Europa/RO) : cheie_folder -> nume romanesc ----
# Tinut sincron cu semne_mtsd_clase.py (sursa folosita la pregatire/antrenare).
NUME_RO_MTSD = {
    "stop": "Stop",
    "cedeaza_trecerea": "Cedeaza trecerea",
    "drum_prioritate": "Drum cu prioritate",
    "sfarsit_drum_prioritate": "Sfarsit drum cu prioritate",
    "prioritate_sens_opus": "Prioritate fata de sensul opus",
    "prioritate_sensului_opus": "Prioritate pentru sensul opus",
    "acces_interzis": "Accesul interzis",
    "depasire_interzisa": "Depasirea interzisa",
    "interzis_camioane": "Interzis camioanelor",
    "intoarcere_interzisa": "Intoarcerea interzisa",
    "stanga_interzis": "Virajul stanga interzis",
    "dreapta_interzis": "Virajul dreapta interzis",
    "inainte_interzis": "Interzis inainte",
    "interzis_biciclete": "Interzis biciclete",
    "interzis_pietoni": "Interzis pietoni",
    "interzis_motociclete": "Interzis motociclete",
    "interzis_marfuri_periculoase": "Interzis marfuri periculoase",
    "stationarea_interzisa": "Stationarea interzisa",
    "oprirea_interzisa": "Oprirea interzisa",
    "drum_inchis": "Drum inchis",
    "limita_inaltime": "Limita de inaltime",
    "limita_greutate": "Limita de greutate",
    "sfarsit_zona_limita": "Sfarsit zona limita viteza",
    "sfarsit_interdictie": "Sfarsit interdictie",
    "control_radar": "Control radar",
    "obligatoriu_dreapta": "Obligatoriu dreapta",
    "obligatoriu_stanga": "Obligatoriu stanga",
    "obligatoriu_inainte": "Obligatoriu inainte",
    "inainte_sau_stanga": "Inainte sau stanga",
    "inainte_sau_dreapta": "Inainte sau dreapta",
    "ocolire_dreapta": "Ocolire pe dreapta",
    "ocolire_stanga": "Ocolire pe stanga",
    "ocolire_ambele_parti": "Ocolire pe ambele parti",
    "sens_giratoriu_obligatoriu": "Sens giratoriu",
    "sens_unic_stanga": "Sens unic stanga",
    "sens_unic_dreapta": "Sens unic dreapta",
    "sens_unic_inainte": "Sens unic inainte",
    "pista_biciclete": "Pista pentru biciclete",
    "drum_pietoni": "Drum pentru pietoni",
    "pista_comuna_pietoni_biciclete": "Pista comuna pietoni/biciclete",
    "doar_mopede_biciclete": "Doar mopede si biciclete",
    "atentie_pietoni": "Atentie, pietoni",
    "copii": "Copii",
    "zona_scolara": "Zona scolara",
    "lucrari": "Lucrari",
    "curba_stanga": "Curba la stanga",
    "curba_dreapta": "Curba la dreapta",
    "curbe_stanga": "Curbe (prima la stanga)",
    "curbe_dreapta": "Curbe (prima la dreapta)",
    "drum_sinuos": "Drum sinuos",
    "denivelare": "Denivelare",
    "drum_denivelat": "Drum denivelat",
    "drum_alunecos": "Drum alunecos",
    "atentie_sens_giratoriu": "Atentie, sens giratoriu",
    "semafor": "Semafor",
    "trecere_cf_bariere": "Trecere CF cu bariere",
    "trecere_cf_fara_bariere": "Trecere CF fara bariere",
    "trecere_cf": "Trecere la nivel cu calea ferata",
    "intersectie": "Intersectie",
    "intersectie_t": "Intersectie in T",
    "drum_secundar_dreapta": "Drum secundar pe dreapta",
    "drum_secundar_stanga": "Drum secundar pe stanga",
    "drum_ingustat": "Drum ingustat",
    "drum_ingustat_stanga": "Drum ingustat pe stanga",
    "drum_ingustat_dreapta": "Drum ingustat pe dreapta",
    "pod_ingust": "Pod ingust",
    "circulatie_dublu_sens": "Circulatie in dublu sens",
    "animale_salbatice": "Animale salbatice",
    "animale_domestice": "Animale domestice",
    "atentie_biciclisti": "Atentie, biciclisti",
    "cadere_pietre": "Cadere de pietre",
    "confluenta_stanga": "Confluenta pe stanga",
    "confluenta_dreapta": "Confluenta pe dreapta",
    "alt_pericol": "Alte pericole",
    "stop_inainte": "Stop inainte",
    "semafor_inainte": "Semafor inainte",
    "sfarsit_drum_separat": "Sfarsit drum cu sensuri separate",
    "trecere_pietoni": "Trecere de pietoni",
    "parcare": "Parcare",
    "autostrada": "Autostrada",
    "sfarsit_autostrada": "Sfarsit autostrada",
    "statie_autobuz": "Statie autobuz",
    "spital": "Spital",
    "persoane_dizabilitati": "Persoane cu dizabilitati",
    "drum_fara_iesire": "Drum fara iesire",
    "iesire": "Iesire",
    "sfarsit_localitate": "Sfarsit localitate",
    "copii_scoala": "Trecere scolari",
    "aeroport": "Aeroport",
    "chevron": "Indicator de directie (curba)",
}
for _v in (5, 10, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100, 110, 120):
    NUME_RO_MTSD[f"limita_{_v}"] = f"Limita {_v}"


# ---- Clasificator GTSRB (vechi) : ID GTSRB (int) -> nume romanesc ----
DICT_GTSRB = {
    0: 'Limita 20', 1: 'Limita 30', 2: 'Limita 50', 3: 'Limita 60', 4: 'Limita 70',
    5: 'Limita 80', 6: 'Sfarsit limita 80', 7: 'Limita 100', 8: 'Limita 120',
    9: 'Depasirea interzisa', 10: 'Depasirea interzisa (camioane)',
    11: 'Intersectie cu prioritate', 12: 'Drum cu prioritate', 13: 'Cedeaza trecerea',
    14: 'Stop', 15: 'Circulatie interzisa', 16: 'Interzis camioanelor', 17: 'Acces interzis',
    18: 'Atentie', 19: 'Curba stanga', 20: 'Curba dreapta', 21: 'Curbe', 22: 'Drum cu denivelari',
    23: 'Drum alunecos', 24: 'Ingustare drum', 25: 'Lucrari', 26: 'Semafor',
    27: 'Pietoni', 28: 'Copii', 29: 'Biciclete', 30: 'Gheata/Zapada', 31: 'Animale',
    32: 'Sfarsit restrictii', 33: 'Obligatoriu dreapta', 34: 'Obligatoriu stanga',
    35: 'Obligatoriu inainte', 36: 'Obligatoriu inainte/dreapta', 37: 'Obligatoriu inainte/stanga',
    38: 'Ocolire prin dreapta', 39: 'Ocolire prin stanga', 40: 'Sens giratoriu',
    41: 'Sfarsit depasire interzisa', 42: 'Sfarsit depasire interzisa (camioane)'
}

# Compatibilitate inapoi (cod vechi care importa DICT_SEMNE)
DICT_SEMNE = DICT_GTSRB


def nume_semn(model_names, idx):
    """Converteste indicele top-1 prezis de clasificator in nume romanesc.

    model_names: dict {index: nume_clasa} din model (clf.names).
    idx: indicele top-1 prezis.
    Returneaza numele romanesc sau None daca nu se poate mapa.

    Detecteaza automat tipul clasificatorului:
      - nume numerice ('0'..'42') -> GTSRB (DICT_GTSRB)
      - nume text ('stop', 'limita_50'...) -> MTSD (NUME_RO_MTSD)
    """
    try:
        nume = model_names[idx]
    except (KeyError, IndexError, TypeError):
        return None

    cheie = str(nume)
    # GTSRB: numele sunt ID-uri numerice
    if cheie.isdigit():
        return DICT_GTSRB.get(int(cheie))
    # MTSD: chei-folder text; daca lipseste din dict, afisam cheia "umanizata"
    return NUME_RO_MTSD.get(cheie, cheie.replace("_", " ").capitalize())
