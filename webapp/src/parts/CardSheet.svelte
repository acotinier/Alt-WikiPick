<script>
  // La fiche d'une carte : l'extrait Wikipédia, tes exemplaires et d'où ils viennent, les amis qui l'ont, les enchères en cours,
  // et les actions (chacune demande une confirmation quand elle engage des pièces ou des cartes).
  import { call } from '../lib/api.js';
  import { EXCLUSIVE, ago, clock, color, fmt, plural, wikiUrl } from '../lib/format.js';
  import { app, coll, collectionChanged, nowSrv, refreshMeSoon, run, toast, ui, watch } from '../lib/store.svelte.js';
  import { tick } from '../lib/ticker.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Icon from '../ui/Icon.svelte';
  import Sheet from '../ui/Sheet.svelte';

  const RECYCLE_CONFIRM = ['R', 'SR', 'UR', 'L', 'M'];
  const DURATIONS = [['10m', '10 minutes'], ['30m', '30 minutes'], ['1h', '1 heure'], ['6h', '6 heures'], ['12h', '12 heures'], ['24h', '24 heures']];
  const STATE = { free: 'Libre', locked: 'Verrouillée', auction: 'Aux enchères', exclusive: 'Exclusive' };

  const c = $derived(ui.card);
  const own = $derived(c ? coll.byCid.get(c.cid) : null);
  const card = $derived(c && own ? { ...c, ...own } : c);
  const url = $derived(card && (card.url || wikiUrl(card.cid)));
  const watched = $derived(!!(card && watch.list.some((w) => w.cid === card.cid)));
  const tagNames = $derived(own ? (own.tags || []).map((id) => (coll.tags.find((t) => t.id === id) || {}).name).filter(Boolean) : []);

  let d = $state(null), loading = $state(false), open = $state(false), start = $state(10), dur = $state('10m');
  $effect(() => { if (c) { d = null; open = false; load(c.cid); } });
  async function load(cid) {
    loading = true;
    const r = await call('load_card', cid);
    if (ui.card && ui.card.cid === cid) { d = r && r.ok ? r : null; loading = false; }
  }
  const reload = () => { if (ui.card) load(ui.card.cid); };
  const done = (msg) => (r) => { toast(typeof msg === 'function' ? msg(r) : msg, 'good'); collectionChanged(); refreshMeSoon(); reload(); };

  // exemplaires de CETTE version (chromatique ou non)
  const version = $derived(d ? d.mine.filter((m) => m.shiny === !!card.shiny) : []);
  const free = $derived(version.filter((m) => m.state === 'free'));
  const locked = $derived(version.filter((m) => m.state === 'locked'));
  const exclusive = $derived(!!card && (EXCLUSIVE.includes(card.rarity) || version.some((m) => m.state === 'exclusive')));
  const gain = $derived(card && app.info.bank ? app.info.bank[card.rarity] : null);

  const prov = (m) => {
    const when = m.ts ? ` · ${ago(m.ts)}` : '';
    if (m.via === 'paquet') return `Obtenue dans un paquet${when}`;
    if (m.via === 'recompense') return `Obtenue en récompense${when}`;
    if (m.via === 'enchere') return `Achetée${m.price != null ? ` ${fmt(m.price)} Wikiki` : ''} aux enchères${m.from ? ` à ${m.from}` : ''}${m.lot ? ' (dans un lot)' : ''}${when}`;
    if (m.via === 'echange') return `Reçue par échange${m.from ? ` avec ${m.from}` : ''}${when}`;
    return `Obtenue${when}`;
  };
  const secs = (a) => { void tick.now; return Math.max(0, Math.ceil(a.ends_at - nowSrv())); }; // relit l'horloge : le compte à rebours bouge

  const recycle = () => run(() => call('recycle', [free[free.length - 1].id]), done((r) => `Carte recyclée : +${fmt(r.gain)} Wikiki. Elle reste 20 minutes dans la corbeille.`));
  const launch = () => run(() => call('auction_create', free[0].id, Math.floor(Number(start)), dur), done('Enchère lancée ! Tu la retrouves dans Marché.'));
  const lock = (on) => run(() => call('card_lock', (on ? free[0] : locked[0]).id, card.cid, !!card.shiny, on), done(on ? 'Carte verrouillée : elle ne peut plus être vendue ni échangée.' : 'Carte déverrouillée.'));
  const setAside = (on) => run(() => call('card_for_sale', free[0].id, on), done((r) => (on ? `Mise de côté (${fmt(r.n)} cartes à vendre).` : 'Retirée des cartes à vendre.')));
  const wish = (on) => run(() => call('wish_set', card.cid, on, { name: card.name, desc: card.desc, img: card.img, rarity: card.rarity, lang: card.lang }), done((r) => (r.wished ? 'Ajoutée à tes souhaits : le site te prévient dès qu’elle passe aux enchères.' : 'Retirée de tes souhaits.')));
  const bid = (a) => run(() => call('bid', a.id, a.min), done('Mise placée : tu es en tête.'));
  async function toggleWatch() {
    const r = await call('watch_set', card.cid, card.name, !watched);
    if (r.ok) watch.list = r.list; else toast(r.error || 'Impossible', 'error');
  }
</script>

<Sheet open={!!c} onclose={() => (ui.card = null)} title={card ? card.name : ''} wide>
  {#if card}
    <div class="wrap" style:--c={color(card.rarity)}>
      <div class="art"><Card {card} width={330} /></div>
      <div class="info">
        {#if card.desc}<p class="desc serif">{card.desc}</p>{/if}
        <div class="row">
          {#if url && url.startsWith('https://')}<a class="btn primary small" href={url} target="_blank" rel="noopener noreferrer"><Icon name="out" />Wikipédia</a>{/if}
          <button class="btn small" onclick={toggleWatch}><Icon name="eye" />{watched ? 'Ne plus surveiller' : 'Surveiller aux enchères'}</button>
        </div>
        <dl>
          <div><dt>Lectures</dt><dd class="num">{fmt(card.reads)}</dd></div>
          {#if own}<div><dt>Exemplaires</dt><dd>{own.copies}</dd></div>{/if}
          {#if tagNames.length}<div><dt>Tags</dt><dd>{tagNames.join(', ')}</dd></div>{/if}
          {#if card.shiny}<div><dt>Version</dt><dd>Chromatique</dd></div>{/if}
        </dl>

        {#if loading && !d}
          <div class="skeleton" style="height:120px"></div>
        {:else if d}
          <section class="box">
            {#if d.mine.length}
              <h3 class="eyebrow">Tes exemplaires ({d.mine.length})</h3>
              {#each d.mine as m}<p class="copy"><span class="st {m.state}">{STATE[m.state] || m.state}</span>{#if m.shiny}<Icon name="spark" />{/if}<span>{prov(m)}</span></p>{/each}
            {:else}<p class="muted">Tu ne possèdes pas encore cette carte.</p>{/if}
          </section>

          {#if d.mine.length}
            <section class="box">
              <h3 class="eyebrow">Actions</h3>
              {#if exclusive}<p class="muted">Carte exclusive : elle ne se vend pas, ne se recycle pas et ne s'échange pas.</p>{/if}
              <div class="row">
                {#if free.length && !exclusive}
                  <ConfirmButton small variant="danger" label={`Recycler${gain ? ` · +${fmt(gain)}` : ''}`} confirm={card.shiny || RECYCLE_CONFIRM.includes(card.rarity) ? `Vraiment ? ${fmt(gain || 1)} Wikiki` : null} onconfirm={recycle} />
                  <ConfirmButton small label="Verrouiller" onconfirm={() => lock(true)} />
                  <ConfirmButton small label={free[0].for_sale ? 'Retirer des cartes à vendre' : 'Mettre de côté pour la vente'} onconfirm={() => setAside(!free[0].for_sale)} />
                {/if}
                {#if locked.length}<ConfirmButton small label="Déverrouiller" onconfirm={() => lock(false)} />{/if}
                <ConfirmButton small label={d.wished ? 'Retirer de mes souhaits' : 'Ajouter à mes souhaits'} onconfirm={() => wish(!d.wished)} />
              </div>
              {#if free.length && !exclusive}
                <div class="auct">
                  <h4 class="eyebrow">Mettre aux enchères</h4>
                  <div class="row nowrap">
                    <label>Départ<input class="field" type="number" inputmode="numeric" min="1" step="1" bind:value={start} /></label>
                    <label>Durée<select bind:value={dur}>{#each DURATIONS as [v, t]}<option value={v}>{t}</option>{/each}</select></label>
                  </div>
                  <ConfirmButton variant="primary" block label="Lancer l'enchère" confirm={() => `Confirmer : lancer à ${fmt(Math.floor(Number(start)))} Wikiki`} check={() => (Math.floor(Number(start)) < 1 ? 'Indique une mise de départ d\'au moins 1 Wikiki.' : '')} onconfirm={launch} />
                  <p class="muted fine">Aucune commission. Une mise dans les 15 dernières secondes relance 1 minute ; sans mise, la carte te revient.</p>
                </div>
              {/if}
            </section>
          {/if}

          {#if d.extract}<p class="extract" class:open>{d.extract}</p>{#if d.extract.length > 380}<button class="link" onclick={() => (open = !open)}>{open ? 'Réduire' : 'Lire la suite'}</button>{/if}{/if}
          {#each [d.friends.length && `Chez ${d.friends.length > 1 ? 'tes amis' : 'ton ami'} : ${d.friends.join(', ')}`, d.guild.length && `Dans ta guilde : ${d.guild.join(', ')}`,
            d.friend_wishes.length && `${d.friend_wishes.length > 1 ? 'Tes amis la souhaitent' : 'Ton ami la souhaite'} : ${d.friend_wishes.join(', ')}`].filter(Boolean) as t}<p class="muted">{t}</p>{/each}

          {#if d.auctions.length}
            <section class="box">
              <h3 class="eyebrow">Aux enchères en ce moment ({d.auctions.length})</h3>
              {#each d.auctions.slice(0, 5) as a}
                <div class="copy"><span class="price"><Icon name="coin" />{fmt(a.price)}</span><span class="muted">par {a.seller || '?'}</span>
                  {#if a.status === 'live'}<span class="pill">{clock(secs(a))}</span>{/if}<span class="sp"></span>
                  {#if a.status === 'live' && !a.mine && !a.leading && a.min > 0}<ConfirmButton small variant="bid" label={`Miser ${fmt(a.min)}`} confirm={`Confirmer : ${fmt(a.min)} Wikiki`} onconfirm={() => bid(a)} />{/if}
                </div>
              {/each}
            </section>
          {/if}
        {:else}
          <p class="muted">Détails indisponibles pour le moment.</p>
        {/if}
      </div>
    </div>
  {/if}
</Sheet>

<style>
  .wrap { display: grid; gap: 20px; }
  .art { width: min(62%, 240px); margin: 6px auto 0; }
  .info { display: grid; gap: 14px; align-content: start; min-width: 0; }
  .desc { font-size: 17px; font-style: italic; color: var(--muted); line-height: 1.4; }
  dl { display: grid; margin: 0; border-top: 1px solid var(--line); }
  dl > div { display: flex; justify-content: space-between; gap: 16px; padding: 9px 0; border-bottom: 1px solid var(--line); }
  dt { color: var(--muted); } dd { font-weight: 500; text-align: right; }
  .box { display: grid; gap: 8px; padding: 14px; background: rgba(255, 255, 255, .025); border: 1px solid var(--line); border-radius: var(--rad-l); }
  .box h3, .auct h4 { margin: 0; }
  .copy { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 10px; margin: 0; font-size: 14px; }
  .st { padding: 1px 9px; font: 600 11.5px/18px var(--sans); border: 1px solid var(--line-2); border-radius: 99px; white-space: nowrap; }
  .st.free { color: var(--good); border-color: color-mix(in srgb, var(--good) 45%, transparent); }
  .st.locked { color: var(--r-L); border-color: color-mix(in srgb, var(--r-L) 50%, transparent); }
  .st.auction { color: var(--r-R); border-color: color-mix(in srgb, var(--r-R) 50%, transparent); }
  .auct { display: grid; gap: 10px; margin-top: 6px; padding-top: 14px; border-top: 1px solid var(--line); }
  .auct label { display: grid; gap: 4px; flex: 1; font-size: 12.5px; color: var(--muted); }
  .nowrap { flex-wrap: nowrap; align-items: end; }
  .fine { font-size: 12.5px; }
  .extract { font: 400 16px/1.6 var(--serif); color: #d7dce5; display: -webkit-box; -webkit-line-clamp: 7; -webkit-box-orient: vertical; overflow: hidden; }
  .extract.open { -webkit-line-clamp: unset; }
  .link { justify-self: start; padding: 0; background: none; border: 0; color: var(--text); text-decoration: underline; text-underline-offset: 3px; cursor: pointer; }
  .price { display: inline-flex; align-items: center; gap: 6px; font: 600 18px var(--serif); }
  .price :global(.i) { color: var(--gold); font-size: 15px; }
  @media (min-width: 700px) {
    .wrap { grid-template-columns: 250px minmax(0, 1fr); gap: 28px; }
    .art { width: 100%; position: sticky; top: 0; align-self: start; margin: 4px 0 0; }
  }
</style>
