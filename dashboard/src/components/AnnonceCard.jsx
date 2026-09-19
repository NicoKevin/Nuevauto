export default function AnnonceCard({ annonce, onClick }) {
  const {
    marque,
    modele,
    annee,
    kilometrage,
    prix,
    ville,
    code_postal,
    energie,
    boite_vitesse,
    image_url,
    statut,
    url_annonce,
  } = annonce;

  const title = [marque, modele].filter(Boolean).join(' ') || 'Véhicule';
  const subtitle = [annee, ville && `${ville} (${code_postal || ''})`]
    .filter(Boolean)
    .join(' — ');

  const formatPrice = (p) => {
    if (!p) return '—';
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(p);
  };

  const formatKm = (km) => {
    if (!km) return null;
    return `${new Intl.NumberFormat('fr-FR').format(km)} km`;
  };

  const normalizeEnergy = (e) => {
    if (!e) return null;
    const lower = e.toLowerCase();
    if (lower.includes('electrique') || lower.includes('électrique')) return 'électrique';
    if (lower.includes('hybride')) return 'hybride';
    if (lower.includes('diesel')) return 'diesel';
    if (lower.includes('essence')) return 'essence';
    return lower;
  };

  const energyNorm = normalizeEnergy(energie);

  return (
    <article className="annonce-card" onClick={() => onClick?.(annonce)}>
      <div className="annonce-card-image">
        {image_url ? (
          <img src={image_url} alt={title} loading="lazy" />
        ) : (
          <div className="annonce-card-image-placeholder">🚗</div>
        )}
        <span
          className="annonce-card-status"
          data-status={statut || 'nouveau'}
        >
          {statut || 'nouveau'}
        </span>
        {prix && (
          <span className="annonce-card-price">{formatPrice(prix)}</span>
        )}
      </div>

      <div className="annonce-card-body">
        <h3 className="annonce-card-title">{title}</h3>
        <p className="annonce-card-subtitle">{subtitle}</p>

        <div className="annonce-card-tags">
          {energyNorm && (
            <span className="tag tag-energy" data-energy={energyNorm}>
              {energyNorm.charAt(0).toUpperCase() + energyNorm.slice(1)}
            </span>
          )}
          {boite_vitesse && (
            <span className="tag">
              {boite_vitesse}
            </span>
          )}
          {formatKm(kilometrage) && (
            <span className="tag">{formatKm(kilometrage)}</span>
          )}
          {annee && <span className="tag">{annee}</span>}
        </div>

        <div className="annonce-card-meta">
          <span className="annonce-card-location">
            {ville || '—'}
          </span>
          <a
            href={url_annonce}
            target="_blank"
            rel="noopener noreferrer"
            className="annonce-card-link"
            onClick={(e) => e.stopPropagation()}
          >
            Voir l'annonce ↗
          </a>
        </div>
      </div>
    </article>
  );
}
