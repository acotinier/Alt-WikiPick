<script>
  // Un pictogramme de la question « es-tu un robot ? » : des formes déjà filtrées par le serveur (liste blanche), redessinées ici.
  let { picto } = $props();
</script>

{#if picto}
  <svg viewBox={picto.viewBox} aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
    {#each picto.shapes as s}<svelte:element this={s.tag} xmlns="http://www.w3.org/2000/svg" {...s.attrs} />{/each}
  </svg>
{:else}
  <span class="muted">?</span>
{/if}
