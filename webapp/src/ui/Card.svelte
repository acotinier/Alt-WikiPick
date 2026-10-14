<script>
  // La face d'une carte, la même partout. Un <button> quand elle est cliquable (clavier et lecteurs d'écran gratuits).
  import { color, compact, isTop, thumb } from '../lib/format.js';
  import { app, coll } from '../lib/store.svelte.js';
  import Icon from './Icon.svelte';
  let { card, onclick = null, mini = false, width = 250, picked = false, children = null } = $props();
  let failed = $state(false);
  const label = $derived(app.names[card.rarity] || card.rarity);
  const dots = $derived(card.tags && card.tags.length ? card.tags.map((id) => (coll.tags.find((t) => t.id === id) || {}).color).filter(Boolean).slice(0, 5) : []);
  const src = $derived(card.img ? thumb(card.img, mini ? 120 : width) : null);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<svelte:element this={onclick ? 'button' : 'div'} class="card" class:top={isTop(card)} class:mini class:picked data-r={card.rarity} style:--c={color(card.rarity)}
  {onclick} type={onclick ? 'button' : undefined} aria-label={onclick ? card.name : undefined}>
  {#if !mini}<span class="name"><span>{card.name}</span></span>{/if}
  <span class="pic">
    {#if src && !failed}
      <img {src} alt="" loading="lazy" decoding="async" onerror={() => (failed = true)} />
    {:else}
      <span class="ini">{[...card.name][0] || '?'}</span>
    {/if}
    {#if dots.length && !mini}<span class="dots">{#each dots as d}<i style:background={d}></i>{/each}</span>{/if}
    {#if card.copies > 1 && !mini}<span class="copies">×{card.copies}</span>{/if}
    {#if children}{@render children()}{/if}
  </span>
  {#if !mini}
    <span class="short">{card.desc || ''}</span>
    <span class="foot"><span class="reads"><Icon name="eye" />{compact(card.reads)}</span>{#if card.locked}<Icon name="lock" />{/if}</span>
    <span class="rar">{label}{#if card.shiny}<Icon name="spark" />{/if}</span>
  {/if}
</svelte:element>

<style>
  /* Comme sur l'appli officielle : la carte est TOUTE de la couleur de sa rareté (fond, cadre clair, bandeau du nom, pied avec le nom de la rareté). */
  .card { --fill: linear-gradient(170deg, #f1f4f8 0%, #d9dee6 62%, #c5ccd6 100%); --frame: #eef1f5; --hd: linear-gradient(100deg, #a3adbc 0%, #d3dae3 100%); --hdc: #151922; --tx: #16120b; --dec: rgba(22, 18, 11, .78);
    position: relative; display: flex; flex-direction: column; width: 100%; padding: 0; text-align: left; color: var(--tx); font: inherit; cursor: default; overflow: hidden; isolation: isolate;
    aspect-ratio: 5 / 7; border-radius: 15px; border: 3px solid var(--frame); background: var(--fill);
    box-shadow: 0 10px 22px -10px rgba(0, 0, 0, .8), 0 0 0 1px rgba(0, 0, 0, .35); content-visibility: auto; contain-intrinsic-size: auto 270px; container-type: inline-size;
    transition: transform .25s var(--ease), box-shadow .3s; }
  .card[data-r="PC"] { --fill: linear-gradient(170deg, #dcf6e9 0%, #a9e3c7 62%, #86d3ae 100%); --frame: #e2f6ec; --hd: linear-gradient(100deg, #2f8f65 0%, #84d8b4 100%); --hdc: #04301e; }
  .card[data-r="R"] { --fill: linear-gradient(170deg, #dcefff 0%, #aad6f7 62%, #88c2ee 100%); --frame: #e3f1ff; --hd: linear-gradient(100deg, #2d7cbe 0%, #8bcaf4 100%); --hdc: #03233f; }
  .card[data-r="SR"] { --fill: radial-gradient(85% 55% at 22% 10%, rgba(255, 255, 255, .15), transparent 60%), linear-gradient(158deg, #1a0631 0%, #3a1060 24%, #55178f 52%, #7c2fc4 76%, #ab68ea 100%);
    --frame: #dcc6f8; --hd: linear-gradient(100deg, #2f0857 0%, #8438d2 100%); --hdc: #fff; --tx: #f7f0ff; --dec: rgba(243, 232, 255, .86); }
  .card[data-r="UR"] { --fill: radial-gradient(85% 50% at 50% 66%, rgba(255, 238, 180, .22), transparent 70%), linear-gradient(125deg, #96600e 0%, #c8971f 17%, #e6bf4e 33%, #cf9f2c 51%, #a97a14 69%, #e2b842 85%, #8a5a0b 100%);
    --frame: #ffeec2; --hd: linear-gradient(100deg, #d1890d 0%, #f5cb55 100%); --hdc: #2a1c02; --tx: #241a03; --dec: rgba(38, 26, 3, .84); }
  .card[data-r="L"] { --fill: radial-gradient(90% 60% at 50% 8%, rgba(255, 236, 180, .34), transparent 64%), linear-gradient(152deg, #ffd07a 0%, #f7a531 12%, #e8811b 26%, #c85f0f 42%, #f2a238 56%, #b9500c 70%, #8a3a08 84%, #5a2405 100%);
    --frame: #ffd98a; --hd: linear-gradient(100deg, #8a3a08 0%, #f5b04a 100%); --hdc: #fff6e0; --tx: #fff4de; --dec: rgba(255, 244, 222, .9); box-shadow: 0 0 20px -4px rgba(232, 129, 27, .55), 0 10px 22px -10px rgba(0, 0, 0, .8); }
  .card[data-r="M"] { --fill: linear-gradient(168deg, #26262b 0%, #131316 38%, #0a0a0c 62%, #1c1c21 100%); --frame: #d9b463; --hd: linear-gradient(180deg, #1b1b20, #0c0c0f); --hdc: #f4dfa2; --tx: #f7e8c0; --dec: rgba(247, 232, 192, .84);
    box-shadow: 0 0 22px 0 rgba(217, 180, 99, .45), 0 0 46px 6px rgba(217, 180, 99, .16), 0 10px 24px -10px rgba(0, 0, 0, .9); }
  .card[data-r="EXC"], .card[data-r="WBC"], .card[data-r="SIXSEVEN"] { --fill: linear-gradient(160deg, #fdeaff 0%, #f0b4f7 50%, #d57ee6 100%); --frame: #fde4ff; --hd: linear-gradient(100deg, #8c1f86 0%, #f0abfc 100%); --hdc: #3b0a38; --dec: rgba(59, 10, 56, .82); }
  button.card { cursor: pointer; }
  .card.picked { outline: 3px solid var(--ivory); outline-offset: 3px; }
  button.card:active { transform: scale(.97); }
  @media (hover: hover) { button.card:hover { transform: translateY(-5px); box-shadow: 0 24px 38px -18px rgba(0, 0, 0, .95), 0 0 30px -8px var(--c); } button.card.top:hover .pic::after { opacity: .4; } }
  .name { flex: none; display: flex; align-items: center; min-height: 2.75em; padding: 4px 9px; background: var(--hd); color: var(--hdc); box-shadow: 0 2px 6px -2px rgba(0, 0, 0, .5); }
  .name span { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; font: 700 13.5px/1.15 var(--serif); letter-spacing: -.005em; }
  .pic { position: relative; flex: 1 1 auto; min-height: 0; margin: 8px 9px 0; border-radius: 5px; overflow: hidden; display: grid; place-items: center; background: #030b08;
    box-shadow: 0 0 0 1px rgba(0, 0, 0, .35), 0 6px 12px -6px rgba(0, 0, 0, .6); }
  .pic img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center 22%; }
  .card.top .pic::after { content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .14; mix-blend-mode: color-dodge; transition: opacity .3s;
    background: repeating-linear-gradient(110deg, transparent 0 5%, rgba(255, 105, 200, .45) 8%, rgba(95, 220, 255, .45) 11%, rgba(255, 235, 120, .45) 14%, transparent 17% 22%); }
  .ini { font: 500 56px/1 var(--serif); color: rgba(255, 255, 255, .22); }
  .copies { position: absolute; top: 6px; right: 6px; z-index: 2; padding: 1px 8px; font: 600 11px/16px var(--sans); color: #fff; background: rgba(5, 7, 11, .72); border-radius: 99px; box-shadow: 0 0 0 1px rgba(255, 255, 255, .18); }
  .dots { position: absolute; left: 6px; bottom: 6px; z-index: 2; display: flex; gap: 4px; }
  .dots i { width: 9px; height: 9px; border-radius: 50%; box-shadow: 0 0 0 1.5px rgba(5, 7, 11, .8); }
  .short { flex: none; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.6em; margin: 6px 10px 0; text-align: center; overflow-wrap: anywhere; font: 400 11.5px/1.3 var(--sans); color: var(--dec); }
  .foot { flex: none; display: flex; justify-content: center; align-items: center; gap: 10px; margin: 2px 10px 0; font-size: 11px; color: var(--dec); opacity: .85; }
  .reads { display: inline-flex; align-items: center; gap: 5px; font-variant-numeric: tabular-nums; }
  .rar { flex: none; display: flex; justify-content: center; align-items: center; gap: 6px; margin: 4px 10px 0; padding: 5px 0 8px; border-top: 1px solid color-mix(in srgb, var(--dec) 38%, transparent); font: 800 13px/1.15 var(--sans); }
  @container (max-width: 150px) {
    .name { min-height: 2.5em; padding: 3px 6px; } .name span { font-size: 11.5px; }
    .pic { margin: 5px 6px 0; } .short, .foot { display: none; }
    .rar { margin: 3px 7px 0; padding: 3px 0 5px; font-size: 11px; }
  }
  .mini { border-radius: 8px; border-width: 2px; contain-intrinsic-size: auto 60px; }
  .mini .pic { margin: 0; border-radius: 0; flex: 1; box-shadow: none; }
  .mini .ini { font-size: 26px; }
</style>
