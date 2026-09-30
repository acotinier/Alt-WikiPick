<script>
  // Tiroir par le bas sur mobile, fenêtre centrée sur grand écran. Échap, clic à côté ou bouton pour fermer ; le focus revient où il était.
  import Icon from './Icon.svelte';
  let { open = false, onclose, title = '', wide = false, children } = $props();
  let box = $state(null), from = null;

  $effect(() => {
    if (!open) return;
    from = document.activeElement;
    const y = scrollY;
    document.body.style.overflow = 'hidden';
    const key = (e) => { if (e.key === 'Escape') onclose(); };
    addEventListener('keydown', key);
    queueMicrotask(() => box && box.focus());
    return () => {
      removeEventListener('keydown', key);
      document.body.style.overflow = '';
      scrollTo(0, y);
      if (from && from.isConnected && from.focus) from.focus({ preventScroll: true });
    };
  });
</script>

{#if open}
  <div class="veil" onclick={onclose} role="presentation">
    <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
    <div class="sheet" class:wide role="dialog" aria-modal="true" aria-label={title} tabindex="-1" bind:this={box} onclick={(e) => e.stopPropagation()}>
      <div class="grab" aria-hidden="true"></div>
      <header>
        <h2>{title}</h2>
        <button class="icon-btn" onclick={onclose} aria-label="Fermer" title="Fermer (Échap)"><Icon name="close" /></button>
      </header>
      <div class="body">{@render children()}</div>
    </div>
  </div>
{/if}

<style>
  .veil { position: fixed; inset: 0; z-index: 40; display: flex; align-items: flex-end; justify-content: center; background: rgba(3, 4, 7, .72); backdrop-filter: blur(8px); animation: fade .2s; }
  .sheet { position: relative; display: flex; flex-direction: column; width: 100%; max-height: 94dvh; background: rgba(12, 16, 23, .97); border-radius: 22px 22px 0 0; box-shadow: var(--sh-3);
    animation: up .32s var(--ease); outline: 0; padding-bottom: var(--sab); }
  @keyframes up { from { transform: translateY(40px); opacity: 0; } }
  .grab { width: 38px; height: 4px; margin: 8px auto 0; border-radius: 2px; background: var(--line-3); }
  header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 6px 12px 0 var(--gut); }
  h2 { font: 600 22px/1.2 var(--serif); letter-spacing: -.01em; overflow-wrap: anywhere; }
  .body { overflow-y: auto; overscroll-behavior: contain; padding: 8px var(--gut) 22px; }
  @media (min-width: 700px) {
    .veil { align-items: center; padding: 24px; }
    .sheet { width: min(640px, 100%); max-height: 90dvh; border-radius: 22px; animation: pop .35s var(--ease); }
    .sheet.wide { width: min(980px, 100%); }
    .grab { display: none; }
    header { padding-top: 16px; }
  }
</style>
