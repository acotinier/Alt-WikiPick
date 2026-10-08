<script>
  // La fusion : 2 ou 3 cartes du même rang -> une carte du rang au-dessus, ou tout est perdu. Le lot automatique ne part qu'après
  // une double confirmation (bouton armé), fait une fusion à la fois, et s'arrête à l'objectif, à la moindre erreur ou sur « Arrêter ».
  import { call } from '../lib/api.js';
  import { color, fmt, plural } from '../lib/format.js';
  import { app, collectionChanged, openCard, refreshMe, toast } from '../lib/store.svelte.js';
  import { dismissFusion, fz, resumeFusion, watchFusion } from '../lib/fusion.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import Sheet from '../ui/Sheet.svelte';

  const name = (r) => app.names[r] || r;
  let st = $state(null), rank = $state(null), size = $state(3), dups = $state(true), count = $state(30), help = $state(false);
  let sel = $state([]), page = $state(0), working = $state(false), failed = $state('');

  async function load(r = rank, p = 0) {
    const d = await call('fusion_get', r, p);
    if (!d.ok) { failed = d.expired ? '' : d.error || 'Atelier indisponible.'; return; }
    failed = ''; st = d; rank = d.rank; page = d.page; sel = [];
    if (d.recipes.length && !d.recipes.some((x) => x.rank === rank)) rank = d.recipes[0].rank;
  }
  load(null);
  resumeFusion();

  const recipe = $derived(st && st.recipes.find((x) => x.rank === rank));
  const avail = $derived(recipe ? recipe.avail : 0);
  const fusions = $derived(Math.floor((Number(count) || 0) / size));
  const consumed = $derived(fusions * size);
  const minutes = $derived(Math.max(1, Math.ceil((fusions * 1.4) / 60)));
  const job = $derived(fz.job);
  const running = $derived(!!(job && job.running));

  const pick = (r) => { if (r !== rank && !running) load(r, 0); };
  const check = () => {
    if (fusions < 1) return `Au moins ${size} cartes.`;
    if (consumed > Math.max(avail, size)) return `Tu n'as que ${plural(avail, 'carte')} de ce rang.`;
    return null;
  };
  const setCount = (n) => { count = Math.max(size, Math.min(n, avail || n)); };

  async function start() {
    if (working || running) return;
    working = true;
    const r = await call('fusion_start', rank, consumed, size, dups);
    working = false;
    if (!r.ok) return r.expired ? undefined : toast(r.error || 'Lot impossible à lancer.', 'error');
    fz.job = r.job; watchFusion();
  }
  const halt = () => call('fusion_stop');
  const finish = () => { dismissFusion(); load(rank, 0); };
  const reasons = { done: 'Objectif atteint.', empty: 'Il ne reste plus assez de cartes éligibles.', stopped: 'Arrêté.', away: "Arrêté : l'appli n'a plus donné signe de vie (écran verrouillé ?)." };

  // à la main : on choisit les cartes une à une
  const toggle = (c) => { sel = sel.includes(c.id) ? sel.filter((i) => i !== c.id) : sel.length < size ? [...sel, c.id] : sel; };
  async function manual() {
    if (working || sel.length !== size) return;
    working = true;
    const r = await call('fusion_do', sel, page);
    working = false;
    if (!r.ok) return r.expired ? undefined : toast(r.error || 'Fusion impossible.', 'error');
    toast(r.success ? `Réussie : ${r.card ? r.card.name : name(r.to)}` : 'Ratée : les cartes sont perdues.', r.success ? 'info' : 'error', 7000);
    if (r.me) { app.me = { ...app.me, ...r.me }; app.meAt = Date.now(); }
    if (r.card) openCard(r.card);
    if (r.state && r.state.rank) { st = r.state; page = r.state.page; }
    sel = []; collectionChanged(); refreshMe();
  }
</script>

<div class="top">
  <div class="chips" role="group" aria-label="Rang à fusionner">
    {#if st}{#each st.recipes as x}
      <button class="chip" class:on={x.rank === rank} class:dim={x.avail < 2} style:--c={color(x.rank)} disabled={running} onclick={() => pick(x.rank)}>{name(x.rank)}<small class="num">{fmt(x.avail)}</small></button>
    {/each}{/if}
  </div>
  <button class="icon-btn" aria-label="Règles et chances de réussite" onclick={() => (help = true)}><Icon name="help" /></button>
</div>

{#if failed}
  <Empty title="L'atelier est fermé" text={failed} />
{:else if !st}
  <div class="skeleton sk"></div>
{:else if running || (job && job.reason)}
  <section class="panel run">
    <h2 class="serif">{running ? 'Fusion en cours' : 'Fusion terminée'}</h2>
    <div class="trk"><i style:width="{job.goal ? (job.fusions / job.goal) * 100 : 0}%"></i></div>
    <p class="muted num">{fmt(job.fusions)} sur {fmt(job.goal)} fusions</p>
    <div class="tally">
      <div><b class="num ok">{fmt(job.won)}</b><span>réussies</span></div>
      <div><b class="num ko">{fmt(job.lost)}</b><span>ratées</span></div>
      <div><b class="num">{fmt(job.used)}</b><span>cartes utilisées</span></div>
      <div><b class="num">{fmt(job.new)}</b><span>nouvelles</span></div>
    </div>
    {#if job.last}<p class="last muted">Dernière carte : <b style:color={color(job.last.rarity)}>{job.last.name}</b></p>{/if}
    {#if running}
      <p class="muted small">Tu peux changer d'écran, mais garde l'appli ouverte : le lot s'arrête si elle ne répond plus.</p>
      <button class="btn block" onclick={halt}>Arrêter</button>
    {:else}
      <p class="end">{job.error ? `Arrêté : ${job.error}` : reasons[job.reason] || ''}</p>
      <button class="btn primary block" onclick={finish}>OK</button>
    {/if}
  </section>
{:else if !recipe}
  <Empty title="Rien à fusionner" text="Ouvre des paquets pour avoir des cartes." />
{:else}
  <section class="panel">
    <h2 class="serif"><span style:color={color(rank)}>{name(rank)}</span> <em>→</em> <span style:color={color(recipe.to)}>{name(recipe.to)}</span></h2>
    <div class="row">
      <label class="n">Cartes à fusionner
        <input type="number" inputmode="numeric" min={size} max={avail} step={size} bind:value={count} />
      </label>
      <div class="quick">
        {#each [30, 150, 600] as n}{#if n <= avail}<button class="chip" onclick={() => setCount(n)}>{fmt(n)}</button>{/if}{/each}
        <button class="chip" onclick={() => setCount(avail)}>Tout</button>
      </div>
    </div>
    <div class="row opts">
      <div class="sz" role="group" aria-label="Cartes par fusion">
        {#each [3, 2] as n}<button class:on={size === n} onclick={() => (size = n)}>{n} par fusion</button>{/each}
      </div>
      <label class="check"><input type="checkbox" bind:checked={dups} />Doublons seulement</label>
    </div>
    <p class="sum">{plural(fusions, 'fusion')} · {plural(consumed, 'carte')} utilisées · environ {minutes} min<br />
      <span class="muted">{dups ? 'Il te reste toujours un exemplaire de chaque carte.' : 'Tes cartes en un seul exemplaire peuvent partir.'} Une fusion ratée perd ses cartes.</span></p>
    <ConfirmButton variant="primary" block label="Lancer la fusion automatique" confirm={() => `Confirmer : fusionner ${fmt(consumed)} cartes ${name(rank).toLowerCase()}s`}
      disabled={working} {check} onconfirm={start} />
  </section>

  <details class="hand">
    <summary>Choisir les cartes à la main</summary>
    {#if st.cards.length}
      <div class="pick">
        {#each st.cards as c (c.id)}<Card card={c} width={150} picked={sel.includes(c.id)} onclick={() => toggle(c)} />{/each}
      </div>
      {#if st.pages > 1}
        <div class="pager">
          <button class="btn small" disabled={page < 1} onclick={() => load(rank, page - 1)}>Précédent</button>
          <span class="muted num">{page + 1} / {st.pages}</span>
          <button class="btn small" disabled={page >= st.pages - 1} onclick={() => load(rank, page + 1)}>Suivant</button>
        </div>
      {/if}
      <ConfirmButton block label={`Fusionner ${sel.length} sur ${size} cartes`} confirm={`Confirmer : ces ${size} cartes peuvent être perdues`} disabled={working || sel.length !== size} onconfirm={manual} />
    {:else}
      <p class="muted">Aucune carte de ce rang à fusionner.</p>
    {/if}
  </details>
{/if}

<Sheet open={help} onclose={() => (help = false)} title="Comment fonctionne la fusion">
  <div class="help">
    <p>Pose <b>2 ou 3 cartes du même rang</b> : le creuset tente d'en faire <b>une carte du rang au-dessus</b>, tirée au hasard. Si la fusion rate, <b>toutes les cartes posées sont perdues</b>, mais ta maîtrise grandit : chaque échec d'affilée ajoute des points de chance sur ce rang.</p>
    {#if st}
      <table>
        <thead><tr><th>Rang</th><th>3 cartes</th><th>2 cartes</th></tr></thead>
        <tbody>
          {#each st.recipes as x}
            <tr><td><span style:color={color(x.rank)}>{name(x.rank)}</span> → <span style:color={color(x.to)}>{name(x.to)}</span></td>
              <td class="num">{x.base} %{#if x.chance > x.base} <u>+{x.chance - x.base}</u>{/if}</td>
              <td class="num">{x.base2} %{#if x.chance2 > x.base2} <u>+{x.chance2 - x.base2}</u>{/if}</td></tr>
          {/each}
        </tbody>
      </table>
      <p class="muted">Chaque échec ajoute {st.bonus} points (à 3 cartes) ou {st.bonus2} points (à 2 cartes) à la tentative suivante sur le même rang.</p>
    {/if}
    <ul>
      <li>Les cartes verrouillées, chromatiques ou exclusives ne se fusionnent pas et n'apparaissent pas ici.</li>
      <li>Les légendaires ne se fusionnent pas ; les mythiques ne se trouvent que dans les paquets.</li>
      <li>Les cartes consommées comptent comme recyclées pour les défis de recyclage.</li>
      <li><b>Fusion automatique</b> : une fusion à la fois, environ une par seconde, jusqu'au nombre de cartes choisi. Elle s'arrête si tu l'arrêtes, s'il n'y a plus de cartes éligibles ou à la moindre erreur. Avec « Doublons seulement », seuls les exemplaires en trop sont utilisés.</li>
    </ul>
  </div>
</Sheet>

<style>
  .top { display: flex; align-items: center; gap: 8px; }
  .chips { flex: 1; min-width: 0; display: flex; gap: 8px; overflow-x: auto; padding: 2px 2px 6px; scrollbar-width: none; }
  .chips::-webkit-scrollbar { display: none; }
  .chip { flex: none; display: inline-flex; align-items: center; gap: 8px; min-height: 34px; padding: 0 13px 0 11px; color: var(--muted); font: 500 13.5px var(--sans); cursor: pointer;
    background: rgba(255, 255, 255, .025); border: 1px solid var(--line); border-radius: 99px; transition: all .18s var(--ease); }
  .chips .chip::before { content: ""; width: 8px; height: 8px; transform: rotate(45deg); border-radius: 2px; background: var(--c); box-shadow: 0 0 8px -1px var(--c); }
  .chip small { color: var(--faint); font-size: 12px; }
  .chip.on { color: var(--text); background: color-mix(in srgb, var(--c) 14%, transparent); border-color: color-mix(in srgb, var(--c) 55%, transparent); }
  .chip.dim { opacity: .5; }
  .chip:disabled { cursor: default; }
  .sk { height: 260px; border-radius: 16px; margin-top: 14px; }
  .panel { display: grid; gap: 14px; margin-top: 14px; padding: 18px; background: var(--ink-1); border: 1px solid var(--line); border-radius: 16px;
    box-shadow: var(--hi), 0 24px 40px -30px rgba(0, 0, 0, .9); }
  h2 { font-size: 24px; letter-spacing: -.01em; } h2 em { font-style: normal; color: var(--faint); }
  .row { display: grid; gap: 10px; }
  .n { display: grid; gap: 6px; font-size: 13px; color: var(--muted); }
  .n input { min-height: 46px; padding: 0 14px; color: var(--text); font: 600 22px var(--serif); background: var(--ink-2); border: 1px solid var(--line-2); border-radius: 12px; outline: 0; }
  .n input:focus { border-color: rgba(241, 232, 212, .5); box-shadow: 0 0 0 3px rgba(241, 232, 212, .1); }
  .quick { display: flex; gap: 8px; flex-wrap: wrap; }
  .opts { grid-template-columns: 1fr; align-items: center; }
  .sz { display: flex; gap: 2px; padding: 3px; background: var(--ink-2); border: 1px solid var(--line); border-radius: 12px; }
  .sz button { flex: 1; min-height: 38px; color: var(--muted); font: 500 14px var(--sans); background: none; border: 0; border-radius: 9px; cursor: pointer; }
  .sz button.on { color: var(--text); background: var(--ink-4); box-shadow: var(--hi); }
  .check { display: flex; align-items: center; gap: 10px; font-size: 14.5px; }
  .check input { width: 20px; height: 20px; accent-color: var(--ivory); }
  .sum { font-size: 15px; line-height: 1.5; } .sum .muted { font-size: 13px; }
  .trk { height: 4px; background: rgba(255, 255, 255, .08); border-radius: 2px; overflow: hidden; } .trk i { display: block; height: 100%; background: var(--ivory); transition: width .4s var(--ease); }
  .tally { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .tally div { display: grid; padding: 10px 12px; background: var(--ink-2); border: 1px solid var(--line); border-radius: 12px; }
  .tally b { font: 600 22px var(--serif); } .tally span { color: var(--muted); font-size: 12.5px; }
  .ok { color: var(--good); } .ko { color: var(--bad); }
  .last { font-size: 14px; } .small { font-size: 12.5px; } .end { font-size: 16px; }
  .hand { margin-top: 18px; } .hand summary { cursor: pointer; padding: 10px 2px; color: var(--muted); font-size: 14.5px; }
  .pick { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; margin: 10px 0 14px; }
  .pager { display: flex; align-items: center; justify-content: center; gap: 14px; margin-bottom: 14px; }
  .help { display: grid; gap: 14px; font-size: 14.5px; line-height: 1.5; }
  .help table { width: 100%; border-collapse: collapse; } .help th { text-align: left; color: var(--muted); font-weight: 500; font-size: 12.5px; }
  .help td, .help th { padding: 7px 4px; border-bottom: 1px solid var(--line); } .help u { color: var(--gold); text-decoration: none; }
  .help ul { display: grid; gap: 8px; padding-left: 18px; } .help .muted { font-size: 13px; }
  @media (min-width: 700px) { .opts { grid-template-columns: 1fr auto; } .tally { grid-template-columns: repeat(4, 1fr); } .row { max-width: 520px; } }
</style>
