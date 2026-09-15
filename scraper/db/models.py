"""
Modèles de données Pydantic pour les annonces scrapées.

RÈGLE DE DESIGN : Aucun champ téléphone, email, nom ou prénom dans ce modèle.
Cette contrainte est vérifiée par le test tests/test_no_pii.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class Source(str, Enum):
    LEBONCOIN = "leboncoin"
    LACENTRALE = "lacentrale"


class Statut(str, Enum):
    NOUVEAU = "nouveau"
    QUALIFIE = "qualifie"
    NOTIFIE = "notifie"
    TRAITE = "traite"
    IGNORE = "ignore"


class AnnonceRaw(BaseModel):
    """
    Données brutes extraites par un collecteur, avant normalisation.
    Les champs sont permissifs (Optional) car tous les sites ne fournissent pas
    les mêmes informations.
    """
    source: Source
    url_annonce: str
    titre_brut: Optional[str] = None    # Ex: "Renault Clio IV 1.5 dCi 90ch"
    prix_brut: Optional[str] = None     # Ex: "8 500 €" — sera parsé en Numeric
    ville_brut: Optional[str] = None    # Ex: "Paris 75001" ou "Paris (75)"
    date_publication_brut: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None

    @field_validator("url_annonce")
    @classmethod
    def url_must_not_contain_pii_patterns(cls, v: str) -> str:
        """
        Garde-fou : l'URL ne doit pas être vide, et ne doit pas contenir
        de numéros de téléphone.
        """
        if not v or not v.strip():
            raise ValueError("url_annonce ne peut pas être vide")
        import re
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
    marque: Optional[str] = None
    modele: Optional[str] = None
    annee: Optional[int] = Field(None, ge=1980, le=2030)
    kilometrage: Optional[int] = Field(None, ge=0, le=2_000_000)
    prix: Optional[float] = Field(None, ge=0, le=500_000)
    ville: Optional[str] = None
    code_postal: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    date_publication: Optional[datetime] = None
    date_collecte: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hash_contenu: Optional[str] = None
    score: float = Field(default=0.0, ge=0, le=100)
    statut: Statut = Statut.NOUVEAU

    @model_validator(mode="after")
    def check_no_pii_in_description(self) -> "AnnonceNormalisee":
        """
        Garde-fou critique : vérifie que la description ne contient pas de PII.
        Ce validator est également testé par test_no_pii.py en CI.
        """
        import re
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
    id: Optional[UUID] = None
    nom: str
    marque: Optional[str] = None
    modele: Optional[str] = None
    prix_min: Optional[float] = None
    prix_max: Optional[float] = None
    annee_min: Optional[int] = None
    annee_max: Optional[int] = None
    km_max: Optional[int] = None
    zone_geo: Optional[str] = None
    priorite: int = Field(default=1, ge=1, le=5)
    actif: bool = True
