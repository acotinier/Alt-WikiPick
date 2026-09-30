<script>
  // Série de connexion, quêtes du jour, quêtes de bienvenue, succès. Tout sauf les succès arrive déjà avec le profil (aucun appel en plus).
  // Réclamer = un clic : le serveur vérifie tout.
  import { call } from '../lib/api.js';
  import { clock, color, fmt, plural } from '../lib/format.js';
  import { app, collectionChanged, refreshMe, run, toast } from '../lib/store.svelte.js';
  import { tick } from '../lib/ticker.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Icon from '../ui/Icon.svelte';

  const rw = $derived(app.rewards || {});
  const ICON = { wikiki: 'coin', paquet: 'pack', dore: 'pack', minipack: 'pack', carte: 'cards' };
  let ach = $state(null), err = $state('');
  call('achievements_get').then((r) => { if (r.ok) ach = r; else err = r.error || 'Succès indisponibles.'; });
  const reloadAch = () => call('achievements_get').then((r) => { if (r.ok) ach = r; });

  // secondes restantes depuis la lecture du profil (l'horloge commune fait bouger les chiffres)
  const until = (secs) => { const left = Math.max(0, secs - (tick.now - app.meAt) / 1000); return clock(left); };
  const pct = (done, goal) => Math.min(100, Math.round((100 * done) / Math.max(1, goal)));
  const prog = (done, goal, fin) => (goal > 1 ? `${fmt(Math.min(done, goal))} / ${fmt(goal)}` : fin ? "C'est fait" : 'Pas encore');

  function claimed(r, fallback) {
    const what = r.titles.length > 1 ? `${r.titles.length} récompenses` : r.titles[0] || fallback;
    toast(`${what} · ${r.packs ? plural(r.gain, 'paquet') + ' offert' + (r.gain > 1 ? 's' : '') : '+' + fmt(r.gain) + ' Wikiki'}`, 'good');
    if (r.gift) setTimeout(() => toast("Bienvenue terminée : un paquet doré de 20 cartes t'attend dans Paquets !", 'good'), 900);
    refreshMe(); reloadAch();
  }
  const claimQuest = (q, i) => run(() => call('claim', 'quete', q.packs ? 2 : 1), (r) => claimed(r, q.title));
  const claimWelcome = (code, title) => run(() => call('claim', 'bienvenue', code), (r) => claimed(r, title));
  const claimAch = (code, title) => run(() => call('claim', 'succes', code), (r) => claimed(r, title));
  const toClaim = $derived((rw.welcome || []).filter((w) => w.finished && !w.claimed));
  const famItems = (f) => (ach ? ach.items.filter((s) => s.family === f) : []);
</script>

{#if rw.streak}
  {@const e = rw.streak}
  <section class="card streak">
    <header><span class="ico fire"><Icon name="flame" /></span>
      <div><h2 class="serif">Série de connexion</h2><p class="muted">Connecte-toi chaque jour : la récompense grossit jusqu'au 7e jour.</p></div>
      <div class="cnt"><b class="serif num">{e.done}</b><small>/7</small></div></header>
    <div class="track"><i style:width="{Math.round((100 * Math.min(7, e.done)) / 7)}%"></i></div>
    <div class="days" class:closed={!e.open || e.wait}>
      {#each e.days as g, i}
        {@const n = i + 1}{@const today = n === e.day && e.open && !e.wait}
        <div class="day" class:done={n <= e.done} class:today class:ready={today && e.ready} class:grand={n === 7}>
          {#if n === 7}<em class="tag">Grand prix</em>{:else if today && n > e.done}<em class="tag now">Aujourd'hui</em>{/if}
          <small class="dn">Jour {n}</small>
          {#if g.kind === 'carte' && g.card}<span class="dcard" style:--c={color(g.card.rarity)} style:background-image={g.card.img ? `url("${g.card.img}")` : null}></span>
          {:else}<span class="dic k-{g.kind}"><Icon name={ICON[g.kind] || 'pack'} /></span>{/if}
          <span class="dt">{g.text}</span>
          {#if n <= e.done}<span class="ok"><Icon name="check" /></span>{/if}
        </div>
      {/each}
    </div>
    <footer>
      {#if !e.open}<span class="muted">La série n'est pas encore ouverte : reviens bientôt.</span>
      {:else if e.wait}<span class="muted">Ton compte doit avoir 48 h : encore {until(e.wait)}</span>
      {:else if e.ready}<button class="btn gold block" onclick={() => run(() => call('claim', 'serie'), (r) => {
          toast(`Jour ${r.day} : ${r.text} !` + (r.kind === 'minipack' ? " Il t'attend dans l'Arène." : r.kind === 'dore' ? " Il t'attend dans Paquets." : r.kind === 'carte' ? ' Elle est dans ta collection.' : ''), 'good');
          refreshMe(); if (r.kind === 'carte') collectionChanged();
        })}>Récupérer le jour {e.day} · {(e.days[e.day - 1] || {}).text}</button>
      {:else}<span class="muted">Prochaine récompense dans {until(e.next)}</span>{/if}
    </footer>
    <p class="muted fine">Un jour manqué et la série repart au jour 1. Après le 7e jour, elle recommence.</p>
  </section>
{/if}

{#if (rw.welcome || []).some((w) => !w.claimed)}
  <section class="card">
    <header><span class="ico gift"><Icon name="gift" /></span>
      <div><h2 class="serif">Quêtes de bienvenue</h2><p class="muted">Quelques gestes pour faire le tour du jeu. Au bout, un paquet doré de 20 cartes t'est offert.</p></div>
      <span class="pill">{rw.welcome.filter((w) => w.finished).length} / {rw.welcome.length}</span></header>
    {#each rw.welcome as w}
      <div class="wrow" class:done={w.finished}>
        <div><b class="serif">{w.title}</b>{#if w.what}<small class="muted">{w.what}</small>{/if}<div class="bar"><i style:width="{pct(w.done, w.goal)}%"></i></div></div>
        <span class="gain">+{fmt(w.gain)} W</span>
        {#if w.claimed}<span class="okt"><Icon name="check" /></span>
        {:else if w.finished}<button class="btn gold small" onclick={() => claimWelcome(w.code, w.title)}>Réclamer</button>
        {:else}<small class="muted">En cours</small>{/if}
      </div>
    {/each}
    {#if toClaim.length > 1}<button class="btn gold block" style="margin-top:12px" onclick={() => claimWelcome(null)}>Tout réclamer · {fmt(toClaim.reduce((t, w) => t + w.gain, 0))} Wikiki</button>{/if}
  </section>
{/if}

{#if (rw.quests || []).length}
  <h2 class="sec">Quêtes du jour</h2>
  <div class="quests">
    {#each rw.quests as q, i}
      {@const gain = q.packs ? plural(q.gain, 'Mini-Pack') : `${fmt(q.gain)} Wikiki`}
      <article class="quest" class:ready={q.finished && !q.claimed && !q.locked} class:claimed={q.claimed} class:locked={q.locked}>
        <span class="eyebrow goldt">{q.locked ? 'Verrouillée' : q.claimed ? 'Récompense touchée' : q.finished ? 'Accomplie' : 'Quête du jour'}</span>
        <h3 class="serif">{q.title}</h3>{#if q.what}<p class="muted">{q.what}</p>{/if}
        {#if q.locked}<p class="muted fine">Termine tes quêtes de bienvenue pour ouvrir la quête du jour.</p>{/if}
        <div class="bar"><i style:width="{pct(q.done, q.goal)}%"></i></div>
        <div class="qline"><span>{prog(q.done, q.goal, q.finished)}</span>{#if q.next}<span>Nouvelle quête dans {until(q.next)}</span>{/if}</div>
        <div class="qside"><span class="qgain"><Icon name={q.packs ? 'pack' : 'coin'} />{gain}</span>
          {#if q.claimed}<span class="okt"><Icon name="check" />Réclamée</span>
          {:else if q.finished && !q.locked}<button class="btn gold small" onclick={() => claimQuest(q, i)}>Réclamer</button>{/if}</div>
      </article>
    {/each}
  </div>
  <p class="muted fine">Une nouvelle quête est tirée chaque nuit à minuit. Les cartes comptent d'où qu'elles viennent : paquet, enchère ou échange.</p>
{/if}

<h2 class="sec">Succès</h2>
{#if err}<p class="muted">{err}</p>
{:else if !ach}<div class="skeleton" style="height:140px"></div>
{:else}
  <div class="atop">
    <div class="tile"><b class="serif num">{fmt(ach.earned)} / {fmt(ach.total)}</b><span>obtenus</span></div>
    <div class="tile"><b class="serif num">{fmt(ach.won)}</b><span>Wikiki gagnés</span></div>
    <div class="tile"><b class="serif num">{ach.to_claim ? fmt(ach.to_claim) : '—'}</b><span>à réclamer</span></div>
  </div>
  {#if ach.to_claim}<button class="btn gold block" onclick={() => claimAch(null)}>Tout réclamer · {fmt(ach.to_claim)} Wikiki</button>{/if}
  {#if ach.locked}<p class="warn">Les succès s'ouvrent quand tes quêtes de bienvenue sont terminées.</p>{/if}
  {#each ach.families as f}
    {@const lot = famItems(f)}
    {#if lot.length}
      <div class="fam" class:locked={ach.locked}>
        <div class="famh"><h3 class="eyebrow">{f}</h3><span class="muted fine">{lot.filter((s) => s.claimed).length} / {lot.length}</span></div>
        <div class="agrid">
          {#each lot as s}
            <div class="ach" class:ready={s.finished && !s.claimed} class:done={s.claimed}>
              <div class="ah"><b class="serif">{s.title}</b><span class="gain">+{fmt(s.gain)} W</span></div>
              {#if s.what}<small class="muted">{s.what}</small>{/if}
              <div class="bar"><i style:width="{pct(s.done, s.goal)}%"></i></div>
              <div class="qline"><span>{prog(s.done, s.goal, s.finished)}</span>
                {#if s.claimed}<span class="okt"><Icon name="check" />Obtenu</span>{:else if s.finished && !ach.locked}<button class="btn gold small" onclick={() => claimAch(s.code, s.title)}>Réclamer</button>{/if}</div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/each}
{/if}

<style>
  .card { display: grid; gap: 14px; padding: 18px; margin-bottom: 14px; border-radius: var(--rad-xl); background: rgba(255, 255, 255, .02); border: 1px solid var(--line); }
  .streak { background: radial-gradient(70% 120% at 0% 0%, rgba(255, 140, 60, .12), transparent 60%), rgba(255, 255, 255, .02); border-color: rgba(255, 170, 90, .22); }
  header { display: flex; align-items: center; gap: 12px; }
  header > div:nth-child(2) { flex: 1; min-width: 0; }
  header h2 { font-size: 20px; } header p { font-size: 13px; }
  .ico { display: grid; place-items: center; flex: none; width: 46px; height: 46px; border-radius: 14px; font-size: 24px; color: #ffb45c; background: radial-gradient(circle at 50% 70%, rgba(255, 140, 60, .35), rgba(255, 140, 60, .06)); box-shadow: inset 0 0 0 1px rgba(255, 170, 90, .3); }
  .ico.gift { color: var(--gold); background: radial-gradient(circle at 50% 70%, rgba(227, 189, 108, .3), rgba(227, 189, 108, .05)); box-shadow: inset 0 0 0 1px rgba(227, 189, 108, .3); }
  .cnt { display: flex; align-items: baseline; gap: 2px; } .cnt b { font-size: 38px; font-weight: 500; line-height: 1; color: #ffd9a8; } .cnt small { color: var(--muted); }
  .track { height: 4px; background: rgba(255, 255, 255, .06); border-radius: 2px; overflow: hidden; }
  .track i { display: block; height: 100%; background: linear-gradient(90deg, #ff8c3c, var(--gold)); box-shadow: 0 0 12px #ff8c3c; transition: width .6s var(--ease); }
  .days { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .days.closed { opacity: .5; filter: saturate(.4); }
  .day { position: relative; display: grid; justify-items: center; align-content: start; gap: 6px; padding: 14px 6px 10px; min-height: 124px; text-align: center; background: rgba(255, 255, 255, .025); border: 1px solid var(--line); border-radius: 14px; }
  .day.done { background: rgba(70, 201, 152, .06); border-color: rgba(70, 201, 152, .3); }
  .day.today { border-color: rgba(255, 170, 90, .55); background: rgba(255, 140, 60, .08); }
  .day.ready { animation: dready 2s ease-in-out infinite; }
  @keyframes dready { 50% { box-shadow: 0 0 0 4px rgba(255, 170, 90, .12), 0 0 28px -6px rgba(255, 140, 60, .7); } }
  .day.grand { grid-column: span 2; background: radial-gradient(90% 90% at 50% 20%, rgba(227, 189, 108, .16), transparent 70%), rgba(255, 255, 255, .025); border-color: rgba(227, 189, 108, .4); }
  .tag { position: absolute; top: -9px; left: 50%; transform: translateX(-50%); padding: 0 8px; font: 700 10.5px/16px var(--sans); font-style: normal; white-space: nowrap; color: #1d1506; background: var(--gold); border-radius: 99px; }
  .tag.now { background: #ffb45c; }
  .dn { font: 600 12.5px var(--sans); letter-spacing: .08em; font-variant-caps: all-small-caps; color: var(--muted); }
  .dic { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 12px; font-size: 22px; color: var(--ivory); background: rgba(255, 255, 255, .05); }
  .dic.k-wikiki { color: var(--gold); } .dic.k-dore { color: #1d1506; background: linear-gradient(160deg, #ffe3a1, var(--gold) 55%, #b98a35); } .dic.k-minipack { color: #9ecbff; }
  .dcard { width: 36px; aspect-ratio: 5 / 7; border: 1px solid var(--c); border-radius: 6px; background: #04060a center / cover no-repeat; box-shadow: 0 0 16px -4px var(--c); }
  .dt { font-size: 12px; line-height: 1.3; }
  .ok { position: absolute; top: 6px; right: 6px; display: grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; font-size: 11px; color: #062b1d; background: var(--good); }
  footer { display: grid; } .fine { font-size: 12.5px; }
  .wrow { display: grid; grid-template-columns: 1fr auto auto; gap: 10px 12px; align-items: center; padding: 10px 0; border-top: 1px solid var(--line); }
  .wrow b { font-size: 15px; display: block; } .wrow.done b { color: var(--muted); }
  .wrow small { display: block; font-size: 12px; }
  .bar { height: 5px; margin-top: 6px; background: rgba(255, 255, 255, .06); border-radius: 3px; overflow: hidden; }
  .bar i { display: block; height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--ivory-2), var(--gold)); }
  .gain { color: var(--gold); font: 600 13px var(--sans); white-space: nowrap; }
  .okt { display: inline-flex; align-items: center; gap: 5px; color: var(--good); font: 600 13px var(--sans); }
  .quests { display: grid; gap: 10px; }
  .quest { display: grid; gap: 6px; padding: 16px; background: rgba(255, 255, 255, .02); border: 1px solid var(--line); border-radius: var(--rad-l); }
  .quest.ready { border-color: rgba(227, 189, 108, .45); background: radial-gradient(90% 140% at 100% 50%, rgba(227, 189, 108, .1), transparent 60%), rgba(255, 255, 255, .02); }
  .quest.claimed, .quest.locked { opacity: .65; }
  .goldt { color: var(--gold); }
  .quest h3 { font-size: 19px; }
  .qline { display: flex; justify-content: space-between; align-items: center; gap: 10px; font-size: 12.5px; color: var(--muted); }
  .qside { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 4px; }
  .qgain { display: inline-flex; align-items: center; gap: 7px; font: 600 18px var(--serif); color: #fff5dd; } .qgain :global(.i) { color: var(--gold); }
  .atop { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
  .tile { display: grid; gap: 2px; padding: 12px; background: rgba(255, 255, 255, .03); border: 1px solid var(--line); border-radius: var(--rad-m); }
  .tile b { font-size: 20px; font-weight: 500; } .tile span { font-size: 12px; color: var(--muted); }
  .warn { margin: 12px 0; padding: 10px 14px; border-left: 3px solid var(--warn); background: color-mix(in srgb, var(--warn) 8%, transparent); border-radius: 0 8px 8px 0; }
  .fam { margin-top: 18px; } .fam.locked { opacity: .5; } .famh { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
  .agrid { display: grid; gap: 8px; }
  .ach { display: grid; gap: 6px; padding: 13px 14px; background: rgba(255, 255, 255, .02); border: 1px solid var(--line); border-radius: var(--rad-m); }
  .ach.ready { border-color: rgba(227, 189, 108, .5); } .ach.done { background: rgba(70, 201, 152, .04); }
  .ah { display: flex; justify-content: space-between; gap: 10px; } .ah b { font-size: 15px; }
  @media (min-width: 700px) { .days { grid-template-columns: repeat(7, 1fr); } .day.grand { grid-column: auto; } .agrid { grid-template-columns: repeat(2, 1fr); } .wrow { grid-template-columns: 1fr 120px 70px 110px; } }
</style>
