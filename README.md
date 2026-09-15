# Nuevauto — Système de veille annonces automobiles

Système de veille et qualification d'annonces auto (LeBonCoin, La Centrale) pour faciliter la prospection commerciale de l'agence. Budget infra : **0€**.

## Architecture

```
GitHub Actions (cron 2x/jour)
  └─▶ scraper/ (Python)
        └─▶ Supabase PostgreSQL (Free)
              └─▶ dashboard/ (React — à venir Phase 2)
```

## Stack

| Composant | Techno |
|---|---|
| Scraper | Python 3.12 + httpx + BeautifulSoup4 |
| Base de données | Supabase (PostgreSQL Free) |
| Orchestration | GitHub Actions (cron) |
| Dashboard | React + Vite (Phase 2) |
| Notifications | Slack Webhooks |

## Démarrage rapide

### Prérequis
- Python 3.12+
- Compte Supabase (gratuit)
- GitHub Secrets configurés (voir [SETUP.md](docs/SETUP.md))

### Installation locale

```bash
cd scraper
pip install -e ".[dev]"
cp .env.example .env
# Remplir .env avec vos credentials Supabase
```

### Lancer les tests

```bash
cd scraper
python -m pytest tests/ -v
```

### Exécuter le scraper localement

```bash
cd scraper
python main.py --dry-run        # Test sans écrire en base
python main.py --source leboncoin  # LeBonCoin uniquement
python main.py                    # Toutes les sources
```

## Structure du projet

```
Nuevauto/
├── .github/workflows/    # CI + scraper + backup + keepalive
├── scraper/              # Package Python (collecteurs, ETL, DB)
├── supabase/migrations/  # Schema SQL versionné
├── dashboard/            # React (Phase 2)
└── docs/SETUP.md         # Guide de setup complet
```

## Configuration GitHub Secrets

| Secret | Description |
|---|---|
| `SUPABASE_URL` | URL du projet Supabase |
| `SUPABASE_SERVICE_KEY` | Clé service_role (accès total, backend uniquement) |
| `SLACK_WEBHOOK_URL` | URL du webhook Slack (optionnel) |

Voir [docs/SETUP.md](docs/SETUP.md) pour les instructions détaillées.

## Conformité & garde-fous

- ❌ Aucun champ téléphone/email dans le modèle de données
- ✅ Test anti-PII bloquant en CI (`tests/test_no_pii.py`)
- ✅ Rate limiting configuré (2s entre chaque requête)
- ✅ Logging de chaque collecte pour traçabilité
- ✅ Facebook Marketplace exclu du périmètre (risque légal)

Voir le [Plan d'ingénierie](Plan%20ingenierie%20veille%20annonces%20auto.MD) pour le contexte complet.