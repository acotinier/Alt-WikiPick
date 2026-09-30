<script>
  import { call } from '../lib/api.js';
  import { ago } from '../lib/format.js';
  import { app, nowSrv, run, setSkew, ui } from '../lib/store.svelte.js';
  import Empty from '../ui/Empty.svelte';
  import Sheet from '../ui/Sheet.svelte';

  let items = $state([]), loading = $state(false);

  $effect(() => { if (ui.bell) load(); });
  async function load() {
    loading = true;
    const r = await call('load_notifications');
    loading = false;
    if (r && r.ok) { setSkew(r.now); items = r.items; }
  }
  const readAll = () => run(() => call('read_notifications'), () => { items = items.map((n) => ({ ...n, read: true })); if (app.me) app.me.unread = 0; });
  const extra = $derived([app.me?.unreadMsg && `${app.me.unreadMsg} message${app.me.unreadMsg > 1 ? 's' : ''} non lu${app.me.unreadMsg > 1 ? 's' : ''}`,
    app.me?.trades && `${app.me.trades} échange${app.me.trades > 1 ? 's' : ''} en attente`,
    app.me?.friendReq && `${app.me.friendReq} demande${app.me.friendReq > 1 ? 's' : ''} d'ami`].filter(Boolean).join(' · '));
</script>

<Sheet open={ui.bell} onclose={() => (ui.bell = false)} title="Notifications">
  {#if loading && !items.length}
    <div class="skeleton" style="height:160px"></div>
  {:else if !items.length}
    <Empty title="Rien de neuf" text="Tes notifications apparaîtront ici." />
  {:else}
    <div class="list">
      {#each items as n (n.id || n.created + n.text)}
        <div class="n" class:unread={!n.read} class:good={n.tone === 'good'} class:bad={n.tone === 'bad'}>
          <i></i><div><span>{n.text}</span><small class="muted">{ago(n.created, nowSrv())}</small></div>
        </div>
      {/each}
    </div>
  {/if}
  {#if extra}<p class="muted extra">{extra}</p>{/if}
  {#if items.some((n) => !n.read)}<button class="btn block" style="margin-top:14px" onclick={readAll}>Tout marquer comme lu</button>{/if}
</Sheet>

<style>
  .n { display: flex; gap: 12px; padding: 12px 14px; background: rgba(255, 255, 255, .02); border: 1px solid var(--line); border-radius: var(--rad-m); }
  .n i { flex: none; width: 3px; border-radius: 2px; background: transparent; }
  .n.unread i { background: var(--ivory); }
  .n.unread.good i { background: var(--good); }
  .n.unread.bad i { background: var(--bad); }
  .n div { display: grid; gap: 2px; min-width: 0; overflow-wrap: anywhere; }
  small { font-size: 12px; }
  .extra { margin-top: 12px; font-size: 13px; }
</style>
