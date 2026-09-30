<script>
  // Grille à défilement virtuel : seules les cartes visibles (plus une marge d'un écran) existent dans la page, que la collection
  // compte 100 ou 10 000 cartes. Le nombre de colonnes suit la largeur ; la hauteur d'une rangée se déduit du format fixe des cartes (5:7),
  // donc rien n'est mesuré carte par carte. La page défile normalement (pas de conteneur à part).
  let { items, item, key = (x) => x, resetKey = null, ratio = 1.4 } = $props();
  let el = $state(null), width = $state(0), wide = $state(false), scrollTop = $state(0), vh = $state(800);

  const minCol = $derived(wide ? 176 : 150), colGap = $derived(wide ? 18 : 12), rowGap = $derived(wide ? 22 : 16);
  const cols = $derived(Math.max(1, Math.floor((width + colGap) / (minCol + colGap))));
  const colW = $derived(width > 0 ? (width - colGap * (cols - 1)) / cols : 1);
  const rowH = $derived(colW * ratio + rowGap);
  const rows = $derived(Math.ceil(items.length / cols));
  const first = $derived(Math.max(0, Math.floor((scrollTop - vh) / rowH)));
  const last = $derived(Math.min(rows, Math.ceil((scrollTop + vh * 2) / rowH)));
  const slice = $derived(width > 0 ? items.slice(first * cols, last * cols) : []);

  let raf = 0;
  function measure() {
    raf = 0;
    if (!el) return;
    scrollTop = -el.getBoundingClientRect().top;
    vh = innerHeight;
  }
  const schedule = () => { if (!raf) raf = requestAnimationFrame(measure); };

  $effect(() => {
    if (!el) return;
    const ro = new ResizeObserver(() => { width = el.clientWidth; wide = innerWidth >= 700; schedule(); });
    ro.observe(el);
    addEventListener('scroll', schedule, { passive: true });
    addEventListener('resize', schedule);
    schedule();
    return () => { ro.disconnect(); removeEventListener('scroll', schedule); removeEventListener('resize', schedule); cancelAnimationFrame(raf); };
  });

  // un autre filtre : on revient en haut de la liste (une simple mise à jour en arrière-plan ne bouge rien)
  let prev = resetKey;
  $effect(() => {
    if (resetKey === prev) return;
    prev = resetKey;
    if (el && el.getBoundingClientRect().top < 0) scrollTo({ top: el.getBoundingClientRect().top + scrollY - 130 });
  });
</script>

<div class="vg" bind:this={el} style:padding-top="{first * rowH}px" style:padding-bottom="{Math.max(0, (rows - last) * rowH)}px">
  <div class="g" style:grid-template-columns="repeat({cols}, minmax(0, 1fr))" style:gap="{rowGap}px {colGap}px">
    {#each slice as it (key(it))}{@render item(it)}{/each}
  </div>
</div>

<style>
  .vg { min-height: 1px; }
  .g { display: grid; }
</style>
