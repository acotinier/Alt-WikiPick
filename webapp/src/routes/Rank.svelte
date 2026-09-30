<script>
  import { call } from '../lib/api.js';
  import { color, duration, fmt } from '../lib/format.js';
  import { app, coll } from '../lib/store.svelte.js';
  import Empty from '../ui/Empty.svelte';
  import Seg from '../ui/Seg.svelte';

  const PERIODS = [['semaine', 'Semaine'], ['mois', 'Mois'], ['tout', 'Depuis le début']];
  const LABEL = { semaine: 'cette semaine', mois: 'ce mois-ci', tout: 'depuis le début' };
  let period = $state('tout'), data = $state(null), err = $state('');
  $effect(() => { const p = period; data = null; err = ''; call('load_ranking', p).then((r) => { if (p === period) { if (r.ok) data = r; else err = r.error || 'Classement indisponible'; } }); });

  const mine = $derived(data ? data.top.find((x) => x.me) : null);
  const own = $derived(coll.rank || {});
  const order = ['M', 'L', 'UR', 'SR', 'R', 'PC', 'C'];
  const rule = $derived(!data ? '' : data.rule === 'acquis'
    ? `Seules comptent les cartes ouvertes en paquet ou remportées aux enchères pendant la période, et encore dans ta collection.${data.reset_in ? ` Remise à zéro dans ${duration(data.reset_in)}.` : ''}`
    : data.rule === 'glissant' ? 'Sur une semaine ou un mois, seules comptent les cartes obtenues pendant la période.' : '');
</script>

<Seg items={PERIODS} value={period} onchange={(p) => (period = p)} />

{#if err}<Empty title="Classement indisponible" text={err} />
{:else if !data}<div class="skeleton" style="height:260px;margin-top:14px"></div>
{:else}
  <section class="me">
    {#if period === 'tout' && own.rank}
      <span class="big serif num">#{fmt(own.rank)}</span>
      <div><b>sur {fmt(own.total)} joueurs, {fmt(own.points)} points</b>{#if own.toNext != null && own.nextName}<p class="muted">{fmt(own.toNext)} points pour dépasser {own.nextName}</p>{/if}</div>
    {:else if mine}
      <span class="big serif num">#{fmt(mine.rank)}</span><div><b>{LABEL[period]}, {fmt(mine.points)} points</b></div>
    {:else}<b>Tu n'apparais pas dans le classement affiché.</b>{/if}
  </section>

  <p class="muted small">Plus une carte est rare, plus elle rapporte de points. À points égaux, celui qui possède le plus de cartes passe devant. {rule}</p>
  <div class="legend">{#each order.filter((k) => data.points[k] != null) as k}<span style:--c={color(k)}>{app.names[k] || k} {fmt(data.points[k])}</span>{/each}{#if data.chroma_points}<span style="--c:var(--text)">Chromatique {fmt(data.chroma_points)}</span>{/if}</div>

  <div class="table">
    {#each data.top as x (x.rank + x.name)}
      <div class="row-r" class:me={x.me} class:top3={x.rank <= 3}>
        <span class="rk serif num">{x.rank}</span>
        <span class="who"><b class="serif">{x.name}</b>{#if x.guild}<small class="muted">{x.guild}</small>{/if}{#if x.me}<em>Toi</em>{/if}</span>
        <span class="cards muted num">{fmt(x.cards)} cartes</span>
        <span class="pts serif num">{fmt(x.points)}</span>
      </div>
    {:else}<Empty title="Personne n'est encore classé" />{/each}
  </div>
{/if}

<style>
  .me { display: flex; align-items: center; gap: 16px; margin: 14px 0 10px; padding: 18px 20px; border-radius: var(--rad-xl); background: radial-gradient(80% 140% at 0% 0%, rgba(227, 189, 108, .13), transparent 60%), rgba(255, 255, 255, .02); border: 1px solid rgba(227, 189, 108, .2); }
  .big { font-size: 48px; line-height: 1; color: #fff5dd; }
  .me b { font: 600 17px var(--serif); } .me p { font-size: 13px; }
  .small { font-size: 12.5px; line-height: 1.55; }
  .legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 10px 0 14px; font-size: 12.5px; }
  .legend span { display: inline-flex; align-items: center; gap: 7px; }
  .legend span::before { content: ""; width: 7px; height: 7px; transform: rotate(45deg); background: var(--c); box-shadow: 0 0 8px var(--c); }
  .table { background: rgba(255, 255, 255, .015); border: 1px solid var(--line); border-radius: var(--rad-l); overflow: hidden; }
  .row-r { display: grid; grid-template-columns: 44px 1fr auto; gap: 4px 12px; align-items: center; padding: 11px 14px; border-bottom: 1px solid var(--line); }
  .row-r:last-child { border-bottom: 0; }
  .row-r.me { background: linear-gradient(90deg, rgba(241, 232, 212, .09), transparent 70%); box-shadow: inset 3px 0 0 var(--ivory); }
  .rk { font-size: 20px; color: var(--muted); }
  .top3 .rk { font-size: 26px; font-weight: 600; }
  .top3:nth-child(1) .rk { color: var(--gold); text-shadow: 0 0 18px rgba(227, 189, 108, .5); } .top3:nth-child(2) .rk { color: #d5dbe6; } .top3:nth-child(3) .rk { color: #d59a6a; }
  .who { display: flex; align-items: baseline; gap: 8px; min-width: 0; flex-wrap: wrap; }
  .who b { font-size: 16px; overflow-wrap: anywhere; } .who small { font-size: 12px; }
  .who em { padding: 0 8px; font: 700 11px/18px var(--sans); font-style: normal; color: var(--on-ivory); background: var(--ivory); border-radius: 99px; }
  .cards { display: none; font-size: 13px; text-align: right; }
  .pts { font-size: 17px; font-weight: 600; text-align: right; }
  @media (min-width: 700px) { .row-r { grid-template-columns: 56px 1fr 130px 110px; } .cards { display: block; } .big { font-size: 60px; } }
</style>
