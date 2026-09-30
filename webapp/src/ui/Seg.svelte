<script>
  // Onglets segmentés : items = [[id, libellé, pastille?]]. Défile horizontalement s'il y en a trop pour l'écran.
  let { items, value, onchange } = $props();
</script>

<div class="seg" role="tablist">
  {#each items as [id, label, n] (id)}
    <button role="tab" aria-selected={value === id} class:on={value === id} onclick={() => onchange(id)}>
      {label}{#if n}<i class="badge">{n}</i>{/if}
    </button>
  {/each}
</div>

<style>
  .seg { display: flex; gap: 2px; padding: 3px; overflow-x: auto; scrollbar-width: none; background: var(--ink-1); border: 1px solid var(--line); border-radius: 13px; box-shadow: inset 0 1px 2px rgba(0, 0, 0, .4); }
  .seg::-webkit-scrollbar { display: none; }
  button { flex: 1 0 auto; display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 38px; padding: 0 14px; background: none; border: 0; border-radius: 10px; color: var(--muted);
    font: 500 14px var(--sans); cursor: pointer; white-space: nowrap; transition: color .15s, background .2s var(--ease); }
  button.on { color: var(--text); background: var(--ink-4); box-shadow: var(--hi), 0 1px 3px rgba(0, 0, 0, .5); }
  .badge { font-style: normal; }
</style>
