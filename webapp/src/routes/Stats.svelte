<script>
  import { color, compact, fmt, plural } from '../lib/format.js';
  import { app, coll, openCard } from '../lib/store.svelte.js';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';

  const s = $derived(coll.stats), rank = $derived(coll.rank || {});
  const maxU = $derived(s ? Math.max(1, ...s.rarities.map((r) => r.unique)) : 1);
  // doublons recyclables : exemplaires en trop × valeur de recyclage du site (hors verrouillées et chromatiques)
  const recycle = $derived.by(() => {
    const bank = app.info.bank || {};
    let n = 0, total = 0;
    for (const c of coll.cards) { if (c.locked || c.shiny || c.copies < 2 || bank[c.rarity] == null) continue; n += c.copies - 1; total += (c.copies - 1) * bank[c.rarity]; }
    return { n, total };
  });
  const open = (c) => { const full = coll.byCid.get(c.cid); if (full) openCard(full); };
</script>

{#if !s}
  {#if coll.loaded}<Empty title="Aucune statistique" />{:else}<div class="skeleton" style="height:300px"></div>{/if}
{:else}
  <section class="hero">
    <div class="rk serif num">{rank.rank ? `#${fmt(rank.rank)}` : '—'}</div>
    <div><b>Classement</b>
      {#if rank.total}<p class="muted">sur {fmt(rank.total)} joueurs</p>{/if}
      {#if rank.toNext != null && rank.nextName}<p class="muted">{fmt(rank.toNext)} points pour dépasser {rank.nextName}</p>{/if}</div>
  </section>

  <div class="tiles">
    <div class="tile"><b class="serif num">{fmt(rank.points)}</b><span>points</span></div>
    <div class="tile"><b class="serif num">{fmt(s.unique)}</b><span>cartes uniques</span></div>
    <div class="tile"><b class="serif num">{fmt(s.copies)}</b><span>exemplaires</span><small>{plural(s.duplicates, 'carte')} en doublon</small></div>
    <div class="tile"><b class="serif num">{fmt(s.shiny)}</b><span>chromatiques</span><small>{fmt(s.locked)} verrouillées</small></div>
    {#if app.info.bank}<div class="tile wide"><b class="serif num">{fmt(recycle.total)} <small>Wikiki</small></b><span>doublons recyclables</span><small>{plural(recycle.n, 'exemplaire en trop', 'exemplaires en trop')}, hors verrouillées et chromatiques</small></div>{/if}
  </div>

  <h2 class="sec">Répartition par rareté</h2>
  <div class="bars">
    {#each s.rarities as r}
      <div class="bar" style:--c={color(r.code)}>
        <span class="lab">{r.label}</span><div class="track"><i style:width="{(r.unique / maxU) * 100}%"></i></div><span class="n muted">{plural(r.unique, 'carte')} · ×{fmt(r.copies)}</span>
      </div>
    {/each}
  </div>

  <h2 class="sec">Les plus lues</h2>
  <div class="list">
    {#each s.top_reads as c}<button class="item" style:--c={color(c.rarity)} onclick={() => open(c)}><i></i><span class="t serif">{c.name}</span><span class="muted"><Icon name="eye" /> {compact(c.reads)}</span></button>{/each}
  </div>
  {#if s.top_copies.length}
    <h2 class="sec">En plusieurs exemplaires</h2>
    <div class="list">{#each s.top_copies as c}<button class="item" style:--c={color(c.rarity)} onclick={() => open(c)}><i></i><span class="t serif">{c.name}</span><span class="muted">×{c.copies}</span></button>{/each}</div>
  {/if}
{/if}

<style>
  .hero { display: flex; align-items: center; gap: 20px; padding: 22px; border-radius: var(--rad-xl); background: radial-gradient(90% 140% at 100% 0%, rgba(227, 189, 108, .14), transparent 60%), rgba(255, 255, 255, .02); border: 1px solid rgba(227, 189, 108, .22); }
  .rk { font-size: 56px; line-height: 1; color: #fff5dd; }
  .hero p { font-size: 13.5px; }
  .tiles { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-top: 12px; }
  .tile { display: grid; gap: 2px; padding: 16px; background: linear-gradient(180deg, rgba(255, 255, 255, .035), rgba(255, 255, 255, .012)); border: 1px solid var(--line); border-radius: var(--rad-l); }
  .tile.wide { grid-column: 1 / -1; }
  .tile b { font-size: 32px; font-weight: 500; line-height: 1.1; }
  .tile b small { font-size: 14px; color: var(--muted); }
  .tile span { font: 600 13px var(--sans); letter-spacing: .08em; font-variant-caps: all-small-caps; color: var(--muted); }
  .tile small { color: var(--muted); font-size: 12.5px; }
  .bars { display: grid; gap: 4px; }
  .bar { display: grid; grid-template-columns: 110px 1fr; grid-template-rows: auto auto; gap: 2px 12px; align-items: center; padding: 6px 0; }
  .lab { display: inline-flex; align-items: center; gap: 9px; font-size: 14px; }
  .lab::before { content: ""; width: 7px; height: 7px; transform: rotate(45deg); background: var(--c); box-shadow: 0 0 8px var(--c); }
  .track { height: 6px; background: rgba(255, 255, 255, .05); border-radius: 3px; overflow: hidden; }
  .track i { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, color-mix(in srgb, var(--c) 55%, transparent), var(--c)); }
  .n { grid-column: 2; font-size: 12.5px; }
  .item { width: 100%; cursor: pointer; text-align: left; font: inherit; color: inherit; min-height: 48px; }
  .item i { width: 7px; height: 7px; transform: rotate(45deg); background: var(--c); flex: none; }
  .t { flex: 1; font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  @media (min-width: 700px) { .tiles { grid-template-columns: repeat(4, 1fr); } .tile.wide { grid-column: span 2; } .rk { font-size: 72px; } }
</style>
