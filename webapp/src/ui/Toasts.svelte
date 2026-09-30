<script>
  import { toasts } from '../lib/store.svelte.js';
</script>

<div class="toasts" aria-live="polite" aria-atomic="false">
  {#each toasts as t (t.id)}
    <div class="toast {t.kind}" role="status"><i></i><span>{t.msg}</span></div>
  {/each}
</div>

<style>
  .toasts { position: fixed; z-index: 60; left: 50%; bottom: calc(var(--nav) + var(--sab) + 14px); transform: translateX(-50%); display: grid; gap: 8px; width: min(520px, calc(100vw - 24px)); pointer-events: none; }
  .toast { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--glass); backdrop-filter: blur(18px) saturate(1.4); border-radius: 14px;
    box-shadow: var(--sh-3); animation: pop .4s var(--spring); overflow-wrap: anywhere; }
  i { flex: none; width: 9px; height: 9px; border-radius: 50%; background: var(--bad); box-shadow: 0 0 0 4px color-mix(in srgb, var(--bad) 20%, transparent); }
  .info i { background: var(--ivory); box-shadow: 0 0 0 4px rgba(241, 232, 212, .15); }
  .good i { background: var(--good); box-shadow: 0 0 0 4px color-mix(in srgb, var(--good) 20%, transparent); }
  @media (min-width: 980px) { .toasts { bottom: 24px; } }
</style>
