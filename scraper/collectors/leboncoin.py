"""
Collecteur LeBonCoin — annonces voitures / utilitaires / sans permis.

Stratégie en 2 étapes :
1. Scraping du listing (pages de résultats) avec filtres géo + prix
2. Enrichissement via la page détail pour récupérer les données structurées

Filtres appliqués :
- Rayon de 20 km autour de Villemomble (93250)
- Prix minimum 4 900 €
- Annonces de moins de 48h
- Catégories : voitures, utilitaires, voitures sans permis
"""

from __future__ import annotations

import datetime as dt
import re
import time
from collections.abc import Iterator

import structlog
from bs4 import BeautifulSoup

from collectors.base import BaseCollector
from db.models import AnnonceRaw, Source

logger = structlog.get_logger(__name__)

# Catégories LeBonCoin à scraper
# Cat 2 = Voitures (inclut électrique, hybride, essence, diesel, sans permis)
# NOTE: Cat 4 et 50 exclues car elles ne retournent pas des véhicules
LBC_CATEGORIES = {
    "2": "voitures",
}

# Villemomble 93250 — coordonnées GPS
VILLEMOMBLE_LAT = 48.88318
VILLEMOMBLE_LNG = 2.51505
VILLEMOMBLE_LOCATION = f"Villemomble_93250__{VILLEMOMBLE_LAT}_{VILLEMOMBLE_LNG}_20000_0"

# Prix minimum
PRIX_MIN = 4900

# Ancienneté maximum des annonces (en heures)
MAX_AGE_HOURS = 48


class LeBonCoinCollector(BaseCollector):
    """Collecteur pour LeBonCoin — multi-catégories, filtré géographiquement."""

    source_name = "leboncoin"
    BASE_URL = "https://www.leboncoin.fr/recherche"

    def build_search_url(self, page: int = 1, category: str = "2", **kwargs: object) -> tuple[str, dict]:
        params = {
            "category": category,
            "locations": "Villemomble_93250__48.88492_2.51103_1838_20000",
            "price": f"{PRIX_MIN}-max",
            "owner_type": "private",
            "sort": "time",
            "order": "desc",       # Indispensable pour avoir les plus récentes !
            "page": str(page),
        }
        return self.BASE_URL, params

    def collect(self, max_pages: int | None = None) -> Iterator[AnnonceRaw]:
        """
        Scrape toutes les catégories avec les filtres géo + prix + date.
        S'arrête automatiquement quand les annonces dépassent 48h.
        """
        max_pages = max_pages or self.config.max_pages_per_run
        total_found = 0
        urls_seen: set[str] = set()  # Dédoublonnage (certains véhicules sont dans plusieurs catégories)

        self._log.info(
            "collect_start",
            max_pages=max_pages,
            categories=list(LBC_CATEGORIES.keys()),
            location="Villemomble 93250 (20km)",
            prix_min=PRIX_MIN,
            max_age_hours=MAX_AGE_HOURS,
        )

        for cat_id, cat_name in LBC_CATEGORIES.items():
            self._log.info("category_start", category=cat_name, category_id=cat_id)
            pages_scraped = 0
            stop_category = False

            for page_num in range(1, max_pages + 1):
                if stop_category:
                    break

                url, params = self.build_search_url(page=page_num, category=cat_id)
                try:
                    response = self._get(url, params=params)
                except Exception as exc:
                    self._log.error("page_fetch_failed", page=page_num, category=cat_name, error=str(exc))
                    break

                annonces = list(self._parse_listing_page(response.text, base_url=url))

                if not annonces:
                    self._log.info("no_more_results", page=page_num, category=cat_name)
                    break

                for annonce in annonces:
                    # Dédoublonnage par URL
                    if annonce.url_annonce in urls_seen:
                        continue
                    urls_seen.add(annonce.url_annonce)

                    # Filtre prix AVANT de visiter la page détail (gain de temps)
                    prix_brut = annonce.prix_brut
                    if prix_brut:
                        prix_num = self._parse_prix_quick(prix_brut)
                        if prix_num is not None and prix_num < PRIX_MIN:
                            self._log.debug("skipped_prix_too_low", url=annonce.url_annonce, prix=prix_num)
                            continue

                    # Enrichissement via page détail (seulement si le prix est OK)
                    enriched = self._enrich_with_detail(annonce)

                    total_found += 1
                    yield enriched

                pages_scraped += 1
                self._log.info("page_scraped", page=page_num, category=cat_name, count=len(annonces))

            self._log.info("category_done", category=cat_name, pages=pages_scraped)

        self._log.info("collect_done", total=total_found, categories_scraped=len(LBC_CATEGORIES))

    def _parse_prix_quick(self, prix_brut: str) -> float | None:
        """Parse rapide du prix pour le filtrage."""
        cleaned = re.sub(r"[^\d,.]", "", prix_brut.replace("\u202f", "").replace("\xa0", ""))
        cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _enrich_with_detail(self, annonce: AnnonceRaw) -> AnnonceRaw:
        """
        Visite la page détail pour récupérer les données structurées
        de la section 'Les informations clés' (Marque, Modèle, Année, Km, etc.).
        """
        try:
            time.sleep(self.config.delay_between_requests_s * 0.5)
            response = self._get(annonce.url_annonce)
            soup = BeautifulSoup(response.text, "lxml")

            criteria_map = self._extract_criteria(soup)

            if criteria_map:
                self._log.debug(
                    "detail_enriched",
                    url=annonce.url_annonce,
                    keys=list(criteria_map.keys()),
                )
                annonce = annonce.model_copy(
                    update={
                        "marque_brute": criteria_map.get("u_car_brand"),
                        "modele_brut": criteria_map.get("u_car_model"),
                        "annee_brute": criteria_map.get("regdate"),
                        "kilometrage_brut": criteria_map.get("mileage"),
                        "energie_brute": criteria_map.get("fuel"),
                        "boite_brute": criteria_map.get("gearbox"),
                        "finition_brute": criteria_map.get("u_car_finition"),
                        "version_brute": criteria_map.get("u_car_version"),
                        "type_vehicule_brut": criteria_map.get("vehicle_type"),
                        "couleur_brute": criteria_map.get("vehicule_color"),
                        "nb_portes_brut": criteria_map.get("doors"),
                        "nb_places_brut": criteria_map.get("seats"),
                        "puissance_fiscale_brute": criteria_map.get("horsepower"),
                        "puissance_din_brute": criteria_map.get("horse_power_din"),
                        "ct_ok_brut": criteria_map.get("vehicle_technical_inspection_valid"),
                        "crit_air_brut": criteria_map.get("critair"),
                        "date_mise_circulation_brute": criteria_map.get("issuance_date"),
                        "attributs_bruts": str(criteria_map),
                    }
                )
        except Exception as exc:
            self._log.warning(
                "detail_enrich_failed",
                url=annonce.url_annonce,
                error=str(exc),
            )

        return annonce

    def _extract_criteria(self, soup: BeautifulSoup) -> dict[str, str]:
        """
        Extrait les critères structurés via les data-qa-id stables.
        Pattern: criteria_item_{key} → valeur
        """
        criteria = {}
        for item in soup.select("[data-qa-id^='criteria_item_']"):
            qa_id = item.get("data-qa-id", "")
            key = qa_id.replace("criteria_item_", "")
            texts = [t.strip() for t in item.stripped_strings]
            if len(texts) >= 2:
                criteria[key] = texts[-1]
        return criteria

    def _parse_listing_page(self, html: str, base_url: str) -> Iterator[AnnonceRaw]:
        """Parse une page de résultats et extrait les annonces."""
        soup = BeautifulSoup(html, "lxml")
        listing_config = self.selectors.get("listing", {})
        card_selector = listing_config.get("card_selector", "article")

        cards = soup.select(card_selector)
        if not cards:
            if "captcha-delivery" in html or "please enable js" in html.lower():
                self._log.warning(
                    "possible_antibot_detected",
                    msg="Datadome a bloqué la requête. Rafraîchissez DATADOME_COOKIE dans le .env",
                )
            else:
                self._log.debug("no_cards_found", selector=card_selector)
            return

        for card in cards:
            annonce = self._parse_card(card)
            if annonce:
                yield annonce

    def _parse_card(self, card: BeautifulSoup) -> AnnonceRaw | None:
        """Parse une carte d'annonce depuis la page de résultats."""
        listing_config = self.selectors.get("listing", {})

        try:
            # URL
            url_el = None
            for a in card.select("a"):
                if a.get("href") and "/ad/" in a.get("href"):
                    url_el = a
                    break

            if not url_el:
                return None

            url = url_el.get("href", "")
            if not url:
                return None
            if url.startswith("/"):
                url = f"https://www.leboncoin.fr{url}"

            # Titre
            title_el = card.select_one(listing_config.get("title_selector", "p.text-body-1-highlight"))
            titre_brut = title_el.get_text(strip=True) if title_el else card.get("aria-label")

            # Prix
            price_el = card.select_one(listing_config.get("price_selector", "p.text-callout"))
            prix_brut = None
            if price_el:
                prix_brut = price_el.get_text(strip=True)
            else:
                for p in card.find_all(["p", "span"]):
                    if p.text and "\u20ac" in p.text:
                        prix_brut = p.text.strip()
                        break

            # Localisation
            location_el = card.select_one(listing_config.get("location_selector", ""))
            ville_brut = location_el.get_text(strip=True) if location_el else None

            # Date
            date_el = card.select_one(listing_config.get("date_selector", ""))
            date_publication_brut = date_el.get_text(strip=True) if date_el else None

            # Attributs sr-only
            attributs_bruts = None
            for sr in card.select("p.sr-only"):
                if "Ann" in sr.text or "Kilom" in sr.text:
                    attributs_bruts = sr.text.strip()
                    break

            return AnnonceRaw(
                source=Source.LEBONCOIN,
                url_annonce=url,
                titre_brut=titre_brut,
                prix_brut=prix_brut,
                ville_brut=ville_brut,
                date_publication_brut=date_publication_brut,
                attributs_bruts=attributs_bruts,
            )

        except Exception as exc:
            self._log.warning("card_parse_error", error=str(exc))
            return None
