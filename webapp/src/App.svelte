<script>
  // La charpente : barre du haut (titre, portefeuille, cloche), onglets en bas sur mobile ou colonne à gauche sur grand écran,
  // sous-onglets du hub courant, et l'écran en cours chargé à la demande (le code d'un écran n'est téléchargé que lorsqu'on y va).
  import { SECTIONS, go, route, startRouter } from './lib/router.svelte.js';
  import { app, boot, refreshMe, toast, ui } from './lib/store.svelte.js';
  import { tick } from './lib/ticker.svelte.js';
  import { clock, compact, fmt } from './lib/format.js';
  import { rewardsReady } from './lib/rewards.js';
  import Icon from './ui/Icon.svelte';
  import Avatar from './ui/Avatar.svelte';
  import Seg from './ui/Seg.svelte';
  import Toasts from './ui/Toasts.svelte';
  import Login from './routes/Login.svelte';
  import CardSheet from './parts/CardSheet.svelte';
  import Notifications from './parts/Notifications.svelte';
  import AccountMenu from './parts/AccountMenu.svelte';
  import TradeComposer from './parts/TradeComposer.svelte';

  const VIEWS = {
    collection: () => import('./routes/Collection.svelte'),
    packs: () => import('./routes/Packs.svelte'),
    'market/auctions': () => import('./routes/Market.svelte'),
    'market/trades': () => import('./routes/Trades.svelte'),
    'social/messages': () => import('./routes/Messages.svelte'),
    'social/friends': () => import('./routes/Friends.svelte'),
    'social/guild': () => import('./routes/Guild.svelte'),
    'social/arena': () => import('./routes/Arena.svelte'),
    'me/profile': () => import('./routes/Profile.svelte'),
    'me/rewards': () => import('./routes/Rewards.svelte'),
    'me/rank': () => import('./routes/Rank.svelte'),
    'me/stats': () => import('./routes/Stats.svelte'),
  };
  const DEFAULT_SUB = { market: 'auctions', social: 'messages', me: 'profile' };

  const section = $derived(route.parts[0] === 'player' ? 'social' : route.parts[0] || 'collection');
  const sub = $derived(route.parts[0] === 'player' ? 'profile' : route.parts[1] || DEFAULT_SUB[section]);
  const current = $derived(SECTIONS.find((s) => s.id === section) || SECTIONS[0]);
  // largeur de la page : la collection et le marché aiment l'espace, la messagerie et la guilde un peu moins, le reste se lit mieux étroit
  const pw = $derived(section === 'collection' || sub === 'auctions' ? '1500px' : sub === 'messages' || sub === 'guild' || sub === 'trades' ? '1100px' : '820px');
  const viewKey = $derived(route.parts[0] === 'player' ? 'me/profile' : current.subs ? `${current.id}/${sub}` : current.id);

  let View = $state(null), loadId = 0;
  $effect(() => {
    const key = viewKey, id = ++loadId;
    (VIEWS[key] || VIEWS.collection)().then((m) => { if (id === loadId) View = m.default; });
  });

  // pastilles : ce qui attend une action, sans ouvrir chaque écran pour le savoir
  const gc = $derived(app.rewards && app.rewards.guild_chat);
  const guildUnread = $derived(!!(gc && gc.last > gc.seen));
  const subBadge = $derived({ messages: app.me?.unreadMsg || 0, friends: app.me?.friendReq || 0, trades: app.me?.trades || 0, rewards: rewardsReady(app) ? '!' : 0, guild: guildUnread ? '•' : 0 });
  const navBadge = $derived({
    market: app.me?.trades || 0,
    social: (app.me?.unreadMsg || 0) + (app.me?.friendReq || 0) || (guildUnread ? '•' : 0),
    me: rewardsReady(app) ? '!' : 0,
  });

  // compte à rebours du prochain paquet ; à zéro on relit le profil (au plus toutes les 5 s)
  let lastPoll = 0;
  const left = $derived(app.me && app.me.next != null ? Math.max(0, Math.ceil(app.me.next - (tick.now - app.meAt) / 1000)) : null);
  const full = $derived(!!app.me && (app.me.packReserve ?? app.me.packs ?? 0) >= (app.me.packMax ?? Infinity));
  $effect(() => {
    if (app.phase === 'app' && left === 0 && !full && Date.now() - Math.max(app.meAt, lastPoll) > 5000) { lastPoll = Date.now(); refreshMe(); }
  });

  startRouter();
  boot();
  if (!location.hash) go('/collection', true);
  addEventListener('keydown', (e) => {
    if (app.phase !== 'app' || e.ctrlKey || e.metaKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test((e.target || {}).tagName || '')) return;
    const i = '12345'.indexOf(e.key);
    if (i >= 0 && !ui.card) go(SECTIONS[i].to);
  });
  addEventListener('offline', () => toast('Hors ligne : les données affichées peuvent être en retard.'));
</script>

{#if app.phase === 'boot'}
  <div class="boot"><span class="mono serif">W</span></div>
{:else if app.phase === 'login'}
  <Login />
{:else}
  <div class="shell">
    <aside class="rail" aria-label="Sections">
      <div class="brand"><span class="mono serif">W</span><b class="serif">Alt<span>·</span>WikiPick</b></div>
      <nav>
        {#each SECTIONS as s}
          <button class:on={section === s.id} onclick={() => go(s.to)} aria-current={section === s.id ? 'page' : undefined}>
            <Icon name={s.icon} /><span class="tl">{s.label}</span>
            {#if navBadge[s.id]}<i class="badge {navBadge[s.id] === '!' ? 'gold' : 'red'}">{navBadge[s.id]}</i>{/if}
          </button>
        {/each}
      </nav>
    </aside>

    <div class="main" style:--pw={pw}>
      <header class="top">
        <span class="mono serif mobile-brand" aria-hidden="true">W</span>
        <h1 class="serif">{route.parts[0] === 'player' ? 'Joueur' : current.label}</h1>
        <span class="sp"></span>
        {#if app.me}
          <div class="wallet" aria-label="Portefeuille">
            <span title="Pièces"><Icon name="coin" /><b class="num">{fmt(app.me.coins)}</b></span>
            <button class="packs" title="Paquets en réserve" onclick={() => go('/packs')}>
              <Icon name="pack" /><b class="num">{app.me.packs ?? 0}</b>{#if left != null}<small class="num">{full ? 'plein' : clock(left)}</small>{/if}
            </button>
          </div>
        {/if}
        <button class="icon-btn bell" aria-label="Notifications" onclick={() => (ui.bell = true)}>
          <Icon name="bell" />{#if app.me?.unread}<i class="badge red">{app.me.unread > 99 ? '99+' : app.me.unread}</i>{/if}
        </button>
        <button class="acc" aria-label="Compte" onclick={() => (ui.menu = true)}><Avatar name={app.name || '?'} url={app.me?.avatar} size={34} /><span class="live" class:down={app.live !== 'live'} title={app.live === 'live' ? 'En direct' : 'Hors direct : reconnexion…'}></span></button>
      </header>

      {#if current.subs && route.parts[0] !== 'player'}
        <div class="subbar"><Seg items={current.subs.map(([id, label]) => [id, label, subBadge[id]])} value={sub} onchange={(id) => go(`/${current.id}/${id}`)} /></div>
      {/if}

      <main class="page">
        {#if View}<View />{:else}<div class="skeleton loading"></div>{/if}
      </main>
    </div>

    <nav class="tabbar" aria-label="Sections">
      {#each SECTIONS as s}
        <button class:on={section === s.id} onclick={() => go(s.to)} aria-current={section === s.id ? 'page' : undefined}>
          <span class="ic"><Icon name={s.icon} />{#if navBadge[s.id]}<i class="dot {navBadge[s.id] === '!' ? 'gold' : ''}">{navBadge[s.id] === '!' || navBadge[s.id] === '•' ? '' : navBadge[s.id]}</i>{/if}</span>
          <span class="tl">{s.label}</span>
        </button>
      {/each}
    </nav>
  </div>

  <CardSheet />
  <Notifications />
  <AccountMenu />
  <TradeComposer />
{/if}
<Toasts />

<style>
  .boot { min-height: 100dvh; display: grid; place-items: center; }
  .mono { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; font: 700 19px/1 var(--serif); color: var(--on-ivory);
    background: linear-gradient(160deg, #fff7e6, var(--ivory) 50%, var(--ivory-2)); box-shadow: inset 0 1px 0 #fff, 0 6px 16px -8px rgba(241, 232, 212, .6); }
  .boot .mono { animation: fade .6s; }

  .shell { min-height: 100dvh; }
  .main { min-width: 0; padding-bottom: calc(var(--nav) + var(--sab)); }
  .top { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; gap: 10px; height: calc(var(--top) + var(--sat)); padding: var(--sat) var(--gut) 0;
    background: rgba(7, 9, 14, .78); backdrop-filter: blur(16px) saturate(1.4); border-bottom: 1px solid var(--line); }
  .mobile-brand { width: 30px; height: 30px; font-size: 17px; flex: none; }
  h1 { font-size: 21px; letter-spacing: -.015em; white-space: nowrap; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
  @media (max-width: 599px) { h1 { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); } } /* sur téléphone, les onglets du bas disent déjà où l'on est */
  .wallet { display: flex; align-items: center; height: 36px; padding: 0 4px; background: rgba(255, 255, 255, .03); border: 1px solid var(--line); border-radius: 11px; }
  .wallet > span, .wallet > button { display: inline-flex; align-items: center; gap: 6px; padding: 0 8px; height: 100%; background: none; border: 0; color: inherit; cursor: pointer; font-size: 14px; }
  .wallet > span + button { border-left: 1px solid var(--line); }
  .wallet :global(.i) { color: var(--muted); font-size: 15px; }
  .wallet > span :global(.i) { color: var(--gold); }
  .wallet small { color: var(--muted); font-size: 12px; }
  .live { position: absolute; right: -1px; bottom: -1px; flex: none; width: 10px; height: 10px; border-radius: 50%; border: 2px solid var(--ink); background: var(--good); box-shadow: 0 0 0 0 rgba(70, 201, 152, .6); animation: ping 2.4s ease-out infinite; }
  .live.down { background: var(--bad); animation: none; }
  @keyframes ping { 70%, 100% { box-shadow: 0 0 0 7px transparent; } }
  .bell .badge { position: absolute; top: 4px; right: 3px; box-shadow: 0 0 0 2px var(--ink); font-size: 10px; line-height: 16px; min-width: 16px; padding: 0 4px; }
  .acc { position: relative; flex: none; padding: 0; background: none; border: 0; border-radius: 50%; cursor: pointer; }
  .subbar { position: sticky; top: calc(var(--top) + var(--sat)); z-index: 15; padding: 10px var(--gut); background: rgba(7, 9, 14, .78); backdrop-filter: blur(16px); }
  .page { max-width: var(--pw); margin: 0 auto; padding: 16px var(--gut) 40px; animation: rise .35s var(--ease) backwards; }
  .loading { height: 240px; margin: 16px var(--gut); }

  /* onglets du bas (mobile) */
  .tabbar { position: fixed; z-index: 30; left: 0; right: 0; bottom: 0; display: grid; grid-template-columns: repeat(5, 1fr); height: calc(var(--nav) + var(--sab)); padding-bottom: var(--sab);
    background: rgba(9, 12, 18, .9); backdrop-filter: blur(18px) saturate(1.4); border-top: 1px solid var(--line); }
  .tabbar button { display: grid; place-items: center; align-content: center; gap: 3px; background: none; border: 0; color: var(--muted); cursor: pointer; font: 500 11px var(--sans); transition: color .15s; }
  .tabbar button.on { color: var(--text); }
  .tabbar .ic { position: relative; font-size: 23px; line-height: 0; transition: transform .25s var(--spring); }
  .tabbar button.on .ic { transform: translateY(-2px); color: var(--ivory); }
  .tabbar .dot { position: absolute; top: -5px; right: -9px; min-width: 16px; height: 16px; padding: 0 4px; border-radius: 8px; font: 700 10px/16px var(--sans); font-style: normal; text-align: center; color: #fff; background: var(--bad); }
  .tabbar .dot.gold { color: #1d1506; background: var(--gold); }
  .tabbar .dot:empty { min-width: 10px; height: 10px; padding: 0; top: -2px; right: -6px; box-shadow: 0 0 0 2px var(--ink); }
  .rail { display: none; }

  /* grand écran : la colonne de gauche remplace les onglets du bas */
  @media (min-width: 980px) {
    .rail { position: fixed; z-index: 30; inset: 0 auto 0 0; width: var(--rail); display: flex; flex-direction: column; gap: 24px; padding: 20px 14px; background: rgba(9, 12, 18, .72); border-right: 1px solid var(--line); }
    .brand { display: flex; align-items: center; gap: 11px; padding: 0 8px; height: 40px; }
    .brand b { font-size: 21px; letter-spacing: -.015em; white-space: nowrap; }
    .brand b span { color: var(--gold); }
    .rail nav { display: grid; gap: 3px; }
    .rail button { position: relative; display: flex; align-items: center; gap: 13px; height: 44px; padding: 0 13px; background: none; border: 0; border-radius: 11px; color: var(--muted); font: 500 15px var(--sans); text-align: left; cursor: pointer; transition: color .15s, background .15s; }
    .rail button :global(.i) { font-size: 19px; }
    .rail button:hover { color: var(--text); background: rgba(255, 255, 255, .04); }
    .rail button.on { color: var(--text); background: linear-gradient(90deg, rgba(255, 255, 255, .08), rgba(255, 255, 255, .03)); box-shadow: var(--hi), inset 0 0 0 1px var(--line); }
    .rail button.on :global(.i) { color: var(--ivory); }
    .rail .badge { margin-left: auto; }
    .tabbar, .mobile-brand { display: none; }
    .main { margin-left: var(--rail); padding-bottom: 0; }
    .subbar { background: none; backdrop-filter: none; position: static; max-width: var(--pw); margin: 0 auto; padding-bottom: 0; }
    h1 { font-size: 26px; }
  }
</style>
