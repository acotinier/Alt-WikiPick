<script>
  // L'objet d'une récompense du Season Pass, dessiné en CSS : le même en grand (vitrine) et en petit (case d'un niveau).
  import { color } from '../lib/format.js';
  import Card from './Card.svelte';
  import Icon from './Icon.svelte';
  let { item, big = false } = $props();
  const k = $derived(item.kind);
  const packs = $derived(['paquets', 'dore', 'legende', 'mythique'].includes(k));
  const tone = $derived(k === 'dore' ? 'gold' : k === 'legende' ? 'ember' : k === 'mythique' ? 'night' : 'plum');
  const sub = $derived(k === 'legende' ? 'Légendaire garantie' : k === 'mythique' ? 'Mythique garantie' : k === 'dore' ? 'Paquet doré' : '');
</script>

<div class="art" class:big style:--rc={color(item.rarity)}>
  {#if k === 'carte' && item.card}
    <div class="cardw"><Card card={item.card} width={big ? 330 : 120} mini={!big} /></div>
  {:else if k === 'carte'}
    <div class="soon"><b class="serif">?</b>{#if big}<small>Carte exclusive<br />bientôt</small>{/if}</div>
  {:else if packs}
    <div class="pile" class:two={item.n > 1}>
      {#if item.n > 1}<div class="pk {tone} back"></div>{/if}
      <div class="pk {tone}"><b class="serif">W<span>·</span>P</b>{#if big && sub}<small>{sub}</small>{/if}</div>
    </div>
    {#if item.n > 1}<i class="times num">×{item.n}</i>{/if}
  {:else if k === 'wikiki'}
    <div class="coin"><span class="serif">W</span></div>{#if item.n && !big}<i class="times num">{item.n}</i>{/if}
  {:else if k === 'dos'}
    <div class="back"><i></i><span class="serif">W</span></div>
  {:else if k === 'cadre'}
    <div class="ring"><span class="serif">A</span></div>
  {:else}
    <div class="misc"><Icon name={k === 'skin' ? 'spark' : 'cards'} /></div>
  {/if}
</div>

<style>
  .art { position: relative; display: grid; place-items: center; width: 100%; height: 100%; --s: 1; }
  .art.big { --s: 2.5; }
  @media (min-width: 700px) { .art.big { --s: 3.3; } }
  .times { position: absolute; right: 0; bottom: 0; padding: 1px 7px; font: 700 calc(11px * var(--s) * .62) var(--sans); color: var(--on-ivory); background: var(--ivory); border-radius: 99px; }
  .art.big .times { font-size: 16px; padding: 3px 12px; right: 8%; bottom: 6%; }
  .pile { position: relative; width: calc(26px * var(--s)); aspect-ratio: 5 / 7.4; }
  .pk { position: absolute; inset: 0; display: grid; place-content: center; gap: 2px; text-align: center; border-radius: calc(3px * var(--s)); border: 1px solid rgba(255, 255, 255, .22);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, .28), 0 calc(6px * var(--s)) calc(12px * var(--s)) -4px rgba(0, 0, 0, .7), 0 0 calc(18px * var(--s)) -6px var(--rc); }
  .pk.back { transform: translate(18%, -5%) rotate(7deg); filter: brightness(.7); }
  .pk b { font-size: calc(10px * var(--s)); letter-spacing: -.02em; color: #fbf3df; text-shadow: 0 1px 8px rgba(0, 0, 0, .5); } .pk b span { color: var(--gold); }
  .pk small { font: 600 calc(3.4px * var(--s)) var(--sans); letter-spacing: .1em; color: rgba(255, 255, 255, .78); text-transform: none; font-variant-caps: all-small-caps; }
  .plum { background: linear-gradient(160deg, #3b2a7a, #1d4278 55%, #0b5560); }
  .gold { background: linear-gradient(160deg, #a8741b, #e7bd58 55%, #8a5a12); }
  .ember { background: linear-gradient(160deg, #b8400f, #f08a34 55%, #7a2208); }
  .night { background: linear-gradient(160deg, #191513, #3b3128 55%, #0d0b0a); border-color: rgba(250, 204, 21, .5); }
  .coin { width: calc(24px * var(--s)); aspect-ratio: 1; display: grid; place-items: center; border-radius: 50%; color: #6b4a08;
    background: radial-gradient(circle at 32% 28%, #fff1b8, var(--gold) 45%, #a8741b); box-shadow: inset 0 0 0 calc(2px * var(--s) * .4) rgba(120, 80, 10, .35), 0 calc(6px * var(--s)) calc(14px * var(--s)) -5px rgba(0, 0, 0, .7), 0 0 calc(20px * var(--s)) -8px var(--gold); }
  .coin span { font-size: calc(13px * var(--s)); font-weight: 700; }
  .back { position: relative; width: calc(24px * var(--s)); aspect-ratio: 5 / 7; display: grid; place-items: center; border-radius: calc(3px * var(--s)); overflow: hidden;
    background: radial-gradient(120% 90% at 50% 0%, color-mix(in srgb, var(--rc) 40%, #1b2f4f), #0b1426); border: 1px solid color-mix(in srgb, var(--rc) 60%, transparent); box-shadow: 0 calc(6px * var(--s)) calc(14px * var(--s)) -5px rgba(0, 0, 0, .7); }
  .back i { position: absolute; inset: calc(2.5px * var(--s)); border: 1px solid color-mix(in srgb, var(--rc) 50%, transparent); border-radius: calc(1.5px * var(--s)); }
  .back span { font-size: calc(11px * var(--s)); color: color-mix(in srgb, var(--rc) 70%, #fff); opacity: .8; }
  .ring { width: calc(22px * var(--s)); aspect-ratio: 1; display: grid; place-items: center; border-radius: 50%; color: var(--on-ivory); background: linear-gradient(160deg, #fff7e6, var(--ivory-2));
    box-shadow: 0 0 0 calc(2px * var(--s) * .55) var(--ink), 0 0 0 calc(3.4px * var(--s) * .6) var(--rc), 0 0 calc(18px * var(--s)) -4px var(--rc); }
  .ring span { font-size: calc(10px * var(--s)); font-weight: 600; }
  .misc { display: grid; place-items: center; width: calc(24px * var(--s)); aspect-ratio: 1; font-size: calc(14px * var(--s)); color: var(--rc); border: 1px dashed color-mix(in srgb, var(--rc) 55%, transparent); border-radius: calc(5px * var(--s)); background: color-mix(in srgb, var(--rc) 9%, transparent); }
  .cardw { width: calc(26px * var(--s)); } .art:not(.big) .cardw { width: 100%; max-width: 40px; }
  .art.big .cardw { width: min(100%, 150px); }
  @media (min-width: 700px) { .art.big .cardw { width: min(100%, 230px); } }
  .soon { display: grid; place-items: center; gap: 6px; width: calc(22px * var(--s)); aspect-ratio: 5 / 7; color: var(--rc); border: 1px dashed color-mix(in srgb, var(--rc) 60%, transparent); border-radius: calc(3px * var(--s)); text-align: center; }
  .soon b { font-size: calc(10px * var(--s)); } .soon small { font-size: 13px; color: var(--muted); line-height: 1.3; }
</style>
