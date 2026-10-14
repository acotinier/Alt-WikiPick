<script>
  // Une enchère précise, ouverte depuis une notification (« on a surenchéri sur… ») : la carte, le prix, qui est en tête, le temps restant et de quoi miser.
  import { call } from '../lib/api.js';
  import { clock, fmt, plural } from '../lib/format.js';
  import { go } from '../lib/router.svelte.js';
  import { nowSrv, openCard, refreshMeSoon, run, toast, ui } from '../lib/store.svelte.js';
  import { tick } from '../lib/ticker.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Icon from '../ui/Icon.svelte';
  import Sheet from '../ui/Sheet.svelte';

  let a = $state(null), failed = $state('');
  $effect(() => { if (ui.auction) load(ui.auction); else { a = null; failed = ''; } });
  async function load(id) {
    a = null; failed = '';
    const r = await call('auction_get', id);
    if (ui.auction !== id) return;
    if (r && r.ok && r.auction && r.auction.id) a = r.auction; else failed = (r && r.error) || "Cette enchère n'est plus disponible.";
  }
  const live = $derived(!!a && a.status === 'live');
  const secs = $derived.by(() => { void tick.now; return a ? Math.max(0, Math.ceil(a.ends_at - nowSrv())) : 0; });
  const card = $derived(a && (a.lot ? { ...(a.lot.cards[0] || {}), name: a.lot.name, copies: 1, desc: '' } : a.card));
  const bid = () => run(() => call('bid', a.id, a.min), () => { toast('Mise placée : tu es en tête.', 'good'); refreshMeSoon(); load(a.id); });
  const market = () => { ui.auction = null; go('/market/auctions'); };
</script>

<Sheet open={!!ui.auction} onclose={() => (ui.auction = null)} title="Enchère">
  {#if failed}
    <p class="muted">{failed}</p>
  {:else if !a}
    <div class="skeleton" style="height:260px"></div>
  {:else}
    <div class="wrap">
      <div class="art">{#if card}<Card {card} width={330} onclick={() => { const c = a.card || a.lot.cards[0]; ui.auction = null; openCard(c); }} />{/if}</div>
      <div class="info">
        {#if a.lot}<p class="muted">Lot de {plural(a.lot.n || a.lot.cards.length, 'carte')}</p>{/if}
        <p class="price serif num"><Icon name="coin" />{fmt(a.price)}</p>
        <p class="muted">{a.bids ? `${plural(a.bids, 'mise')} · en tête : ${a.leader || a.seller}` : `par ${a.seller}`}{a.leading ? ' (toi)' : ''}</p>
        <p class="st">{live ? (secs > 0 ? `Se termine dans ${clock(secs)}` : 'Clôture…') : a.status === 'cancelled' ? 'Annulée' : a.leader ? `Adjugé à ${a.leader}` : 'Terminée sans preneur'}</p>
        {#if live && !a.mine && !a.leading && a.min > 0}
          <ConfirmButton block variant="bid" label={`Miser ${fmt(a.min)}`} confirm={`Confirmer : miser ${fmt(a.min)} Wikiki`} onconfirm={bid} />
        {:else if live && a.leading}<p class="good">Tu es en tête.</p>{/if}
        <button class="btn block" onclick={market}>Voir le marché</button>
      </div>
    </div>
  {/if}
</Sheet>

<style>
  .wrap { display: grid; gap: 16px; }
  .art { width: min(60%, 220px); margin: 4px auto 0; }
  .info { display: grid; gap: 8px; align-content: start; } .price { display: inline-flex; align-items: center; gap: 8px; font-size: 30px; font-weight: 600; } .price :global(.i) { color: var(--gold); font-size: 22px; }
  .st { font-weight: 600; color: var(--ivory); } .good { color: var(--good); font-weight: 600; }
  @media (min-width: 700px) { .wrap { grid-template-columns: 220px minmax(0, 1fr); gap: 26px; } .art { width: 100%; margin: 0; } }
</style>
