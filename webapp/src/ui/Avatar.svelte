<script>
  let { name = '?', url = null, size = 36 } = $props();
  let broken = $state(false);
</script>

<span class="av" style:width="{size}px" style:height="{size}px" style:font-size="{Math.round(size * 0.42)}px" aria-hidden="true">
  <span>{([...String(name)][0] || '?').toUpperCase()}</span>
  {#if url && !broken}<img src={url} alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror={() => (broken = true)} />{/if}
</span>

<style>
  .av { position: relative; flex: none; display: grid; place-items: center; overflow: hidden; border-radius: 50%; font-family: var(--serif); font-weight: 600; color: var(--on-ivory);
    background: linear-gradient(160deg, #fff7e6, var(--ivory-2)); box-shadow: 0 0 0 1px var(--line-2); }
  img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
</style>
