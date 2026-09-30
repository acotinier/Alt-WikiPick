<script>
  // L'arène : ton quota de combats, ton Mini-Pack, tes adversaires et tes derniers duels.
  // Le rejeu des duels à deux n'est pas encore dans la version web : pour combattre, ouvre wiki-pick.com (l'appli de bureau les gère).
  import { call } from '../lib/api.js';
  import { ago, clock, fmt, plural } from '../lib/format.js';
  import { app, nowSrv, refreshMeSoon, run, setSkew, toast, collectionChanged, openCard } from '../lib/store.svelte.js';
  import { tick } from '../lib/ticker.svelte.js';
  import Avatar from '../ui/Avatar.svelte';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';

  let info = $state(null), err = $state(''), prize = $state(null);
  call('combat_info').then((r) => { if (r.ok) info = r; else err = r.error || 'Arène indisponible'; });
  const reset = $derived(info ? (void tick.now, Math.max(0, Math.round(info.next - nowSrv()))) : 0);
  const openChest = () => run(() => call('combat_chest'), (r) => { prize = r; info.chests = r.left; refreshMeSoon(); if (r.card) collectionChanged(); });
</script>

{#if err}<Empty title="Arène indisponible" text={err} />
{:else if !info}<div class="skeleton" style="height:240px"></div>
{:else}
  <p class="muted intro">Défie un joueur connecté : vous alignez {info.size} cartes chacun et le duel se joue en direct. Tes cartes ne quittent jamais ta collection : l'arène ne risque rien.</p>
  <div class="note"><Icon name="sword" /><span>Les combats à deux se jouent pour l'instant sur <a href="https://wiki-pick.com" target="_blank" rel="noopener noreferrer">wiki-pick.com</a> ou avec l'appli de bureau. Le rejeu des duels arrive dans la version web.</span></div>

  <section class="quota surface">
    <div class="dots">{#each Array(info.total) as _, i}<i class:on={i < info.left}></i>{/each}</div>
    <div><b>Combats disponibles : {info.left} / {info.total}</b>
      <small class="muted">{info.next > 0 ? (info.left > 0 ? `Le compteur revient à ${info.total} dans ${clock(reset)}` : `Tes combats reviennent dans ${clock(reset)}`) : `${info.total} combats toutes les ${Math.round(info.window / 60)} minutes : le compte à rebours démarre à ton premier combat.`}</small></div>
  </section>

  <section class="chest surface" class:ready={info.chests > 0}>
    {#if prize}
      <b class="serif">Mini-Pack ouvert !</b>
      <div class="prize">{#if prize.kind === 'packs'}<b class="serif">{plural(prize.n, 'paquet')} !</b>{:else}<span class="gain"><Icon name="coin" /><b class="serif">+{fmt(prize.n)}</b> Wikiki</span>{/if}
        {#if prize.card}<div class="pc"><Card card={prize.card} onclick={() => openCard(prize.card)} /></div>{/if}</div>
      <p class="muted">{prize.left ? `Il t'en reste ${plural(prize.left, 'autre')} à ouvrir.` : 'Rejoue pour en mériter un autre.'}</p>
    {:else if info.chests > 0}
      <b class="serif">{info.chests > 1 ? `${info.chests} Mini-Packs t'attendent` : "Un Mini-Pack t'attend"}</b>
      <p class="muted">Ouvre-le : des récompenses, rares ou moins rares, t'attendent à l'intérieur.</p>
      <ConfirmButton variant="gold" label="Ouvrir le Mini-Pack" onconfirm={openChest} />
    {:else}
      <b class="serif">Ton prochain Mini-Pack</b>
      <p class="muted">Joue {plural(info.chest_all, 'combat')} pour le débloquer : {info.chest_all - info.chest_left} / {info.chest_all} joués.</p>
      <div class="bar"><i style:width="{Math.min(100, Math.round((100 * (info.chest_all - info.chest_left)) / info.chest_all))}%"></i></div>
    {/if}
  </section>

  <h2 class="sec">Amis</h2>
  <div class="list">
    {#each info.opponents as u}
      <div class="item"><Avatar name={u.name} size={38} /><div class="tx"><b class="serif">{u.fav ? '★ ' : ''}{u.name}</b><small class="muted">{u.online ? (u.fighting ? 'En combat' : 'En ligne') + (u.cards != null ? `, ${plural(u.cards, 'carte')}` : '') : 'Hors ligne'}</small></div>
        <span class="dot" class:on={u.online}></span></div>
    {:else}<p class="muted">Tu n'as pas encore d'amis à défier.</p>{/each}
  </div>

  {#if info.history.length}
    <h2 class="sec">Tes derniers combats</h2>
    <div class="list">{#each info.history as h}
      <div class="item hist" class:win={h.me > h.them}><b>{h.me > h.them ? 'Victoire' : 'Défaite'}</b><span>{h.me} – {h.them}</span><span class="muted">{h.defended ? 'défié par' : 'contre'} {h.opponent}</span><span class="sp"></span><span class="gain num">{h.gain ? `+${fmt(h.gain)}` : '—'}</span><small class="muted">{ago(h.when, nowSrv())}</small></div>{/each}</div>
  {/if}
{/if}

<style>
  .intro { font-size: 14px; margin-bottom: 12px; }
  .note { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 14px; padding: 12px 14px; font-size: 13.5px; color: var(--muted); background: color-mix(in srgb, var(--warn) 6%, transparent); border: 1px solid color-mix(in srgb, var(--warn) 25%, transparent); border-radius: var(--rad-m); }
  .note :global(.i) { font-size: 18px; color: var(--warn); flex: none; margin-top: 2px; } .note a { color: var(--text); }
  .quota { display: flex; gap: 16px; align-items: center; margin-bottom: 12px; } .quota small { display: block; }
  .dots { display: flex; gap: 6px; } .dots i { width: 10px; height: 10px; transform: rotate(45deg); border-radius: 2px; border: 1px solid var(--faint); } .dots i.on { background: var(--gold); border-color: var(--gold); box-shadow: 0 0 10px -2px var(--gold); }
  .chest { display: grid; gap: 8px; } .chest.ready { border-color: rgba(227, 189, 108, .5); background: radial-gradient(90% 120% at 100% 0%, rgba(227, 189, 108, .16), transparent 60%), rgba(255, 255, 255, .02); }
  .chest > b { font-size: 19px; }
  .bar { height: 5px; background: rgba(255, 255, 255, .06); border-radius: 3px; overflow: hidden; } .bar i { display: block; height: 100%; background: linear-gradient(90deg, var(--ivory-2), var(--gold)); }
  .prize { display: flex; align-items: center; gap: 14px; animation: pop .5s var(--spring); } .prize b { font-size: 22px; } .pc { width: 100px; }
  .gain { display: inline-flex; align-items: center; gap: 6px; color: var(--gold); font-weight: 600; } .gain :global(.i) { font-size: 16px; }
  .tx { display: grid; flex: 1; } .tx b { font-size: 16px; } .tx small { font-size: 12.5px; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--faint); } .dot.on { background: var(--good); box-shadow: 0 0 8px var(--good); }
  .hist { flex-wrap: wrap; gap: 4px 12px; } .hist b { color: #ff8d97; } .hist.win b { color: var(--good); }
</style>
