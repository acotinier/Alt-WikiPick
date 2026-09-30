<script>
  // Messagerie : la liste des conversations, puis la conversation. Sur téléphone on voit l'une ou l'autre (adresse #/social/messages/<pseudo>) ;
  // sur grand écran, les deux côte à côte. Les messages des autres sont toujours du texte, jamais du HTML.
  import { call } from '../lib/api.js';
  import { ago, debounce, same } from '../lib/format.js';
  import { go, route } from '../lib/router.svelte.js';
  import { app, nowSrv, on, refreshMeSoon, run, toast } from '../lib/store.svelte.js';
  import Avatar from '../ui/Avatar.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Icon from '../ui/Icon.svelte';
  import SendBox from '../ui/SendBox.svelte';

  const current = $derived(route.parts[2] || null);
  let convs = $state([]), thread = $state(null), loadingList = $state(true), draft = $state(''), found = $state([]), find = $state(''), sending = $state(false), seq = 0, body = $state(null);

  async function loadList() {
    const r = await call('conversations_get');
    loadingList = false;
    if (r.ok) convs = r.conversations;
  }
  async function loadThread() {
    const name = current, mine = ++seq;
    if (!name) { thread = null; return; }
    const r = await call('thread_get', name);
    if (mine !== seq) return;
    if (!r.ok) { if (!r.expired) toast(r.error || 'Conversation indisponible', 'error'); return; }
    thread = r.thread;
    queueMicrotask(() => { if (body) body.scrollTop = body.scrollHeight; });
    refreshMeSoon(); loadList();
  }
  $effect(() => { current; thread = null; loadThread(); });
  loadList();
  $effect(() => on('message', (d) => { loadList(); if (same(d.from, current)) loadThread(); }));

  const search = debounce(async (v) => {
    if (!v.trim()) { found = []; return; }
    const r = await call('players_search', v.trim());
    found = r.ok ? r.users.filter((u) => !u.me) : [];
  }, 280);
  const openWith = (n) => { find = ''; found = []; go(`/social/messages/${n}`); };
  const send = async (text, clear) => {
    sending = true;
    const r = await run(() => call('message_send', current, text), () => {});
    sending = false;
    if (r) { clear(); loadThread(); }
  };
  const block = (on_) => run(() => call('friend_action', on_ ? 'block' : 'unblock', current), () => { toast(on_ ? `${current} est bloqué(e) : vous ne vous verrez plus sur le site.` : `${current} est débloqué(e).`, 'good'); if (on_) go('/social/messages'); else loadThread(); });
</script>

<div class="msgs" class:in-thread={!!current}>
  <aside class="list-pane">
    <label class="search"><Icon name="search" /><input type="search" placeholder="Écrire à un joueur…" autocomplete="off" bind:value={find} oninput={() => search(find)} /></label>
    {#if found.length}
      <div class="list">{#each found as u}<button class="conv" onclick={() => openWith(u.name)}><Avatar name={u.name} url={u.avatar} /><span class="tx"><b class="serif">{u.name}</b><small class="muted">{u.relation === 'friends' ? 'Ami(e)' : 'Joueur'}</small></span></button>{/each}</div>
    {/if}
    <div class="convs">
      {#if loadingList}<div class="skeleton" style="height:150px"></div>
      {:else if !convs.length}<p class="muted pad">Aucune conversation pour l'instant. Cherche un joueur ci-dessus pour lui écrire.</p>
      {:else}{#each convs as c (c.name)}
        <button class="conv" class:on={same(c.name, current)} class:unread={c.unread} onclick={() => openWith(c.name)}>
          <Avatar name={c.name} url={c.avatar} size={42} />
          <span class="tx"><b class="serif">{#if c.fav}<i class="fav">★</i>{/if}{c.name}{#if c.blocked}<em>Bloqué</em>{/if}</b><small class="muted">{c.mine ? 'Toi : ' : ''}{c.last}</small></span>
          {#if c.unread}<i class="badge">{c.unread}</i>{:else}<small class="when muted">{ago(c.created, nowSrv())}</small>{/if}
        </button>{/each}{/if}
    </div>
  </aside>

  <section class="thread-pane">
    {#if !current}
      <div class="none"><b class="serif">Tes conversations</b><span class="muted">Choisis une conversation, ou cherche un joueur pour lui écrire.</span></div>
    {:else if !thread}<div class="skeleton" style="height:220px;margin:16px"></div>
    {:else}
      <header><button class="icon-btn back" aria-label="Retour" onclick={() => go('/social/messages')}><Icon name="back" /></button>
        <Avatar name={thread.with} url={thread.avatar} size={40} />
        <div class="who"><button class="name serif" onclick={() => go(`/player/${thread.with}`)}>{thread.with}</button>{#if thread.friend}<span class="pill good">Ami(e)</span>{/if}</div>
        <span class="sp"></span>
        {#if thread.blocked === 'moi'}<button class="btn small" onclick={() => block(false)}>Débloquer</button>
        {:else if thread.blocked !== 'lui'}<ConfirmButton small variant="ghost" label="Bloquer" confirm="Confirmer le blocage" onconfirm={() => block(true)} />{/if}</header>
      <div class="body" bind:this={body}>
        {#each thread.messages as m (m.id)}<div class="bub" class:mine={m.mine}>{m.text}</div>
        {:else}<p class="muted center first">Écris ton premier message à {thread.with}.</p>{/each}
      </div>
      {#if thread.blocked === 'moi'}<p class="blocked muted">Tu as bloqué {thread.with} : vous ne pouvez plus vous écrire.</p>
      {:else if thread.blocked === 'lui'}<p class="blocked muted">Tu ne peux plus écrire à {thread.with}.</p>
      {:else}<div class="foot"><SendBox placeholder={`Écrire à ${thread.with}…`} max={1000} busy={sending} bind:value={draft} onsend={send} /></div>{/if}
    {/if}
  </section>
</div>

<style>
  .msgs { display: grid; min-height: calc(100dvh - var(--top) - var(--sat) - 130px); }
  .list-pane { display: grid; gap: 10px; align-content: start; min-width: 0; }
  .thread-pane { display: none; min-width: 0; }
  .msgs.in-thread .list-pane { display: none; } .msgs.in-thread .thread-pane { display: flex; flex-direction: column; }
  .search { display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 14px; color: var(--faint); background: var(--ink-2); border: 1px solid var(--line-2); border-radius: 12px; }
  .search:focus-within { color: var(--text); border-color: rgba(241, 232, 212, .5); }
  .search input { flex: 1; min-width: 0; background: none; border: 0; outline: 0; color: var(--text); font: 16px var(--sans); }
  .list, .convs { display: grid; gap: 2px; }
  .conv { display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px 10px; text-align: left; cursor: pointer; background: none; border: 0; border-radius: 12px; color: inherit; }
  .conv:hover { background: rgba(255, 255, 255, .04); } .conv.on { background: rgba(255, 255, 255, .07); }
  .tx { display: grid; flex: 1; min-width: 0; } .tx b { font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .tx small { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .conv.unread small { color: var(--text); font-weight: 500; } .fav { color: var(--gold); font-style: normal; margin-right: 4px; }
  em { margin-left: 6px; font: 600 11px var(--sans); font-style: normal; color: #ff8d97; } .when { font-size: 11px; flex: none; }
  .pad { padding: 14px; }
  .none { display: grid; gap: 6px; place-content: center; text-align: center; min-height: 280px; } .none b { font-size: 20px; }
  .thread-pane header { display: flex; align-items: center; gap: 10px; padding: 4px 0 12px; border-bottom: 1px solid var(--line); }
  .back { display: grid; } .who { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; min-width: 0; }
  .name { padding: 0; background: none; border: 0; color: var(--text); font-size: 19px; font-weight: 600; cursor: pointer; overflow-wrap: anywhere; text-align: left; }
  .body { flex: 1; display: flex; flex-direction: column; gap: 6px; padding: 16px 0; min-height: 260px; }
  .bub { align-self: flex-start; max-width: 82%; padding: 9px 14px; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.45; background: var(--ink-3); border: 1px solid var(--line); border-radius: 16px 16px 16px 5px; animation: rise .25s var(--ease) backwards; }
  .bub.mine { align-self: flex-end; color: var(--on-ivory); background: linear-gradient(180deg, #f8f0de, var(--ivory)); border-color: transparent; border-radius: 16px 16px 5px 16px; }
  .first { margin: auto; }
  .foot { position: sticky; bottom: calc(var(--nav) + var(--sab) + 8px); padding: 10px 0; background: linear-gradient(transparent, var(--ink) 30%); }
  .blocked { padding: 16px 0; }
  @media (min-width: 700px) {
    .msgs { grid-template-columns: 300px minmax(0, 1fr); gap: 20px; }
    .list-pane, .msgs.in-thread .list-pane { display: grid; } .thread-pane, .msgs.in-thread .thread-pane { display: flex; flex-direction: column; }
    .back { display: none; }
    .thread-pane { background: rgba(255, 255, 255, .015); border: 1px solid var(--line); border-radius: var(--rad-l); padding: 0 16px; }
  }
  @media (min-width: 980px) { .foot { bottom: 8px; } }
</style>
