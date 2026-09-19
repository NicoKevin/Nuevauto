"""
Module de normalisation des données brutes scrapées.
Convertit AnnonceRaw → AnnonceNormalisee avec types stricts.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re

import structlog

from db.models import AnnonceNormalisee, AnnonceRaw

logger = structlog.get_logger(__name__)

# ------------------------------------------------------------------
# Référentiel de normalisation des marques
# Associe des variantes brutes à leur forme canonique
# ------------------------------------------------------------------
MARQUE_NORMALIZATION: dict[str, str] = {
    # Renault
    "renault": "Renault", "renaul": "Renault", "reno": "Renault",
    # Peugeot
    "peugeot": "Peugeot", "peugot": "Peugeot", "pgt": "Peugeot",
    # Citroën
    "citroen": "Citroën", "citroën": "Citroën", "ds": "DS",
    # Volkswagen
    "volkswagen": "Volkswagen", "vw": "Volkswagen",
    # BMW
    "bmw": "BMW",
    # Mercedes
    "mercedes": "Mercedes-Benz",
    "mercedes-benz": "Mercedes-Benz",
    "mercédès": "Mercedes-Benz",
    # Audi
    "audi": "Audi",
    # Toyota
    "toyota": "Toyota",
    # Ford
    "ford": "Ford",
    # Opel
    "opel": "Opel",
    # Fiat
    "fiat": "Fiat",
    # Nissan
    "nissan": "Nissan",
    # Seat
    "seat": "SEAT",
    # Skoda
    "skoda": "Škoda", "škoda": "Škoda",
    # Dacia
    "dacia": "Dacia",
    # Hyundai
    "hyundai": "Hyundai",
    # Kia
    "kia": "Kia",
    # Volvo
    "volvo": "Volvo",
}

# Modèles connus (marque -> [modèles])
MODELES_CONNUS: dict[str, list[str]] = {
    "Renault": [
        "Clio", "Mégane", "Megane", "Captur", "Kadjar",
        "Zoe", "Zoé", "Scenic", "Twingo", "Talisman", "Koleos",
    ],
    "Peugeot": [
        "208", "308", "3008", "5008", "2008", "508",
        "106", "107", "206", "207", "407", "Rifter",
    ],
    "Citroën": [
        "C3", "C4", "C5", "C1", "C2", "Berlingo",
        "Picasso", "DS3", "DS4", "DS5",
    ],
    "Volkswagen": [
        "Golf", "Polo", "Passat", "Tiguan", "T-Roc",
        "Touareg", "Up!", "ID.3", "ID.4",
    ],
    "BMW": [
        "Série 1", "Série 2", "Série 3", "Série 5",
        "X1", "X3", "X5",
    ],
    "Mercedes-Benz": [
        "Classe A", "Classe B", "Classe C", "Classe E",
        "GLA", "GLB", "GLC",
    ],
    "Dacia": ["Sandero", "Duster", "Logan", "Spring", "Jogger"],
}


def normalize_annonce(raw: AnnonceRaw) -> AnnonceNormalisee | None:
    """
    Transforme une AnnonceRaw en AnnonceNormalisee.
    Retourne None si les données sont trop incomplètes pour être utiles.
    """
    try:
        # --- Marque & Modèle ---
        # Priorité 1 : champs structurés de la page détail (data-qa-id fiables)
        # Priorité 2 : inférence depuis le titre
        if getattr(raw, "marque_brute", None):
            marque = raw.marque_brute.strip().title()
            # Correction des marques en MAJUSCULES (ex: "HONDA" -> "Honda", "BMW" -> "BMW")
            marque = MARQUE_NORMALIZATION.get(marque.lower(), marque)
            modele = raw.modele_brut.strip().title() if getattr(raw, "modele_brut", None) else None
        else:
            marque, modele = _extract_marque_modele(raw.titre_brut)

        # --- Prix ---
        prix = _parse_prix(raw.prix_brut)

        # --- Localisation ---
        ville, code_postal = _parse_localisation(raw.ville_brut)

        # --- Année & Kilométrage ---
        # Priorité 1 : champs structurés de la page détail
        annee = _parse_annee(getattr(raw, "annee_brute", None))
        kilometrage = _parse_km(getattr(raw, "kilometrage_brut", None))
        # Priorité 2 : attributs sr-only + titre
        if not annee or not kilometrage:
            annee2, km2 = _extract_annee_km(
                raw.titre_brut,
                getattr(raw, "attributs_bruts", None),
            )
            if not annee:
                annee = annee2
            if not kilometrage:
                kilometrage = km2

        date_pub = _parse_date(raw.date_publication_brut)

        # --- Champs véhicule enrichis (page détail) ---
        energie = getattr(raw, "energie_brute", None)
        boite_vitesse = getattr(raw, "boite_brute", None)
        type_vehicule = getattr(raw, "type_vehicule_brut", None)
        couleur = getattr(raw, "couleur_brute", None)
        finition = getattr(raw, "finition_brute", None)
        version = getattr(raw, "version_brute", None)
        puissance_din = getattr(raw, "puissance_din_brute", None)
        crit_air = getattr(raw, "crit_air_brut", None)
        date_mise_circulation = getattr(raw, "date_mise_circulation_brute", None)

        # Parsing des entiers (nb portes, places, CV fiscaux)
        nb_portes = _parse_int(getattr(raw, "nb_portes_brut", None))
        nb_places = _parse_int(getattr(raw, "nb_places_brut", None))
        puissance_fiscale = _parse_int(getattr(raw, "puissance_fiscale_brute", None))

        # CT OK (booléen depuis texte)
        ct_ok_str = getattr(raw, "ct_ok_brut", None)
        ct_ok = ct_ok_str.lower() in ("oui", "yes", "true") if ct_ok_str else None

        # Hash du contenu pour détecter les mises à jour
        hash_input = f"{raw.url_annonce}|{raw.prix_brut}|{raw.titre_brut}"
        hash_contenu = hashlib.sha256(hash_input.encode()).hexdigest()

        return AnnonceNormalisee(
            source=raw.source,
            url_annonce=raw.url_annonce,
            marque=marque,
            modele=modele,
            annee=annee,
            kilometrage=kilometrage,
            prix=prix,
            ville=ville,
            code_postal=code_postal,
            energie=energie,
            boite_vitesse=boite_vitesse,
            type_vehicule=type_vehicule,
            couleur=couleur,
            nb_portes=nb_portes,
            nb_places=nb_places,
            puissance_fiscale=puissance_fiscale,
            puissance_din=puissance_din,
            finition=finition,
            version=version,
            ct_ok=ct_ok,
            crit_air=crit_air,
            date_mise_circulation=date_mise_circulation,
            description=raw.description,
            image_url=raw.image_url,
            date_publication=date_pub,
            hash_contenu=hash_contenu,
        )
    except Exception as exc:
        logger.warning("normalize_failed", url=raw.url_annonce, error=str(exc))
        return None


def _parse_int(val: str | None) -> int | None:
    """Parse un entier depuis une chaîne brute. Ex: '5 CV' -> 5, '3' -> 3."""
    if not val:
        return None
    digits = re.sub(r"[^\d]", "", val)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _parse_prix(prix_brut: str | None) -> float | None:
    """Extrait le prix numérique depuis une chaîne comme '8 500 €' ou '12500€'."""
    if not prix_brut:
        return None
    cleaned = re.sub(
        r"[^\d,.]", "",
        prix_brut.replace("\u202f", "").replace("\xa0", ""),
    )
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_annee(annee_brute: str | None) -> int | None:
    """Parse une année depuis une chaîne brute issue de la page détail. Ex: '2004' -> 2004"""
    if not annee_brute:
        return None
    match = re.search(r"\b(19[9]\d|20[0-2]\d)\b", annee_brute)
    if match:
        return int(match.group(1))
    return None


def _parse_km(km_brut: str | None) -> int | None:
    """Parse un kilométrage depuis une chaîne brute issue de la page détail. Ex: '198000 km' -> 198000"""
    if not km_brut:
        return None
    km_str = re.sub(r"[^\d]", "", km_brut.replace("\u202f", "").replace("\xa0", ""))
    if not km_str:
        return None
    try:
        km = int(km_str)
        return km if km <= 2_000_000 else None
    except ValueError:
        return None


def _parse_localisation(
    ville_brut: str | None,
) -> tuple[str | None, str | None]:
    """
    Extrait ville et code postal depuis une chaîne comme:
    - 'Paris (75001)' → ('Paris', '75')
    - 'Lyon 69003' → ('Lyon', '69')
    - 'Bordeaux' → ('Bordeaux', None)
    """
    if not ville_brut:
        return None, None

    ville_brut = ville_brut.strip()
    cp_match = re.search(r"\b(\d{5})\b", ville_brut)
    code_postal_complet = cp_match.group(1) if cp_match else None
    # Département = 2 premiers chiffres (sauf 97x pour DOM-TOM)
    departement = code_postal_complet[:2] if code_postal_complet else None

    # Nettoyer la ville (supprimer le code postal et les parenthèses)
    ville = re.sub(r"\s*\(?\d{5}\)?", "", ville_brut).strip()
    ville = ville if ville else None

    return ville, departement


def _extract_marque_modele(
    titre: str | None,
) -> tuple[str | None, str | None]:
    """
    Tente d'extraire la marque et le modèle depuis le titre de l'annonce.
    Ex: 'Renault Clio IV 1.5 dCi 90 CH' → ('Renault', 'Clio')
    """
    if not titre:
        return None, None

    titre_lower = titre.lower().strip()

    for raw_marque, marque_canon in MARQUE_NORMALIZATION.items():
        if (
            titre_lower.startswith(raw_marque)
            or f" {raw_marque} " in f" {titre_lower} "
        ):
            # Marque trouvée — chercher le modèle dans les mots suivants
            modele = _extract_modele_for_marque(titre, marque_canon)
            return marque_canon, modele

    # 2. Chercher par modèle connu (plus spécifique, utile si la marque est absente du titre)
    for marque_canon, modeles in MODELES_CONNUS.items():
        for modele in modeles:
            if titre_lower.startswith(modele.lower()) or f" {modele.lower()} " in f" {titre_lower} ":
                return marque_canon, modele

    return None, None


def _extract_modele_for_marque(titre: str, marque: str) -> str | None:
    """Extrait le modèle en cherchant dans la liste des modèles connus."""
    modeles = MODELES_CONNUS.get(marque, [])
    titre_lower = titre.lower()

    for modele in modeles:
        if modele.lower() in titre_lower:
            return modele

    # Si pas de correspondance exacte, prendre le deuxième mot du titre
    words = titre.split()
    if len(words) >= 2:
        return words[1]

    return None


def _extract_annee_km(
    titre: str | None,
    attributs_bruts: str | None = None,
) -> tuple[int | None, int | None]:
    """
    Extrait l'année et le kilométrage depuis le titre ou les attributs bruts.
    Ex: 'Renault Clio 2019 85000 km' ou 'Année: 2019. Kilométrage: 85000 km'
    """
    annee = None
    km = None

    # Tenter d'abord d'extraire depuis les attributs explicites (très fiables)
    if attributs_bruts:
        # Année: "2017" ou "Année 2017"
        year_match = re.search(r"Ann(?:é|e|\\xe9)e\s*[:-]?\s*[\"\']?(19[9]\d|20[0-2]\d)[\"\']?", attributs_bruts, re.IGNORECASE)
        if year_match:
            annee = int(year_match.group(1))

        # Kilométrage: "176500 km" ou "Kilométrage: 176500 km"
        km_match = re.search(r"Kilom(?:é|e|\\xe9)trage\s*[:-]?\s*[\"\']?([\d\s]{2,7})[\"\']?\s*km", attributs_bruts, re.IGNORECASE)
        if km_match:
            km_str = re.sub(r"\s", "", km_match.group(1))
            try:
                km = int(km_str)
                if km > 2_000_000: km = None
            except ValueError:
                km = None

    # Fallback: extraction depuis le titre
    if not annee and titre:
        year_match = re.search(r"\b(19[9]\d|20[0-2]\d)\b", titre)
        if year_match:
            annee = int(year_match.group(1))

    if not km and titre:
        km_match = re.search(r"(\d[\d\s]{2,6})\s*km\b", titre, re.IGNORECASE)
        if km_match:
            km_str = re.sub(r"\s", "", km_match.group(1))
            try:
                km = int(km_str)
                if km > 2_000_000: km = None
            except ValueError:
                km = None

    return annee, km


def _parse_date(date_brut: str | None) -> dt.datetime | None:
    """
    Parse des formats de date courants sur les sites d'annonces.
    LeBonCoin utilise des formulations relatives ('Aujourd'hui', 'Hier').
    """
    if not date_brut:
        return None

    now = dt.datetime.now(tz=dt.UTC)
    date_lower = date_brut.lower().strip()

    if "aujourd" in date_lower:
        return now
    if "hier" in date_lower:
        return now - dt.timedelta(days=1)

    # Tentative de parse de dates absolues
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return dt.datetime.strptime(date_brut.strip(), fmt).replace(
                tzinfo=dt.UTC,
            )
        except ValueError:
            continue

    return None
