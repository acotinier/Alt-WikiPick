<script>
  let { title = '', text = '' } = $props();
</script>

<div class="empty"><b>{title}</b>{#if text}<span>{text}</span>{/if}</div>

<style>
  .empty { display: grid; gap: 6px; justify-items: center; padding: 48px 16px; text-align: center; color: var(--muted); grid-column: 1 / -1; }
  b { font: 600 20px var(--serif); color: var(--text); }
  span { max-width: 46ch; font-size: 14px; }
</style>
