// Routeur minimal par hash : #/section/sous-page/paramètre. Aucune dépendance.
export const route = $state({ path: '/collection', parts: ['collection'] });

function parse() {
  let h = decodeURIComponent((location.hash || '').replace(/^#/, '')) || '/collection';
  if (!h.startsWith('/')) h = '/' + h;
  route.path = h.split('?')[0];
  route.parts = route.path.split('/').filter(Boolean);
}

export function startRouter() {
  parse();
  addEventListener('hashchange', parse);
}

export const go = (path, replace = false) => {
  const target = '#' + path.split('/').map((p, i) => (i ? encodeURIComponent(p) : p)).join('/');
  if (replace) history.replaceState(null, '', target), parse();
  else location.hash = target;
};

// Sections de l'appli : 5 onglets en bas (mobile) ou dans la colonne de gauche (grand écran).
export const SECTIONS = [
  { id: 'collection', label: 'Collection', icon: 'cards', to: '/collection' },
  { id: 'packs', label: 'Paquets', icon: 'pack', to: '/packs' },
  { id: 'market', label: 'Marché', icon: 'gavel', to: '/market/auctions',
    subs: [['auctions', 'Enchères'], ['trades', 'Échanges']] },
  { id: 'social', label: 'Social', icon: 'users', to: '/social/messages',
    subs: [['messages', 'Messages'], ['friends', 'Amis'], ['guild', 'Guilde'], ['arena', 'Arène']] },
  { id: 'me', label: 'Moi', icon: 'user', to: '/me/profile',
    subs: [['profile', 'Profil'], ['rewards', 'Récompenses'], ['rank', 'Classement'], ['stats', 'Stats']] },
];
