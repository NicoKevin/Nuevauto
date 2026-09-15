-- =============================================================================
-- Nuevauto — Migration initiale
-- Système de veille & qualification d'annonces automobiles
-- =============================================================================
-- Aucun champ téléphone/email dans ce schéma — contrainte de design (voir §7 du plan)

-- -----------------------------------------------------------------------------
-- Table: criteres_recherche
-- Définie en premier car annonces y fait référence
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS criteres_recherche (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nom         TEXT NOT NULL,
    marque      TEXT,
    modele      TEXT,
    prix_min    NUMERIC(10, 2),
    prix_max    NUMERIC(10, 2),
    annee_min   INTEGER,
    annee_max   INTEGER,
    km_max      INTEGER,
    zone_geo    TEXT,        -- ex: "75,92,93,94" (codes départements) ou "Île-de-France"
    priorite    INTEGER NOT NULL DEFAULT 1 CHECK (priorite BETWEEN 1 AND 5),
    actif       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE criteres_recherche IS 'Critères de recherche configurés par les commerciaux. Utilisés pour scorer les annonces.';
COMMENT ON COLUMN criteres_recherche.priorite IS '1 = basse, 5 = critique';
COMMENT ON COLUMN criteres_recherche.zone_geo IS 'Codes département(s) séparés par virgule, ou nom de région';

-- -----------------------------------------------------------------------------
-- Table: annonces
-- Données scrapées — AUCUNE donnée personnelle (téléphone, email, nom)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS annonces (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source              TEXT NOT NULL CHECK (source IN ('leboncoin', 'lacentrale')),
    url_annonce         TEXT NOT NULL UNIQUE,
    marque              TEXT,
    modele              TEXT,
    annee               INTEGER,
    kilometrage         INTEGER,
    prix                NUMERIC(10, 2),
    ville               TEXT,
    code_postal         TEXT,
    description         TEXT,   -- Description brute de l'annonce (sans PII)
    image_url           TEXT,   -- URL de la première image (hébergée sur le site source)
    date_publication    TIMESTAMPTZ,
    date_collecte       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    date_mise_a_jour    TIMESTAMPTZ,
    hash_contenu        TEXT,   -- SHA256 du contenu normalisé (détection de mise à jour)
    statut              TEXT NOT NULL DEFAULT 'nouveau'
                            CHECK (statut IN ('nouveau', 'qualifie', 'notifie', 'traite', 'ignore')),
    score               NUMERIC(5, 2) NOT NULL DEFAULT 0,
    critere_id          UUID REFERENCES criteres_recherche(id) ON DELETE SET NULL,
    notes_commerciales  TEXT,   -- Notes libres saisies par le commercial via le dashboard
    traite_par          TEXT,   -- Identifiant du commercial qui a traité l'annonce
    traite_le           TIMESTAMPTZ
);

COMMENT ON TABLE annonces IS 'Annonces de vente de véhicules scrapées. Aucune PII (téléphone, email, nom) ne doit apparaître dans cette table.';
COMMENT ON COLUMN annonces.hash_contenu IS 'SHA256 du contenu normalisé. Permet de détecter les mises à jour de prix ou de description.';
COMMENT ON COLUMN annonces.score IS 'Score de pertinence calculé par le moteur de scoring ETL (0-100).';
COMMENT ON COLUMN annonces.statut IS 'Workflow: nouveau -> qualifie -> notifie -> traite/ignore';

-- -----------------------------------------------------------------------------
-- Table: notifications_envoyees
-- Anti-doublon : empêche d'envoyer deux fois la même alerte pour la même annonce
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications_envoyees (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    annonce_id  UUID NOT NULL REFERENCES annonces(id) ON DELETE CASCADE,
    canal       TEXT NOT NULL CHECK (canal IN ('slack', 'email', 'digest')),
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE notifications_envoyees IS 'Historique des notifications envoyées. Utilisé pour éviter les doublons.';

-- -----------------------------------------------------------------------------
-- Indexes — performance des requêtes dashboard + scraper
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_annonces_statut       ON annonces(statut);
CREATE INDEX IF NOT EXISTS idx_annonces_source       ON annonces(source);
CREATE INDEX IF NOT EXISTS idx_annonces_score        ON annonces(score DESC);
CREATE INDEX IF NOT EXISTS idx_annonces_date_collecte ON annonces(date_collecte DESC);
CREATE INDEX IF NOT EXISTS idx_annonces_code_postal  ON annonces(code_postal);
CREATE INDEX IF NOT EXISTS idx_annonces_marque_modele ON annonces(marque, modele);
CREATE INDEX IF NOT EXISTS idx_annonces_prix         ON annonces(prix);
CREATE INDEX IF NOT EXISTS idx_notifs_annonce        ON notifications_envoyees(annonce_id);

-- -----------------------------------------------------------------------------
-- Trigger: mise à jour automatique de updated_at sur criteres_recherche
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_criteres
    BEFORE UPDATE ON criteres_recherche
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_updated_at();

-- -----------------------------------------------------------------------------
-- Row Level Security (RLS)
-- On active RLS sur toutes les tables.
-- Le scraper utilise la service_role key (bypass RLS) — accès total côté serveur.
-- Le dashboard utilise la anon key — soumis aux policies ci-dessous.
-- Pour une V1 simple sans auth utilisateur, on ouvre en lecture/écriture à anon.
-- À restreindre avec Supabase Auth si on ajoute des comptes commerciaux.
-- -----------------------------------------------------------------------------
ALTER TABLE annonces              ENABLE ROW LEVEL SECURITY;
ALTER TABLE criteres_recherche    ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications_envoyees ENABLE ROW LEVEL SECURITY;

-- Policy V1 : accès lecture/écriture pour tous (dashboard interne sans auth)
-- À remplacer par des policies basées sur auth.uid() quand on ajoute Supabase Auth
CREATE POLICY "allow_all_annonces" ON annonces
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "allow_all_criteres" ON criteres_recherche
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "allow_all_notifications" ON notifications_envoyees
    FOR ALL USING (true) WITH CHECK (true);

-- -----------------------------------------------------------------------------
-- Données de seed — critères de recherche initiaux (exemples)
-- À adapter selon les besoins réels de l'agence
-- -----------------------------------------------------------------------------
INSERT INTO criteres_recherche (nom, marque, modele, prix_min, prix_max, annee_min, km_max, zone_geo, priorite, actif)
VALUES
    ('Renault Clio récente - IDF', 'Renault', 'Clio', 3000, 12000, 2018, 100000, '75,92,93,94,78,91,95,77', 3, true),
    ('Peugeot 208 - IDF', 'Peugeot', '208', 4000, 14000, 2018, 100000, '75,92,93,94,78,91,95,77', 3, true),
    ('Volkswagen Golf - National', 'Volkswagen', 'Golf', 5000, 18000, 2016, 150000, NULL, 2, true),
    ('SUV compact - Budget serré', NULL, NULL, 6000, 20000, 2017, 120000, '75,92,93,94', 4, true)
ON CONFLICT DO NOTHING;
