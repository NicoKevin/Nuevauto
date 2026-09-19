-- =============================================================================
-- Nuevauto — Migration 0002 : ajout des colonnes véhicule détaillées
-- Données extraites de la section "Les informations clés" de LeBonCoin
-- =============================================================================

ALTER TABLE annonces ADD COLUMN IF NOT EXISTS energie         TEXT;  -- Essence, Diesel, Hybride, Électrique, GPL
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS boite_vitesse   TEXT;  -- Manuelle, Automatique
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS type_vehicule   TEXT;  -- Berline, SUV, Break, Citadine, etc.
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS couleur         TEXT;  -- Noir, Blanc, Gris, etc.
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS nb_portes       INTEGER;
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS nb_places       INTEGER;
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS puissance_fiscale INTEGER;  -- CV fiscaux
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS puissance_din   TEXT;      -- Ex: "110 Ch"
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS finition        TEXT;      -- Ex: "GT Line", "Allure", "Edition One"
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS version         TEXT;      -- Ex: "1.6 HDi 110", "2.0 TDI 150"
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS ct_ok           BOOLEAN;   -- Contrôle technique OK ?
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS crit_air        TEXT;      -- Crit'Air 1, 2, 3...
ALTER TABLE annonces ADD COLUMN IF NOT EXISTS date_mise_circulation TEXT; -- "03/2019"

-- Index pour les filtres du dashboard
CREATE INDEX IF NOT EXISTS idx_annonces_energie ON annonces(energie);
CREATE INDEX IF NOT EXISTS idx_annonces_boite   ON annonces(boite_vitesse);

COMMENT ON COLUMN annonces.energie IS 'Type de carburant : Essence, Diesel, Hybride, Électrique, GPL';
COMMENT ON COLUMN annonces.boite_vitesse IS 'Type de boîte : Manuelle ou Automatique';
COMMENT ON COLUMN annonces.finition IS 'Niveau de finition du véhicule (ex: GT Line, Allure)';
COMMENT ON COLUMN annonces.version IS 'Version technique du véhicule (ex: 1.6 HDi 110)';
COMMENT ON COLUMN annonces.ct_ok IS 'Contrôle technique valide au moment du scraping';
