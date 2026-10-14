<script>
  // Un clic = un paquet (jamais en boucle). Quand le site demande sa vérification, on pose SA question au joueur et on transmet SON clic.
  import { call } from '../lib/api.js';
  import { clock, color, fmt, isTop, plural, rarityRank, ago } from '../lib/format.js';
  import { app, collectionChanged, openCard, refreshMe, toast } from '../lib/store.svelte.js';
  import { tick } from '../lib/ticker.svelte.js';
  import Card from '../ui/Card.svelte';
  import Challenge from '../ui/Challenge.svelte';
  import RarityFx from '../ui/RarityFx.svelte';
  import Sheet from '../ui/Sheet.svelte';

  let phase = $state('idle'), cards = $state([]), flipped = $state([]), opening = $state(false), ask = $state(null), history = $state([]), shown = $state(6);
  const me = $derived(app.me || {});
  let batch = $state(null), many = $state(null);   // many : null = le maximum disponible (par défaut)
  const maxK = $derived(Math.min(me.packs ?? 0, 20));
  const k = $derived(Math.max(2, Math.min(many ?? maxK, maxK)));
  const n = $derived(me.packs ?? 0);
  const gold = $derived(!!(me.proPack || me.paquetOr));
  const left = $derived(me.next != null ? Math.max(0, Math.ceil(me.next - (tick.now - app.meAt) / 1000)) : null);
  const full = $derived((me.packReserve ?? me.packs ?? 0) >= (me.packMax ?? Infinity));
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const loadHistory = () => call('pack_history').then((r) => { if (r.ok) history = r.packs; });
  loadHistory();

  async function challenge() { // -> { defi, rep } ou null si le joueur renonce
    const r = await call('pack_challenge');
    if (!r.ok) { if (!r.expired) toast(r.error || 'Vérification indisponible pour le moment.', 'error'); return null; }
    return new Promise((resolve) => { ask = { q: r.challenge, resolve }; });
  }
  const answer = (rep) => { const a = ask; ask = null; a.resolve({ defi: a.q.id, rep }); };
  const other = async () => { const a = ask; ask = null; a.resolve(await challenge()); };
  const cancel = () => { const a = ask; ask = null; a.resolve(null); };

  async function open(kind, proof) {
    if (opening || (kind === 'gold' ? !gold : n < 1)) return;
    if (kind !== 'gold' && !proof && me.defi) { // le site veut une vérification : sa question d'abord, le paquet ensuite
      opening = true; const p = await challenge(); opening = false;
      return p ? open(kind, p) : undefined;
    }
    opening = true; phase = 'tearing';
    const [r] = await Promise.all([kind === 'gold' ? call('open_gold_pack') : proof ? call('open_pack', proof.defi, proof.rep) : call('open_pack'), sleep(reduced ? 150 : 900)]);
    if (!r.ok) {
      opening = false; phase = 'idle';
      if (r.expired) return;
      if (r.challenge && !proof) { app.me.defi = true; return open(kind); }
      return toast(r.error || 'Ouverture impossible', 'error');
    }
    app.me = r.me; app.meAt = Date.now();
    cards = [...r.cards].sort((a, b) => rarityRank(b.rarity) - rarityRank(a.rarity) || Number(a.shiny) - Number(b.shiny)); // la meilleure pour la fin
    flipped = []; phase = 'reveal'; opening = false;
    scrollTo({ top: 0 }); // sur téléphone la page peut être plus bas : la révélation commence en haut
    call('pack_seen'); // « les cartes sont à l'écran », comme le fait le site
    if (history) loadHistory();
  }
  // plusieurs paquets d'affilée : nombre choisi par le joueur ; s'arrête si le site demande sa vérification (c'est alors à toi d'y répondre)
  async function openMany(count, proof) {
    if (opening || n < 2) return;
    if (!proof && me.defi) { opening = true; const p = await challenge(); opening = false; return p ? openMany(count, p) : undefined; }
    opening = true;
    const r = proof ? await call('open_packs', count, proof.defi, proof.rep) : await call('open_packs', count);
    opening = false;
    if (!r.ok) {
      if (r.expired) return;
      if (r.challenge && !proof) { app.me.defi = true; return openMany(count); }
      return toast(r.error || 'Ouverture impossible', 'error');
    }
    app.me = r.me; app.meAt = Date.now();
    many = null;
    batch = { packs: r.packs.length, wanted: r.wanted, stopped: r.stopped, error: r.error, cards: r.packs.flat().sort((a, b) => rarityRank(a.rarity) - rarityRank(b.rarity) || Number(b.shiny) - Number(a.shiny)) };
    phase = 'batch'; scrollTo({ top: 0 });
    call('pack_seen');
    loadHistory(); collectionChanged();
  }
  const closeBatch = () => { batch = null; phase = 'idle'; scrollTo({ top: 0 }); collectionChanged(); refreshMe(); };
  // une belle carte (Épique et plus) déclenche une mise en scène d'autant plus folle que la rareté est haute
  const GALA = ['SR', 'UR', 'L', 'M'];
  let fx = $state(null), shake = $state(false), fxN = 0;
  const FX_MS = { SR: 1700, UR: 2700, L: 4500, M: 7500 };   // durée de chaque mise en scène (RarityFx), avec une marge
  const BUZZ = { SR: [30], UR: [40, 40, 80], L: [60, 50, 60, 200], M: [30, 40, 30, 40, 40, 40, 60, 40, 80, 40, 400, 80, 120] };
  function celebrate(c) {
    if (reduced || !GALA.includes(c.rarity)) return;
    fx = { r: c.rarity, n: ++fxN, title: app.names[c.rarity] || c.rarity, card: c };
    if (c.rarity === 'L' || c.rarity === 'M') { shake = c.rarity; setTimeout(() => (shake = false), c.rarity === 'M' ? 3300 : 1900); }
    try { navigator.vibrate && navigator.vibrate(BUZZ[c.rarity]); } catch { /* pas de vibreur : tant pis */ }
    const n = fxN; setTimeout(() => { if (fx && fx.n === n) fx = null; }, FX_MS[c.rarity]);
  }
  const flip = (i) => { if (!flipped.includes(i)) { flipped = [...flipped, i]; celebrate(cards[i]); } else openCard(cards[i]); };
  async function flipAll() { // « tout retourner » : seule la plus belle carte a droit à sa mise en scène
    const todo = cards.map((c, i) => i).filter((i) => !flipped.includes(i));
    const best = todo.reduce((b, i) => (b < 0 || rarityRank(cards[i].rarity) < rarityRank(cards[b].rarity) ? i : b), -1);
    for (const i of todo) { flipped = [...flipped, i]; if (i === best) celebrate(cards[i]); await sleep(reduced ? 0 : 220); }
  }
  // ---- démonstration : un tirage FICTIF (aucun appel au jeu, rien ne change dans ta collection) pour voir l'animation de chaque rareté ----
  const DEMO = [["Lune", "satellite naturel de la Terre", "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/e1/FullMoon2010.jpg/330px-FullMoon2010.jpg"], ["Mont Blanc", "plus haut sommet des Alpes", "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d0/Mont_Blanc_oct_2005.jpg/330px-Mont_Blanc_oct_2005.jpg"], ["Lion", "espèce de mammifères carnivores", "https://thumb.wikimedia.org/wikipedia/commons/thumb/7/73/Lion_waiting_in_Namibia.jpg/330px-Lion_waiting_in_Namibia.jpg"], ["La Grande Vague de Kanagawa", "estampe de Hokusai, 1830", "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a5/Tsunami_by_hokusai_19th_century.jpg/330px-Tsunami_by_hokusai_19th_century.jpg"], ["Tour Eiffel", "tour de fer puddlé de 330 mètres à Paris", "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/a8/Tour_Eiffel_Wikimedia_Commons.jpg/330px-Tour_Eiffel_Wikimedia_Commons.jpg"]];
  const DEMO_RARITIES = ['C', 'PC', 'R', 'SR', 'UR', 'L', 'M'];
  let demo = $state(false), demoPick = $state(false);
  function startDemo(r) {
    const lower = ['C', 'C', 'PC', 'R', 'SR'].filter((x) => rarityRank(x) > rarityRank(r)).slice(0, 4);
    while (lower.length < 4) lower.unshift('C');
    const order = [...lower, r];
    cards = order.map((rar, i) => ({ cid: 'demo:' + i, name: DEMO[i][0], desc: DEMO[i][1], img: DEMO[i][2], rarity: rar, reads: 9000 + i * 4300000, shiny: false, copies: 1, locked: false, tags: [], ids: [], new: i % 2 === 1 }));
    flipped = []; demo = true; demoPick = false; phase = 'reveal'; scrollTo({ top: 0 });
  }
  const done = (again) => { if (demo) { demo = false; phase = 'idle'; cards = []; scrollTo({ top: 0 }); return; } phase = 'idle'; scrollTo({ top: 0 }); collectionChanged(); refreshMe(); if (again) open(); };
  const finished = $derived(phase === 'reveal' && flipped.length >= cards.length);
  const best = $derived(cards[cards.length - 1]);

  // ta chance mesurée : paquets contenant au moins une carte de la rareté, contre les chances annoncées par le site
  const luck = $derived.by(() => {
    const odds = app.info.odds || {}, nb = history.length, rows = [];
    for (const r of ['M', 'L', 'UR', 'SR', 'R']) {
      if (odds[r] == null || odds[r] >= 50) continue;
      rows.push([r, app.names[r] || r, history.filter((p) => p.cards.some((c) => c.rarity === r)).length, (nb * odds[r]) / 100]);
    }
    return { nb, rows };
  });
  const dec = (x) => (x > 0 && x < 0.1 ? '< 0,1' : x.toLocaleString('fr-FR', { maximumFractionDigits: 1 }));
</script>

{#if phase === 'batch' && batch}
  <section class="batch">
    <h2 class="serif">{plural(batch.packs, 'paquet')} ouvert{batch.packs > 1 ? 's' : ''}</h2>
    <p class="muted">{plural(batch.cards.length, 'carte')}, dont {plural(batch.cards.filter((c) => c.new).length, 'nouvelle')}.{#if batch.cards.length} La plus rare : <b style:color={color(batch.cards[0].rarity)}>{batch.cards[0].name}</b>.{/if}</p>
    {#if batch.stopped === 'challenge'}<p class="note">Le site demande une petite vérification : elle t'attend au prochain paquet que tu ouvres.</p>
    {:else if batch.stopped === 'error'}<p class="note">Arrêt après {plural(batch.packs, 'paquet')} : {batch.error}</p>
    {:else if batch.packs < batch.wanted}<p class="note">Plus de paquet en réserve : {plural(batch.packs, 'paquet')} ouvert{batch.packs > 1 ? 's' : ''} sur {batch.wanted}.</p>{/if}
    <div class="bgrid">{#each batch.cards as c, i (c.cid + i)}<Card card={c} width={150} onclick={() => openCard(c)}>{#if c.new}<span class="new">Nouvelle</span>{/if}</Card>{/each}</div>
    <button class="btn primary block" onclick={closeBatch}>Terminer</button>
  </section>
{:else if phase !== 'reveal'}
  <section class="idle">
    <div class="pack-wrap" class:empty={n < 1} class:tearing={phase === 'tearing'} data-n={Math.min(n, 3)}>
      <div class="pk under u2"><div class="art"></div></div><div class="pk under u1"><div class="art"></div></div>
      <div class="pk main"><div class="shape ptop"><div class="art"></div></div>
        <div class="shape pbody"><div class="art"><span class="logo serif">Wiki<span>·</span>Pick</span><span class="sub">5 articles au hasard</span></div></div><div class="flash"></div></div>
    </div>
    <h2 class="count serif">{n < 1 ? 'Aucun paquet en réserve' : plural(n, 'paquet') + ' en réserve'}</h2>
    <p class="next muted num">{left == null ? '' : full ? 'Réserve pleine' : `Prochain paquet dans ${clock(left)}`}</p>
    <div class="actions">
      <button class="btn primary big" disabled={opening || n < 1} onclick={() => open()}>{opening ? 'Ouverture…' : 'Ouvrir un paquet'}</button>
      <button class="btn small ghost demo" onclick={() => (demoPick = true)}>Voir les animations</button>
      {#if n >= 2}
        <div class="many">
          <div class="mhead"><span>Plusieurs d'un coup</span><div class="stepper"><button aria-label="Moins" disabled={k <= 2} onclick={() => (many = k - 1)}>−</button><b class="num">{k}</b><button aria-label="Plus" disabled={k >= maxK} onclick={() => (many = k + 1)}>+</button></div></div>
          {#if maxK > 2}<input class="range" type="range" min="2" max={maxK} step="1" value={k} aria-label="Nombre de paquets" oninput={(e) => (many = +e.currentTarget.value)} />{/if}
          <button class="btn big block" disabled={opening} onclick={() => openMany(k)}>Ouvrir {k} paquets d'un coup</button>
        </div>
      {/if}
      {#if gold}<button class="btn gold big" disabled={opening} onclick={() => open('gold')}>{me.proPack ? 'Paquet PRO du jour' : 'Ton paquet doré offert'} · {plural(me.proCards || 20, 'carte')}</button>{/if}
    </div>
  </section>

  {#if history.length}
    <section class="journal">
      <h2 class="sec">Tes derniers paquets</h2>
      <p class="muted small">{plural(history.length, 'paquet')} ouvert{history.length > 1 ? 's' : ''} avec l'appli.{history.length < 10 ? " La comparaison avec les chances du site devient parlante à partir d'une dizaine de paquets." : ''}</p>
      {#if luck.rows.length}
        <div class="luck">{#each luck.rows as [r, name, got, exp]}<div style:--c={color(r)}><span class="lab">{name}</span><b class="num">{got} sur {luck.nb}</b><small class="muted num">attendu : {dec(exp)}</small></div>{/each}</div>
      {/if}
      {#each history.slice(0, shown) as p}
        <div class="hrow"><small class="muted">{ago(p.ts)}</small><div class="minis">{#each [...p.cards].sort((a, b) => rarityRank(a.rarity) - rarityRank(b.rarity)) as c}
          <button class="mini" style:--c={color(c.rarity)} class:new={c.new} title={c.name} aria-label={c.name} onclick={() => openCard(c)}>{#if c.img}<img src={c.img} alt="" loading="lazy" />{/if}</button>{/each}</div></div>
      {/each}
      {#if history.length > shown}<button class="btn small block" onclick={() => (shown += 12)}>Voir plus de paquets</button>{/if}
    </section>
  {/if}
{:else}
  <section class="reveal" class:many={cards.length > 6} class:fx-shake-l={shake === 'L'} class:fx-shake-m={shake === 'M'} style:--n={cards.length} style:--rows={Math.ceil(cards.length / 3)}>
    <div class="pcards">
      {#each cards as c, i (c.cid + i)}
        <button class="pcard" class:open={flipped.includes(i)} class:top={isTop(c)} data-rv={flipped.includes(i) && GALA.includes(c.rarity) ? c.rarity : null} style:--i={i} style:--c={color(c.rarity)} aria-label={flipped.includes(i) ? c.name : 'Retourner la carte'} onclick={() => flip(i)}>
          <span class="inner"><span class="face back"><b class="serif">W·P</b></span>
            <span class="face front"><Card card={c} width={330}>{#if c.new}<span class="new">Nouvelle</span>{/if}</Card></span></span>
        </button>
      {/each}
    </div>
    {#if !finished}
      <div class="pbar"><div class="trk"><i style:width="{(flipped.length / cards.length) * 100}%"></i></div><span class="muted num">{flipped.length} sur {cards.length}</span><button class="btn small" onclick={flipAll}>Tout retourner</button></div>
    {:else}
      <div class="end">
        {#if demo}
          <p class="serif">Démonstration : {app.names[best.rarity] || best.rarity}. Ce paquet est fictif, ta collection n'a pas bougé.</p>
          <div class="row center"><button class="btn" onclick={() => done(false)}>Terminer</button><button class="btn primary" onclick={() => startDemo(best.rarity)}>Rejouer</button></div>
        {:else}
        <p class="serif">Paquet ouvert : {plural(cards.length, 'carte')}, dont {plural(cards.filter((c) => c.new).length, 'nouvelle')}. La plus rare : {best.name} ({app.names[best.rarity] || best.rarity}).</p>
        <div class="row center"><button class="btn" onclick={() => done(false)}>Terminer</button><button class="btn primary" disabled={n < 1} onclick={() => done(true)}>Ouvrir un autre paquet</button></div>
        {/if}
      </div>
    {/if}
  </section>
{/if}

<Sheet open={demoPick} onclose={() => (demoPick = false)} title="Voir les animations">
  <p class="muted">Un tirage fictif : la carte de la rareté choisie arrive en dernier. Ça ne consomme aucun paquet et ne touche pas à ta collection.</p>
  <div class="dpick">{#each DEMO_RARITIES as r}<button class="dchip" style:--c={color(r)} onclick={() => startDemo(r)}>{app.names[r] || r}</button>{/each}</div>
</Sheet>

{#if fx}{#key fx.n}<RarityFx r={fx.r} title={fx.title} card={fx.card} />{/key}{/if}

<Sheet open={!!ask} onclose={cancel} title="Avant d'ouvrir ton paquet">
  {#if ask}<Challenge challenge={ask.q} onanswer={answer} onother={other} oncancel={cancel} />{/if}
</Sheet>

<style>
  .idle { display: grid; justify-items: center; gap: 8px; padding: 20px 0 30px; text-align: center; }
  .count { font-size: 28px; margin-top: 8px; } .next { min-height: 21px; margin-bottom: 10px; }
  .actions { display: grid; gap: 12px; width: min(340px, 100%); }
  .actions .btn { width: 100%; }
  .pack-wrap { position: relative; width: clamp(130px, 22dvh, 190px); aspect-ratio: 5 / 8; margin: 6px 0 30px; perspective: 900px; animation: bob 5.5s ease-in-out infinite; }
  @keyframes bob { 50% { transform: translateY(-9px); } }
  .pk { position: absolute; inset: 0; filter: drop-shadow(0 26px 26px rgba(0, 0, 0, .55)) drop-shadow(0 0 36px rgba(80, 140, 255, .2)); }
  .pk.under { filter: drop-shadow(0 12px 14px rgba(0, 0, 0, .45)) brightness(.7); }
  .u1 { transform: translate(16px, 8px) rotate(5deg); } .u2 { transform: translate(-18px, 12px) rotate(-6deg); }
  .pack-wrap[data-n="0"] .under, .pack-wrap[data-n="1"] .under, .pack-wrap[data-n="2"] .u2 { display: none; }
  .pack-wrap.empty .main { filter: grayscale(.8) brightness(.5) drop-shadow(0 26px 28px rgba(0, 0, 0, .55)); }
  .shape { position: absolute; inset: 0; }
  .ptop { clip-path: polygon(0 0, 100% 0, 100% 13%, 90% 16%, 80% 13%, 70% 16%, 60% 13%, 50% 16%, 40% 13%, 30% 16%, 20% 13%, 10% 16%, 0 13%); transform-origin: 0 100%; }
  .pbody { clip-path: polygon(0 13%, 10% 16%, 20% 13%, 30% 16%, 40% 13%, 50% 16%, 60% 13%, 70% 16%, 80% 13%, 90% 16%, 100% 13%, 100% 100%, 0 100%); }
  .art { position: absolute; inset: 0; border-radius: 10px; overflow: hidden; background:
    repeating-linear-gradient(90deg, rgba(255, 255, 255, .18) 0 2px, transparent 2px 6px) top / 100% 3% no-repeat, repeating-linear-gradient(90deg, rgba(255, 255, 255, .18) 0 2px, transparent 2px 6px) bottom / 100% 3% no-repeat,
    radial-gradient(120% 60% at 50% 0%, rgba(255, 255, 255, .14), transparent 60%), linear-gradient(165deg, #15264a 0%, #1f4178 46%, #0e5a6e 100%); }
  .art::after { content: ""; position: absolute; inset: 0; mix-blend-mode: color-dodge; opacity: .5; background: linear-gradient(115deg, transparent 12%, rgba(255, 90, 200, .42) 30%, rgba(90, 220, 255, .48) 48%, rgba(255, 235, 120, .42) 66%, transparent 84%); }
  .pbody .art::before { content: ""; position: absolute; inset: 20% 9% 9%; border: 1px solid rgba(255, 255, 255, .28); border-radius: 6px; }
  .logo { position: absolute; left: 0; right: 0; top: 37%; text-align: center; font-size: 32px; font-weight: 700; line-height: 1; letter-spacing: -.02em; color: #f7f2e6; text-shadow: 0 2px 16px rgba(0, 0, 0, .5); }
  .logo span { color: var(--gold); }
  .sub { position: absolute; left: 0; right: 0; bottom: 15%; text-align: center; font: 600 12px var(--sans); letter-spacing: .16em; font-variant-caps: all-small-caps; color: rgba(255, 255, 255, .7); }
  .flash { position: absolute; left: -30%; right: -30%; top: 2%; height: 26%; opacity: 0; filter: blur(4px); background: radial-gradient(ellipse at center, rgba(255, 255, 255, .95), rgba(160, 220, 255, .4) 40%, transparent 70%); }
  .tearing .ptop { animation: tear-top .8s cubic-bezier(.3, .6, .2, 1) forwards; } .tearing .pbody { animation: tear-body .9s ease forwards; } .tearing .flash { animation: flash .9s .12s ease-out forwards; }
  @keyframes tear-top { 25% { transform: translate(0, -6px) rotate(-2deg); } 100% { transform: translate(26px, -120px) rotate(-16deg); opacity: 0; } }
  @keyframes tear-body { 15% { transform: translateX(-4px); } 30% { transform: translateX(4px); } 45% { transform: translateX(-3px); } 60% { transform: scale(1.03); } 100% { transform: translateY(30px) scale(.9); opacity: 0; } }
  @keyframes flash { 0% { opacity: 0; transform: scaleX(.3); } 30% { opacity: 1; } 100% { opacity: 0; transform: scaleX(1.6); } }

  /* la révélation tient dans l'écran, sans défilement : les cartes prennent la place restante (3 par rangée, 1 rangée dès 700 px) */
  .reveal.many { height: auto; display: grid; gap: 14px; justify-items: stretch; padding-bottom: calc(var(--nav) + var(--sab) + 70px); }
  .reveal.many .pcards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; align-content: start; container-type: normal; perspective: 1400px; }
  .reveal.many .pcard { width: auto; }
  .reveal.many .pbar, .reveal.many .end { position: sticky; bottom: calc(var(--nav) + var(--sab) + 10px); z-index: 5; height: auto; padding: 12px 14px; background: var(--glass); backdrop-filter: blur(14px); border: 1px solid var(--line-2); border-radius: 16px; }
  .reveal.many .end { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 12px; animation: none; } .reveal.many .end p { font-size: 15px; text-align: center; } .reveal.many .end .row { flex-wrap: nowrap; }
  .reveal { --bot: calc(var(--nav) + var(--sab)); --cols: 3; --rws: var(--rows); --gap: 12px;
    display: flex; flex-direction: column; align-items: center; gap: 10px; width: 100%;
    height: max(360px, calc(100dvh - var(--top) - var(--sat) - var(--bot) - 132px)); }
  .pcards { flex: 1; min-height: 0; width: 100%; container-type: size; display: flex; flex-wrap: wrap; align-content: center; justify-content: center; gap: var(--gap); perspective: 1200px; }
  .pcard { position: relative; flex: none; padding: 0; aspect-ratio: 5 / 7; width: min(calc((100cqw - (var(--cols) - 1) * var(--gap)) / var(--cols)), calc((100cqh - (var(--rws) - 1) * var(--gap)) / var(--rws) * 5 / 7)); background: none; border: 0; border-radius: 13px; cursor: pointer; animation: deal .55s cubic-bezier(.2, .9, .25, 1.1) backwards; animation-delay: calc(var(--i) * 90ms); }
  @keyframes deal { from { opacity: 0; transform: translateY(-50px) rotate(-5deg) scale(.85); } }
  .inner { position: absolute; inset: 0; transform-style: preserve-3d; transition: transform .7s cubic-bezier(.3, .7, .2, 1); }
  .pcard.open .inner { transform: rotateY(180deg); }
  .face { position: absolute; inset: 0; backface-visibility: hidden; -webkit-backface-visibility: hidden; border-radius: 13px; }
  .front { transform: rotateY(180deg); }
  .front :global(.card) { position: absolute; inset: 0; aspect-ratio: auto; content-visibility: visible; }
  .back { display: grid; place-items: center; border: 1px solid var(--line-2); box-shadow: inset 0 1px 0 rgba(255, 255, 255, .12), 0 20px 40px -20px rgba(0, 0, 0, .9);
    background: radial-gradient(120% 80% at 50% 0%, rgba(255, 255, 255, .08), transparent 55%), repeating-linear-gradient(45deg, rgba(255, 255, 255, .035) 0 1px, transparent 1px 9px), repeating-linear-gradient(-45deg, rgba(255, 255, 255, .035) 0 1px, transparent 1px 9px), linear-gradient(160deg, #1f4034, #0c211a 60%, #08160f); }
  .back b { font-size: 32px; color: rgba(255, 255, 255, .2); }
  .pcard.top:not(.open) .back { animation: aura 2.2s ease-in-out infinite; border-color: rgba(160, 210, 255, .4); }
  @keyframes aura { 50% { box-shadow: 0 0 34px 4px rgba(120, 200, 255, .45), inset 0 1px 0 rgba(255, 255, 255, .12); } }
  .pcard.pcard.open[data-rv="SR"] { animation: deal .55s backwards, rv-sr .9s .2s ease-out; }
  .pcard.pcard.open[data-rv="UR"] { animation: deal .55s backwards, rv-ur 1.2s .2s ease-out; }
  .pcard.pcard.open[data-rv="L"] { animation: deal .55s backwards, rv-l 1.6s .2s ease-out; z-index: 3; }
  .pcard.pcard.open[data-rv="M"] { animation: deal .55s backwards, rv-m 2.4s .2s ease-out; z-index: 4; }
  @keyframes rv-sr { 35% { transform: scale(1.07); filter: drop-shadow(0 0 22px #9b5de5); } }
  @keyframes rv-ur { 30% { transform: scale(1.1) rotate(-1deg); filter: drop-shadow(0 0 30px #f6c945); } 60% { transform: scale(1.05) rotate(.8deg); } }
  @keyframes rv-l { 20% { transform: scale(1.22) rotate(-2deg); filter: drop-shadow(0 0 44px #ff9a3c) brightness(1.25); } 50% { transform: scale(1.12) rotate(1.4deg); filter: drop-shadow(0 0 34px #ff9a3c); } 75% { transform: scale(1.06); } }
  @keyframes rv-m { 12% { transform: scale(1.35) rotate(-2.5deg); filter: drop-shadow(0 0 60px #f4d27a) brightness(1.4); } 45% { transform: scale(1.22) rotate(1.8deg); filter: drop-shadow(0 0 46px #f4d27a) brightness(1.15); } 75% { transform: scale(1.1); filter: drop-shadow(0 0 30px #f4d27a); } }
  .pcard.open.top { animation: deal .55s backwards, glow 1.3s .35s ease-out; } @keyframes glow { 30% { filter: drop-shadow(0 0 26px var(--c)); } }
  .new { position: absolute; top: 6px; left: 6px; z-index: 3; padding: 1px 9px; font: 600 11px/17px var(--sans); color: var(--on-ivory); background: var(--ivory); border-radius: 99px; }
  .pbar, .end { flex: none; height: 104px; align-content: center; }
  .pbar { display: flex; align-items: center; gap: 14px; width: 100%; max-width: 560px; }
  .trk { flex: 1; height: 3px; background: rgba(255, 255, 255, .08); border-radius: 2px; overflow: hidden; } .trk i { display: block; height: 100%; background: var(--ivory); transition: width .4s var(--ease); }
  .end { display: grid; gap: 18px; text-align: center; animation: rise .5s var(--ease); } .end { gap: 12px; } .end p { font-size: 16px; line-height: 1.3; max-width: 40ch; }

  .demo { justify-self: center; margin-top: 4px; }
  .dpick { display: grid; gap: 10px; margin-top: 14px; }
  .dchip { display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 0 16px; color: var(--text); font: 600 16px var(--serif); text-align: left; cursor: pointer;
    background: color-mix(in srgb, var(--c) 14%, var(--ink-2)); border: 1px solid color-mix(in srgb, var(--c) 55%, transparent); border-radius: 13px; }
  .dchip::before { content: ""; width: 10px; height: 10px; transform: rotate(45deg); border-radius: 2px; background: var(--c); box-shadow: 0 0 10px var(--c); }
  .many { display: grid; gap: 12px; width: 100%; padding: 14px; background: var(--ink-1); border: 1px solid var(--line); border-radius: 16px; }
  .mhead { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 14px; color: var(--muted); }
  .range { width: 100%; height: 28px; accent-color: var(--ivory); }
  .stepper { display: flex; align-items: center; gap: 2px; padding: 3px; background: var(--ink-2); border: 1px solid var(--line); border-radius: 12px; }
  .stepper button { width: 38px; height: 38px; color: var(--text); font: 600 20px var(--sans); background: none; border: 0; border-radius: 9px; cursor: pointer; } .stepper button:disabled { opacity: .35; cursor: default; }
  .stepper b { min-width: 34px; text-align: center; font: 600 19px var(--serif); color: var(--ivory); }
  .batch { display: grid; gap: 14px; } .batch .note { padding: 10px 12px; background: var(--ink-1); border: 1px solid var(--line); border-radius: 12px; font-size: 14px; }
  .bgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 12px; }
  .journal { margin-top: 10px; } .small { font-size: 12.5px; }
  .luck { display: grid; margin: 10px 0 18px; } .luck > div { display: grid; grid-template-columns: 1fr auto auto; gap: 14px; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--line); }
  .lab { display: inline-flex; align-items: center; gap: 9px; } .lab::before { content: ""; width: 7px; height: 7px; transform: rotate(45deg); background: var(--c); box-shadow: 0 0 8px var(--c); }
  .hrow { display: flex; align-items: center; gap: 14px; padding: 10px 0; border-bottom: 1px solid var(--line); } .hrow small { flex: none; width: 92px; }
  .minis { display: flex; flex-wrap: wrap; gap: 7px; }
  .mini { position: relative; width: 40px; aspect-ratio: 5 / 7; padding: 0; overflow: hidden; border: 1px solid var(--c); border-radius: 6px; background: #030b08; box-shadow: 0 0 12px -6px var(--c); cursor: pointer; }
  .mini img { width: 100%; height: 100%; object-fit: cover; } .mini.new::after { content: ""; position: absolute; top: 2px; right: 2px; width: 8px; height: 8px; border-radius: 50%; background: var(--ivory); }
  @media (min-width: 700px) { .reveal.many .pcards { grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; } .reveal.many { width: min(1000px, calc(100vw - 2 * var(--gut))); margin-left: 50%; transform: translateX(-50%); } }
  @media (min-width: 700px) { .reveal:not(.many) { --cols: var(--n); --rws: 1; --gap: 18px; width: min(1000px, calc(100vw - 2 * var(--gut))); margin-left: 50%; transform: translateX(-50%); } .pack-wrap { width: 220px; } }
  @media (min-width: 980px) { .reveal.many { width: min(1000px, calc(100vw - var(--rail) - 2 * var(--gut))); } .reveal.many .pbar, .reveal.many .end { bottom: 14px; } }
  @media (min-width: 980px) { .reveal { --bot: 0px; width: min(1000px, calc(100vw - var(--rail) - 2 * var(--gut))); } }
</style>
