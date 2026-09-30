<script>
  // Composer un échange (ou une contre-proposition) : jusqu'à 10 cartes de chaque côté, plus des Wikiki. Envoyer demande une confirmation.
  import { call } from '../lib/api.js';
  import { fmt, plural, rarityRank } from '../lib/format.js';
  import { coll, collectionChanged, refreshMeSoon, run, toast, ui } from '../lib/store.svelte.js';
  import { go } from '../lib/router.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import Seg from '../ui/Seg.svelte';
  import Sheet from '../ui/Sheet.svelte';

  const t = $derived(ui.trade);
  let side = $state('give'), q = $state(''), give = $state([]), take = $state([]), gc = $state(''), tc = $state(''), message = $state(''), theirs = $state(null), lim = $state(60);

  $effect(() => {
    if (!t) return;
    side = 'give'; q = ''; give = []; take = []; gc = ''; tc = ''; message = ''; theirs = null; lim = 60;
    call('user_cards', t.to).then((r) => { if (ui.trade === t) { if (r.ok) theirs = r.groups; else { toast(r.error || 'Impossible de lire les cartes de ce joueur', 'error'); ui.trade = null; } } });
  });

  const mine = $derived(coll.cards.filter((c) => c.free_ids && c.free_ids.length).map((c) => ({ card: c, ids: c.free_ids })));
  const groups = $derived((side === 'give' ? mine : theirs || []).filter((g) => !q || g.card.name.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => rarityRank(a.card.rarity) - rarityRank(b.card.rarity) || b.card.reads - a.card.reads));
  const chosen = $derived(side === 'give' ? give : take);
  const count = (g) => g.ids.filter((id) => chosen.includes(id)).length;
  function pick(g) { // un clic ajoute un exemplaire, encore un autre, puis retire tout (comme sur le site)
    const list = side === 'give' ? give : take, have = count(g);
    let next;
    if (have < g.ids.length) { if (list.length >= 10) return toast('10 cartes au maximum de chaque côté.'); next = [...list, g.ids.find((i) => !list.includes(i))]; }
    else next = list.filter((x) => !g.ids.includes(x));
    if (side === 'give') give = next; else take = next;
  }
  const num = (v) => Math.max(0, Math.floor(Number(v) || 0));
  const empty = () => (!give.length && !take.length && !num(gc) && !num(tc) ? "L'échange est vide : choisis au moins une carte ou des Wikiki." : '');
  const send = () => run(() => call('trade_send', t.to, give, take, num(gc), num(tc), message, t.counterOf), () => {
    toast(t.counterOf ? `Contre-proposition envoyée à ${t.to}.` : `Proposition envoyée à ${t.to}.`, 'good');
    ui.trade = null; collectionChanged(); refreshMeSoon(); go('/market/trades');
    window.dispatchEvent(new CustomEvent('altwp:trades-changed', { detail: 'sent' }));
  });
</script>

<Sheet open={!!t} onclose={() => (ui.trade = null)} title={t ? (t.counterOf ? `Contre-proposition à ${t.to}` : `Échange avec ${t.to}`) : ''} wide>
  {#if t}
    {#if t.note}<p class="muted">{t.note}</p>{/if}
    <Seg items={[['give', `Tu donnes · ${give.length}/10`], ['take', `Tu reçois · ${take.length}/10`]]} value={side} onchange={(s) => { side = s; q = ''; lim = 60; }} />
    <label class="search"><Icon name="search" /><input type="search" placeholder="Chercher une carte" bind:value={q} oninput={() => (lim = 60)} /></label>
    <p class="muted fine">Touche une carte pour l'ajouter (encore une fois pour un autre exemplaire). Rangées de la plus rare à la plus commune.</p>
    {#if side === 'take' && !theirs}<div class="skeleton" style="height:160px"></div>
    {:else}
      <div class="grid">
        {#each groups.slice(0, lim) as g (g.card.cid + (g.card.shiny ? '*' : ''))}
          {@const n = count(g)}
          <Card card={{ ...g.card, copies: g.ids.length }} picked={n > 0} onclick={() => pick(g)}>{#if n}<span class="mark">{g.ids.length > 1 ? `${n}/${g.ids.length}` : '✓'}</span>{/if}</Card>
        {:else}<Empty title="Aucune carte" text={side === 'give' ? "Tu n'as aucune carte disponible." : `${t.to} n'a aucune carte disponible.`} />{/each}
      </div>
      {#if groups.length > lim}<button class="btn small block" onclick={() => (lim += 60)}>Afficher plus (encore {groups.length - lim})</button>{/if}
    {/if}
    <div class="coins">
      <label><Icon name="coin" />Wikiki offerts en plus<input class="field" type="number" inputmode="numeric" min="0" bind:value={gc} /></label>
      <label><Icon name="coin" />Wikiki demandés en plus<input class="field" type="number" inputmode="numeric" min="0" bind:value={tc} /></label>
    </div>
    <input class="field" maxlength="200" placeholder={`Un message pour ${t.to} (facultatif)`} bind:value={message} />
    <ConfirmButton variant="primary" block label="Envoyer la proposition" confirm={() => `Confirmer : ${plural(give.length, 'carte')} contre ${plural(take.length, 'carte')}`} check={empty} onconfirm={send} />
  {/if}
</Sheet>

<style>
  .search { display: flex; align-items: center; gap: 10px; min-height: 44px; margin: 12px 0 6px; padding: 0 14px; color: var(--faint); background: var(--ink-2); border: 1px solid var(--line-2); border-radius: 12px; }
  .search input { flex: 1; min-width: 0; background: none; border: 0; outline: 0; color: var(--text); font: 16px var(--sans); }
  .fine { font-size: 12.5px; margin-bottom: 10px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 10px; max-height: 46dvh; overflow-y: auto; padding: 6px; margin: 0 -6px; }
  .mark { position: absolute; top: 6px; left: 6px; z-index: 3; padding: 0 8px; font: 700 11px/17px var(--sans); color: var(--on-ivory); background: var(--ivory); border-radius: 99px; }
  .coins { display: grid; gap: 10px; margin: 14px 0 10px; }
  .coins label { display: grid; grid-template-columns: auto 1fr; gap: 4px 10px; align-items: center; font-size: 13px; color: var(--muted); }
  .coins label :global(.i) { color: var(--gold); grid-row: 1; }
  .coins input { grid-column: 1 / -1; }
  .field { margin-bottom: 12px; }
  @media (min-width: 700px) { .coins { grid-template-columns: 1fr 1fr; } }
</style>
