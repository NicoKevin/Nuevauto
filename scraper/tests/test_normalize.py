"""
Tests du moteur de normalisation ETL.
"""

from __future__ import annotations

import pytest

from db.models import AnnonceRaw, Source
from etl.normalize import (
    _extract_marque_modele,
    _parse_localisation,
    _parse_prix,
    normalize_annonce,
)


class TestParsePrix:
    def test_prix_simple(self):
        assert _parse_prix("8500€") == 8500.0

    def test_prix_avec_espaces(self):
        assert _parse_prix("8 500 €") == 8500.0

    def test_prix_espace_insecable(self):
        # \xa0 = espace insécable (courant sur les sites FR)
        assert _parse_prix("12\xa0000\xa0€") == 12000.0

    def test_prix_none(self):
        assert _parse_prix(None) is None

    def test_prix_vide(self):
        assert _parse_prix("") is None

    def test_prix_virgule_decimale(self):
        assert _parse_prix("8 500,00 €") == 8500.0


class TestParseLocalisation:
    def test_paris_avec_cp(self):
        ville, cp = _parse_localisation("Paris (75001)")
        assert ville == "Paris"
        assert cp == "75"

    def test_lyon(self):
        ville, cp = _parse_localisation("Lyon 69003")
        assert ville == "Lyon"
        assert cp == "69"

    def test_ville_sans_cp(self):
        ville, cp = _parse_localisation("Bordeaux")
        assert ville == "Bordeaux"
        assert cp is None

    def test_none(self):
        ville, cp = _parse_localisation(None)
        assert ville is None
        assert cp is None


class TestExtractMarqueModele:
    def test_renault_clio(self):
        marque, modele = _extract_marque_modele("Renault Clio IV 1.5 dCi 90ch")
        assert marque == "Renault"
        assert modele == "Clio"

    def test_peugeot_308(self):
        marque, modele = _extract_marque_modele("Peugeot 308 SW 1.6 HDi")
        assert marque == "Peugeot"
        assert modele == "308"

    def test_vw_golf(self):
        marque, modele = _extract_marque_modele("VW Golf 7 GTI")
        assert marque == "Volkswagen"
        assert modele == "Golf"

    def test_titre_inconnu(self):
        marque, modele = _extract_marque_modele("Voiture occasion bon état")
        assert marque is None

    def test_titre_none(self):
        marque, modele = _extract_marque_modele(None)
        assert marque is None
        assert modele is None


class TestNormalizeAnnonce:
    def test_annonce_complete(self):
        raw = AnnonceRaw(
            source=Source.LEBONCOIN,
            url_annonce="https://www.leboncoin.fr/voitures/123.htm",
            titre_brut="Renault Clio IV 2019 85000 km",
            prix_brut="8 500 €",
            ville_brut="Paris (75001)",
            description="Belle Clio en très bon état, CT ok.",
        )
        result = normalize_annonce(raw)
        assert result is not None
        assert result.marque == "Renault"
        assert result.prix == 8500.0
        assert result.code_postal == "75"
        assert result.hash_contenu is not None

    def test_annonce_url_vide(self):
        """Une annonce sans URL doit échouer à la validation Pydantic."""
        with pytest.raises(Exception):
            AnnonceRaw(
                source=Source.LEBONCOIN,
                url_annonce="",  # URL vide
            )
