// Petit cache local (IndexedDB) : la collection s'affiche instantanément au lancement, puis se met à jour.
// Toujours facultatif : si le navigateur refuse (navigation privée…), l'appli marche sans.
const open = () => new Promise((resolve, reject) => {
  const r = indexedDB.open('altwp', 1);
  r.onupgradeneeded = () => r.result.createObjectStore('kv');
  r.onsuccess = () => resolve(r.result);
  r.onerror = () => reject(r.error);
});

async function tx(mode, fn) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction('kv', mode);
    const out = fn(t.objectStore('kv'));
    t.oncomplete = () => { db.close(); resolve(out && out.result); };
    t.onerror = t.onabort = () => { db.close(); reject(t.error); };
  });
}

export const idbGet = (key) => tx('readonly', (s) => s.get(key)).catch(() => undefined);
export const idbSet = (key, value) => tx('readwrite', (s) => s.put(value, key)).catch(() => {});
export const idbClear = () => tx('readwrite', (s) => s.clear()).catch(() => {});
