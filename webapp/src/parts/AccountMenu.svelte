<script>
  // Le compte : actualiser, exporter, corbeille, journal des actions, déconnexion.
  import { call } from '../lib/api.js';
  import { ago, fmt, plural } from '../lib/format.js';
  import { app, collectionChanged, logout, refreshCollection, refreshMe, run, toast, ui } from '../lib/store.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import Sheet from '../ui/Sheet.svelte';

  let view = $state('menu'), log = $state([]), trash = $state(null), busyLoad = $state(false);
  $effect(() => { if (!ui.menu) view = 'menu'; });

  const close = () => (ui.menu = false);
  async function showLog() {
    view = 'log'; busyLoad = true;
    const r = await call('actions_get');
    busyLoad = false;
    log = r && r.ok ? r.actions : [];
  }
  async function showTrash() {
    view = 'trash'; busyLoad = true;
    const r = await call('corbeille_get');
    busyLoad = false;
    trash = r && r.ok ? r : null;
    if (!trash) toast((r && r.error) || 'Corbeille indisponible', 'error');
  }
  const afterTrash = () => { collectionChanged(); refreshMe(); showTrash(); };
  const left = (s) => (s >= 60 ? `encore ${Math.ceil(s / 60)} min` : "moins d'une minute");
  const titles = { menu: 'Compte', log: "Journal des actions", trash: 'Corbeille' };
</script>

<Sheet open={ui.menu} onclose={close} title={titles[view]}>
  {#if view === 'menu'}
    <p class="who serif">{app.name}</p>
    <div class="list">
      <button class="item" onclick={() => { refreshMe(); refreshCollection(); toast('Actualisé.', 'good'); close(); }}><Icon name="refresh" /><span>Actualiser depuis le site</span></button>
      <a class="item" href="/api/export.csv" download><Icon name="out" /><span>Exporter la collection (CSV)</span></a>
      <button class="item" onclick={showTrash}><Icon name="trash" /><span>Corbeille (recyclées récemment)</span></button>
      <button class="item" onclick={showLog}><Icon name="list" /><span>Journal des actions</span></button>
      <a class="item" href="https://wiki-pick.com" target="_blank" rel="noopener noreferrer"><Icon name="out" /><span>Ouvrir wiki-pick.com</span></a>
    </div>
    <div style="margin-top:18px"><ConfirmButton label="Se déconnecter" confirm="Confirmer la déconnexion" variant="danger" block onconfirm={() => { close(); logout(); }} /></div>
    <p class="muted fine">Se déconnecter efface la session de cet appareil. Si aucun autre appareil n'est connecté, l'instance oublie aussi ta session wiki-pick et ton cache.</p>
  {:else if view === 'log'}
    <button class="btn small ghost" onclick={() => (view = 'menu')}><Icon name="back" />Retour</button>
    <p class="muted fine">Ce que tu as fait depuis l'appli (200 dernières actions), conservé sur l'instance.</p>
    {#if busyLoad}<div class="skeleton" style="height:120px"></div>
    {:else if !log.length}<Empty title="Rien pour l'instant" text="Chaque mise, vente, échange ou recyclage apparaîtra ici." />
    {:else}<div class="list">{#each log.slice(0, 100) as a}<div class="item log" class:bad={!a.ok}><small class="muted">{ago(a.ts)}</small><span>{a.action}</span><em>{a.ok ? 'fait' : a.error || 'refusé'}</em></div>{/each}</div>{/if}
  {:else}
    <button class="btn small ghost" onclick={() => (view = 'menu')}><Icon name="back" />Retour</button>
    {#if busyLoad || !trash}<div class="skeleton" style="height:120px"></div>
    {:else}
      <p class="muted fine">Une carte recyclée reste ici {trash.minutes} minutes. La récupérer coûte {fmt(trash.price)} Wikiki : celui que la banque t'avait donné.</p>
      {#if !trash.items.length}<Empty title="La corbeille est vide" text={`Rien n'a été recyclé ces ${trash.minutes} dernières minutes.`} />
      {:else}
        <div class="row" style="margin:12px 0">
          <ConfirmButton small variant="primary" label={`Tout récupérer · ${fmt(trash.items.length * trash.price)} W`} confirm="Confirmer" onconfirm={() => run(() => call('corbeille_restore', null, true), (r) => { toast(`${plural(r.restored, 'carte récupérée', 'cartes récupérées')} pour ${fmt(r.cost)} Wikiki.`, 'good'); afterTrash(); })} />
          <ConfirmButton small variant="danger" label="Vider la corbeille" confirm={`Effacer ${plural(trash.items.length, 'carte')} pour de bon`} onconfirm={() => run(() => call('corbeille_empty'), (r) => { toast(`${plural(r.erased, 'carte effacée', 'cartes effacées')} pour de bon.`, 'good'); afterTrash(); })} />
        </div>
        <div class="tgrid">
          {#each trash.items as x (x.id)}
            <div class="tslot"><Card card={x.card} width={250} />
              <ConfirmButton small label={`Récupérer · ${fmt(trash.price)} W`} confirm="Confirmer" onconfirm={() => run(() => call('corbeille_restore', [x.id], false), (r) => { toast(`Carte récupérée pour ${fmt(r.cost)} Wikiki.`, 'good'); afterTrash(); })} />
              <small class="muted">{left(x.left)}</small></div>
          {/each}
        </div>
      {/if}
    {/if}
  {/if}
</Sheet>

<style>
  .who { font-size: 26px; margin: 4px 0 14px; }
  .item { color: inherit; text-decoration: none; cursor: pointer; font: inherit; text-align: left; width: 100%; }
  a.item:hover, button.item:hover { background: rgba(255, 255, 255, .05); }
  .item :global(.i) { font-size: 18px; color: var(--muted); }
  .fine { font-size: 12.5px; margin: 12px 0; }
  .log { display: grid; grid-template-columns: 92px 1fr auto; gap: 10px; min-height: 0; padding: 9px 12px; }
  .log em { font-style: normal; color: var(--good); font-size: 13px; }
  .log.bad em { color: #ff8d97; }
  .tgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 14px; }
  .tslot { display: grid; gap: 7px; }
</style>
