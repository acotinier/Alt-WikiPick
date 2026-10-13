<script>
  // Une pile de cartes reçue d'un coup (paquet légendaire du Season Pass, par exemple) : toutes visibles, la plus rare en premier.
  import { color, plural, rarityRank } from '../lib/format.js';
  import { app, openCard, ui } from '../lib/store.svelte.js';
  import Card from '../ui/Card.svelte';
  import Sheet from '../ui/Sheet.svelte';
  const h = $derived(ui.haul);
  const cards = $derived(h ? [...h.cards].sort((a, b) => rarityRank(a.rarity) - rarityRank(b.rarity) || Number(b.shiny) - Number(a.shiny)) : []);
  const fresh = $derived(cards.filter((c) => c.new).length);
</script>

<Sheet open={!!h} onclose={() => (ui.haul = null)} title={h ? h.title : ''} wide>
  {#if h}
    <p class="muted sum">{h.hint || plural(cards.length, 'carte')}{#if fresh} · {plural(fresh, 'nouvelle')}{/if}</p>
    <div class="grid">{#each cards as c, i (c.cid + i)}<Card card={c} width={150} onclick={() => openCard(c)}>{#if c.new}<span class="new">Nouvelle</span>{/if}</Card>{/each}</div>
    <button class="btn primary block" style="margin-top:16px" onclick={() => (ui.haul = null)}>Terminer</button>
  {/if}
</Sheet>

<style>
  .sum { margin-bottom: 14px; }
  .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
  .new { position: absolute; top: 5px; left: 5px; z-index: 3; padding: 1px 8px; font: 600 10.5px/16px var(--sans); color: var(--on-ivory); background: var(--ivory); border-radius: 99px; }
  @media (min-width: 700px) { .grid { grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; } }
</style>
