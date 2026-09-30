<script>
  // La question « es-tu un robot ? » du site : c'est le joueur qui clique, l'appli ne devine jamais la réponse.
  import Picto from './Picto.svelte';
  let { challenge, onanswer, onother = null, oncancel = null, busy = false } = $props();
</script>

<div class="defi">
  <p class="q serif">{challenge.consigne || 'Choisis la bonne forme'}</p>
  <div class="grid">
    {#each challenge.choix as p, i}
      <button class="c" type="button" disabled={!p || busy} aria-label={`Forme ${i + 1}`} onclick={() => onanswer(i)}><Picto picto={p} /></button>
    {/each}
  </div>
  <p class="muted small">Le site vérifie de temps en temps qu'un humain agit. Clique la forme demandée : c'est ton choix qui est envoyé, rien d'autre.</p>
  <div class="row">
    {#if onother}<button class="btn small ghost" type="button" onclick={onother} disabled={busy}>Une autre question</button>{/if}
    {#if oncancel}<button class="btn small" type="button" onclick={oncancel}>Annuler</button>{/if}
  </div>
</div>

<style>
  .defi { display: grid; gap: 16px; }
  .q { font-size: 22px; font-style: italic; line-height: 1.3; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .c { display: grid; place-items: center; aspect-ratio: 1; padding: 20%; cursor: pointer; background: linear-gradient(180deg, rgba(255, 255, 255, .045), rgba(255, 255, 255, .015));
    border: 1px solid var(--line-2); border-radius: var(--rad-l); transition: transform .2s var(--spring), border-color .15s, background .15s; }
  .c :global(svg) { width: 100%; height: 100%; filter: drop-shadow(0 6px 14px rgba(0, 0, 0, .45)); }
  .c:hover { transform: translateY(-3px) scale(1.03); border-color: rgba(241, 232, 212, .45); background: rgba(255, 255, 255, .07); }
  .c:active { transform: scale(.96); }
  .c:disabled { opacity: .3; cursor: default; transform: none; }
  .small { font-size: 12.5px; }
</style>
