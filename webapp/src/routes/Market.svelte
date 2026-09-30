<script>
  // Les enchères : le marché (recherche, tri et raretés côté site), tes ventes, tes mises, l'historique. Les prix bougent en direct.
  // Miser = deux pressions (la seconde confirme). Le flux du marché n'est demandé que pendant que cet écran est ouvert.
  import { call } from '../lib/api.js';
  import { clock, color, debounce, fmt, plural } from '../lib/format.js';
  import { app, nowSrv, on, openCard, refreshMeSoon, run, setSkew, toast, collectionChanged } from '../lib/store.svelte.js';
  import { tick } from '../lib/ticker.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import Seg from '../ui/Seg.svelte';

  const SCOPES = [['live', 'Toutes'], ['mine', 'En vente'], ['bidding', 'Mes mises'], ['purchases', 'Achetées'], ['ventes', 'Vendues']];
  const SORTS = [['fin', 'Fin proche'], ['rarete', 'Rareté'], ['prixbas', 'Prix croissant'], ['prix', 'Prix décroissant'], ['mises', 'Nombre de mises']];
  const RAR = ['M', 'L', 'UR', 'SR', 'R', 'PC', 'C'];

  let scope = $state('live'), q = $state(''), typed = $state(''), sort = $state('fin'), rars = $state([]), items = $state.raw([]), page = $state(0), pages = $state(1), total = $state(0);
  let loading = $state(false), history = $state(false), sum = $state(0), seq = 0, priceEdit = $state({});
  const setQ = debounce((v) => (q = v.trim()), 350);
  const more = $derived(page + 1 < pages);

  // le flux ne transmet les enchères que pendant que le marché est à l'écran
  $effect(() => { call('stream_watch_market', true); return () => { call('stream_watch_market', false); }; });

  async function load(reset = true) {
    const mine = ++seq;
    loading = true;
    if (reset) { items = []; page = 0; }
    const r = await call('load_market', scope, reset ? 0 : page + 1, q, rars, sort, '');
    if (mine !== seq) return;
    loading = false;
    if (!r.ok) { if (!r.expired) toast(r.error || 'Marché indisponible', 'error'); return; }
    setSkew(r.now); history = !!r.history; sum = r.sum || 0;
    const base = reset ? 0 : items.length;
    const got = r.history ? r.items.map((h, i) => ({ id: -(base + i + 1), card: h.card, lot: h.lot, price: h.price, min: 0, bids: 0, leader: '', seller: '', mine: false, leading: false, ends_at: 0, status: 'done', hist: h })) : r.items;
    items = reset ? got : items.concat(got.filter((x) => !items.some((y) => y.id === x.id)));
    page = r.page; pages = r.pages; total = r.total;
  }
  // un autre filtre ou une autre vue : on relit (une seule demande compte, les plus anciennes sont ignorées)
  $effect(() => { scope; q; sort; rars; load(true); });

  const upd = (id, patch) => { items = items.map((a) => (a.id === id ? { ...a, ...patch } : a)); };
  async function sync(id) { // relit CETTE enchère : une mise a pu passer avant la nôtre
    const r = await call('auction_get', id);
    if (r.ok && r.auction && r.auction.id) { const n = r.auction; upd(id, { price: n.price, leader: n.leader, min: n.min, bids: n.bids, leading: n.leading, ends_at: n.ends_at, status: n.status }); }
  }
  const off = on('auction', (d) => {
    const a = items.find((x) => x.id === d.id), me = app.me && app.me.id;
    if (!a) return;
    if (d.what === 'bid') upd(a.id, { price: Number(d.price) || a.price, leader: d.leader ?? a.leader, min: Number(d.min) || a.min, ends_at: Number(d.endsAt) || a.ends_at, bids: a.bids + 1, leading: d.leaderId === me });
    else if (d.what === 'end') {
      upd(a.id, { status: d.sold ? 'sold' : 'unsold', price: d.price ? Number(d.price) : a.price, leading: !!d.sold && d.winnerId === me, leader: d.sold ? a.leader : '' });
      if (d.sold && d.winnerId === me) collectionChanged();
      if (scope === 'live') setTimeout(() => { items = items.filter((x) => x.id !== a.id); total = Math.max(0, total - 1); }, 8000); // une enchère terminée quitte le marché
    } else if (d.what === 'cancel') upd(a.id, { status: 'cancelled' });
    else if (d.what === 'prix') upd(a.id, { price: Number(d.price) || a.price, min: Number(d.min) || a.min });
  });
  $effect(() => off);

  const bid = (a) => run(() => call('bid', a.id, a.min), async (r) => { toast(r.extended ? 'Mise placée ! Le chrono repart à 1 minute.' : 'Mise placée : tu es en tête.', 'good'); refreshMeSoon(); await sync(a.id); });
  const cancel = (a) => run(() => call('auction_cancel', a.id), () => { toast('Enchère annulée : la carte revient dans ta collection.', 'good'); items = items.filter((x) => x.id !== a.id); collectionChanged(); });
  const reprice = (a) => { const v = Math.floor(Number(priceEdit[a.id])); return run(() => call('auction_price', a.id, v), () => { toast(`Mise de départ changée : ${fmt(v)} Wikiki.`, 'good'); sync(a.id); }); };

  const secs = (a) => { void tick.now; return Math.max(0, Math.ceil(a.ends_at - nowSrv())); };
  const cardOf = (a) => (a.lot ? { ...(a.lot.cards[0] || {}), name: a.lot.name, copies: 1, desc: '' } : a.card);
  const stateOf = (a) => {
    if (a.hist) return `${a.hist.sold ? 'Vendu à' : 'Acheté à'} ${a.hist.who}`;
    if (a.status === 'cancelled') return 'Annulée';
    if (a.status !== 'live') return a.leader ? `Adjugé à ${a.leader}` : 'Terminé sans preneur';
    return a.mine ? (a.lot ? 'Ton lot' : 'Ta carte') : a.leading ? 'Tu es en tête' : '';
  };

  let sentinel = $state(null), lastMore = 0;
  $effect(() => {
    if (!sentinel) return;
    const io = new IntersectionObserver((e) => { if (e[0].isIntersecting && !loading && Date.now() - lastMore > 1200) { lastMore = Date.now(); load(false); } }, { rootMargin: '500px' });
    io.observe(sentinel);
    return () => io.disconnect();
  });
  const toggle = (r) => (rars = rars.includes(r) ? rars.filter((x) => x !== r) : [...rars, r]);
</script>

<div class="scopes"><Seg items={SCOPES} value={scope} onchange={(s) => (scope = s)} /></div>

{#if scope === 'live'}
  <div class="bar">
    <label class="search"><Icon name="search" /><input type="search" placeholder="Rechercher une enchère" bind:value={typed} oninput={() => setQ(typed)} /></label>
    <select aria-label="Trier" bind:value={sort}>{#each SORTS as [v, t]}<option value={v}>{t}</option>{/each}</select>
  </div>
  <div class="chips">{#each RAR as r}<button class="chip" class:on={rars.includes(r)} style:--c={color(r)} onclick={() => toggle(r)}>{app.names[r] || r}</button>{/each}</div>
{/if}

<p class="count muted">{loading && !items.length ? 'Chargement…' : history ? `${plural(total, scope === 'ventes' ? 'vente' : 'achat')}${sum ? ` · ${fmt(sum)} Wikiki` : ''}` : `${fmt(items.length)} affichées sur ${fmt(total)}`}</p>

<div class="grid">
  {#if loading && !items.length}
    {#each Array(6) as _}<div class="skeleton sk"></div>{/each}
  {:else if !items.length}
    <Empty title="Aucune enchère" text={{ mine: "Tu n'as aucune carte en vente pour l'instant.", bidding: "Tu n'as misé sur aucune enchère en cours.", purchases: 'Les cartes que tu remportes aux enchères apparaîtront ici.', ventes: 'Les cartes que tu vends aux enchères apparaîtront ici.' }[scope] || 'Aucune enchère ne correspond.'} />
  {:else}
    {#each items as a (a.id)}
      {@const c = cardOf(a)}{@const fini = a.status !== 'live' && !a.hist}
      <article class="offer" class:fini class:lead={a.leading}>
        {#if c}<Card card={c} onclick={() => openCard(a.card || a.lot.cards[0])}>{#if a.lot}<span class="lot">Lot de {plural(a.lot.n || a.lot.cards.length, 'carte')}</span>{/if}</Card>{/if}
        <div class="deal">
          <div><span class="price serif num"><Icon name="coin" />{fmt(a.price)}</span>
            <small class="muted who">{a.hist ? stateOf(a) : a.bids ? (fini ? '' : 'en tête : ') + (a.leader || a.seller) : 'par ' + a.seller}</small></div>
          {#if a.hist}<span class="pill">{new Date(a.hist.ts * 1000).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })}</span>
          {:else if fini}<span class="pill">Terminé</span>
          {:else}<span class="pill timer" class:hot={secs(a) <= 15}>{secs(a) > 0 ? clock(secs(a)) : 'Clôture…'}</span>{/if}
        </div>
        {#if !a.hist && stateOf(a)}<p class="st">{stateOf(a)}</p>{/if}
        {#if !a.hist && a.status === 'live'}
          {#if a.mine}
            <div class="acts"><ConfirmButton small variant="danger" label="Annuler la vente" confirm="Confirmer l'annulation" onconfirm={() => cancel(a)} />
              {#if !a.bids}<div class="pe"><input class="field" type="number" inputmode="numeric" min="1" placeholder={String(a.price)} bind:value={priceEdit[a.id]} aria-label="Nouveau prix de départ" />
                <ConfirmButton small label="Changer" check={() => (Math.floor(Number(priceEdit[a.id])) < 1 ? "Indique une mise de départ d'au moins 1 Wikiki." : '')} onconfirm={() => reprice(a)} /></div>{/if}</div>
          {:else if !a.leading && a.min > 0}
            <ConfirmButton small block variant="bid" label={`Miser ${fmt(a.min)}`} confirm={`Confirmer : miser ${fmt(a.min)} Wikiki`} onconfirm={() => bid(a)} />
          {/if}
        {/if}
      </article>
    {/each}
  {/if}
</div>
{#if more && !loading}<div bind:this={sentinel} class="sentinel"></div>{/if}

<style>
  .scopes { margin-bottom: 12px; }
  .bar { display: flex; gap: 10px; }
  .search { flex: 1; min-width: 0; display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 14px; color: var(--faint); background: var(--ink-2); border: 1px solid var(--line-2); border-radius: 12px; }
  .search:focus-within { color: var(--text); border-color: rgba(241, 232, 212, .5); }
  .search input { flex: 1; min-width: 0; background: none; border: 0; outline: 0; color: var(--text); font: 16px var(--sans); }
  .bar select { width: 150px; flex: none; }
  .chips { display: flex; gap: 8px; margin: 12px calc(var(--gut) * -1) 0; padding: 0 var(--gut) 4px; overflow-x: auto; scrollbar-width: none; }
  .chips::-webkit-scrollbar { display: none; }
  .chip { flex: none; display: inline-flex; align-items: center; gap: 8px; min-height: 34px; padding: 0 13px 0 11px; color: var(--muted); font: 500 13.5px var(--sans); cursor: pointer; background: rgba(255, 255, 255, .025); border: 1px solid var(--line); border-radius: 99px; }
  .chip::before { content: ""; width: 8px; height: 8px; transform: rotate(45deg); border-radius: 2px; background: var(--c); box-shadow: 0 0 8px -1px var(--c); }
  .chip.on { color: var(--text); background: color-mix(in srgb, var(--c) 14%, transparent); border-color: color-mix(in srgb, var(--c) 55%, transparent); }
  .count { margin: 12px 2px; font-size: 13px; }
  .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 12px; }
  .sk { aspect-ratio: 5 / 9; border-radius: 13px; }
  .offer { display: grid; gap: 8px; align-content: start; min-width: 0; transition: opacity .35s; }
  .offer.fini { opacity: .55; }
  .lot { position: absolute; top: 6px; left: 6px; z-index: 3; padding: 1px 9px; font: 600 11px/17px var(--sans); color: var(--on-ivory); background: var(--ivory); border-radius: 99px; }
  .deal { display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; padding: 0 2px; }
  .price { display: inline-flex; align-items: center; gap: 6px; font-size: 19px; font-weight: 600; line-height: 1.1; } .price :global(.i) { color: var(--gold); font-size: 14px; }
  .who { display: block; margin-top: 2px; overflow-wrap: anywhere; font-size: 12px; }
  .timer { font-variant-numeric: tabular-nums; } .pill.hot { color: #fff; background: color-mix(in srgb, var(--bad) 30%, transparent); border-color: color-mix(in srgb, var(--bad) 60%, transparent); animation: hot 1s ease-in-out infinite; }
  @keyframes hot { 50% { box-shadow: 0 0 14px -2px var(--bad); } }
  .st { padding: 0 2px; font-size: 12.5px; font-weight: 600; color: var(--ivory); } .lead .st { color: var(--good); }
  .acts { display: grid; gap: 6px; } .pe { display: flex; gap: 6px; } .pe .field { min-height: 34px; padding: 0 8px; width: 0; flex: 1; font-size: 14px; }
  .sentinel { height: 1px; }
  @media (min-width: 700px) { .grid { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 22px 16px; } }
</style>
