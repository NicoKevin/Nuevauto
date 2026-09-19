export default function FiltersSidebar({
  user,
  filters,
  onFilterChange,
  marques,
  onLogout,
}) {
  const statusOptions = ['tous', 'nouveau', 'qualifie', 'traite', 'ignore'];

  return (
    <aside className="sidebar">
      {/* ── Brand ──────────────────────────── */}
      <div className="sidebar-header">
        <h1>Nuevauto</h1>
        <p>Dashboard Commercial</p>
      </div>

      {/* ── Status Filter ──────────────────── */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">Statut</div>
        <div className="status-filters">
          {statusOptions.map((s) => (
            <button
              key={s}
              className={`status-btn ${filters.statut === s ? 'active' : ''}`}
              data-status={s}
              onClick={() => onFilterChange('statut', s)}
            >
              {s === 'tous' ? '🔍 Tous' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* ── Search ─────────────────────────── */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">Recherche</div>
        <div className="filter-group">
          <input
            type="text"
            className="filter-input"
            placeholder="Rechercher marque, modèle…"
            value={filters.search}
            onChange={(e) => onFilterChange('search', e.target.value)}
          />
        </div>
      </div>

      {/* ── Filters ────────────────────────── */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">Filtres</div>

        <div className="filter-group">
          <label>Marque</label>
          <select
            className="filter-select"
            value={filters.marque}
            onChange={(e) => onFilterChange('marque', e.target.value)}
          >
            <option value="">Toutes les marques</option>
            {marques.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Énergie</label>
          <select
            className="filter-select"
            value={filters.energie}
            onChange={(e) => onFilterChange('energie', e.target.value)}
          >
            <option value="">Toutes</option>
            <option value="essence">Essence</option>
            <option value="diesel">Diesel</option>
            <option value="electrique">Électrique</option>
            <option value="hybride">Hybride</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Prix max</label>
          <input
            type="number"
            className="filter-input"
            placeholder="Ex: 15000"
            value={filters.prixMax}
            onChange={(e) => onFilterChange('prixMax', e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>Km max</label>
          <input
            type="number"
            className="filter-input"
            placeholder="Ex: 100000"
            value={filters.kmMax}
            onChange={(e) => onFilterChange('kmMax', e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>Tri</label>
          <select
            className="filter-select"
            value={filters.sort}
            onChange={(e) => onFilterChange('sort', e.target.value)}
          >
            <option value="date_collecte-desc">Plus récentes</option>
            <option value="prix-asc">Prix croissant</option>
            <option value="prix-desc">Prix décroissant</option>
            <option value="kilometrage-asc">Km croissant</option>
          </select>
        </div>
      </div>

      {/* ── User ───────────────────────────── */}
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-user-avatar">
            {user?.email?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-email">{user?.email}</div>
          </div>
          <button className="btn-logout" onClick={onLogout} title="Déconnexion">
            ⏻
          </button>
        </div>
      </div>
    </aside>
  );
}
