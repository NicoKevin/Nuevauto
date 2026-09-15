# Guide de setup — Nuevauto

Ce guide décrit les étapes à effectuer manuellement une seule fois pour démarrer le projet.

---

## 1. Supabase — Créer le schéma

1. Connectez-vous sur [supabase.com](https://supabase.com) → votre projet `nuevauto`
2. Allez dans **SQL Editor** (menu gauche)
3. Cliquez **New query**
4. Copiez-collez le contenu de [`supabase/migrations/0001_init.sql`](../supabase/migrations/0001_init.sql)
5. Cliquez **Run**

Vous devriez voir les tables `annonces`, `criteres_recherche`, `notifications_envoyees` apparaître dans **Table Editor**.

## 2. Supabase — Récupérer les credentials

1. Dans Supabase → **Settings** → **API**
2. Notez les valeurs suivantes (vous en aurez besoin à l'étape 3) :
   - **Project URL** : `https://VOTRE_ID.supabase.co`
   - **Secret key** (service_role) : `sb_secret_...`

> ⚠️ Ne jamais partager la `service_role key` publiquement. Elle bypass RLS et donne accès total à la base.

## 3. GitHub — Configurer les Secrets

1. Dans GitHub → votre repo `Nuevauto` → **Settings** → **Secrets and variables** → **Actions**
2. Cliquez **New repository secret** et ajoutez :

| Nom | Valeur |
|---|---|
| `SUPABASE_URL` | `https://VOTRE_ID.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Votre `sb_secret_...` |
| `SLACK_WEBHOOK_URL` | (optionnel) URL du webhook Slack |

## 4. Vérifier que GitHub Actions fonctionne

1. Allez dans **Actions** → **🧪 Tests CI** → **Run workflow**
2. Le workflow doit passer au vert (tests anti-PII + tests unitaires)

3. Allez dans **Actions** → **💓 Keepalive Supabase** → **Run workflow**
4. Doit passer au vert (heartbeat vers Supabase)

5. Pour tester le scraper sans écrire en base :
   - **Actions** → **🚗 Scraper Annonces** → **Run workflow**
   - Cocher **Dry run** → **Run workflow**

## 5. Test local (développement)

```bash
# 1. Cloner le repo
git clone https://github.com/VOTRE_USERNAME/Nuevauto.git
cd Nuevauto/scraper

# 2. Créer un environnement virtuel
python -m venv venv
venv\Scripts\activate  # Windows
# ou: source venv/bin/activate  # macOS/Linux

# 3. Installer les dépendances
pip install -e ".[dev]"

# 4. Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos vraies valeurs Supabase

# 5. Lancer les tests
python -m pytest tests/ -v

# 6. Lancer le scraper en dry-run
python main.py --dry-run
```

## 6. Ajouter des critères de recherche

Via l'interface **Table Editor** de Supabase → table `criteres_recherche` :

Des critères de base ont été insérés par la migration (exemples Île-de-France). 
Modifiez-les selon les besoins réels de l'agence :

| Champ | Description |
|---|---|
| `nom` | Label interne (ex: "Clio pour client Dupont") |
| `marque` | Marque exacte (ex: "Renault") |
| `modele` | Modèle (ex: "Clio") |
| `prix_min/max` | Fourchette de prix en € |
| `annee_min` | Année minimum |
| `km_max` | Kilométrage maximum |
| `zone_geo` | Codes département séparés par virgule (ex: "75,92,93") |
| `priorite` | 1 (basse) à 5 (critique) — influence le score |
| `actif` | `true` pour activer le critère |

---

## Troubleshooting

**Le scraper ne trouve pas d'annonces**
→ LeBonCoin a peut-être changé ses sélecteurs CSS. Vérifiez `scraper/config/selectors.yaml` et comparez avec le HTML réel de la page de résultats.

**Supabase est mis en pause**
→ Le workflow `keepalive.yml` tourne toutes les 3 jours. Si le projet a été inactif plus de 7 jours, réactivez-le manuellement dans le dashboard Supabase.

**GitHub Actions scheduled ne se déclenche pas**
→ Poussez un commit sur `main` pour "réveiller" le scheduler GitHub. Sur un repo public, ce problème ne devrait pas survenir.
