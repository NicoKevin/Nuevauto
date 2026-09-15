"""
Collecteur LeBonCoin — annonces voitures de particuliers.

Stratégie : httpx + BeautifulSoup (pas de Playwright).
LeBonCoin charge ses annonces en SSR (Server-Side Rendering) pour les pages
de résultats, ce qui permet un scraping HTTP simple sans navigateur headless.

Si cette stratégie échoue (anti-bot renforcé), migrer vers Playwright uniquement
pour ce collecteur, sans impacter les autres.
"""

from __future__ import annotations

from collections.abc import Iterator

import structlog
from bs4 import BeautifulSoup

from collectors.base import BaseCollector
from db.models import AnnonceRaw, Source

logger = structlog.get_logger(__name__)


class LeBonCoinCollector(BaseCollector):
    """Collecteur pour LeBonCoin — catégorie Voitures, vendeurs particuliers."""

    source_name = "leboncoin"

    BASE_URL = "https://www.leboncoin.fr/recherche"

    def build_search_url(self, page: int = 1, **kwargs: object) -> tuple[str, dict]:
        params = {
            "category": "2",       # Catégorie Voitures
            "owner_type": "private",  # Particuliers uniquement
            "page": str(page),
        }
        return self.BASE_URL, params

    def collect(self, max_pages: int | None = None) -> Iterator[AnnonceRaw]:
        """
        Scrape les pages de résultats LeBonCoin et yield chaque annonce.
        S'arrête si une page ne contient aucune annonce (fin des résultats).
        """
        max_pages = max_pages or self.config.max_pages_per_run
        pages_scraped = 0
        total_found = 0

        self._log.info("collect_start", max_pages=max_pages)

        for page_num in range(1, max_pages + 1):
            url, params = self.build_search_url(page=page_num)
            try:
                response = self._get(url, params=params)
            except Exception as exc:
                self._log.error("page_fetch_failed", page=page_num, error=str(exc))
                break

            annonces = list(self._parse_listing_page(response.text, base_url=url))

            if not annonces:
                self._log.info("no_more_results", page=page_num)
                break

            for annonce in annonces:
                total_found += 1
                yield annonce

            pages_scraped += 1
            self._log.info("page_scraped", page=page_num, count=len(annonces))

        self._log.info("collect_done", pages=pages_scraped, total=total_found)

    def _parse_listing_page(self, html: str, base_url: str) -> Iterator[AnnonceRaw]:
        """
        Parse une page de résultats et extrait les annonces.
        Utilise les sélecteurs du fichier selectors.yaml.
        """
        soup = BeautifulSoup(html, "lxml")
        listing_config = self.selectors.get("listing", {})
        card_selector = listing_config.get("card_selector", "")

        cards = soup.select(card_selector)
        if not cards:
            # Tentative de détection d'anti-bot (page vide ou CAPTCHA)
            if "captcha" in html.lower() or "robot" in html.lower():
                self._log.warning("possible_antibot_detected")
            else:
                self._log.debug("no_cards_found", selector=card_selector)
            return

        for card in cards:
            annonce = self._parse_card(card)
            if annonce:
                yield annonce

    def _parse_card(self, card: BeautifulSoup) -> AnnonceRaw | None:
        """Parse une carte d'annonce individuelle."""
        listing_config = self.selectors.get("listing", {})

        try:
            # URL de l'annonce
            url_el = card.select_one(listing_config.get("url_selector", "a"))
            if not url_el:
                return None
            url = url_el.get(listing_config.get("url_attribute", "href"), "")
            if not url:
                return None
            # Normaliser l'URL (certains liens sont relatifs)
            if url.startswith("/"):
                url = f"https://www.leboncoin.fr{url}"

            # Prix brut
            price_el = card.select_one(listing_config.get("price_selector", ""))
            prix_brut = price_el.get_text(strip=True) if price_el else None

            # Titre brut (marque + modèle)
            title_el = card.select_one(listing_config.get("title_selector", ""))
            titre_brut = title_el.get_text(strip=True) if title_el else None

            # Localisation
            location_el = card.select_one(listing_config.get("location_selector", ""))
            ville_brut = location_el.get_text(strip=True) if location_el else None

            # Date de publication
            date_el = card.select_one(listing_config.get("date_selector", ""))
            date_publication_brut = date_el.get_text(strip=True) if date_el else None

            return AnnonceRaw(
                source=Source.LEBONCOIN,
                url_annonce=url,
                titre_brut=titre_brut,
                prix_brut=prix_brut,
                ville_brut=ville_brut,
                date_publication_brut=date_publication_brut,
            )

        except Exception as exc:
            self._log.warning("card_parse_error", error=str(exc))
            return None
