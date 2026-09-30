<script>
  // La guilde : le fil (ce que les membres ont sorti de plus beau), le tchat, les membres, les demandes, le classement des guildes.
  // Le fil et le tchat ne se lisent que de l'intérieur ; les actions de gestion se confirment.
  import { call } from '../lib/api.js';
  import { ago, color, fmt, plural } from '../lib/format.js';
  import { go } from '../lib/router.svelte.js';
  import { app, nowSrv, on, openCard, run, toast } from '../lib/store.svelte.js';
  import Avatar from '../ui/Avatar.svelte';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import Seg from '../ui/Seg.svelte';
  import SendBox from '../ui/SendBox.svelte';
  import Sheet from '../ui/Sheet.svelte';

  let list = $state(null), g = $state(null), view = $state(null), tab = $state('feed'), err = $state(''), open = $state([]), draft = $state(''), cdraft = $state({}), sending = $state(false), create = $state(false), form = $state({ name: '', tag: '', descr: '' }), chatEl = $state(null), seq = 0;

  async function load() {
    const mine = ++seq;
    const l = await call('guilds_get');
    if (mine !== seq) return;
    if (!l.ok) { err = l.error || 'Guildes indisponibles'; return; }
    list = l;
    const id = view || l.mine;
    if (!id) { g = null; return; }
    const r = await call('guild_get', id);
    if (mine !== seq) return;
    if (!r.ok) { view = null; g = null; return; }
    g = r.guild;
    if (!g.is_member && !['members', 'board'].includes(tab)) tab = 'members';
    if (tab === 'chat') queueMicrotask(afterChat);
  }
  load();
  let t;
  $effect(() => on('guild', () => { clearTimeout(t); t = setTimeout(() => { if (!(draft || Object.values(cdraft).some(Boolean))) load(); }, 600); })); // ce qu'on tape n'est pas écrasé

  function afterChat() {
    if (chatEl) chatEl.scrollTop = chatEl.scrollHeight;
    const gc = app.rewards && app.rewards.guild_chat;
    if (gc && g && g.id === gc.guild && gc.last > gc.seen) { gc.seen = gc.last; call('guild_chat_seen'); }
  }
  $effect(() => { if (tab === 'chat' && g) queueMicrotask(afterChat); });

  const tabs = $derived(g ? (g.is_member ? [['feed', 'Le fil', g.feed.length || null], ['chat', 'Tchat'], ['members', 'Membres']] : [['members', 'Membres']])
    .concat(g.is_manager ? [['apply', 'Demandes', g.applications.length || null]] : []).concat([['board', 'Guildes']]) : []);
  const act = (action, arg, text, okMsg, after = load) => run(() => call('guild_action', action, arg, text), (r) => { if (okMsg) toast(typeof okMsg === 'function' ? okMsg(r) : okMsg, 'good'); return after(r); });
  const tint = (x) => (x && x.color ? `--g:${x.color}` : '');
  const what = (f) => (f.card.shiny ? 'une carte chromatique' : `une ${(app.names[f.card.rarity] || f.card.rarity).toLowerCase()}`);
  const toggleOpen = (id) => (open = open.includes(id) ? open.filter((x) => x !== id) : [...open, id]);
  async function sendChat(text, clear) { sending = true; const r = await act('chat', null, text); sending = false; if (r) { clear(); } }
  async function sendComment(f, text, clear) { const r = await act('comment', f.id, text); if (r) clear(); }
  const like = (f) => run(() => call('guild_action', 'like', f.id), (r) => { f.liked = r.liked; f.likes = Math.max(0, f.likes + (r.liked ? 1 : -1)); g = { ...g }; });
  const found = () => act('create', form, null, 'Ta guilde est fondée !', () => { create = false; view = null; load(); });
</script>

{#if err}<Empty title="Guildes indisponibles" text={err} />
{:else if !list}<div class="skeleton" style="height:240px"></div>
{:else if !g}
  <p class="muted intro">Une guilde vaut ce que valent les collections de ses membres : quand l'un d'eux sort une grosse carte, toute la guilde monte avec lui. Le fil et le tchat ne se lisent que de l'intérieur.</p>
  {#if !list.mine}<button class="btn primary block" style="margin-bottom:16px" onclick={() => (create = true)}><Icon name="plus" />Fonder une guilde</button>{/if}
  <div class="list">
    {#each list.guilds as x}
      <div class="item">
        <span class="gtag sm" style={tint(x)}>{x.tag}</span>
        <div class="tx"><button class="nm serif" onclick={() => { view = x.id; tab = 'members'; load(); }}>{x.name}</button><small class="muted">#{x.rank} · {plural(x.members, 'membre')} · {fmt(x.score)} pts{x.descr ? ' · ' + x.descr : ''}</small></div>
        {#if !list.mine}{#if x.applied}<ConfirmButton small variant="ghost" label="Demandée" confirm="Annuler" onconfirm={() => act('apply/cancel', x.id, null, 'Demande annulée.')} />
          {:else}<ConfirmButton small variant="primary" label="Rejoindre" onconfirm={() => act('apply', x.id, null, 'Demande envoyée au chef de la guilde.')} />{/if}{/if}
      </div>
    {:else}<Empty title="Aucune guilde pour l'instant" text="Sois le premier à en fonder une." />{/each}
  </div>
  <Sheet open={create} onclose={() => (create = false)} title="Fonder une guilde">
    <div class="form"><label>Nom<input class="field" maxlength="30" placeholder="Les Encyclopédistes" bind:value={form.name} /></label>
      <label>Blason (2 à 5 lettres)<input class="field upper" maxlength="5" placeholder="WIKI" bind:value={form.tag} /></label>
      <label>Description<textarea class="field" rows="3" maxlength="200" placeholder="Ce qui rassemble ta guilde" bind:value={form.descr}></textarea></label>
      <ConfirmButton variant="primary" block label="Fonder la guilde" confirm={() => `Confirmer : fonder « ${form.name.trim()} »`} check={() => (form.name.trim().length < 2 || !/^[a-z0-9]{2,5}$/i.test(form.tag.trim()) ? 'Donne un nom (2 caractères au moins) et un blason de 2 à 5 lettres ou chiffres.' : '')} onconfirm={found} /></div>
  </Sheet>
{:else}
  <header class="head">
    <span class="gtag" style={tint(g)}>{g.tag}</span>
    <div><h2 class="serif">{g.name}</h2><p class="muted">{g.descr || 'Pas de description.'}</p></div>
  </header>
  <div class="stats">
    <div class="st"><b class="serif num">#{g.rank || '—'}</b><span>sur {plural(g.count, 'guilde')}</span></div>
    <div class="st"><b class="serif num">{fmt(g.score)}</b><span>points</span></div>
    <div class="st"><b class="serif num">{g.members.length}<small> / {g.max_members}</small></b><span>membres</span></div>
    <div class="st"><b class="serif">{g.leader || '—'}</b><span>chef</span></div>
  </div>
  <div class="acts">
    {#if view && view !== list.mine}<button class="btn small ghost" onclick={() => { view = null; g = null; load(); }}><Icon name="back" />Toutes les guildes</button>{/if}
    {#if !g.is_member && !list.mine}{#if g.applied}<ConfirmButton small variant="ghost" label="Demandée · annuler" confirm="Confirmer" onconfirm={() => act('apply/cancel', g.id, null, 'Demande annulée.')} />{:else}<ConfirmButton small variant="primary" label="Demander à rejoindre" onconfirm={() => act('apply', g.id, null, 'Demande envoyée.')} />{/if}{/if}
    {#if g.is_member}<ConfirmButton small variant="ghost" label="Quitter la guilde" confirm="Confirmer : quitter" onconfirm={() => run(() => call('guild_action', 'leave'), (r) => { toast(r.dissolved ? 'Tu étais le dernier membre : la guilde est dissoute.' : 'Tu as quitté la guilde.', 'good'); view = null; g = null; load(); })} />{/if}
  </div>
  <Seg items={tabs} value={tab} onchange={(k) => (tab = k)} />

  <div class="tab">
    {#if tab === 'feed'}
      {#each g.feed as f (f.id)}
        <article class="gf">
          <div class="fc"><Card card={f.card} onclick={() => openCard(f.card)} /></div>
          <div class="fb">
            <p class="ft"><button class="nm serif" onclick={() => go(`/player/${f.name}`)}>{f.name}</button> a sorti <b style:color={color(f.card.rarity)}>{what(f)}</b></p>
            <p class="muted fs">« {f.card.name} » · {ago(f.ts, nowSrv())}</p>
            <div class="fa"><button class="pact" class:on={f.liked} aria-label="J'aime" onclick={() => like(f)}><Icon name="heart" />{f.likes}</button>
              <button class="pact" class:on={open.includes(f.id)} onclick={() => toggleOpen(f.id)}><Icon name="chat" />{f.comments.length}</button><span class="sp"></span><span class="pts">+{fmt(f.points)} pts</span></div>
            {#if open.includes(f.id)}
              <div class="gcom">{#each f.comments as c}<div class="cm"><button class="nm serif" onclick={() => go(`/player/${c.name}`)}>{c.name}</button> {c.text}<small class="muted"> · {ago(c.ts, nowSrv())}</small>
                {#if c.can_delete}<ConfirmButton small variant="ghost" label="Supprimer" confirm="Confirmer" onconfirm={() => act('comment/delete', c.id)} />{/if}</div>{/each}
                <SendBox placeholder="Féliciter, commenter…" max={400} bind:value={cdraft[f.id]} onsend={(t, clear) => sendComment(f, t, clear)} /></div>
            {/if}
          </div>
        </article>
      {:else}<Empty title="Rien d'exceptionnel pour l'instant" text="Dès qu'un membre tire une légendaire, une mythique ou une carte chromatique, elle s'affiche ici." />{/each}
    {:else if tab === 'chat'}
      <div class="chat" bind:this={chatEl}>
        {#each g.chat as m (m.id)}{@const mine = app.me && m.uid === app.me.id}<div class="bub" class:mine>{#if !mine}<b>{m.name}</b>{/if}<span>{m.text}</span><small>{ago(m.ts, nowSrv())}</small></div>
        {:else}<p class="muted center">Personne n'a encore parlé ici. Lance la discussion.</p>{/each}
      </div>
      <div class="foot"><SendBox placeholder="Écris à ta guilde…" max={400} busy={sending} bind:value={draft} onsend={sendChat} /></div>
    {:else if tab === 'members'}
      <div class="list">
        {#each g.members as m, i}
          <div class="item" class:me={m.me}>
            <span class="rk serif">{i + 1}</span><Avatar name={m.name} size={34} />
            <div class="tx"><button class="nm serif" onclick={() => go(`/player/${m.name}`)}>{m.name}</button>{#if m.leader}<span class="pill gold">Chef</span>{:else if m.officer}<span class="pill">Officier</span>{/if}
              <small class="muted">{fmt(m.total)} pts{m.joined ? ` · membre ${ago(m.joined, nowSrv())}` : ''}</small></div>
            {#if g.is_leader && !m.me}<ConfirmButton small variant="ghost" label={m.officer ? 'Retirer officier' : 'Officier'} confirm="Confirmer" onconfirm={() => act('officier', m.name, !m.officer)} />{/if}
            {#if g.is_manager && !m.me && !m.leader && (g.is_leader || !m.officer)}<ConfirmButton small variant="ghost" label="Exclure" confirm="Confirmer l'exclusion" onconfirm={() => act('kick', m.name)} />{/if}
          </div>
        {/each}
      </div>
    {:else if tab === 'apply'}
      {#each g.applications as a}<div class="item"><Avatar name={a.name} size={34} /><div class="tx"><button class="nm serif" onclick={() => go(`/player/${a.name}`)}>{a.name}</button><small class="muted">a demandé {ago(a.created, nowSrv())}</small></div>
        <ConfirmButton small variant="primary" label="Accepter" onconfirm={() => act('apply/accept', a.name, null, `${a.name} rejoint la guilde !`)} /><ConfirmButton small variant="ghost" label="Refuser" confirm="Confirmer" onconfirm={() => act('apply/decline', a.name, null, 'Demande refusée.')} /></div>
      {:else}<Empty title="Aucune demande en attente" text="Quand un joueur demande à rejoindre ta guilde, il apparaît ici." />{/each}
    {:else}
      <div class="list">{#each list.guilds as x}<div class="item" class:me={x.id === list.mine}><span class="gtag sm" style={tint(x)}>{x.tag}</span><div class="tx"><button class="nm serif" onclick={() => { view = x.id; tab = 'members'; load(); }}>{x.name}</button><small class="muted">#{x.rank} · {plural(x.members, 'membre')} · {fmt(x.score)} pts</small></div></div>{/each}</div>
    {/if}
  </div>
{/if}

<style>
  .intro { font-size: 14px; margin-bottom: 14px; }
  .gtag { flex: none; display: inline-grid; place-items: center; min-width: 60px; height: 60px; padding: 0 10px; border-radius: 16px; font: 700 17px var(--sans); letter-spacing: .06em; color: #fff; text-shadow: 0 1px 4px rgba(0, 0, 0, .4);
    background: linear-gradient(160deg, color-mix(in srgb, var(--g, #8b5cf6) 90%, #fff), var(--g, #8b5cf6) 55%, color-mix(in srgb, var(--g, #8b5cf6) 70%, #000)); box-shadow: inset 0 1px 0 rgba(255, 255, 255, .35), 0 12px 28px -12px var(--g, #8b5cf6); }
  .gtag.sm { min-width: 46px; height: 32px; border-radius: 9px; font-size: 12px; }
  .head { display: flex; gap: 14px; align-items: center; padding: 16px; border-radius: var(--rad-xl); background: rgba(255, 255, 255, .02); border: 1px solid var(--line); } .head h2 { font-size: 24px; line-height: 1.1; } .head p { font-size: 13.5px; }
  .stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 10px 0; }
  .st { display: grid; padding: 12px; background: rgba(255, 255, 255, .03); border: 1px solid var(--line); border-radius: var(--rad-m); } .st b { font-size: 20px; font-weight: 500; overflow-wrap: anywhere; } .st small { font-size: 13px; color: var(--muted); } .st span { font-size: 12px; color: var(--muted); }
  .acts { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; } .acts:empty { display: none; }
  .tab { margin-top: 14px; display: grid; gap: 10px; }
  .tx { display: grid; flex: 1; min-width: 0; } .nm { padding: 0; background: none; border: 0; color: var(--text); font-size: 16px; font-weight: 600; cursor: pointer; text-align: left; overflow-wrap: anywhere; } .tx small { font-size: 12.5px; }
  .item { flex-wrap: wrap; } .item.me { background: linear-gradient(90deg, rgba(241, 232, 212, .08), transparent 70%); border-color: rgba(241, 232, 212, .2); } .rk { width: 22px; color: var(--muted); font-size: 18px; text-align: center; }
  .gf { display: flex; gap: 14px; padding: 14px; background: rgba(255, 255, 255, .02); border: 1px solid var(--line); border-radius: var(--rad-l); } .fc { flex: none; width: 96px; } .fb { flex: 1; min-width: 0; display: grid; gap: 5px; align-content: start; }
  .ft { font: 500 16px/1.35 var(--serif); } .fs { font-size: 12.5px; } .fa { display: flex; align-items: center; gap: 8px; margin-top: 2px; } .pts { color: var(--gold); font: 600 14px var(--serif); }
  .pact { display: inline-flex; align-items: center; gap: 6px; min-height: 34px; padding: 0 12px; color: var(--muted); font: 500 13px var(--sans); cursor: pointer; background: rgba(255, 255, 255, .03); border: 1px solid var(--line); border-radius: 99px; }
  .pact.on { color: #ff8da6; border-color: rgba(255, 110, 150, .4); background: rgba(255, 110, 150, .08); } .pact.on :global(.i) { fill: currentColor; }
  .gcom { display: grid; gap: 8px; margin-top: 6px; padding-top: 10px; border-top: 1px solid var(--line); } .cm { font-size: 14px; } .cm .nm { font-size: 14px; }
  .chat { display: flex; flex-direction: column; gap: 6px; min-height: 280px; max-height: 52dvh; overflow-y: auto; padding: 4px 0; }
  .bub { align-self: flex-start; max-width: 84%; padding: 8px 13px; overflow-wrap: anywhere; line-height: 1.4; background: var(--ink-3); border: 1px solid var(--line); border-radius: 16px 16px 16px 5px; }
  .bub b { display: block; font: 600 12.5px var(--sans); color: var(--gold); } .bub small { display: block; font-size: 11px; opacity: .55; margin-top: 2px; }
  .bub.mine { align-self: flex-end; color: var(--on-ivory); background: linear-gradient(180deg, #f8f0de, var(--ivory)); border-color: transparent; border-radius: 16px 16px 5px 16px; }
  .foot { position: sticky; bottom: calc(var(--nav) + var(--sab) + 8px); padding: 8px 0; background: linear-gradient(transparent, var(--ink) 30%); }
  .form { display: grid; gap: 14px; padding-top: 6px; } .form label { display: grid; gap: 6px; font-size: 13px; color: var(--muted); } .upper { text-transform: uppercase; }
  @media (min-width: 700px) { .stats { grid-template-columns: repeat(4, 1fr); } .fc { width: 120px; } }
  @media (min-width: 980px) { .foot { bottom: 8px; } }
</style>
