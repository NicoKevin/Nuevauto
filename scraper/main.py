"""
Point d'entrée principal du scraper Nuevauto.
Exécuté par GitHub Actions via le workflow scraper.yml.

Usage:
    python main.py                    # Run complet (toutes sources actives)
    python main.py --heartbeat        # Heartbeat Supabase uniquement (keepalive)
    python main.py --source leboncoin # Source spécifique uniquement
    python main.py --dry-run          # Scrape mais n'écrit pas en base
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import structlog
from dotenv import load_dotenv

# Chargement des variables d'environnement depuis .env en local
# En GitHub Actions, les secrets sont injectés directement dans l'environnement
load_dotenv()

from config.settings import AppConfig
from collectors.leboncoin import LeBonCoinCollector
from db.client import SupabaseClient
from db.models import Statut
from etl.normalize import normalize_annonce
from etl.scoring import score_annonce

# Configuration du logging structuré (JSON pour CI, humain-lisible en local)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer() if sys.stdout.isatty() else structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger(__name__)


def run_scraper(config: AppConfig, source: str | None = None, dry_run: bool = False) -> dict:
    """
    Lance le pipeline complet : collect → normalize → score → upsert.

    Retourne un dict de statistiques (inséré, mis à jour, ignoré, erreurs).
    """
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0, "start": datetime.now(tz=timezone.utc).isoformat()}

    db = SupabaseClient(config.supabase)
    criteres = db.get_criteres_actifs()

    if not criteres:
        logger.warning("no_active_criteria", msg="Aucun critère de recherche actif. Ajoutez des critères dans Supabase.")

    # Sélection des collecteurs à exécuter
    collectors_to_run = []
    if source is None or source == "leboncoin":
        collectors_to_run.append(LeBonCoinCollector(config.scraper))

    logger.info("scraper_start", sources=[c.source_name for c in collectors_to_run], dry_run=dry_run)

    for collector in collectors_to_run:
        with collector:
            for raw_annonce in collector.collect():
                try:
                    # Normalisation
                    annonce = normalize_annonce(raw_annonce)
                    if annonce is None:
                        stats["skipped"] += 1
                        continue

                    # Scoring
                    score, critere_id = score_annonce(annonce, criteres)
                    annonce = annonce.model_copy(update={
                        "score": score,
                        "critere_id": critere_id,
                        "statut": Statut.QUALIFIE if score >= config.score_notification_threshold else Statut.NOUVEAU,
                    })

                    if dry_run:
                        logger.info("dry_run_annonce", url=annonce.url_annonce, score=score)
                        stats["inserted"] += 1
                        continue

                    # Insertion/mise à jour en base
                    result = db.upsert_annonce(annonce)
                    if result:
                        stats["inserted"] += 1
                    else:
                        stats["errors"] += 1

                except Exception as exc:
                    logger.error("pipeline_error", url=getattr(raw_annonce, "url_annonce", "?"), error=str(exc))
                    stats["errors"] += 1

    stats["end"] = datetime.now(tz=timezone.utc).isoformat()
    logger.info("scraper_done", **stats)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Nuevauto — Scraper d'annonces automobiles")
    parser.add_argument("--heartbeat", action="store_true", help="Heartbeat Supabase uniquement")
    parser.add_argument("--source", choices=["leboncoin", "lacentrale"], help="Source à scraper")
    parser.add_argument("--dry-run", action="store_true", help="Scrape sans écrire en base")
    args = parser.parse_args()

    try:
        config = AppConfig.from_env()
    except ValueError as exc:
        logger.error("config_error", error=str(exc))
        return 1

    if args.heartbeat:
        db = SupabaseClient(config.supabase)
        ok = db.heartbeat()
        return 0 if ok else 1

    stats = run_scraper(config, source=args.source, dry_run=args.dry_run)
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
