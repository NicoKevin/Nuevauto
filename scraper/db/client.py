"""
Client Supabase pour le scraper.
Utilise la clé service_role (bypass RLS) — uniquement côté serveur/scraper.
"""

from __future__ import annotations

import structlog
from supabase import Client, create_client

from config.settings import SupabaseConfig
from db.models import AnnonceNormalisee, CritereRecherche

logger = structlog.get_logger(__name__)


class SupabaseClient:
    """
    Wrapper autour du client Supabase officiel.
    Fournit des méthodes métier adaptées au projet.
    """

    def __init__(self, config: SupabaseConfig) -> None:
        self._client: Client = create_client(config.url, config.service_key)
        logger.info("supabase_client_initialized", url=config.url)

    # ------------------------------------------------------------------
    # Annonces
    # ------------------------------------------------------------------

    def upsert_annonce(self, annonce: AnnonceNormalisee) -> dict | None:
        """
        Insère une annonce ou la met à jour si l'URL existe déjà.
        Utilise ON CONFLICT sur url_annonce (UNIQUE en base).
        Retourne le record inséré/mis à jour, ou None en cas d'erreur.
        """
        data = annonce.to_db_dict()
        try:
            result = (
                self._client.table("annonces")
                .upsert(data, on_conflict="url_annonce")
                .execute()
            )
            if result.data:
                logger.info(
                    "annonce_upserted",
                    url=annonce.url_annonce,
                    source=annonce.source.value,
                    statut=annonce.statut.value,
                )
                return result.data[0]
            return None
        except Exception as exc:
            logger.error("upsert_annonce_failed", url=annonce.url_annonce, error=str(exc))
            return None

    def get_annonces_by_statut(self, statut: str, limit: int = 100) -> list[dict]:
        """Récupère les annonces filtrées par statut, triées par score décroissant."""
        try:
            result = (
                self._client.table("annonces")
                .select("*")
                .eq("statut", statut)
                .order("score", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            logger.error("get_annonces_failed", statut=statut, error=str(exc))
            return []

    def url_already_exists(self, url: str) -> bool:
        """Vérifie si une annonce avec cette URL existe déjà en base."""
        try:
            result = (
                self._client.table("annonces")
                .select("id")
                .eq("url_annonce", url)
                .execute()
            )
            return len(result.data or []) > 0
        except Exception:
            return False

    def get_urls_seen(self, urls: list[str]) -> set[str]:
        """
        Retourne le sous-ensemble d'URLs qui existent déjà en base.
        Plus efficace que de faire un appel par URL.
        """
        if not urls:
            return set()
        try:
            result = (
                self._client.table("annonces")
                .select("url_annonce")
                .in_("url_annonce", urls)
                .execute()
            )
            return {row["url_annonce"] for row in (result.data or [])}
        except Exception as exc:
            logger.error("get_urls_seen_failed", error=str(exc))
            return set()

    # ------------------------------------------------------------------
    # Critères de recherche
    # ------------------------------------------------------------------

    def get_criteres_actifs(self) -> list[CritereRecherche]:
        """Récupère tous les critères de recherche actifs."""
        try:
            result = (
                self._client.table("criteres_recherche")
                .select("*")
                .eq("actif", True)
                .order("priorite", desc=True)
                .execute()
            )
            return [CritereRecherche(**row) for row in (result.data or [])]
        except Exception as exc:
            logger.error("get_criteres_failed", error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Notifications anti-doublon
    # ------------------------------------------------------------------

    def mark_notification_sent(self, annonce_id: str, canal: str) -> None:
        """Enregistre qu'une notification a été envoyée pour cette annonce."""
        try:
            self._client.table("notifications_envoyees").insert({
                "annonce_id": annonce_id,
                "canal": canal,
            }).execute()
        except Exception as exc:
            logger.error("mark_notification_failed", annonce_id=annonce_id, error=str(exc))

    def annonce_already_notified(self, annonce_id: str, canal: str) -> bool:
        """Vérifie si une notification a déjà été envoyée pour cette annonce sur ce canal."""
        try:
            result = (
                self._client.table("notifications_envoyees")
                .select("id")
                .eq("annonce_id", annonce_id)
                .eq("canal", canal)
                .execute()
            )
            return len(result.data or []) > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Heartbeat (keep-alive Supabase Free)
    # ------------------------------------------------------------------

    def heartbeat(self) -> bool:
        """
        Requête légère pour garder le projet Supabase actif (évite la mise en pause).
        Appelé par le workflow keepalive.yml toutes les 3 jours.
        """
        try:
            self._client.table("criteres_recherche").select("id").limit(1).execute()
            logger.info("supabase_heartbeat_ok")
            return True
        except Exception as exc:
            logger.error("supabase_heartbeat_failed", error=str(exc))
            return False
