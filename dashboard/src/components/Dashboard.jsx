import { useState, useEffect, useMemo, useCallback } from 'react';
import { supabase } from '../lib/supabaseClient';
import AnnonceCard from './AnnonceCard';
import FiltersSidebar from './FiltersSidebar';
import QualificationPanel from './QualificationPanel';

export default function Dashboard({ user }) {
  const [annonces, setAnnonces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAnnonce, setSelectedAnnonce] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [filters, setFilters] = useState({
    statut: 'tous',
    search: '',
    marque: '',
    energie: '',
    prixMax: '',
    kmMax: '',
    sort: 'date_collecte-desc',
  });

  const [errorMsg, setErrorMsg] = useState(null);

  /* ── Fetch annonces from Supabase ──────────────────── */
  const fetchAnnonces = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    const { data, error } = await supabase
      .from('annonces')
      .select('*')
      .order('date_collecte', { ascending: false });

    if (error) {
      console.error('Erreur chargement annonces:', error);
      setErrorMsg(error.message || JSON.stringify(error));
    } else {
      setAnnonces(data || []);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAnnonces();
  }, [fetchAnnonces]);

  /* ── Handle filter changes ─────────────────────────── */
  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  /* ── Derived: unique marques ───────────────────────── */
  const marques = useMemo(() => {
    const set = new Set();
    annonces.forEach((a) => {
      if (a.marque) set.add(a.marque);
    });
    return [...set].sort();
  }, [annonces]);

  /* ── Derived: filtered & sorted annonces ───────────── */
  const filteredAnnonces = useMemo(() => {
    let result = [...annonces];

    // Status filter
    if (filters.statut !== 'tous') {
      result = result.filter((a) => a.statut === filters.statut);
    }

    // Text search
    if (filters.search) {
      const q = filters.search.toLowerCase();
      result = result.filter(
        (a) =>
          (a.marque && a.marque.toLowerCase().includes(q)) ||
          (a.modele && a.modele.toLowerCase().includes(q)) ||
          (a.description && a.description.toLowerCase().includes(q)) ||
          (a.ville && a.ville.toLowerCase().includes(q))
      );
    }

    // Marque filter
    if (filters.marque) {
      result = result.filter((a) => a.marque === filters.marque);
    }

    // Energie filter
    if (filters.energie) {
      const e = filters.energie.toLowerCase();
      result = result.filter(
        (a) => a.energie && a.energie.toLowerCase().includes(e)
      );
    }

    // Prix max
    if (filters.prixMax) {
      const max = parseFloat(filters.prixMax);
      result = result.filter((a) => a.prix && a.prix <= max);
    }

    // Km max
    if (filters.kmMax) {
      const max = parseFloat(filters.kmMax);
      result = result.filter((a) => a.kilometrage && a.kilometrage <= max);
    }

    // Sort
    const [sortField, sortDir] = filters.sort.split('-');
    result.sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (sortDir === 'asc') return aVal > bVal ? 1 : -1;
      return aVal < bVal ? 1 : -1;
    });

    return result;
  }, [annonces, filters]);

  /* ── Counts ────────────────────────────────────────── */
  const counts = useMemo(() => {
    const c = { total: annonces.length, nouveau: 0, qualifie: 0, traite: 0, ignore: 0 };
    annonces.forEach((a) => {
      if (c[a.statut] !== undefined) c[a.statut]++;
    });
    return c;
  }, [annonces]);

  /* ── Handle annonce updated (from qualification panel) */
  const handleAnnonceUpdated = (updated) => {
    setAnnonces((prev) =>
      prev.map((a) => (a.id === updated.id ? { ...a, ...updated } : a))
    );
    setSelectedAnnonce(null);
  };

  /* ── Logout ────────────────────────────────────────── */
  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="app-layout">
      {/* Mobile menu toggle */}
      <button
        className="btn-icon"
        style={{
          position: 'fixed',
          top: 16,
          left: 16,
          zIndex: 200,
          display: 'none',
        }}
        onClick={() => setSidebarOpen(!sidebarOpen)}
        id="mobile-menu-toggle"
      >
        ☰
      </button>

      <style>{`
        @media (max-width: 1024px) {
          #mobile-menu-toggle { display: flex !important; }
        }
      `}</style>

      {/* Sidebar */}
      <FiltersSidebar
        user={user}
        filters={filters}
        onFilterChange={handleFilterChange}
        marques={marques}
        onLogout={handleLogout}
      />

      {/* Sidebar overlay on mobile */}
      {sidebarOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            zIndex: 99,
          }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="main-content">
        <div className="topbar">
          <h2>Annonces</h2>
          <div className="topbar-stats">
            <span className="stat-chip">
              Total <span className="count">{counts.total}</span>
            </span>
            <span className="stat-chip">
              Affichées <span className="count">{filteredAnnonces.length}</span>
            </span>
            <span className="stat-chip">
              🆕 <span className="count">{counts.nouveau}</span>
            </span>
            <span className="stat-chip">
              ✅ <span className="count">{counts.traite}</span>
            </span>
          </div>
        </div>

        {errorMsg ? (
          <div className="login-error" style={{ marginBottom: '20px' }}>
            Erreur Supabase : {errorMsg}
          </div>
        ) : filteredAnnonces.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <h3>Aucune annonce trouvée</h3>
            <p>Essayez de modifier les filtres ou de lancer un nouveau scraping.</p>
          </div>
        ) : (
          <div className="annonces-grid">
            {filteredAnnonces.map((annonce) => (
              <AnnonceCard
                key={annonce.id}
                annonce={annonce}
                onClick={setSelectedAnnonce}
              />
            ))}
          </div>
        )}
      </main>

      {/* Qualification Modal */}
      {selectedAnnonce && (
        <QualificationPanel
          annonce={selectedAnnonce}
          onClose={() => setSelectedAnnonce(null)}
          onUpdated={handleAnnonceUpdated}
        />
      )}
    </div>
  );
}
