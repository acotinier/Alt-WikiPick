<script>
  // Toute action qui engage des pièces ou des cartes : un premier clic arme le bouton, le second (dans les 4,5 s) confirme.
  import { toast } from '../lib/store.svelte.js';
  let { label, confirm = null, onconfirm, variant = '', small = false, disabled = false, check = null, block = false } = $props();
  let armed = $state(false), timer;
  function press(e) {
    e.stopPropagation();
    const bad = check && check();
    if (bad) { armed = false; clearTimeout(timer); return toast(bad, 'error'); }
    if (confirm && !armed) {
      armed = true;
      timer = setTimeout(() => (armed = false), 4500);
      return;
    }
    clearTimeout(timer); armed = false;
    onconfirm(e);
  }
  $effect(() => () => clearTimeout(timer));
</script>

<button class="btn {variant}" class:small class:armed class:block {disabled} onclick={press} type="button">
  {armed ? (typeof confirm === 'function' ? confirm() : confirm) : label}
</button>
