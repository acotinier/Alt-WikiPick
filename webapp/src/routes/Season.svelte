<script>
  // Le Season Pass : cinquante niveaux, une récompense par niveau. La récompense choisie s'affiche en grand, les niveaux défilent en dessous.
  // Récupérer = un clic par niveau. Les récompenses réservées aux abonnés WIKI-PRO ne se récupèrent pas sans l'être : le serveur le refuse aussi.
  import { call } from '../lib/api.js';
  import { clock, color, fmt, plural } from '../lib/format.js';
  import { app, collectionChanged, run, toast, ui } from '../lib/store.svelte.js';
  import { levelProgress, levelState, loadSeason, season } from '../lib/season.svelte.js';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import RewardArt from '../ui/RewardArt.svelte';
  import Sheet from '../ui/Sheet.svelte';

  const KIND = { paquets: 'Paquets', dore: 'Paquet doré', wikiki: 'Wikiki', dos: 'Dos de carte', carte: 'Carte exclusive', skin: 'Skin de carte', cadre: 'Cadre de photo',
    vitrine: 'Vitrine', fond: 'Fond de vitrine', legende: 'Paquet légendaire', mythique: 'Paquet mythique' };
  const SITE = 'https://wiki-pick.com/season-pass';
  const d = $derived(season.d);
  const tone = (r) => (r === 'C' ? 'var(--ivory-2)' : color(r));
  let sel = $state(null), rules = $state(false), track = $state(null);

  loadSeason(true);
  const first = $derived(d && (d.levels.find((x) => levelState(d, x) === 'ready') || d.levels.find((x) => x.level > d.me.level) || d.levels[0]));
  $effect(() => { if (d && sel == null && first) sel = first.level; });
  const item = $derived(d && d.levels.find((x) => x.level === sel));
  const st = $derived(d && item ? levelState(d, item) : '');
  const ready = $derived(d ? d.levels.filter((x) => levelState(d, x) === 'ready').length : 0);
  const pct = $derived(Math.round(levelProgress(d) * 100));
  const left = $derived(d ? d.season.left : 0);

  // la case choisie se place au centre de la bande de niveaux
  $effect(() => {
    if (!track || sel == null) return;
    const el = track.querySelector(`[data-l="${sel}"]`);
    if (el) track.scrollTo({ left: el.offsetLeft - track.clientWidth / 2 + el.clientWidth / 2, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  });

  const take = () => run(() => call('season_take', item.level), (r) => {
    season.d = r.state.levels.length ? r.state : season.d;
    if (r.me) app.me = { ...app.me, ...r.me };
    collectionChanged();
    if (r.cards.length) ui.haul = { title: r.mythic ? 'Ton paquet mythique' : 'Ton paquet légendaire', hint: `${plural(r.cards.length, 'carte')}, dont une ${r.mythic ? 'mythique' : 'légendaire'} garantie.`, cards: r.cards };
    else if (r.merge) toast(`Fusion : ${r.merge.from} devient ${r.merge.to}.`, 'good', 7000);
    else toast(`${r.title} : c'est à toi !`, 'good');
    if (r.badge) toast("Un insigne de saison est maintenant à côté de ton pseudo.", 'good');
  });
  const equip = (kind) => run(() => call('season_equip', kind, `${d.season.key}-${item.key}`), () => toast(kind === 'dos' ? 'Ce dos est maintenant sur tes cartes.' : 'Ce cadre est maintenant autour de ta photo.', 'good'));
  const when = (s) => { const j = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600); return j ? `${j} j ${h} h` : h ? `${h} h` : 'moins d’une heure'; };
  const nav = (n) => { sel = Math.max(1, Math.min(d.levels.length, (sel || 1) + n)); };
</script>

{#if season.error && !d}
  <Empty title="Le Season Pass ne répond pas" text={season.error} />
  <button class="btn block" style="margin-top:14px" onclick={() => loadSeason(true)}>Réessayer</button>
{:else if !d}
  <div class="skeleton sk"></div>
{:else if d.season.future}
  <Empty title={d.season.name || 'Season Pass'} text={`La saison commence dans ${when(d.season.in)}.`} />
{:else}
  <header class="head">
    <div class="lvl"><span class="lab">Niveau</span><b class="serif num">{d.me.level}</b></div>
    <div class="prog">
      <div class="trk"><i style:width="{pct}%"></i></div>
      <div class="meta num"><span>{d.me.xp_next ? `${fmt(d.me.xp)} / ${fmt(d.me.xp_next)} XP` : `${fmt(d.me.xp)} XP · niveau maximum`}</span><span>{d.season.open ? `se termine dans ${when(left)}` : 'terminée'}</span></div>
    </div>
    <button class="icon-btn" aria-label="Comment gagner de l'XP" onclick={() => (rules = true)}><Icon name="help" /></button>
  </header>
  {#if !d.me.subscriber}<p class="note">{d.season.free.length} récompenses gratuites · les autres avec WIKI-PRO</p>{/if}

  {#if item}
    <section class="stage" style:--rc={tone(item.rarity)} class:reserved={st === 'reserved'}>
      <div class="rays" aria-hidden="true"></div>
      <div class="obj" class:tall={item.kind === 'carte' && item.card}><RewardArt {item} big /></div>
      <div class="txt">
        <p class="kind">{KIND[item.kind] || ''} · {item.bonus ? 'Bonus' : `Niveau ${item.level}`}</p>
        <h2 class="serif">{item.title}</h2>
        {#if item.text}<p class="desc">{item.text}</p>{/if}
        <div class="act">
          {#if st === 'ready'}
            <ConfirmButton variant="primary" block label={item.kind === 'legende' || item.kind === 'mythique' ? 'Récupérer et ouvrir' : 'Récupérer'} onconfirm={take} />
          {:else if st === 'taken'}
            <span class="done"><Icon name="check" /> Récupérée</span>
            {#if item.kind === 'dos'}<button class="btn small" onclick={() => equip('dos')}>Utiliser ce dos</button>{/if}
            {#if item.kind === 'cadre'}<button class="btn small" onclick={() => equip('cadre')}>Mettre sur ma photo</button>{/if}
            {#if ['skin', 'vitrine', 'fond'].includes(item.kind)}<a class="btn small" href="https://wiki-pick.com/" target="_blank" rel="noopener noreferrer"><Icon name="out" />Sur wiki-pick.com</a>{/if}
          {:else if st === 'reserved'}
            <span class="lockl"><Icon name="lock" /> Réservée aux abonnés WIKI-PRO</span>
            <a class="btn small" href={SITE} target="_blank" rel="noopener noreferrer"><Icon name="out" />Voir sur le site</a>
          {:else if st === 'soon'}
            <span class="lockl">Niveau atteint · la carte arrive bientôt</span>
          {:else}
            <span class="lockl"><Icon name="lock" /> Encore {fmt(Math.max(0, item.xp - d.me.xp))} XP</span>
          {/if}
        </div>
      </div>
    </section>
  {/if}

  <div class="bandw">
    <button class="arr" aria-label="Niveau précédent" disabled={sel <= 1} onclick={() => nav(-1)}><Icon name="back" /></button>
    <div class="band" bind:this={track}>
      {#each d.levels as x (x.level + (x.bonus ? 'b' : ''))}
        {@const s = levelState(d, x)}
        <button class="cell {s}" class:on={x.level === sel && !!item && x.bonus === item.bonus} data-l={x.level} style:--rc={tone(x.rarity)} onclick={() => (sel = x.level)}
          title={`${x.bonus ? 'Bonus' : 'Niveau ' + x.level} · ${x.title}`}>
          <span class="n num">{x.bonus ? '★' : x.level}</span>
          <span class="mini"><RewardArt item={x} /></span>
          <span class="st">{#if s === 'taken'}<Icon name="check" />{:else if s === 'ready'}<i class="dot"></i>{:else if s === 'reserved'}<Icon name="lock" />{:else if s === 'locked'}<Icon name="clock" />{/if}</span>
        </button>
      {/each}
    </div>
    <button class="arr" aria-label="Niveau suivant" disabled={sel >= d.levels.length} onclick={() => nav(1)}><Icon name="chev" /></button>
  </div>
  {#if ready}<p class="foot"><button class="link" onclick={() => (sel = first.level)}>{plural(ready, 'récompense')} à récupérer</button></p>{/if}

  <Sheet open={rules} onclose={() => (rules = false)} title="Comment gagner de l'XP">
    <ul class="rules">
      <li><span>Ouvrir un paquet</span><b class="num">+{d.rules.pack}</b></li>
      <li><span>Ouvrir un paquet doré</span><b class="num">+{d.rules.gold_pack}</b></li>
      <li><span>Tes {d.rules.market_first} premiers achats aux enchères du jour</span><b class="num">+{d.rules.bid}</b></li>
      <li><span>Tes {d.rules.market_first} premières ventes du jour</span><b class="num">+{d.rules.sale}</b></li>
      <li><span>Achats et ventes suivants</span><b class="num">+{d.rules.bid_after}</b></li>
      <li><span>Réussir un défi WBC</span><b class="num">+{d.rules.wbc}</b></li>
      {#if d.rules.active_xp}<li><span>Rester actif (un vrai geste toutes les {d.rules.active_every} min)</span><b class="num">+{d.rules.active_xp} / {d.rules.active_every} min</b></li>{/if}
      <li class="sub">Chaque carte trouvée dans un paquet</li>
      {#each Object.entries(d.rules.cards) as [r, xp]}<li><span style:color={color(r)}>{app.names[r] || r}</span><b class="num">+{xp}</b></li>{/each}
      {#if d.rules.shiny}<li><span>Chromatique</span><b class="num">+{d.rules.shiny}</b></li>{/if}
    </ul>
    <p class="muted fine">{d.me.active_minutes ? `Aujourd'hui : ${d.me.active_minutes} min comptées sur ${d.rules.active_max}. ` : ''}Le temps passé rapporte de l'XP seulement si tu joues vraiment : le signal part quand tu touches l'écran, au plus toutes les {d.rules.active_every} minutes, et le jeu décide.</p>
  </Sheet>
{/if}

<style>
  .sk { height: 380px; border-radius: 18px; }
  .head { display: flex; align-items: center; gap: 16px; }
  .lvl { display: grid; gap: 4px; line-height: 1; } .lvl .lab { font: 600 12px var(--sans); letter-spacing: .1em; font-variant-caps: all-small-caps; color: var(--muted); }
  .lvl b { font-size: 46px; font-weight: 600; letter-spacing: -.03em; color: var(--ivory); text-shadow: 0 0 36px rgba(228, 197, 133, .35); }
  .prog { flex: 1; min-width: 0; display: grid; gap: 8px; }
  .trk { height: 6px; overflow: hidden; background: rgba(255, 255, 255, .07); border-radius: 4px; }
  .trk i { display: block; height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--ivory-2), var(--ivory) 60%, #fff1c7); box-shadow: 0 0 14px rgba(228, 197, 133, .6); transition: width .6s var(--ease); }
  .meta { display: flex; justify-content: space-between; gap: 10px; font-size: 12.5px; color: var(--muted); flex-wrap: wrap; }
  .note { margin-top: 10px; padding: 6px 12px; font-size: 12.5px; line-height: 1.4; text-align: center; color: var(--muted); background: var(--ink-1); border: 1px solid var(--line); border-radius: 12px; }

  .stage { position: relative; isolation: isolate; display: grid; gap: 8px; margin-top: 10px; padding: 14px 16px 14px; overflow: hidden; border-radius: 22px;
    background: radial-gradient(120% 90% at 50% 0%, color-mix(in srgb, var(--rc) 22%, transparent), transparent 62%), linear-gradient(180deg, var(--ink-2), var(--ink-1));
    border: 1px solid color-mix(in srgb, var(--rc) 38%, var(--line)); box-shadow: var(--hi), 0 30px 60px -36px color-mix(in srgb, var(--rc) 70%, #000); }
  .rays { position: absolute; z-index: -1; left: 50%; top: 24%; width: 160%; aspect-ratio: 1; translate: -50% -50%; opacity: .13; pointer-events: none;
    background: repeating-conic-gradient(from 0deg, var(--rc) 0 5deg, transparent 5deg 16deg); mask: radial-gradient(circle, #000 0 18%, transparent 58%); animation: spin 90s linear infinite; }
  @keyframes spin { to { rotate: 360deg; } }
  .obj { display: grid; place-items: center; height: 132px; filter: drop-shadow(0 18px 24px rgba(0, 0, 0, .55)); }
  .txt { display: grid; gap: 8px; text-align: center; justify-items: center; }
  .kind { font: 600 12.5px var(--sans); letter-spacing: .1em; font-variant-caps: all-small-caps; color: var(--rc); }
  .stage h2 { font: 600 24px/1.12 var(--serif); letter-spacing: -.02em; }
  .desc { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; max-width: 46ch; font: 400 15.5px/1.5 var(--serif); color: var(--muted); }
  .act { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 10px; width: 100%; max-width: 360px; margin-top: 6px; }
  .done { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; color: var(--good); }
  .lockl { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: var(--muted); }
  .obj.tall { height: 236px; }
  .stage.reserved .obj { filter: drop-shadow(0 18px 24px rgba(0, 0, 0, .55)) saturate(.85); }

  .bandw { display: flex; align-items: center; gap: 6px; margin: 14px calc(var(--gut) * -1) 0; padding: 0 6px; }
  .arr { display: none; flex: none; width: 36px; height: 36px; place-items: center; color: var(--muted); background: var(--ink-2); border: 1px solid var(--line); border-radius: 50%; cursor: pointer; font-size: 17px; }
  .arr:disabled { opacity: .3; cursor: default; } .arr :global(.i) { rotate: 0deg; } .arr:last-of-type :global(.i) { rotate: -90deg; } .arr:first-of-type :global(.i) { rotate: 0deg; }
  .band { flex: 1; min-width: 0; display: flex; gap: 8px; padding: 10px var(--gut) 12px; overflow-x: auto; scroll-snap-type: x proximity; scrollbar-width: none; }
  .band::-webkit-scrollbar { display: none; }
  .cell { position: relative; flex: none; display: grid; grid-template-rows: auto 1fr auto; justify-items: center; gap: 4px; width: 66px; height: 96px; padding: 6px 4px 5px; scroll-snap-align: center; cursor: pointer; color: var(--muted);
    background: var(--ink-1); border: 1px solid var(--line); border-radius: 13px; transition: transform .2s var(--ease), border-color .2s, background .2s; }
  .cell .n { font: 600 12px var(--sans); } .cell .mini { width: 100%; min-height: 0; overflow: hidden; display: grid; place-items: center; }
  .cell .st { height: 14px; display: grid; place-items: center; font-size: 13px; }
  .cell.taken { opacity: .6; } .cell.taken .st { color: var(--good); }
  .cell.ready { color: var(--text); border-color: color-mix(in srgb, var(--ivory) 70%, transparent); background: linear-gradient(180deg, rgba(228, 197, 133, .16), var(--ink-1)); box-shadow: 0 0 22px -8px var(--ivory); }
  .cell.ready .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ivory); box-shadow: 0 0 10px var(--ivory); }
  .cell.reserved .mini { filter: grayscale(.8) brightness(.8); } .cell.reserved .st { color: var(--ivory-2); }
  .cell.locked .mini { opacity: .7; }
  .cell.on { transform: translateY(-4px); color: var(--text); border-color: var(--rc); background: linear-gradient(180deg, color-mix(in srgb, var(--rc) 18%, var(--ink-2)), var(--ink-1)); }
  .foot { margin-top: 2px; text-align: center; } .link { padding: 0; background: none; border: 0; color: var(--ivory); text-decoration: underline; text-underline-offset: 3px; cursor: pointer; font-size: 14px; }

  .rules { display: grid; margin: 0 0 12px; padding: 0; list-style: none; }
  .rules li { display: flex; justify-content: space-between; gap: 14px; padding: 9px 0; border-bottom: 1px solid var(--line); }
  .rules li.sub { color: var(--muted); font-size: 13px; border-bottom: 0; padding-bottom: 2px; padding-top: 16px; }
  .rules b { color: var(--ivory); white-space: nowrap; } .fine { font-size: 12.5px; }

  @media (min-width: 700px) {
    .stage { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); align-items: center; padding: 30px 36px; gap: 30px; }
    .obj { height: 300px; } .obj.tall { height: 340px; } .txt { text-align: left; justify-items: start; } .act { justify-content: flex-start; max-width: none; }
    .stage h2 { font-size: 34px; } .arr { display: grid; } .bandw { margin: 14px 0 0; padding: 0; } .band { padding-inline: 4px; }
    .cell { width: 74px; height: 106px; }
  }
</style>
