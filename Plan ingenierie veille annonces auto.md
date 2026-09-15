# Plan d'ingénierie — Système de veille & qualification d'annonces automobiles

**Destinataire** : Antigravity IDE (agent de développement)
**Auteur** : Spécification produite avec Claude

---

## 1. Contexte & objectif métier

L'agence souhaite identifier rapidement les particuliers qui mettent un véhicule en vente sur LeBonCoin, La Centrale et Facebook Marketplace, afin qu'un commercial humain puisse les contacter pour proposer un rachat rapide et/ou une mise en relation avec un acheteur.

**Reformulation du besoin (suite à l'échange précédent) :**
Le système ne doit **pas** extraire automatiquement les coordonnées personnelles (téléphone/email) des particuliers ni leur envoyer un message automatisé. À la place, il doit :

1. Collecter les **métadonnées publiques** des annonces (marque, modèle, année, kilométrage, prix, ville, date de publication, lien de l'annonce).
2. Scorer/filtrer ces annonces selon des critères métier (véhicules recherchés par vos clients, zone géographique, fourchette de prix).
3. Notifier une **équipe humaine** (dashboard interne + Slack/email) qui décide qui contacter et comment, manuellement, via l'annonce elle-même (messagerie native de la plateforme) ou après avoir obtenu le contact autrement.

C'est un système d'**aide à la prospection**, pas un système de **prospection automatisée**.

---

## 2. Périmètre

### Dans le périmètre
- Scraping des pages de résultats et fiches annonces (données publiques, non nominatives) sur LeBonCoin Auto et La Centrale.
- Normalisation, dédoublonnage, stockage en base.
- Moteur de scoring/matching contre une liste de "véhicules recherchés" (definie par vos commerciaux).
- Dashboard interne pour visualiser, filtrer, marquer le statut ("à traiter", "contacté", "converti", "ignoré").
- Notifications internes (Slack/email) quand une annonce correspond à un critère prioritaire.
- Historisation et anti-doublon (ne pas re-notifier deux fois la même annonce).

### Hors périmètre (explicitement exclu)
- Contournement de systèmes anti-bot avancés (CAPTCHA solving, empreintes navigateur falsifiées, comptes factices).
- Facebook Marketplace en V1 (voir §8 — Facebook restreint fortement l'accès non-officiel à ces données ; à traiter séparément avec une validation légale renforcée, ou à écarter au profit de Meta Ads pour du reciblage publicitaire légitime).

### Gate obligatoire — Phase 0
Avant tout développement de la Phase 1, un point de validation légale/interne est requis :
- Décision sur la fréquence de collecte (pour rester "raisonnable" et limiter le risque de blocage IP/juridique).

---

## 3. Architecture générale

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│   Collecteurs    │────▶│  Pipeline ETL     │────▶│   Base de données   │
│ (LBC, LaCentrale)│     │ (normalisation,   │     │   PostgreSQL        │
│  scheduler cron  │     │  dédoublonnage,   │     │  (annonces, scores) │
└─────────────────┘     │  scoring)         │     └─────────┬──────────┘
                         └──────────────────┘               │
                                                             ▼
                          ┌──────────────────┐     ┌───────────────────┐
                          │  API backend      │◀───▶│  Dashboard interne │
                          │  (FastAPI)        │     │  (React)           │
                          └────────┬─────────┘     └───────────────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │ Notifications     │
                          │ (Slack, email)    │
                          └──────────────────┘
```

---

## 4. Modèle de données (simplifié)

**Table `annonces`**
| Champ | Type | Notes |
|---|---|---|
| id | UUID | clé primaire |
| source | enum | `leboncoin`, `lacentrale` |
| url_annonce | text | lien public, unique |
| marque, modele | text | |
| annee | int | |
| kilometrage | int | |
| prix | numeric | |
| ville, code_postal | text | |
| date_publication | timestamp | |
| date_collecte | timestamp | |
| hash_contenu | text | pour détecter les mises à jour |
| statut | enum | `nouveau`, `qualifie`, `notifie`, `traite`, `ignore` |

⚠️ **Aucun champ téléphone/email n'existe dans ce modèle — c'est une contrainte de design, pas un oubli.**

**Table `criteres_recherche`**
| Champ | Type |
|---|---|
| id | UUID |
| marque, modele | text |
| prix_min, prix_max | numeric |
| zone_geo | text/geojson |
| priorite | int |
| actif | bool |

**Table `notifications_envoyees`**
Historique des alertes déjà envoyées, pour éviter les doublons.

---

## 5. Composants détaillés

### 5.1 Collecteurs (scrapers)
- Un module par site, avec interface commune (`collect() -> List[Annonce]`).
- Respect d'un **rate limiting** raisonnable (ex: 1 requête toutes les X secondes, exécution planifiée hors heures de pointe).
- Parsing HTML avec sélecteurs isolés dans un fichier de config par site, pour faciliter la maintenance quand les sites changent leur structure (ça arrive souvent).
- Stockage du HTML brut désactivé par défaut (on ne garde que les champs normalisés) pour limiter les risques et le volume de données.

### 5.2 Pipeline ETL
- Déduplication via `url_annonce` + `hash_contenu`.
- Enrichissement : normalisation marque/modèle (référentiel type "Renault Clio" vs "RENAULT CLIO IV").
- Scoring : score = pondération (correspondance critère client, fraîcheur de l'annonce, écart prix marché).

### 5.3 API Backend (FastAPI)
- Endpoints CRUD sur `annonces`, `criteres_recherche`.
- Endpoint `/annonces?statut=nouveau&score_min=...` pour le dashboard.
- Endpoint `/annonces/{id}/statut` pour que le commercial mette à jour manuellement.

### 5.4 Dashboard interne (React)
- Vue liste/kanban par statut.
- Filtres (marque, prix, ville, score).
- Bouton "marquer comme contacté" (action manuelle, tracée avec l'utilisateur qui l'a faite).
- Lien direct vers l'annonce d'origine (le commercial contacte via la messagerie native du site, pas via un canal automatisé).

### 5.5 Notifications internes
- Slack webhook ou email quand une nouvelle annonce dépasse un score seuil.
- Digest quotidien récapitulatif plutôt que temps réel, pour éviter le bruit.

---

## 6. Stack technique recommandée

| Composant | Techno | Justification |
|---|---|---|
| Scraping | Python + Playwright (rendu JS) ou `httpx`/`BeautifulSoup` si pages statiques | Playwright gère les sites dynamiques (LBC utilise du JS) |
| Orchestration | Cron simple (V1) → Celery/Airflow (V2 si volume augmente) | Simplicité d'abord |
| Base de données | PostgreSQL | Robuste, bon support géo (PostGIS si besoin de zones) |
| Backend API | FastAPI (Python) | Cohérent avec l'écosystème scraping, rapide à développer |
| Frontend | React + Tailwind | Dashboard simple, itératif |
| Notifications | Slack SDK / SMTP | Standard |
| Déploiement | Docker Compose (V1) | Simplicité, un seul serveur suffit au départ |

---

## 7. Garde-fous techniques (compliance by design)

Ces règles doivent être codées en dur, pas laissées à la discrétion de l'utilisateur du dashboard :

1. **Aucun parseur ne doit extraire de champ correspondant à un téléphone ou un email**, même si la donnée est visible dans le HTML source. Ajouter un test automatisé qui échoue si un champ scrapé matche un pattern de téléphone/email (regex de contrôle en CI).
2. **Aucun module d'envoi de message vers le vendeur** ne doit exister dans le code (pas de SMTP/SMS sortant vers un contact extrait d'annonce).
3. Journalisation de chaque collecte (traçabilité en cas de contrôle).
4. Politique de rétention : purger les annonces après X jours si non traitées (évite l'accumulation de données inutiles).

---

## 8. Cas Facebook Marketplace

Facebook ne fournit pas d'API publique pour Marketplace, et le scraping y est activement détecté et bloqué (Meta a engagé des actions légales contre plusieurs scrapers par le passé). Je recommande de **ne pas inclure Facebook Marketplace dans le MVP**. Alternative plus durable : campagnes Meta Ads ciblant les intentions "vendre ma voiture", qui est un canal officiel et sans risque juridique. Si vous tenez à Facebook Marketplace, ça mérite une étude de faisabilité et une validation légale séparées avant d'y allouer du budget d'ingénierie.

---

## 9. Roadmap par phases

| Phase | Contenu | Durée estimée |
|---|---|---|
| **Phase 0** | Validation légale interne, définition des critères de recherche métier | 1 semaine |
| **Phase 1 — MVP** | Collecteur LeBonCoin uniquement, stockage, dashboard en lecture seule | 2-3 semaines |
| **Phase 2** | Ajout La Centrale, moteur de scoring, notifications Slack | 2 semaines |
| **Phase 3** | Dashboard interactif complet (statuts, filtres, historique) | 1-2 semaines |
| **Phase 4** | Analytics (taux de conversion par source/critère), ajustement du scoring | continu |
| **Phase 5 (optionnelle)** | Étude Facebook Marketplace ou API officielle LeBonCoin Pro / La Centrale Pro | à part |

---

## 10. Risques & mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Blocage IP par anti-bot | Interruption du service | Rate limiting raisonnable, pas de contournement agressif |
| Changement de structure HTML des sites | Scraper cassé | Tests automatisés qui alertent en cas d'échec de parsing |
| Action légale d'une plateforme (violation CGU) | Risque juridique/financier | Décision assumée en Phase 0, volumétrie raisonnable, pas de revente de données |
| Dérive vers extraction de PII (ajout futur non maîtrisé) | Risque RGPD/CNIL | Garde-fous techniques §7, revue de code obligatoire sur les parseurs |

---

## 11. Structure de repo suggérée pour Antigravity IDE

```
car-listing-tracker/
├── collectors/
│   ├── base.py
│   ├── leboncoin.py
│   └── lacentrale.py
├── etl/
│   ├── normalize.py
│   ├── dedupe.py
│   └── scoring.py
├── api/
│   ├── main.py (FastAPI)
│   ├── models.py
│   └── routes/
├── dashboard/
│   └── (React app)
├── notifications/
│   └── slack.py
├── tests/
│   ├── test_no_pii_extraction.py   ← test critique, voir §7
│   └── fixtures/ (pages HTML d'exemple pour tests de parsing)
├── docker-compose.yml
└── README.md
```

---

## 12. Prochaine étape

Une fois ce plan validé de votre côté (notamment la Phase 0), je peux vous aider à :
- Rédiger les specs détaillées de chaque module pour Antigravity IDE.
- Écrire le squelette de code (modèles de données, structure FastAPI, structure des collecteurs) — en évitant toute logique d'extraction de contact ou d'envoi automatisé, conformément au périmètre défini.