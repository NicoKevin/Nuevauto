"""
Collecteur La Centrale — placeholder Phase 2.
Implémenté en Phase 2 après validation du collecteur LeBonCoin.
"""

from __future__ import annotations

from collections.abc import Iterator

import structlog

from collectors.base import BaseCollector
from db.models import AnnonceRaw

logger = structlog.get_logger(__name__)


class LaCentraleCollector(BaseCollector):
    """
    Collecteur pour La Centrale — Phase 2.
    Non implémenté en Phase 1 (MVP LeBonCoin uniquement).
    """

    source_name = "lacentrale"

    def build_search_url(self, page: int = 1, **kwargs: object) -> tuple[str, dict]:
        raise NotImplementedError("La Centrale collector not implemented yet — Phase 2")

    def collect(self, max_pages: int | None = None) -> Iterator[AnnonceRaw]:
        logger.warning("lacentrale_collector_not_implemented")
        return iter([])
