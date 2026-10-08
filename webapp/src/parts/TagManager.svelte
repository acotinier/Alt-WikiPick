<script>
  // Les étiquettes : créer, renommer, recolorer, supprimer. (Les poser sur une carte se fait depuis la fiche de la carte.)
  import { call } from '../lib/api.js';
  import { coll, run, setTags, toast, ui } from '../lib/store.svelte.js';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Sheet from '../ui/Sheet.svelte';

  const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6', '#8b5cf6', '#ec4899', '#64748b', '#a16207'];
  let name = $state(''), color = $state(COLORS[5]), edits = $state({});
  const cur = (t) => edits[t.id] || t;
  const setEdit = (t, patch) => { edits[t.id] = { name: cur(t).name, color: cur(t).color, ...patch }; };

  const apply = (r) => setTags(r.tags);
  const create = () => run(() => call('tag_save', null, name, color), (r) => { apply(r); name = ''; color = COLORS[(r.tags.length) % COLORS.length]; toast('Étiquette créée.', 'good'); });
  const save = (t) => run(() => call('tag_save', t.id, edits[t.id].name, edits[t.id].color), (r) => { apply(r); delete edits[t.id]; toast('Étiquette modifiée.', 'good'); });
  const remove = (t) => run(() => call('tag_delete', t.id), (r) => { apply(r); toast(`« ${t.name} » supprimée.`, 'good'); });
  const changed = (t) => { const e = edits[t.id]; return !!e && (e.name.trim() !== t.name || e.color !== t.color); };
</script>

<Sheet open={ui.tags} onclose={() => (ui.tags = false)} title="Étiquettes">
  <div class="new">
    <input class="field" maxlength="20" placeholder="Nouvelle étiquette" bind:value={name} onkeydown={(e) => e.key === 'Enter' && name.trim() && create()} aria-label="Nom de la nouvelle étiquette" />
    <div class="sw" role="group" aria-label="Couleur">{#each COLORS as c}<button class:on={color === c} style:background={c} aria-label={c} onclick={() => (color = c)}></button>{/each}</div>
    <button class="btn primary block" disabled={!name.trim()} onclick={create}>Créer l'étiquette</button>
  </div>
  {#if coll.tags.length}
    <ul class="list">
      {#each coll.tags as t (t.id)}
        <li>
          <input class="field" maxlength="20" value={cur(t).name} oninput={(ev) => setEdit(t, { name: ev.target.value })} aria-label="Nom" />
          <div class="sw sm" role="group" aria-label="Couleur">{#each COLORS as c}<button class:on={cur(t).color === c} style:background={c} aria-label={c} onclick={() => setEdit(t, { color: c })}></button>{/each}</div>
          <div class="acts">
            <button class="btn small" disabled={!changed(t) || !cur(t).name.trim()} onclick={() => save(t)}>Enregistrer</button>
            <ConfirmButton small variant="danger" label="Supprimer" confirm="Confirmer" onconfirm={() => remove(t)} />
          </div>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="muted">Tu n'as pas encore d'étiquette. Crée la première ci-dessus, puis pose-la sur tes cartes depuis leur fiche.</p>
  {/if}
</Sheet>

<style>
  .new { display: grid; gap: 12px; padding-bottom: 16px; border-bottom: 1px solid var(--line); }
  .sw { display: flex; flex-wrap: wrap; gap: 8px; }
  .sw button { width: 28px; height: 28px; padding: 0; border: 2px solid transparent; border-radius: 50%; cursor: pointer; }
  .sw.sm button { width: 22px; height: 22px; }
  .sw button.on { border-color: var(--ivory); box-shadow: 0 0 0 2px var(--ink-1) inset; }
  .list { display: grid; gap: 14px; margin: 16px 0 0; padding: 0; list-style: none; }
  .list li { display: grid; gap: 10px; padding: 12px; background: rgba(255, 255, 255, .025); border: 1px solid var(--line); border-radius: var(--rad-m); }
  .acts { display: flex; gap: 8px; }
</style>
