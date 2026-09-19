import { useState } from 'react';
import { supabase } from '../lib/supabaseClient';

const STATUT_OPTIONS = ['nouveau', 'qualifie', 'traite', 'ignore'];

export default function QualificationPanel({ annonce, onClose, onUpdated }) {
  const [statut, setStatut] = useState(annonce.statut || 'nouveau');
  const [notes, setNotes] = useState(annonce.notes_commerciales || '');
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  const formatPrice = (p) => {
    if (!p) return '—';
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(p);
  };

  const formatKm = (km) => {
    if (!km) return '—';
    return `${new Intl.NumberFormat('fr-FR').format(km)} km`;
  };

  const handleSave = async () => {
    setSaving(true);
    const { error } = await supabase
      .from('annonces')
      .update({
        statut,
        notes_commerciales: notes,
        date_mise_a_jour: new Date().toISOString(),
      })
      .eq('id', annonce.id);

    if (error) {
      setToast({ type: 'error', message: 'Erreur lors de la sauvegarde' });
    } else {
      setToast({ type: 'success', message: 'Annonce mise à jour ✓' });
      onUpdated?.({ ...annonce, statut, notes_commerciales: notes });
      setTimeout(() => onClose(), 800);
    }
    setSaving(false);
    setTimeout(() => setToast(null), 3000);
  };

  const title = [annonce.marque, annonce.modele].filter(Boolean).join(' ') || 'Véhicule';

  const details = [
    { label: 'Marque', value: annonce.marque },
    { label: 'Modèle', value: annonce.modele },
    { label: 'Année', value: annonce.annee },
    { label: 'Kilométrage', value: formatKm(annonce.kilometrage) },
    { label: 'Prix', value: formatPrice(annonce.prix) },
    { label: 'Énergie', value: annonce.energie },
    { label: 'Boîte', value: annonce.boite_vitesse },
    { label: 'Finition', value: annonce.finition },
    { label: 'Couleur', value: annonce.couleur },
    { label: 'Ville', value: annonce.ville },
    { label: 'CT OK', value: annonce.ct_ok != null ? (annonce.ct_ok ? 'Oui ✅' : 'Non ❌') : null },
    { label: "Crit'Air", value: annonce.crit_air },
  ].filter((d) => d.value);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-panel glass-strong"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div>
            <h3>{title}</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
              {annonce.annee} — {annonce.ville}
            </p>
          </div>
          <button className="modal-close" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Image */}
        {annonce.image_url && (
          <div
            style={{
              borderRadius: 'var(--radius-md)',
              overflow: 'hidden',
              marginBottom: '24px',
              maxHeight: '250px',
            }}
          >
            <img
              src={annonce.image_url}
              alt={title}
              style={{ width: '100%', height: '250px', objectFit: 'cover' }}
            />
          </div>
        )}

        {/* Details Grid */}
        <div className="modal-detail-grid">
          {details.map((d) => (
            <div className="detail-item" key={d.label}>
              <div className="detail-item-label">{d.label}</div>
              <div className="detail-item-value">{d.value}</div>
            </div>
          ))}
        </div>

        {/* Lien annonce */}
        <div style={{ marginBottom: '24px' }}>
          <a
            href={annonce.url_annonce}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary btn-sm"
            style={{ display: 'inline-flex' }}
          >
            Voir sur LeBonCoin ↗
          </a>
        </div>

        {/* Qualification — Status */}
        <div className="qualification-section">
          <h4>Qualification</h4>
          <div className="status-select-group">
            {STATUT_OPTIONS.map((s) => (
              <button
                key={s}
                className={`status-option ${statut === s ? 'selected' : ''}`}
                onClick={() => setStatut(s)}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div className="qualification-section">
          <h4>Notes commerciales</h4>
          <textarea
            className="notes-textarea"
            placeholder="Ajouter des notes pour le suivi de cette annonce…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>

        {/* Actions */}
        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Annuler
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={saving}
            style={{ width: 'auto' }}
          >
            {saving ? 'Sauvegarde…' : 'Sauvegarder'}
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`toast toast-${toast.type}`}>{toast.message}</div>
      )}
    </div>
  );
}
