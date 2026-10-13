<script>
  // Les notes de version d'Alt-WikiPick (fichier local). Celles du site lui-même sont sur wiki-pick.com/nouveautes : un lien, pas une copie.
  import { call } from '../lib/api.js';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  const KIND = { new: 'Nouveau', better: 'Amélioré', fix: 'Corrigé' };
  let news = $state(null), failed = $state(false);
  call('news_get').then((r) => { if (r && r.ok) news = r; else failed = true; });
  const day = (s) => new Date(s + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
</script>

{#if failed}
  <Empty title="Nouveautés indisponibles" text="Réessaie dans un instant." />
{:else if !news}
  <div class="skeleton" style="height:220px"></div>
{:else}
  <a class="site" href={news.site_url} target="_blank" rel="noopener noreferrer"><Icon name="out" /><span>Les mises à jour de wiki-pick.com<small>Les notes du jeu lui-même, sur le site</small></span></a>
  {#each news.versions as v, i (v.version)}
    <article class="ver" class:latest={i === 0}>
      <header><b class="serif num">{v.version}</b><span class="muted">{day(v.date)}</span>{#if i === 0}<em>Dernière</em>{/if}</header>
      <h2 class="serif">{v.title}</h2>
      <ul>{#each v.items as it}<li><span class="k {it.kind}">{KIND[it.kind]}</span><p>{it.text}</p></li>{/each}</ul>
    </article>
  {/each}
{/if}

<style>
  .site { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; padding: 14px 16px; color: inherit; text-decoration: none; background: var(--ink-1); border: 1px solid var(--line-2); border-radius: 16px; }
  .site :global(.i) { font-size: 20px; color: var(--ivory); } .site span { display: grid; font-weight: 500; } .site small { color: var(--muted); font-weight: 400; font-size: 12.5px; }
  .ver { padding: 20px 4px 22px; border-top: 1px solid var(--line-2); }
  .ver.latest { padding: 22px 18px; border: 1px solid color-mix(in srgb, var(--ivory) 35%, var(--line)); border-radius: 20px; margin-bottom: 8px;
    background: radial-gradient(120% 100% at 0% 0%, rgba(228, 197, 133, .1), transparent 60%), var(--ink-1); }
  header { display: flex; align-items: baseline; gap: 12px; } header b { font-size: 30px; letter-spacing: -.02em; color: var(--ivory); }
  header em { margin-left: auto; font: 600 11px var(--sans); font-style: normal; letter-spacing: .08em; font-variant-caps: all-small-caps; color: var(--on-ivory); background: var(--ivory); padding: 2px 10px; border-radius: 99px; }
  h2 { margin: 6px 0 14px; font: 600 21px/1.2 var(--serif); }
  ul { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
  li { display: grid; grid-template-columns: 82px minmax(0, 1fr); gap: 12px; align-items: baseline; }
  li p { font-size: 14.5px; line-height: 1.5; }
  .k { justify-self: start; padding: 1px 9px; font: 600 11.5px/18px var(--sans); border: 1px solid var(--line-2); border-radius: 99px; color: var(--muted); }
  .k.new { color: var(--ivory); border-color: color-mix(in srgb, var(--ivory) 50%, transparent); } .k.fix { color: var(--good); border-color: color-mix(in srgb, var(--good) 45%, transparent); }
  .k.better { color: #8fb7ff; border-color: color-mix(in srgb, #8fb7ff 45%, transparent); }
</style>
