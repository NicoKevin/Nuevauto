"""
Classe de base pour tous les collecteurs.
Définit l'interface commune que chaque collecteur doit implémenter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

import httpx
import structlog
import yaml
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.settings import ScraperConfig
from db.models import AnnonceRaw

logger = structlog.get_logger(__name__)

# Chemin vers le fichier de config des sélecteurs
SELECTORS_PATH = Path(__file__).parent.parent / "config" / "selectors.yaml"


def load_selectors() -> dict:
    """Charge le fichier de sélecteurs YAML."""
    with open(SELECTORS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


class BaseCollector(ABC):
    """
    Classe abstraite pour tous les collecteurs.
    Gère le client HTTP, le rate limiting et les retries.
    """

    # Nom du site — doit correspondre à une clé dans selectors.yaml
    source_name: str = ""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.selectors = load_selectors().get(self.source_name, {})
        self._client = httpx.Client(
            headers={
                **config.headers,
                "User-Agent": config.user_agent,
            },
            timeout=config.http_timeout_s,
            follow_redirects=True,
        )
        self._log = logger.bind(collector=self.source_name)

    def __enter__(self) -> BaseCollector:
        return self

    def __exit__(self, *args: object) -> None:
        self._client.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        """
        Effectue une requête GET avec retry automatique.
        Log chaque requête pour traçabilité.
        """
        import time
        self._log.debug("http_get", url=url, params=params)
        response = self._client.get(url, params=params)
        response.raise_for_status()
        # Rate limiting : pause entre les requêtes
        time.sleep(self.config.delay_between_requests_s)
        self._log.debug("http_get_ok", url=url, status=response.status_code)
        return response

    @abstractmethod
    def collect(self, max_pages: int | None = None) -> Iterator[AnnonceRaw]:
        """
        Collecte les annonces depuis le site.
        Yield chaque annonce dès qu'elle est parsée (streaming).

        Args:
            max_pages: Nombre maximum de pages à scraper. None = config par défaut.

        Yields:
            AnnonceRaw: Annonce brute, avant normalisation.
        """
        ...

    @abstractmethod
    def build_search_url(self, page: int = 1, **kwargs: object) -> tuple[str, dict]:
        """
        Construit l'URL de recherche et les paramètres query string.

        Returns:
            Tuple (url_base, params_dict)
        """
        ...
