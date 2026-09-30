<script>
  import { ICONS } from '../lib/icons.js';
  let { name, size = null } = $props();
</script>

<svg class="i" viewBox="0 0 24 24" aria-hidden="true" style:font-size={size}>{@html ICONS[name] || ''}</svg>
