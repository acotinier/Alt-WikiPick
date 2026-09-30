<script>
  import { call } from '../lib/api.js';
  import { debounce } from '../lib/format.js';
  import { go } from '../lib/router.svelte.js';
  import { openTrade, refreshMeSoon, run, toast } from '../lib/store.svelte.js';
  import Avatar from '../ui/Avatar.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import FriendActions from '../ui/FriendActions.svelte';
  import Icon from '../ui/Icon.svelte';

  let data = $state(null), q = $state(''), found = $state([]);
  const load = async () => { const r = await call('friends_list'); if (r.ok) data = r; else if (!r.expired) toast(r.error || 'Amis indisponibles', 'error'); };
  load();
  const search = debounce(async (v) => {
    if (!v.trim()) { found = []; return; }
    const r = await call('players_search', v.trim());
    found = r.ok ? r.users : [];
  }, 280);
  const again = () => { load(); search(q); };
  const star = (u) => run(() => call('friend_favorite', u.name, !u.fav), load);
  const remove = (u) => run(() => call('friend_action', 'remove', u.name), () => { toast(`${u.name} ne fait plus partie de tes ami(e)s.`, 'good'); refreshMeSoon(); load(); });
</script>

<label class="search"><Icon name="search" /><input type="search" placeholder="Chercher un joueur à ajouter" autocomplete="off" bind:value={q} oninput={() => search(q)} /></label>
{#if found.length}
  <div class="list found">{#each found as u}
    <div class="item"><Avatar name={u.name} url={u.avatar} /><button class="who serif" onclick={() => go(`/player/${u.name}`)}>{u.name}</button><span class="sp"></span>
      {#if u.me}<span class="pill">Toi</span>{:else}<FriendActions name={u.name} relation={u.relation} ondone={again} />{/if}</div>{/each}</div>
{:else if q.trim()}<p class="muted note">Aucun joueur ne correspond.</p>{/if}

{#if !data}<div class="skeleton" style="height:180px;margin-top:16px"></div>
{:else}
  {#if data.incoming.length}
    <h2 class="sec">Demandes reçues · {data.incoming.length}</h2>
    <div class="list">{#each data.incoming as u}<div class="item"><Avatar name={u.name} url={u.avatar} /><button class="who serif" onclick={() => go(`/player/${u.name}`)}>{u.name}</button><span class="sp"></span><FriendActions name={u.name} relation="incoming" ondone={load} /></div>{/each}</div>
  {/if}
  <h2 class="sec">Tes ami(e)s · {data.friends.length}</h2>
  {#if !data.friends.length}<p class="muted">Tu n'as pas encore d'ami(e)s. Cherche des joueurs ci-dessus et envoie-leur une demande : les échanges se font entre amis.</p>{/if}
  <div class="list">
    {#each data.friends as u (u.name)}
      <div class="item" class:fav={u.fav}>
        <Avatar name={u.name} url={u.avatar} />
        <button class="who serif" onclick={() => go(`/player/${u.name}`)}>{u.name}</button><span class="sp"></span>
        <button class="icon-btn star" class:on={u.fav} aria-label={u.fav ? 'Retirer des favoris' : 'Mettre en favori'} onclick={() => star(u)}><Icon name="star" /></button>
        <button class="icon-btn" aria-label="Message" onclick={() => go(`/social/messages/${u.name}`)}><Icon name="chat" /></button>
        <button class="icon-btn" aria-label="Échanger" onclick={() => openTrade(u.name)}><Icon name="swap" /></button>
        <ConfirmButton small variant="ghost" label="Retirer" confirm="Confirmer" onconfirm={() => remove(u)} />
      </div>
    {/each}
  </div>
  {#if data.outgoing.length}
    <h2 class="sec">Demandes envoyées</h2>
    <div class="list">{#each data.outgoing as u}<div class="item"><Avatar name={u.name} url={u.avatar} /><button class="who serif" onclick={() => go(`/player/${u.name}`)}>{u.name}</button><span class="sp"></span><FriendActions name={u.name} relation="outgoing" ondone={load} /></div>{/each}</div>
  {/if}
{/if}

<style>
  .search { display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 14px; color: var(--faint); background: var(--ink-2); border: 1px solid var(--line-2); border-radius: 12px; }
  .search:focus-within { color: var(--text); border-color: rgba(241, 232, 212, .5); }
  .search input { flex: 1; min-width: 0; background: none; border: 0; outline: 0; color: var(--text); font: 16px var(--sans); }
  .found { margin-top: 10px; } .note { margin-top: 10px; font-size: 13.5px; }
  .who { padding: 0; background: none; border: 0; color: var(--text); font-size: 17px; font-weight: 600; cursor: pointer; text-align: left; overflow-wrap: anywhere; min-width: 0; }
  .item { flex-wrap: wrap; } .item.fav { border-color: rgba(227, 189, 108, .25); }
  .star.on { color: var(--gold); } .star.on :global(.i) { fill: currentColor; }
  .icon-btn { width: 38px; height: 38px; }
</style>
