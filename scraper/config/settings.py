"""
Configuration centralisée du scraper Nuevauto.
Toutes les valeurs sensibles (URLs, clés API) proviennent des variables d'environnement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_key: str  # Clé service_role — bypass RLS, uniquement côté scraper/backend

    @classmethod
    def from_env(cls) -> SupabaseConfig:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
        if not url or not key:
            raise ValueError(
                "Variables d'environnement manquantes : SUPABASE_URL et SUPABASE_SERVICE_KEY "
                "sont obligatoires. En local, créez un fichier .env à la racine de scraper/."
            )
        return cls(url=url, service_key=key)


@dataclass(frozen=True)
class ScraperConfig:
    # Rate limiting — entre chaque requête vers le même site
    delay_between_requests_s: float = 2.0
    # Timeout HTTP (secondes)
    http_timeout_s: float = 15.0
    # Nombre de pages à scraper par exécution (limite de sécurité)
    max_pages_per_run: int = 10
    # Nombre de retries en cas d'erreur réseau
    max_retries: int = 3
    # User-Agent simulant un navigateur courant
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    # Headers communs envoyés avec chaque requête
    headers: dict = field(default_factory=lambda: {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })


@dataclass(frozen=True)
class NotificationConfig:
    slack_webhook_url: str | None

    @classmethod
    def from_env(cls) -> NotificationConfig:
        return cls(
            slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL") or None,
        )


@dataclass(frozen=True)
class AppConfig:
    supabase: SupabaseConfig
    scraper: ScraperConfig
    notifications: NotificationConfig
    # Seuil de score minimum pour déclencher une notification
    score_notification_threshold: float = 60.0
    # Rétention des annonces ignorées (jours)
    retention_ignored_days: int = 30

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            supabase=SupabaseConfig.from_env(),
            scraper=ScraperConfig(),
            notifications=NotificationConfig.from_env(),
        )
