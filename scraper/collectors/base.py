"""
Classe de base pour tous les collecteurs.
Définit l'interface commune que chaque collecteur doit implémenter.
Utilise curl_cffi avec une session persistante pour imiter Chrome et maintenir
les cookies Datadome entre les requêtes (listing + détail).
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

import structlog
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential

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
    Gère le client HTTP (curl_cffi session), le rate limiting et les retries.
    """

    source_name: str = ""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self.selectors = load_selectors().get(self.source_name, {})
        self._log = logger.bind(collector=self.source_name)

        # Session curl_cffi avec impersonation Chrome (TLS fingerprint réaliste)
        from curl_cffi import requests as curl_requests
        self._session = curl_requests.Session(impersonate="chrome")

        # Injecter le cookie Datadome si disponible
        if config.datadome_cookie:
            self._session.cookies.set("datadome", config.datadome_cookie, domain=".leboncoin.fr")
            self._log.info("datadome_cookie_injected")

    def __enter__(self) -> BaseCollector:
        return self

    def __exit__(self, *args: object) -> None:
        self._session.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _get(self, url: str, params: dict | None = None) -> object:
        """
        Effectue une requête GET avec retry automatique via curl_cffi.
        La session maintient automatiquement les cookies entre les requêtes.
        """
        self._log.debug("http_get", url=url, params=params)
        response = self._session.get(
            url,
            params=params,
            timeout=self.config.http_timeout_s,
            headers={"User-Agent": self.config.user_agent},
        )
        response.raise_for_status()
        time.sleep(self.config.delay_between_requests_s)
        self._log.debug("http_get_ok", url=url, status=response.status_code)
        return response

    @abstractmethod
    def collect(self, max_pages: int | None = None) -> Iterator[AnnonceRaw]:
        """
        Collecte les annonces depuis le site.
        Yield chaque annonce dès qu'elle est parsée (streaming).
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
