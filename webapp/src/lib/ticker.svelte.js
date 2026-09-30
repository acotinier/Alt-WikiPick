// Une seule horloge d'une seconde pour toute l'appli (comptes à rebours, « il y a… »), en pause quand l'onglet est caché.
export const tick = $state({ now: Date.now() });
setInterval(() => { if (!document.hidden) tick.now = Date.now(); }, 1000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) tick.now = Date.now(); });
