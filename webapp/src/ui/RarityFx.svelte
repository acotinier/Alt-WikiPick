<script>
  // La mise en scène d'une belle carte : plus la rareté est haute (Épique, Exceptionnelle, Légendaire, Mythique), plus c'est démesuré.
  // Tout est en CSS (aucune image) et s'efface seul ; « réduire les animations » la coupe.
  let { r, title = '' } = $props();
  const TIER = {
    SR: { c: '#9b5de5', dur: 1.2, flash: 0.35, rings: 1, sparks: 14, rays: false, veil: false, big: false },
    UR: { c: '#f6c945', dur: 1.7, flash: 0.55, rings: 2, sparks: 24, rays: false, veil: false, big: true },
    L: { c: '#ff9a3c', dur: 2.3, flash: 0.8, rings: 3, sparks: 36, rays: true, veil: false, big: true },
    M: { c: '#f4d27a', dur: 3.2, flash: 1, rings: 4, sparks: 56, rays: true, veil: true, big: true },
  };
  const t = $derived(TIER[r] || TIER.SR);
  // des étincelles toujours les mêmes pour une rareté donnée : angle, portée, durée et retard viennent d'une suite fixe
  const sparks = $derived(Array.from({ length: t.sparks }, (_, i) => {
    const k = Math.sin(i * 12.9898 + 4.1414) * 43758.5453, j = k - Math.floor(k);
    return { a: Math.round((i * 360) / t.sparks + j * 18), d: Math.round(26 + j * 30), s: (0.9 + j * 0.7).toFixed(2), w: (j * 0.18).toFixed(2) };
  }));
</script>

<div class="fx" style:--c={t.c} style:--dur="{t.dur}s" style:--fl={t.flash} aria-hidden="true">
  {#if t.veil}<i class="veil"></i>{/if}
  <i class="flash"></i>
  {#if t.rays}<i class="rays"></i>{/if}
  {#each Array(t.rings) as _, i}<i class="ring" style:--i={i}></i>{/each}
  {#each sparks as s}<i class="spark" style:--a="{s.a}deg" style:--d="{s.d}vmin" style:--t="{s.s}s" style:--w="{s.w}s"></i>{/each}
  {#if t.big && title}<b class="title serif">{title}</b>{/if}
</div>

<style>
  .fx { position: fixed; inset: 0; z-index: 90; pointer-events: none; overflow: hidden; animation: life var(--dur) linear forwards; }
  @keyframes life { 0%, 88% { opacity: 1; } 100% { opacity: 0; } }
  .veil { position: absolute; inset: 0; background: radial-gradient(circle at 50% 45%, transparent 8%, rgba(0, 0, 0, .82) 78%); opacity: 0; animation: veil var(--dur) ease-out forwards; }
  @keyframes veil { 0% { opacity: 0; } 14% { opacity: 1; } 82% { opacity: 1; } 100% { opacity: 0; } }
  .flash { position: absolute; inset: 0; background: radial-gradient(circle at 50% 45%, #fff, var(--c) 34%, transparent 70%); opacity: 0; animation: flash .8s ease-out forwards; }
  @keyframes flash { 0% { opacity: 0; } 10% { opacity: var(--fl); } 100% { opacity: 0; } }
  .ring { position: absolute; left: 50%; top: 45%; width: 30vmin; aspect-ratio: 1; translate: -50% -50%; border-radius: 50%; border: 3px solid var(--c); box-shadow: 0 0 36px var(--c), inset 0 0 36px var(--c);
    opacity: 0; animation: ring 1.15s cubic-bezier(.1, .7, .2, 1) forwards; animation-delay: calc(var(--i) * .17s); }
  @keyframes ring { 0% { scale: .1; opacity: .95; } 100% { scale: 3.6; opacity: 0; } }
  .rays { position: absolute; left: 50%; top: 45%; width: 170vmax; aspect-ratio: 1; translate: -50% -50%; opacity: 0; animation: rays var(--dur) ease-out forwards;
    background: repeating-conic-gradient(from 0deg, color-mix(in srgb, var(--c) 70%, #fff) 0 3deg, transparent 3deg 11deg); mask: radial-gradient(circle, #000 0 7%, transparent 44%); }
  @keyframes rays { 0% { opacity: 0; rotate: 0deg; scale: .4; } 20% { opacity: .8; } 100% { opacity: 0; rotate: 55deg; scale: 1.05; } }
  .spark { position: absolute; left: 50%; top: 45%; width: 7px; height: 7px; border-radius: 50%; background: color-mix(in srgb, var(--c) 55%, #fff); box-shadow: 0 0 12px var(--c);
    opacity: 0; animation: spark var(--t) cubic-bezier(.1, .8, .3, 1) forwards; animation-delay: var(--w); }
  @keyframes spark { 0% { opacity: 1; transform: rotate(var(--a)) translateX(0) scale(1); } 100% { opacity: 0; transform: rotate(var(--a)) translateX(var(--d)) scale(.2); } }
  .title { position: absolute; left: 0; right: 0; bottom: 20%; text-align: center; font-size: clamp(30px, 9vw, 64px); line-height: 1; font-weight: 700; letter-spacing: -.02em;
    color: color-mix(in srgb, var(--c) 40%, #fff); text-shadow: 0 0 24px var(--c), 0 4px 30px rgba(0, 0, 0, .8); opacity: 0; animation: title var(--dur) ease-out forwards; }
  @keyframes title { 0% { opacity: 0; transform: scale(.7) translateY(14px); letter-spacing: .2em; } 18% { opacity: 1; transform: none; letter-spacing: -.02em; } 80% { opacity: 1; } 100% { opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { .ring, .rays, .spark { display: none; } }
</style>
