"""
Moteur de scoring des annonces.
Calcule un score de 0 à 100 basé sur la correspondance avec les critères de recherche.
"""

from __future__ import annotations

from typing import Optional

import structlog

from db.models import AnnonceNormalisee, CritereRecherche

logger = structlog.get_logger(__name__)


def score_annonce(
    annonce: AnnonceNormalisee,
    criteres: list[CritereRecherche],
) -> tuple[float, Optional[str]]:
    """
    Calcule le score d'une annonce en la comparant aux critères actifs.

    Retourne:
        - score: float entre 0 et 100
        - critere_id: UUID du critère le plus pertinent, ou None

    Algorithme:
        1. Pour chaque critère actif, calculer un score partiel.
        2. Retenir le critère avec le meilleur score.
        3. Appliquer un bonus de priorité (critère de priorité 5 booste le score).
    """
    if not criteres:
        return 0.0, None

    best_score = 0.0
    best_critere_id: Optional[str] = None

    for critere in criteres:
        partial_score = _score_against_critere(annonce, critere)
        if partial_score > best_score:
            best_score = partial_score
            best_critere_id = str(critere.id) if critere.id else None

    return round(min(best_score, 100.0), 2), best_critere_id


def _score_against_critere(annonce: AnnonceNormalisee, critere: CritereRecherche) -> float:
    """
    Score une annonce contre un critère spécifique.
    Score maximum = 100 si tous les critères correspondent parfaitement.
    """
    score = 0.0
    max_possible = 0.0

    # --- Correspondance marque (poids: 25) ---
    if critere.marque:
        max_possible += 25
        if annonce.marque and annonce.marque.lower() == critere.marque.lower():
            score += 25
        elif annonce.marque:
            score += 0  # Mauvaise marque = score nul (pas de partiel)

    # --- Correspondance modèle (poids: 20) ---
    if critere.modele:
        max_possible += 20
        if annonce.modele and critere.modele.lower() in annonce.modele.lower():
            score += 20

    # --- Prix dans la fourchette (poids: 20) ---
    if critere.prix_min is not None or critere.prix_max is not None:
        max_possible += 20
        if annonce.prix is not None:
            in_range = True
            if critere.prix_min is not None and annonce.prix < critere.prix_min:
                in_range = False
            if critere.prix_max is not None and annonce.prix > critere.prix_max:
                in_range = False
            if in_range:
                score += 20
            else:
                # Bonus partiel si prix légèrement hors fourchette (±10%)
                if critere.prix_max and annonce.prix <= critere.prix_max * 1.10:
                    score += 8
                if critere.prix_min and annonce.prix >= critere.prix_min * 0.90:
                    score += 8

    # --- Kilométrage (poids: 15) ---
    if critere.km_max is not None:
        max_possible += 15
        if annonce.kilometrage is not None:
            if annonce.kilometrage <= critere.km_max:
                score += 15
            elif annonce.kilometrage <= critere.km_max * 1.15:
                score += 7  # Légèrement au-dessus

    # --- Année (poids: 10) ---
    if critere.annee_min is not None:
        max_possible += 10
        if annonce.annee is not None:
            if annonce.annee >= critere.annee_min:
                score += 10
            elif annonce.annee >= critere.annee_min - 2:
                score += 5  # 1-2 ans plus vieux

    # --- Zone géographique (poids: 10) ---
    if critere.zone_geo:
        max_possible += 10
        if annonce.code_postal:
            departements_cibles = {d.strip() for d in critere.zone_geo.split(",")}
            if annonce.code_postal in departements_cibles:
                score += 10
            # Bonus partiel si département contigu (simplifié)

    # --- Normaliser par rapport au max possible ---
    if max_possible == 0:
        return 0.0

    normalized = (score / max_possible) * 100

    # --- Bonus de priorité ---
    priority_bonus = (critere.priorite - 1) * 3  # 0 à +12 points
    normalized = min(normalized + priority_bonus, 100.0)

    # --- Malus fraîcheur (annonce très ancienne) ---
    if annonce.date_publication:
        from datetime import datetime, timezone
        age_days = (datetime.now(tz=timezone.utc) - annonce.date_publication).days
        if age_days > 30:
            normalized *= 0.7  # -30% si plus de 30 jours
        elif age_days > 14:
            normalized *= 0.85

    return normalized
