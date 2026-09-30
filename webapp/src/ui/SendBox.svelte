<script>
  // Champ d'envoi : Entrée envoie, Maj+Entrée va à la ligne ; la zone grandit avec le texte.
  import Icon from './Icon.svelte';
  let { placeholder = '', max = 400, onsend, value = $bindable(''), busy = false } = $props();
  let ta = $state(null);
  function grow() { if (ta) { ta.style.height = 'auto'; ta.style.height = Math.min(140, ta.scrollHeight) + 'px'; } }
  function send() { const t = value.trim(); if (t && !busy) onsend(t, () => { value = ''; queueMicrotask(grow); }); }
  function key(e) { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } }
</script>

<div class="sendbox">
  <textarea class="field" rows="1" maxlength={max} {placeholder} bind:value bind:this={ta} oninput={grow} onkeydown={key} enterkeyhint="send"></textarea>
  <button class="btn primary" type="button" disabled={busy || !value.trim()} aria-label="Envoyer" onclick={send}><Icon name="send" /></button>
</div>

<style>
  .sendbox { display: flex; align-items: flex-end; gap: 8px; }
  textarea { flex: 1; min-height: 44px; max-height: 140px; }
  .btn { width: 46px; min-height: 44px; padding: 0; }
  .btn :global(.i) { font-size: 18px; }
</style>
