// Tous les appels vers le serveur. Un seul point d'entrée : `call('méthode', ...args)` (les mêmes méthodes que l'appli de bureau).
const MOCK = import.meta.env.VITE_MOCK;
let mock = null;
const loadMock = () => (mock ||= import('./mock.js'));

let onExpired = () => {};
export const setExpiredHandler = (fn) => { onExpired = fn; };

async function json(path, init) {
  let r;
  try {
    r = await fetch(path, { credentials: 'same-origin', ...init });
  } catch {
    return { ok: false, error: 'Réseau indisponible : vérifie ta connexion.' };
  }
  let data;
  try { data = await r.json(); } catch { data = { ok: false, error: `Erreur du serveur (${r.status}).` }; }
  return data;
}

export async function call(method, ...args) {
  if (MOCK) return (await loadMock()).rpc(method, args);
  const data = await json(`/api/rpc/${method}`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ args }) });
  if (data && data.expired) onExpired(data);
  return data;
}

const post = (path, body) => json(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body || {}) });

export const auth = {
  async me() { return MOCK ? (await loadMock()).auth('me') : json('/api/auth/me'); },
  async challenge() { return MOCK ? (await loadMock()).auth('challenge') : json('/api/auth/challenge'); },
  async login(body) { return MOCK ? (await loadMock()).auth('login', body) : post('/api/auth/login', body); },
  async logout() { return MOCK ? (await loadMock()).auth('logout') : post('/api/auth/logout'); },
};

// ---- temps réel : UNE connexion SSE, fermée quand l'onglet est caché longtemps (un téléphone en poche ne consomme rien) ----
const HIDDEN_CLOSE_MS = 45000;

export function connectEvents({ onState, onEvent, onResume }) {
  let es = null, hiddenTimer = null, stopped = false;
  const open = () => {
    if (es || stopped) return;
    if (MOCK) { loadMock().then((m) => { if (!es && !stopped) es = m.events(onState, onEvent); }); return; }
    es = new EventSource('/api/events');
    es.addEventListener('live', (e) => onState(JSON.parse(e.data)));
    es.addEventListener('msg', (e) => { try { onEvent(JSON.parse(e.data)); } catch { /* message illisible : ignoré */ } });
    es.onerror = () => onState('down'); // EventSource se reconnecte seul
  };
  const close = () => { if (es) { es.close && es.close(); es = null; } onState('down'); };
  const visibility = () => {
    if (document.hidden) {
      hiddenTimer = setTimeout(close, HIDDEN_CLOSE_MS);
    } else {
      clearTimeout(hiddenTimer);
      if (!es) { open(); onResume(); } // retour après une longue absence : on relit ce qui compte
    }
  };
  document.addEventListener('visibilitychange', visibility);
  open();
  return () => { stopped = true; clearTimeout(hiddenTimer); document.removeEventListener('visibilitychange', visibility); close(); };
}
