"""
Test critique — DOIT PASSER EN CI AVANT TOUT MERGE.

Vérifie qu'aucun champ PII (téléphone, email) n'est extrait ou stocké.
Ce test est la concrétisation du garde-fou §7 du plan d'ingénierie.

Toute modification du modèle AnnonceNormalisee qui ajouterait un champ
téléphone ou email doit faire échouer ce test.
"""

from __future__ import annotations

import re

import pytest

from db.models import AnnonceNormalisee, AnnonceRaw, Source


# ------------------------------------------------------------------
# Patterns PII
# ------------------------------------------------------------------
PHONE_PATTERNS = [
    r"\b0[67]\d{8}\b",              # Mobile FR: 06/07
    r"\b0[1-5]\d{8}\b",             # Fixe FR
    r"\+33\s?[1-9](\s?\d{2}){4}",  # Format international
]
EMAIL_PATTERN = r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b"


def contains_phone(text: str) -> bool:
    return any(re.search(p, text) for p in PHONE_PATTERNS)


def contains_email(text: str) -> bool:
    return bool(re.search(EMAIL_PATTERN, text))


# ------------------------------------------------------------------
# Test 1 : Le modèle AnnonceNormalisee ne doit pas avoir de champs PII
# ------------------------------------------------------------------
class TestModelNoPIIFields:
    FORBIDDEN_FIELD_NAMES = {
        "telephone", "phone", "tel", "mobile", "portable",
        "email", "mail", "courriel",
        "nom", "prenom", "first_name", "last_name", "name",
        "contact", "vendeur",
    }

    def test_annonce_normalisee_has_no_pii_fields(self):
        """Vérifie que AnnonceNormalisee n'a aucun champ dont le nom correspond à une PII."""
        model_fields = set(AnnonceNormalisee.model_fields.keys())
        forbidden_found = model_fields & self.FORBIDDEN_FIELD_NAMES
        assert not forbidden_found, (
            f"Champs PII interdits trouvés dans AnnonceNormalisee : {forbidden_found}\n"
            "Ces champs ne doivent JAMAIS exister dans le modèle de données."
        )

    def test_annonce_raw_has_no_pii_fields(self):
        """Vérifie que AnnonceRaw n'a aucun champ dont le nom correspond à une PII."""
        model_fields = set(AnnonceRaw.model_fields.keys())
        forbidden_found = model_fields & self.FORBIDDEN_FIELD_NAMES
        assert not forbidden_found, (
            f"Champs PII interdits trouvés dans AnnonceRaw : {forbidden_found}\n"
            "Ces champs ne doivent JAMAIS exister dans le modèle de données."
        )


# ------------------------------------------------------------------
# Test 2 : Le validator Pydantic masque les PII dans les descriptions
# ------------------------------------------------------------------
class TestDescriptionPIIMasking:
    def test_phone_in_description_is_masked(self):
        """Une description contenant un numéro de téléphone doit être masquée."""
        annonce = AnnonceNormalisee(
            source=Source.LEBONCOIN,
            url_annonce="https://www.leboncoin.fr/voitures/123.htm",
            description="Belle Clio, appelez-moi au 0612345678 pour rdv",
        )
        assert "0612345678" not in (annonce.description or ""), (
            "Le numéro de téléphone n'a pas été masqué dans la description"
        )
        assert "[NUMÉRO MASQUÉ]" in (annonce.description or ""), (
            "Le placeholder [NUMÉRO MASQUÉ] devrait apparaître"
        )

    def test_email_in_description_is_masked(self):
        """Une description contenant un email doit être masquée."""
        annonce = AnnonceNormalisee(
            source=Source.LEBONCOIN,
            url_annonce="https://www.leboncoin.fr/voitures/456.htm",
            description="Contactez-moi à jean.dupont@gmail.com pour plus d'infos",
        )
        assert "jean.dupont@gmail.com" not in (annonce.description or ""), (
            "L'email n'a pas été masqué dans la description"
        )
        assert "[EMAIL MASQUÉ]" in (annonce.description or ""), (
            "Le placeholder [EMAIL MASQUÉ] devrait apparaître"
        )

    def test_clean_description_unchanged(self):
        """Une description sans PII ne doit pas être modifiée."""
        original = "Renault Clio IV en très bon état, CT ok, première main."
        annonce = AnnonceNormalisee(
            source=Source.LEBONCOIN,
            url_annonce="https://www.leboncoin.fr/voitures/789.htm",
            description=original,
        )
        assert annonce.description == original, (
            "Une description propre ne devrait pas être modifiée par le validator"
        )


# ------------------------------------------------------------------
# Test 3 : to_db_dict() ne doit pas sérialiser de PII
# ------------------------------------------------------------------
class TestDatabaseDictNoPII:
    def test_db_dict_has_no_pii_keys(self):
        """Le dictionnaire pour Supabase ne doit contenir aucune clé PII."""
        annonce = AnnonceNormalisee(
            source=Source.LEBONCOIN,
            url_annonce="https://www.leboncoin.fr/voitures/999.htm",
            marque="Renault",
            modele="Clio",
            prix=8500.0,
        )
        db_dict = annonce.to_db_dict()
        forbidden_keys = {
            "telephone", "phone", "tel", "mobile", "email", "mail",
            "nom", "prenom", "contact",
        }
        found_forbidden = set(db_dict.keys()) & forbidden_keys
        assert not found_forbidden, (
            f"Clés PII trouvées dans to_db_dict() : {found_forbidden}"
        )


# ------------------------------------------------------------------
# Test 4 : Vérifier que les fixtures HTML de test ne contiennent pas de vrais contacts
# ------------------------------------------------------------------
class TestFixturesNoPII:
    """
    Vérifie que les fichiers HTML dans tests/fixtures/ ne contiennent pas
    de numéros de téléphone ou d'emails réels.
    Les fixtures doivent contenir uniquement des données fictives.
    """

    def test_fixtures_html_no_real_phone(self, fixture_html_files: list):
        for path, content in fixture_html_files:
            assert not contains_phone(content), (
                f"Fichier fixture {path} contient un vrai numéro de téléphone. "
                "Remplacez-le par '06 XX XX XX XX' ou similaire."
            )

    def test_fixtures_html_no_real_email(self, fixture_html_files: list):
        for path, content in fixture_html_files:
            assert not contains_email(content), (
                f"Fichier fixture {path} contient une vraie adresse email. "
                "Remplacez-la par 'exemple@example.com'."
            )


# ------------------------------------------------------------------
# Conftest / Fixtures pytest
# ------------------------------------------------------------------
@pytest.fixture
def fixture_html_files() -> list[tuple[str, str]]:
    """Charge tous les fichiers HTML depuis tests/fixtures/."""
    from pathlib import Path
    fixtures_dir = Path(__file__).parent / "fixtures"
    if not fixtures_dir.exists():
        return []
    return [
        (str(p), p.read_text(encoding="utf-8", errors="ignore"))
        for p in fixtures_dir.glob("*.html")
    ]
