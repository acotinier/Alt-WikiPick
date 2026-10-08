<script>
  // La collection : recherche, raretés, tri, doublons. Défilement virtuel : seules les cartes visibles existent dans la page.
  import { call } from '../lib/api.js';
  import { debounce, fmt, plural, rarityRank, color } from '../lib/format.js';
  import { app, coll, hidden, openCard, ui } from '../lib/store.svelte.js';
  import Card from '../ui/Card.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import Sheet from '../ui/Sheet.svelte';
  import VirtualGrid from '../ui/VirtualGrid.svelte';

  let q = $state(''), typed = $state(''), sort = $state('rarity'), tag = $state(''), dups = $state(false), rars = $state([]), filters = $state(false), showHidden = $state(false);
  const setQ = debounce((v) => (q = v.trim().toLowerCase()), 160);

  call('prefs_get').then((r) => { if (r && r.ok && ['rarity', 'reads', 'name', 'copies', 'recent'].includes(r.prefs.collection_sort)) sort = r.prefs.collection_sort; });
  const changeSort = (v) => { sort = v; call('prefs_set', 'collection_sort', v); };

  const present = $derived([...new Set(coll.cards.map((c) => c.rarity))].sort((a, b) => rarityRank(a) - rarityRank(b)));
  // date d'obtention : le dernier exemplaire reçu (les identifiants d'exemplaires croissent avec le temps, quelle que soit la source :
  // paquet, échange, achat, fusion, récompense). Calculé une fois par carte.
  const lastId = (() => { const m = new WeakMap(); return (c) => { let v = m.get(c); if (v === undefined) { v = 0; for (const i of c.ids || []) if (i > v) v = i; m.set(c, v); } return v; }; })();
  const SORTS = {
    recent: (a, b) => lastId(b) - lastId(a) || rarityRank(a.rarity) - rarityRank(b.rarity),
    reads: (a, b) => b.reads - a.reads,
    rarity: (a, b) => rarityRank(a.rarity) - rarityRank(b.rarity) || Number(b.shiny) - Number(a.shiny) || b.reads - a.reads,
    name: (a, b) => a.name.localeCompare(b.name, 'fr'),
    copies: (a, b) => b.copies - a.copies || b.reads - a.reads,
  };
  const list = $derived.by(() => {
    const out = coll.cards.filter((c) => (!rars.length || rars.includes(c.rarity)) && (!q || c.name.toLowerCase().includes(q) || c.desc.toLowerCase().includes(q))
      && (!tag || (c.tags || []).map(String).includes(tag)) && (!dups || c.copies > 1) && hidden.set.has(c.cid) === showHidden);
    return out.sort(SORTS[sort]);
  });
  const toggle = (r) => (rars = rars.includes(r) ? rars.filter((x) => x !== r) : [...rars, r]);
  const active = $derived((tag ? 1 : 0) + (dups ? 1 : 0) + (showHidden ? 1 : 0) + (sort !== 'rarity' ? 1 : 0));
</script>

<div class="bar">
  <label class="search"><Icon name="search" /><input type="search" placeholder="Rechercher une carte" autocomplete="off" bind:value={typed} oninput={() => setQ(typed)} /></label>
  <button class="btn filt" onclick={() => (filters = true)} aria-label="Filtres et tri"><Icon name="list" />{#if active}<i class="badge">{active}</i>{/if}</button>
</div>

<div class="chips" role="group" aria-label="Raretés">
  {#each present as r}
    <button class="chip" class:on={rars.includes(r)} style:--c={color(r)} onclick={() => toggle(r)}>{app.names[r] || r}</button>
  {/each}
</div>

<p class="count muted">{coll.loaded ? `${fmt(list.length)} carte${list.length > 1 ? 's' : ''}` : 'Chargement…'}{#if coll.loading && coll.loaded}<Icon name="refresh" />{/if}</p>

{#if !coll.loaded}
  <div class="grid">{#each Array(12) as _}<div class="skeleton sk"></div>{/each}</div>
{:else if !list.length}
  <div class="grid"><Empty title="Aucune carte" text={coll.cards.length ? 'Aucune carte ne correspond à ces filtres.' : 'Ouvre quelques paquets pour commencer ta collection.'} /></div>
{:else}
  <VirtualGrid items={list} key={(c) => c.cid + (c.shiny ? '*' : '')} resetKey={`${q}|${sort}|${tag}|${dups}|${showHidden}|${rars.join()}`}>
    {#snippet item(c)}<Card card={c} onclick={() => openCard(c)} />{/snippet}
  </VirtualGrid>
{/if}

<Sheet open={filters} onclose={() => (filters = false)} title="Filtres et tri">
  <div class="form">
    <label>Trier par
      <select value={sort} onchange={(e) => changeSort(e.target.value)}>
        <option value="rarity">Rareté</option><option value="recent">Date d'obtention</option><option value="reads">Lectures</option><option value="name">Nom</option><option value="copies">Exemplaires</option>
      </select>
    </label>
    <label>Tag
      <select bind:value={tag}><option value="">Tous les tags</option>{#each coll.tags as t}<option value={String(t.id)}>{t.name}</option>{/each}</select>
    </label>
    <label class="check"><input type="checkbox" bind:checked={dups} />Doublons seulement</label>
    <label class="check"><input type="checkbox" bind:checked={showHidden} />Seulement les cartes masquées ({hidden.list.length})</label>
    <button class="btn block" onclick={() => { filters = false; ui.tags = true; }}>Gérer mes étiquettes</button>
    <button class="btn primary block" onclick={() => (filters = false)}>Voir {plural(list.length, 'carte')}</button>
  </div>
</Sheet>

<style>
  .bar { display: flex; gap: 10px; }
  .search { flex: 1; display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 14px; color: var(--faint); background: var(--ink-2); border: 1px solid var(--line-2); border-radius: 12px; }
  .search:focus-within { color: var(--text); border-color: rgba(241, 232, 212, .5); box-shadow: 0 0 0 3px rgba(241, 232, 212, .1); }
  .search input { flex: 1; min-width: 0; height: 100%; background: none; border: 0; outline: 0; color: var(--text); font: 16px var(--sans); }
  .filt { position: relative; width: 44px; padding: 0; }
  .filt .badge { position: absolute; top: -6px; right: -6px; font-style: normal; }
  .chips { display: flex; gap: 8px; margin: 14px calc(var(--gut) * -1) 0; padding: 0 var(--gut) 4px; overflow-x: auto; scrollbar-width: none; scroll-snap-type: x proximity; }
  .chips::-webkit-scrollbar { display: none; }
  .chip { flex: none; display: inline-flex; align-items: center; gap: 8px; min-height: 34px; padding: 0 13px 0 11px; color: var(--muted); font: 500 13.5px var(--sans); cursor: pointer; scroll-snap-align: start;
    background: rgba(255, 255, 255, .025); border: 1px solid var(--line); border-radius: 99px; transition: all .18s var(--ease); }
  .chip::before { content: ""; width: 8px; height: 8px; transform: rotate(45deg); border-radius: 2px; background: var(--c); box-shadow: 0 0 8px -1px var(--c); }
  .chip.on { color: var(--text); background: color-mix(in srgb, var(--c) 14%, transparent); border-color: color-mix(in srgb, var(--c) 55%, transparent); }
  .count { display: flex; align-items: center; gap: 8px; margin: 12px 2px 12px; font-size: 13px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px 12px; }
  .sk { aspect-ratio: 5 / 7; border-radius: 13px; }
  .form { display: grid; gap: 16px; padding-top: 6px; }
  .form label { display: grid; gap: 6px; font-size: 13px; color: var(--muted); }
  .check { display: flex !important; align-items: center; gap: 10px; color: var(--text) !important; font-size: 15px !important; }
  .check input { width: 20px; height: 20px; accent-color: var(--ivory); }
  @media (min-width: 700px) { .grid { grid-template-columns: repeat(auto-fill, minmax(176px, 1fr)); gap: 22px 18px; } }
</style>
