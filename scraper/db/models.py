"""
Modèles de données Pydantic pour les annonces scrapées.

RÈGLE DE DESIGN : Aucun champ téléphone, email, nom ou prénom dans ce modèle.
Cette contrainte est vérifiée par le test tests/test_no_pii.py.
"""

from __future__ import annotations

import datetime as dt
import re
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class Source(StrEnum):
    LEBONCOIN = "leboncoin"
    LACENTRALE = "lacentrale"


class Statut(StrEnum):
    NOUVEAU = "nouveau"
    QUALIFIE = "qualifie"
    NOTIFIE = "notifie"
    TRAITE = "traite"
    IGNORE = "ignore"


class AnnonceRaw(BaseModel):
    """
    Données brutes extraites par un collecteur, avant normalisation.
    Les champs sont permissifs (X | None) car tous les sites ne fournissent pas
    les mêmes informations.
    """
    source: Source
    url_annonce: str
    titre_brut: str | None = None    # Ex: "Renault Clio IV 1.5 dCi 90ch"
    prix_brut: str | None = None     # Ex: "8 500 €" — sera parsé en Numeric
    ville_brut: str | None = None    # Ex: "Paris 75001" ou "Paris (75)"
    date_publication_brut: str | None = None
    attributs_bruts: str | None = None  # Chaîne brute des attributs sr-only
    # --- Champs enrichis depuis la page détail (data-qa-id stables) ---
    marque_brute: str | None = None       # Ex: "HONDA"
    modele_brut: str | None = None        # Ex: "Accord"
    annee_brute: str | None = None        # Ex: "2004"
    kilometrage_brut: str | None = None   # Ex: "198000 km"
    energie_brute: str | None = None      # Ex: "Essence"
    boite_brute: str | None = None        # Ex: "Manuelle"
    finition_brute: str | None = None     # Ex: "GT Line"
    version_brute: str | None = None      # Ex: "1.6 HDi 110"
    type_vehicule_brut: str | None = None # Ex: "Berline"
    couleur_brute: str | None = None      # Ex: "Noir"
    nb_portes_brut: str | None = None     # Ex: "5"
    nb_places_brut: str | None = None     # Ex: "5"
    puissance_fiscale_brute: str | None = None  # Ex: "6 CV"
    puissance_din_brute: str | None = None      # Ex: "110 Ch"
    ct_ok_brut: str | None = None         # Ex: "Oui"
    crit_air_brut: str | None = None      # Ex: "1"
    date_mise_circulation_brute: str | None = None  # Ex: "03/2019"
    description: str | None = None
    image_url: str | None = None

    @field_validator("url_annonce")
    @classmethod
    def url_must_not_contain_pii_patterns(cls, v: str) -> str:
        """
        Garde-fou : l'URL ne doit pas être vide, et ne doit pas contenir
        de numéros de téléphone.
        """
        if not v or not v.strip():
            raise ValueError("url_annonce ne peut pas être vide")
        if re.search(r"\b0[67]\d{8}\b", v):
            raise ValueError(f"URL suspecte : contient un pattern téléphone : {v}")
        return v


class AnnonceNormalisee(BaseModel):
    """
    Annonce après passage dans le pipeline ETL (normalize.py).
    Types stricts — prête pour insertion en base.
    """
    source: Source
    url_annonce: str
    marque: str | None = None
    modele: str | None = None
    annee: int | None = Field(None, ge=1980, le=2030)
    kilometrage: int | None = Field(None, ge=0, le=2_000_000)
    prix: float | None = Field(None, ge=0, le=500_000)
    ville: str | None = None
    code_postal: str | None = None
    # --- Nouveaux champs véhicule (page détail) ---
    energie: str | None = None          # Essence, Diesel, Hybride, Électrique
    boite_vitesse: str | None = None    # Manuelle, Automatique
    type_vehicule: str | None = None    # Berline, SUV, Break
    couleur: str | None = None
    nb_portes: int | None = None
    nb_places: int | None = None
    puissance_fiscale: int | None = None
    puissance_din: str | None = None    # Ex: "110 Ch"
    finition: str | None = None         # Ex: "GT Line"
    version: str | None = None          # Ex: "1.6 HDi 110"
    ct_ok: bool | None = None
    crit_air: str | None = None
    date_mise_circulation: str | None = None
    # --- Champs existants ---
    description: str | None = None
    image_url: str | None = None
    date_publication: dt.datetime | None = None
    date_collecte: dt.datetime = Field(
        default_factory=lambda: dt.datetime.now(dt.UTC),
    )
    hash_contenu: str | None = None
    score: float = Field(default=0.0, ge=0, le=100)
    statut: Statut = Statut.NOUVEAU

    @model_validator(mode="after")
    def check_no_pii_in_description(self) -> AnnonceNormalisee:
        """
        Garde-fou critique : vérifie que la description ne contient pas de PII.
        Ce validator est également testé par test_no_pii.py en CI.
        """
        if self.description:
            # Pattern téléphone français (mobile + fixe)
            phone_pattern = r"\b0[1-9](?:[\s.\-]?\d{2}){4}\b"
            # Pattern email basique
            email_pattern = r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"
            if re.search(phone_pattern, self.description):
                # On ne lève pas d'exception (l'annonce peut quand même être utile)
                # mais on masque le contenu suspect
                self.description = re.sub(phone_pattern, "[NUMÉRO MASQUÉ]", self.description)
            if re.search(email_pattern, self.description):
                self.description = re.sub(email_pattern, "[EMAIL MASQUÉ]", self.description)
        return self

    def to_db_dict(self) -> dict:
        """Convertit en dict compatible avec l'API Supabase (snake_case, sérialisable JSON)."""
        data = self.model_dump(exclude_none=True)
        # Convertir les enums en valeurs string
        data["source"] = self.source.value
        data["statut"] = self.statut.value
        # Convertir les datetimes en ISO 8601
        if self.date_publication:
            data["date_publication"] = self.date_publication.isoformat()
        data["date_collecte"] = self.date_collecte.isoformat()
        return data


class CritereRecherche(BaseModel):
    """Critère de recherche tel que stocké en base."""
    id: UUID | None = None
    nom: str
    marque: str | None = None
    modele: str | None = None
    prix_min: float | None = None
    prix_max: float | None = None
    annee_min: int | None = None
    annee_max: int | None = None
    km_max: int | None = None
    zone_geo: str | None = None
    priorite: int = Field(default=1, ge=1, le=5)
    actif: bool = True
