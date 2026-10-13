// Le Season Pass : l'état lu une fois à l'ouverture de l'appli (un seul appel, comme le site), puis mis à jour par ce qu'on y fait.
// L'XP au temps passé : comme le site, un signal n'est envoyé que si le joueur a réellement touché l'écran depuis le précédent (clic, touche, molette,
// doigt), onglet visible, au plus une fois par tranche (le serveur la fixe, 5 minutes par défaut). Le serveur du jeu décide de l'XP.
import { call } from './api.js';
import { app, toast } from './store.svelte.js';

export const season = $state({ d: null, loading: false, error: '' });

export async function loadSeason(force = false) {
  if (season.loading || (season.d && !force)) return;
  season.loading = true;
  const r = await call('season_get');
  season.loading = false;
  if (r && r.ok) { season.d = r; season.error = ''; }
  else if (r && !r.expired) season.error = r.error || 'Season Pass indisponible pour le moment.';
}

let touched = false, after = 0, busy = false, timer = 0, lastLevel = null, who = null;
const touch = () => { touched = true; };
async function signal() {
  const now = Date.now();
  if (busy || !touched || document.visibilityState !== 'visible' || now < after || app.phase !== 'app') return;
  if (who !== app.name) { who = app.name; lastLevel = null; after = 0; }
  busy = true; touched = false;
  after = now + 60000;
  try {
    const r = await call('season_active');
    if (!r || !r.ok) return;
    if (!r.sent) { after = now + (r.wait || 60) * 1000; touched = true; return; } // trop tôt pour le serveur local : le geste compte toujours
    after = now + r.wait * 1000;
    if (!r.open) { touched = true; return; }
    if (lastLevel != null && r.level > lastLevel) toast(`Season Pass : niveau ${r.level} atteint${r.to_take > 0 ? ' — une récompense t’attend.' : '.'}`, 'good');
    lastLevel = r.level;
    if (app.me) app.me.niveau = r.level;
    const m = season.d && season.d.me;   // l'affichage suit, sans relire /api/saison
    if (m) Object.assign(m, { level: r.level, xp: r.xp, xp_level: r.xp_level, xp_next: r.xp_next, subscriber: r.subscriber, active_minutes: r.active_minutes });
  } finally { busy = false; }
}
export function watchActivity() {
  if (timer) return;
  for (const t of ['pointerdown', 'keydown', 'wheel', 'touchstart']) addEventListener(t, touch, { capture: true, passive: true });
  timer = setInterval(signal, window.__actEvery || 20000); // (les tests raccourcissent l'attente)
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
