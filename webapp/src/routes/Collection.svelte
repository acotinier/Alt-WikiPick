<script>
  // La collection : recherche, raretés, tri, doublons. Défilement virtuel : seules les cartes visibles existent dans la page.
  import { call } from '../lib/api.js';
  import { debounce, fmt, plural, rarityRank, color, EXCLUSIVE } from '../lib/format.js';
  import { app, coll, collectionChanged, hidden, openCard, run, setHidden, setLocks, setTagMany, toast, ui } from '../lib/store.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import Sheet from '../ui/Sheet.svelte';
  import VirtualGrid from '../ui/VirtualGrid.svelte';

  let q = $state(''), typed = $state(''), sort = $state('rarity'), tag = $state(''), dups = $state(false), rars = $state([]), filters = $state(false), showHidden = $state(false), hideExcl = $state(false);
  let selecting = $state(false), sel = $state(new Set()), tagSheet = $state(false);
  const setQ = debounce((v) => (q = v.trim().toLowerCase()), 160);

  call('prefs_get').then((r) => { if (r && r.ok) { if (['rarity', 'reads', 'name', 'copies', 'recent'].includes(r.prefs.collection_sort)) sort = r.prefs.collection_sort; hideExcl = r.prefs.hide_exclusive === true; } });
  const setHideExcl = (v) => { hideExcl = v; call('prefs_set', 'hide_exclusive', v); };
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
      && (!tag || (c.tags || []).map(String).includes(tag)) && (!dups || c.copies > 1) && hidden.set.has(c.cid) === showHidden && (showHidden || !(hideExcl && EXCLUSIVE.includes(c.rarity))));
    return out.sort(SORTS[sort]);
  });
  const toggle = (r) => (rars = rars.includes(r) ? rars.filter((x) => x !== r) : [...rars, r]);
  const active = $derived((tag ? 1 : 0) + (dups ? 1 : 0) + (showHidden ? 1 : 0) + (hideExcl ? 1 : 0) + (sort !== 'rarity' ? 1 : 0));

  // ---- sélection multiple : verrouiller, étiqueter ou masquer en masse (au plus 500 à la fois vers le jeu, le reste par paquets) ----
  const chunks = (arr, n = 500) => Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n));
  const chosen = $derived(coll.cards.filter((c) => sel.has(c.cid)));
  const freeIds = $derived(chosen.flatMap((c) => c.free_ids || []));
  const lockedIds = $derived(chosen.flatMap((c) => c.locked_ids || []));
  const pick = (c) => { const s = new Set(sel); if (s.has(c.cid)) s.delete(c.cid); else s.add(c.cid); sel = s; };
  const endSel = () => { selecting = false; sel = new Set(); tagSheet = false; };
  const selectList = () => (sel = new Set(list.map((c) => c.cid)));
  const selectDups = () => (sel = new Set(list.filter((c) => c.copies > 1).map((c) => c.cid)));
  async function lockAll(on) {
    const ids = on ? freeIds : lockedIds, done = [];
    if (!ids.length) return toast(on ? 'Ces cartes sont déjà verrouillées.' : "Aucune de ces cartes n'est verrouillée.", 'error');
    await run(async () => { for (const part of chunks(ids)) { const r = await call('cards_lock', part, on); if (!r.ok) return r; done.push(...r.ids); } return { ok: true }; },
      () => { toast(done.length ? `${plural(done.length, on ? 'exemplaire verrouillé' : 'exemplaire déverrouillé', on ? 'exemplaires verrouillés' : 'exemplaires déverrouillés')}.` : 'Rien à changer : les cartes exclusives n’ont pas de cadenas.', done.length ? 'good' : 'error'); });
    if (done.length) { setLocks(done, on); collectionChanged(); }
  }
  const portent = (tid) => chosen.filter((c) => (c.tags || []).includes(tid)).length;
  async function tagAll(t) {
    const pose = portent(t.id) !== chosen.length, cids = [...sel], done = [];
    await run(async () => { for (const part of chunks(cids)) { const r = await call('cards_tag', part, t.id, pose); if (!r.ok) return r; done.push(...r.cids); } return { ok: true }; },
      () => toast(`« ${t.name} » ${pose ? 'posée sur' : 'retirée de'} ${plural(done.length, 'carte')}.`, 'good'));
    if (done.length) setTagMany(done, t.id, pose);
  }
  async function hideSel(on = true) {
    const cids = [...sel];
    await run(async () => { let r; for (const part of chunks(cids)) { r = await call('hidden_set', part, on); if (!r.ok) return r; } return r; },
      (r) => { setHidden(r.list); toast(on ? `${plural(cids.length, 'carte masquée', 'cartes masquées')} : retrouve-les avec « Seulement les cartes masquées ».` : `${plural(cids.length, 'carte réaffichée', 'cartes réaffichées')} dans ta collection.`, 'good'); sel = new Set(); });
  }
</script>

<div class="bar">
  <label class="search"><Icon name="search" /><input type="search" placeholder="Rechercher une carte" autocomplete="off" bind:value={typed} oninput={() => setQ(typed)} /></label>
  <button class="btn selb" class:on={selecting} onclick={() => (selecting ? endSel() : (selecting = true))} aria-label={selecting ? 'Terminer la sélection' : 'Sélectionner des cartes'} aria-pressed={selecting}><Icon name="check" /></button>
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
  <VirtualGrid items={list} key={(c) => c.cid + (c.shiny ? '*' : '')} resetKey={`${q}|${sort}|${tag}|${dups}|${showHidden}|${hideExcl}|${rars.join()}`}>
    {#snippet item(c)}<Card card={c} picked={selecting && sel.has(c.cid)} onclick={() => (selecting ? pick(c) : openCard(c))} />{/snippet}
  </VirtualGrid>
{/if}
{#if selecting}<div class="pad"></div>{/if}

{#if selecting}
  <div class="selbar" role="toolbar" aria-label="Sélection de cartes">
    <div class="sinfo"><b class="num">{fmt(sel.size)}</b> {sel.size > 1 ? 'cartes sélectionnées' : 'carte sélectionnée'}<small>{sel.size ? `${plural(freeIds.length, 'exemplaire libre', 'exemplaires libres')} · ${plural(lockedIds.length, 'verrouillé', 'verrouillés')}` : 'Touche des cartes pour les choisir'}</small></div>
    <div class="spick"><button onclick={selectList}>Toute la liste ({fmt(list.length)})</button><button onclick={selectDups}>Les doublons</button><button disabled={!sel.size} onclick={() => (sel = new Set())}>Aucune</button></div>
    <div class="sacts">
      <button class="btn small" disabled={!sel.size} onclick={() => (tagSheet = true)}>Étiqueter</button>
      <ConfirmButton small label="Verrouiller" confirm="Confirmer" disabled={!sel.size} onconfirm={() => lockAll(true)} />
      <ConfirmButton small label="Déverrouiller" confirm="Confirmer" disabled={!sel.size} onconfirm={() => lockAll(false)} />
      <button class="btn small" disabled={!sel.size} onclick={() => hideSel(!showHidden)}>{showHidden ? 'Réafficher' : 'Masquer'}</button>
      <button class="btn small primary" onclick={endSel}>Terminer</button>
    </div>
  </div>
{/if}

<Sheet open={tagSheet} onclose={() => (tagSheet = false)} title={`Étiqueter ${plural(sel.size, 'carte')}`}>
  {#if coll.tags.length}
    <p class="muted">Touche une étiquette : si toutes les cartes l'ont déjà, elle est retirée de toutes ; sinon elle est posée sur toutes.</p>
    <div class="tgs">{#each coll.tags as t (t.id)}
      <button class="tg" class:all={portent(t.id) === chosen.length && chosen.length > 0} style:--t={t.color} onclick={() => tagAll(t)}>{portent(t.id) === chosen.length ? '✓ ' : ''}{t.name}<small class="num">{portent(t.id)}/{chosen.length}</small></button>
    {/each}</div>
  {:else}<p class="muted">Tu n'as pas encore d'étiquette.</p>{/if}
  <button class="btn block" style="margin-top:14px" onclick={() => { tagSheet = false; ui.tags = true; }}>Gérer mes étiquettes</button>
</Sheet>

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
    <label class="check"><input type="checkbox" checked={hideExcl} onchange={(e) => setHideExcl(e.target.checked)} />Masquer les cartes exclusives</label>
    <label class="check"><input type="checkbox" bind:checked={showHidden} />Seulement les cartes masquées ({hidden.list.length})</label>
    <button class="btn block" onclick={() => { filters = false; ui.tags = true; }}>Gérer mes étiquettes</button>
    <button class="btn primary block" onclick={() => (filters = false)}>Voir {plural(list.length, 'carte')}</button>
  </div>
</Sheet>

<style>
  .bar { display: flex; gap: 10px; }
  .selb { width: 44px; padding: 0; }
  .selb.on { color: var(--on-ivory); background: linear-gradient(180deg, #f6e2b0, var(--ivory-2)); border-color: transparent; }
  .pad { height: 190px; }
  .selbar { position: fixed; z-index: 25; left: 10px; right: 10px; bottom: calc(var(--nav) + var(--sab) + 2px); display: grid; gap: 10px; padding: 12px 14px; background: var(--glass); backdrop-filter: blur(20px) saturate(1.5);
    border: 1px solid var(--line-3); border-radius: 18px; box-shadow: 0 20px 44px -16px rgba(0, 0, 0, .95), inset 0 1px 0 rgba(228, 197, 133, .14); animation: pop .3s var(--spring); }
  .sinfo { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; } .sinfo b { font: 600 22px var(--serif); color: var(--ivory); } .sinfo small { flex-basis: 100%; color: var(--muted); font-size: 12.5px; }
  .spick { display: flex; gap: 14px; flex-wrap: wrap; } .spick button { padding: 0; background: none; border: 0; color: var(--ivory); font-size: 13.5px; text-decoration: underline; text-underline-offset: 3px; cursor: pointer; } .spick button:disabled { opacity: .4; cursor: default; }
  .sacts { display: flex; gap: 8px; flex-wrap: wrap; }
  .tgs { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .tg { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 14px; color: var(--text); font: 500 14px var(--sans); cursor: pointer; background: color-mix(in srgb, var(--t) 22%, transparent); border: 1px solid color-mix(in srgb, var(--t) 60%, transparent); border-radius: 99px; }
  .tg.all { background: var(--t); color: #0b0b0b; } .tg small { opacity: .8; font-size: 12px; }
  @media (min-width: 980px) { .selbar { left: calc(var(--rail) + 24px); right: 24px; bottom: 20px; grid-template-columns: auto 1fr auto; align-items: center; } .sinfo small { flex-basis: auto; } }
  .search { flex: 1; display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 14px; color: var(--faint); background: var(--ink-2); border: 1px solid var(--line-2); border-radius: 12px; }
  .search:focus-within { color: var(--text); border-color: rgba(228, 197, 133, .5); box-shadow: 0 0 0 3px rgba(228, 197, 133, .1); }
  .search input { flex: 1; min-width: 0; height: 100%; background: none; border: 0; outline: 0; color: var(--text); font: 16px var(--sans); }
  .filt { position: relative; width: 44px; padding: 0; }
  .filt .badge { position: absolute; top: -6px; right: -6px; font-style: normal; }
  .chips { display: flex; gap: 8px; margin: 14px calc(var(--gut) * -1) 0; padding: 0 var(--gut) 4px; overflow-x: auto; scrollbar-width: none; scroll-snap-type: x proximity; }
  .chips::-webkit-scrollbar { display: none; }
  .chip { flex: none; display: inline-flex; align-items: center; gap: 8px; min-height: 34px; padding: 0 13px 0 11px; color: var(--muted); font: 500 13.5px var(--sans); cursor: pointer; scroll-snap-align: start;
    background: rgba(228, 197, 133, .03); border: 1px solid var(--line); border-radius: 99px; transition: all .18s var(--ease); }
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
