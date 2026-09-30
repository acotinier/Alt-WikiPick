<script>
  // La face d'une carte, la même partout. Un <button> quand elle est cliquable (clavier et lecteurs d'écran gratuits).
  import { color, compact, isTop, thumb } from '../lib/format.js';
  import { app } from '../lib/store.svelte.js';
  import Icon from './Icon.svelte';
  let { card, onclick = null, mini = false, width = 250, picked = false, children = null } = $props();
  let failed = $state(false);
  const label = $derived(app.names[card.rarity] || card.rarity);
  const src = $derived(card.img ? thumb(card.img, mini ? 120 : width) : null);
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<svelte:element this={onclick ? 'button' : 'div'} class="card" class:top={isTop(card)} class:mini class:picked style:--c={color(card.rarity)}
  {onclick} type={onclick ? 'button' : undefined} aria-label={onclick ? card.name : undefined}>
  <span class="pic">
    {#if src && !failed}
      <img {src} alt="" loading="lazy" decoding="async" onerror={() => (failed = true)} />
    {:else}
      <span class="ini">{[...card.name][0] || '?'}</span>
    {/if}
    {#if card.copies > 1 && !mini}<span class="copies">×{card.copies}</span>{/if}
    {#if children}{@render children()}{/if}
  </span>
  {#if !mini}
    <span class="meta">
      <span class="rar">{label}{#if card.shiny}<Icon name="spark" />{/if}</span>
      <span class="name">{card.name}</span>
      <span class="foot"><span class="reads"><Icon name="eye" />{compact(card.reads)}</span>{#if card.locked}<Icon name="lock" />{/if}</span>
    </span>
  {/if}
</svelte:element>

<style>
  .card { position: relative; display: flex; flex-direction: column; width: 100%; padding: 0; text-align: left; color: inherit; font: inherit; cursor: default; overflow: hidden; isolation: isolate;
    aspect-ratio: 5 / 7; border-radius: 13px; border: 1px solid color-mix(in srgb, var(--c) 42%, rgba(255, 255, 255, .06));
    background: radial-gradient(130% 70% at 50% 0%, color-mix(in srgb, var(--c) 16%, transparent), transparent 60%), linear-gradient(165deg, color-mix(in srgb, var(--c) 9%, var(--ink-3)), var(--ink-2) 50%, color-mix(in srgb, var(--c) 7%, var(--ink-1)));
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, .08), 0 14px 26px -16px rgba(0, 0, 0, .9);
    content-visibility: auto; contain-intrinsic-size: auto 270px; /* hors écran, le navigateur ne dessine rien : une collection de milliers de cartes reste fluide */
    transition: transform .25s var(--ease), box-shadow .3s; }
  button.card { cursor: pointer; }
  .card.top { border-color: color-mix(in srgb, var(--c) 70%, transparent); box-shadow: inset 0 1px 0 rgba(255, 255, 255, .12), 0 0 0 1px color-mix(in srgb, var(--c) 22%, transparent), 0 14px 30px -16px color-mix(in srgb, var(--c) 75%, transparent); }
  .card.picked { outline: 2px solid var(--ivory); outline-offset: 3px; }
  button.card:active { transform: scale(.97); }
  @media (hover: hover) {
    button.card:hover { transform: translateY(-5px); border-color: color-mix(in srgb, var(--c) 75%, transparent);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, .1), 0 26px 40px -22px rgba(0, 0, 0, .95), 0 16px 44px -24px color-mix(in srgb, var(--c) 80%, transparent); }
    button.card.top:hover .pic::after { opacity: .4; }
  }
  .pic { position: relative; flex: 1 1 60%; min-height: 0; margin: 6px 6px 0; border-radius: 9px; overflow: hidden; display: grid; place-items: center; background: #04060a;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .07), inset 0 -40px 40px -24px rgba(0, 0, 0, .75); }
  .pic img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center 22%; }
  .card.top .pic::after { content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .14; mix-blend-mode: color-dodge; transition: opacity .3s;
    background: repeating-linear-gradient(110deg, transparent 0 5%, rgba(255, 105, 200, .45) 8%, rgba(95, 220, 255, .45) 11%, rgba(255, 235, 120, .45) 14%, transparent 17% 22%); }
  .ini { font: 500 56px/1 var(--serif); color: color-mix(in srgb, var(--c) 35%, var(--ink-4)); }
  .copies { position: absolute; top: 6px; right: 6px; z-index: 2; padding: 1px 8px; font: 600 11px/16px var(--sans); background: rgba(5, 7, 11, .72); border-radius: 99px; box-shadow: 0 0 0 1px var(--line-2); }
  .meta { position: relative; display: grid; gap: 3px; align-content: start; padding: 8px 10px 10px; }
  .rar { display: inline-flex; align-items: center; gap: 7px; font: 600 10.5px var(--sans); letter-spacing: .09em; text-transform: none; font-variant-caps: all-small-caps; font-size: 12.5px; color: var(--c); }
  .rar::before { content: ""; width: 6px; height: 6px; transform: rotate(45deg); border-radius: 1px; background: var(--c); box-shadow: 0 0 8px var(--c); }
  .name { font: 600 15px/1.18 var(--serif); letter-spacing: -.005em; min-height: 2.36em; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .foot { display: flex; justify-content: space-between; align-items: center; font-size: 11.5px; color: var(--muted); }
  .reads { display: inline-flex; align-items: center; gap: 5px; font-variant-numeric: tabular-nums; }
  .mini { border-radius: 8px; contain-intrinsic-size: auto 60px; }
  .mini .pic { margin: 3px; border-radius: 6px; flex: 1; }
  .mini .ini { font-size: 26px; }
</style>
