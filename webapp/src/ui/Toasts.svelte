<script>
  import { toasts } from '../lib/store.svelte.js';
  import { follow, linkKind } from '../lib/notifLink.js';
</script>

<div class="toasts" aria-live="polite" aria-atomic="false">
  {#each toasts as t (t.id)}
    {#if t.link && linkKind(t.link)}
      <button class="toast link {t.kind}" onclick={() => follow(t.link)}><i></i><span>{t.msg}</span><em>Ouvrir</em></button>
    {:else}
      <div class="toast {t.kind}" role="status"><i></i><span>{t.msg}</span></div>
    {/if}
  {/each}
</div>

<style>
  .toasts { position: fixed; z-index: 60; left: 50%; bottom: calc(var(--nav) + var(--sab) + 14px); transform: translateX(-50%); display: grid; gap: 8px; width: min(520px, calc(100vw - 24px)); pointer-events: none; }
  .toast { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--glass); backdrop-filter: blur(18px) saturate(1.4); border-radius: 14px;
    box-shadow: var(--sh-3); animation: pop .4s var(--spring); overflow-wrap: anywhere; }
  button.toast { pointer-events: auto; width: 100%; text-align: left; color: inherit; font: inherit; border: 0; cursor: pointer; } .toast em { margin-left: auto; font: 600 12.5px var(--sans); font-style: normal; color: var(--ivory); }
  i { flex: none; width: 9px; height: 9px; border-radius: 50%; background: var(--bad); box-shadow: 0 0 0 4px color-mix(in srgb, var(--bad) 20%, transparent); }
  .info i { background: var(--ivory); box-shadow: 0 0 0 4px rgba(228, 197, 133, .15); }
  .good i { background: var(--good); box-shadow: 0 0 0 4px color-mix(in srgb, var(--good) 20%, transparent); }
  @media (min-width: 980px) { .toasts { bottom: 24px; } }
</style>
