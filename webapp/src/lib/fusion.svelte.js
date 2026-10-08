// Le lot de fusions en cours, suivi une fois par seconde (appel local au serveur d'Alt-WikiPick, pas vers wiki-pick.com).
// C'est cette demande régulière qui garde le lot en vie côté serveur : sans elle, il s'arrête de lui-même. Elle vit ici, hors de
// l'écran Fusion, pour que le lot continue quand on regarde autre chose dans l'appli.
import { call } from './api.js';
import { collectionChanged, refreshMe } from './store.svelte.js';

export const fz = $state({ job: null });
let timer = 0;

const stop = () => { clearInterval(timer); timer = 0; };

async function poll() {
  const r = await call('fusion_job');
  if (!r || !r.ok) { if (r && r.expired) stop(); return; } // un raté réseau passager : on réessaie à la seconde suivante
  const wasRunning = !!(fz.job && fz.job.running);
  fz.job = r.job;
  if (!r.job || !r.job.running) {
    stop();
    if (wasRunning) { collectionChanged(); refreshMe(); }
  }
}

export function watchFusion() {
  if (!timer) { timer = setInterval(poll, 1000); poll(); }
}

// À l'ouverture de l'appli : un lot lancé depuis un autre appareil ou avant un rechargement est-il encore en route ?
export async function resumeFusion() {
  const r = await call('fusion_job');
  if (r && r.ok && r.job && r.job.running) { fz.job = r.job; watchFusion(); }
}

export const dismissFusion = () => { fz.job = null; };
