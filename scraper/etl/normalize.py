"""
Module de normalisation des données brutes scrapées.
Convertit AnnonceRaw → AnnonceNormalisee avec types stricts.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

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
    "mercedes": "Mercedes-Benz", "mercedes-benz": "Mercedes-Benz", "mercédès": "Mercedes-Benz",
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
    "Renault": ["Clio", "Mégane", "Megane", "Captur", "Kadjar", "Zoe", "Zoé", "Scenic", "Twingo", "Talisman", "Koleos"],
    "Peugeot": ["208", "308", "3008", "5008", "2008", "508", "106", "107", "206", "207", "407", "Rifter"],
    "Citroën": ["C3", "C4", "C5", "C1", "C2", "Berlingo", "Picasso", "DS3", "DS4", "DS5"],
    "Volkswagen": ["Golf", "Polo", "Passat", "Tiguan", "T-Roc", "Touareg", "Up!", "ID.3", "ID.4"],
    "BMW": ["Série 1", "Série 2", "Série 3", "Série 5", "X1", "X3", "X5"],
    "Mercedes-Benz": ["Classe A", "Classe B", "Classe C", "Classe E", "GLA", "GLB", "GLC"],
    "Dacia": ["Sandero", "Duster", "Logan", "Spring", "Jogger"],
}


def normalize_annonce(raw: AnnonceRaw) -> Optional[AnnonceNormalisee]:
    """
    Transforme une AnnonceRaw en AnnonceNormalisee.
    Retourne None si les données sont trop incomplètes pour être utiles.
    """
    try:
        marque, modele = _extract_marque_modele(raw.titre_brut)
        prix = _parse_prix(raw.prix_brut)
        ville, code_postal = _parse_localisation(raw.ville_brut)
        annee, kilometrage = _extract_from_title(raw.titre_brut)
        date_pub = _parse_date(raw.date_publication_brut)

        # Calculer le hash du contenu pour détecter les mises à jour
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
            description=raw.description,
            image_url=raw.image_url,
            date_publication=date_pub,
            hash_contenu=hash_contenu,
        )
    except Exception as exc:
        logger.warning("normalize_failed", url=raw.url_annonce, error=str(exc))
        return None


def _parse_prix(prix_brut: Optional[str]) -> Optional[float]:
    """Extrait le prix numérique depuis une chaîne comme '8 500 €' ou '12500€'."""
    if not prix_brut:
        return None
    # Supprimer tout sauf chiffres et virgule/point
    cleaned = re.sub(r"[^\d,.]", "", prix_brut.replace("\u202f", "").replace("\xa0", ""))
    # Gérer les formats européens (virgule décimale)
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_localisation(ville_brut: Optional[str]) -> tuple[Optional[str], Optional[str]]:
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


def _extract_marque_modele(titre: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Tente d'extraire la marque et le modèle depuis le titre de l'annonce.
    Ex: 'Renault Clio IV 1.5 dCi 90 CH' → ('Renault', 'Clio')
    """
    if not titre:
        return None, None

    titre_lower = titre.lower().strip()

    for raw_marque, marque_canon in MARQUE_NORMALIZATION.items():
        if titre_lower.startswith(raw_marque) or f" {raw_marque} " in f" {titre_lower} ":
            # Marque trouvée — chercher le modèle dans les mots suivants
            modele = _extract_modele_for_marque(titre, marque_canon)
            return marque_canon, modele

    return None, None


def _extract_modele_for_marque(titre: str, marque: str) -> Optional[str]:
    """Extrait le modèle en cherchant dans la liste des modèles connus pour cette marque."""
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


def _extract_from_title(titre: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """
    Tente d'extraire l'année et le kilométrage depuis le titre.
    Ex: 'Renault Clio 2019 85000 km' → (2019, 85000)
    Note: ces infos sont rarement dans le titre de LBC — souvent dans les détails.
    """
    if not titre:
        return None, None

    annee = None
    km = None

    # Année (entre 1990 et 2030)
    year_match = re.search(r"\b(19[9]\d|20[0-2]\d)\b", titre)
    if year_match:
        annee = int(year_match.group(1))

    # Kilométrage (ex: "85 000 km" ou "85000km")
    km_match = re.search(r"(\d[\d\s]{2,6})\s*km\b", titre, re.IGNORECASE)
    if km_match:
        km_str = re.sub(r"\s", "", km_match.group(1))
        try:
            km = int(km_str)
            if km > 2_000_000:
                km = None  # Valeur aberrante
        except ValueError:
            km = None

    return annee, km


def _parse_date(date_brut: Optional[str]) -> Optional[datetime]:
    """
    Parse des formats de date courants sur les sites d'annonces.
    LeBonCoin utilise des formulations relatives ('Aujourd'hui', 'Hier', '15 sept.').
    """
    if not date_brut:
        return None

    now = datetime.now(tz=timezone.utc)
    date_lower = date_brut.lower().strip()

    if "aujourd" in date_lower:
        return now
    if "hier" in date_lower:
        from datetime import timedelta
        return now - timedelta(days=1)

    # Tentative de parse de dates absolues
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_brut.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None
