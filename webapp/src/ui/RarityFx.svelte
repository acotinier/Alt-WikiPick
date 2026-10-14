<script>
  // La mise en scène d'une belle carte : plus la rareté est haute (Épique, Exceptionnelle, Légendaire, Mythique), plus c'est démesuré.
  // Tout est en CSS (fx.css, partagé avec l'appli Windows) et s'efface seul ; « réduire les animations » la coupe (voir Packs.svelte).
  import './fx.css';
  import Card from './Card.svelte';
  let { r, title = '', card = null } = $props();
  // t0 : le moment de l'explosion (les raretés hautes chargent d'abord) ; hw : la taille de la carte géante
  const TIER = {
    SR: { c: '#9b5de5', dur: 1.2, t0: 0, flash: 0.35, rings: 1, sparks: 14 },
    UR: { c: '#f6c945', dur: 2.2, t0: 0, flash: 0.6, rings: 3, sparks: 34, title: true },
    L: { c: '#ff9a3c', dur: 4.0, t0: 0.5, flash: 0.9, rings: 4, sparks: 52, rays: 1, bolts: 4, conv: 14, orb: true, hero: 'min(60vw, 230px)', title: true, confetti: 0 },
    M: { c: '#f4d27a', dur: 7.0, t0: 1.4, flash: 1, rings: 6, sparks: 96, rays: 2, bolts: 8, conv: 40, orb: true, veil: true, hero: 'min(72vw, 300px)', title: true, confetti: 54 },
  };
  // les appareils modestes en ont moins : même spectacle, moitié moins de particules
  const lite = typeof navigator !== 'undefined' && (navigator.hardwareConcurrency || 8) <= 4;
  const t = $derived(TIER[r] || TIER.SR);
  const half = (n) => (lite ? Math.ceil(n / 2) : n);
  // suites fixes pour une rareté donnée : angle, portée, durée, retard
  const rnd = (i, seed) => { const k = Math.sin(i * 12.9898 + seed) * 43758.5453; return k - Math.floor(k); };
  const sparks = $derived.by(() => { const n = half(t.sparks); return Array.from({ length: n }, (_, i) => { const j = rnd(i, 4.14); return { a: Math.round((i * 360) / n + j * 18), d: Math.round(26 + j * 34), s: (0.9 + j * 0.8).toFixed(2), w: (j * 0.2).toFixed(2) }; }); });
  const conv = $derived.by(() => { const n = half(t.conv || 0); return Array.from({ length: n }, (_, i) => { const j = rnd(i, 9.7); return { a: Math.round((i * 360) / n + j * 25), d: Math.round(46 + j * 22), w: (j * t.t0 * 0.4).toFixed(2) }; }); });
  const bolts = $derived.by(() => { const n = t.bolts || 0; return Array.from({ length: n }, (_, i) => { const j = rnd(i, 2.3); return { a: Math.round((i * 360) / n + j * 30) + 180, w: (j * 0.3).toFixed(2) }; }); });
  const COLORS = ['#f4d27a', '#fff3c4', '#e9a23b', '#ffffff', '#c9871f'];
  const conf = $derived(Array.from({ length: half(t.confetti || 0) }, (_, i) => { const j = rnd(i, 6.1), j2 = rnd(i, 1.9); return { l: Math.round(j * 100), x: Math.round((j2 - 0.5) * 24) + 'vw', r: Math.round(360 + j * 900) + 'deg', t: (2.6 + j2 * 1.6).toFixed(2), w: (rnd(i, 3.3) * 1.8).toFixed(2), k: COLORS[i % COLORS.length] }; }));
  const letters = $derived(t.title && title ? [...title.toUpperCase()] : []);
</script>

<div class="fx" style:--c={t.c} style:--dur="{t.dur}s" style:--t0="{t.t0}s" style:--fl={t.flash} style:--hw={t.hero || 'auto'} aria-hidden="true">
  {#if t.veil}<i class="fx-veil"></i>{/if}
  {#if t.orb}<i class="fx-orb"></i>{/if}
  {#each conv as s}<i class="fx-conv" style:--a="{s.a}deg" style:--d="{s.d}vmin" style:--w="{s.w}s"></i>{/each}
  <i class="fx-flash"></i>
  {#each Array(t.rays || 0) as _, i}<i class="fx-rays" class:b={i === 1}></i>{/each}
  {#each Array(t.rings) as _, i}<i class="fx-ring" style:--i={i}></i>{/each}
  {#each bolts as s}<i class="fx-bolt" style:--a="{s.a}deg" style:--w="{s.w}s"></i>{/each}
  {#each sparks as s}<i class="fx-spark" style:--a="{s.a}deg" style:--d="{s.d}vmin" style:--t="{s.s}s" style:--w="{s.w}s"></i>{/each}
  {#each conf as s}<i class="fx-conf" style:left="{s.l}%" style:--x={s.x} style:--r={s.r} style:--t="{s.t}s" style:--w="{s.w}s" style:--k={s.k}></i>{/each}
  {#if t.hero && card}<div class="fx-hero"><Card {card} width={330} /></div>{/if}
  {#if letters.length}<b class="fx-title serif">{#each letters as ch, i}<i style:--i={i}>{ch === ' ' ? ' ' : ch}</i>{/each}</b>{/if}
</div>
