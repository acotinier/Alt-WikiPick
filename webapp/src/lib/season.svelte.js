// Le Season Pass : l'état lu une fois à l'ouverture de l'appli (un seul appel, comme le site), puis mis à jour par ce qu'on y fait.
// Le signal d'activité du site (qui rapporte de l'XP au temps passé) n'est volontairement PAS reproduit : voir docs/API.md.
import { call } from './api.js';

export const season = $state({ d: null, loading: false, error: '' });

export async function loadSeason(force = false) {
  if (season.loading || (season.d && !force)) return;
  season.loading = true;
  const r = await call('season_get');
  season.loading = false;
  if (r && r.ok) { season.d = r; season.error = ''; }
  else if (r && !r.expired) season.error = r.error || 'Season Pass indisponible pour le moment.';
}

// progression vers le niveau suivant, de 0 à 1 (1 au niveau maximum)
export const levelProgress = (d) => {
  if (!d) return 0;
  const { xp, xp_level: a, xp_next: b } = d.me;
  return !b ? 1 : Math.max(0, Math.min(1, (xp - a) / Math.max(1, b - a)));
};

// ce qu'un joueur peut faire d'un niveau : prise, réservé aux abonnés, atteint, ou encore verrouillé
export const levelState = (d, item) => {
  const reached = Math.min(item.level, d.season.levels) <= d.me.level;
  if (d.me.taken.includes(item.level)) return 'taken';
  if (!d.season.free.includes(item.level) && !d.me.subscriber) return 'reserved';
  if (!reached) return 'locked';
  if (item.kind === 'carte' && !item.card) return 'soon';
  return 'ready';
};
