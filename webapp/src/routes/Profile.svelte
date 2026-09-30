<script>
  // Ton profil, ou celui d'un joueur (#/player/<pseudo>) : ses statistiques, sa guilde, ses vitrines et sa collection (réservée aux amis).
  import { call } from '../lib/api.js';
  import { fmt, plural } from '../lib/format.js';
  import { go, route } from '../lib/router.svelte.js';
  import { app, collectionChanged, openCard, openTrade, refreshMeSoon, run, toast } from '../lib/store.svelte.js';
  import Avatar from '../ui/Avatar.svelte';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import FriendActions from '../ui/FriendActions.svelte';
  import Icon from '../ui/Icon.svelte';

  const name = $derived(route.parts[0] === 'player' ? route.parts[1] : null);
  let p = $state(null), err = $state(''), cards = $state.raw([]), page = $state(0), pages = $state(1), total = $state(0), q = $state(''), order = $state(''), loadingCards = $state(false), seq = 0, cseq = 0;

  async function load() {
    const n = name, mine = ++seq;
    p = null; err = '';
    const r = await call('profile_get', n);
    if (mine !== seq) return;
    if (!r.ok) { err = r.error || 'Profil introuvable'; return; }
    p = r.profile; page = 0; q = '';
    if (p.me || p.relation === 'friends') loadCards();
  }
  async function loadCards() {
    if (!p) return;
    const mine = ++cseq; loadingCards = true;
    const r = await call('player_cards', p.name, page, q, [], order);
    if (mine !== cseq) return;
    loadingCards = false;
    if (r.ok) { cards = r.cards; page = r.page; pages = r.pages; total = r.total; }
  }
  $effect(() => { name; load(); });
  let t;
  const search = () => { clearTimeout(t); t = setTimeout(() => { page = 0; loadCards(); }, 280); };
  const go_page = (d) => { page += d; loadCards(); scrollTo({ top: 0, behavior: 'smooth' }); };

  const friendish = $derived(p && (p.me || p.relation === 'friends'));
  const since = $derived(p && p.created ? new Date(p.created * 1000).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' }) : '');
  const block = (on) => run(() => call('friend_action', on ? 'block' : 'unblock', p.name), () => { toast(on ? `${p.name} est bloqué(e).` : `${p.name} est débloqué(e).`, 'good'); refreshMeSoon(); load(); });
  const remove = () => run(() => call('friend_action', 'remove', p.name), () => { toast(`${p.name} ne fait plus partie de tes ami(e)s.`, 'good'); refreshMeSoon(); load(); });
</script>

{#if err}<Empty title="Profil introuvable" text={err} />
{:else if !p}<div class="skeleton" style="height:220px"></div>
{:else if p.blocked === 'moi'}
  <Empty title={`Tu as bloqué ${p.name}`} text="Vous ne vous voyez plus sur le site : ni ses messages, ni son profil." />
  <div class="row center"><button class="btn small" onclick={() => block(false)}>Débloquer</button></div>
{:else}
  <section class="head">
    <Avatar name={p.name} url={p.avatar} size={84} />
    <div class="id"><h2 class="serif">{p.name}{#if p.relation === 'incoming'}<span class="pill">Veut être ton ami(e)</span>{/if}</h2>
      <p class="muted">{since ? `Membre depuis le ${since}` : ''}{#if p.guild} · guilde <button class="link" onclick={() => go('/social/guild')}>[{p.guild.tag}] {p.guild.name}</button>{/if}</p>
      {#if p.bio}<p class="bio serif">{p.bio}</p>{/if}</div>
  </section>
  {#if !p.me}
    <div class="acts">
      {#if p.relation === 'friends'}<button class="btn primary small" onclick={() => openTrade(p.name)}><Icon name="swap" />Échanger</button>{:else}<FriendActions name={p.name} relation={p.relation} ondone={load} />{/if}
      <button class="btn small" onclick={() => go(`/social/messages/${p.name}`)}><Icon name="chat" />Message</button>
      {#if p.relation === 'friends'}<ConfirmButton small variant="ghost" label="Retirer" confirm="Confirmer le retrait" onconfirm={remove} />{/if}
      <ConfirmButton small variant="ghost" label="Bloquer" confirm="Confirmer le blocage" onconfirm={() => block(true)} />
    </div>
  {/if}

  <div class="stats">
    <div class="st hero"><b class="serif num">{p.rank ? `#${fmt(p.rank.rank)}` : '—'}</b><span>{p.rank ? `sur ${fmt(p.rank.total)}` : 'classement'}</span></div>
    <div class="st"><b class="serif num">{fmt(p.rank ? p.rank.points : 0)}</b><span>points</span></div>
    <div class="st"><b class="serif num">{fmt(p.stats.cards)}</b><span>cartes</span></div>
    <div class="st"><b class="serif num">{fmt(p.stats.distinct)}</b><span>différentes</span></div>
    <div class="st legend"><b class="serif num">{fmt(p.stats.legend)}</b><span>légendaires</span></div>
    <div class="st"><b class="serif num">{fmt(p.stats.sales)}</b><span>ventes</span></div>
    <div class="st"><b class="serif num">{fmt(p.friends)}</b><span>ami(e)s</span></div>
  </div>

  <h2 class="sec">Vitrines</h2>
  {#if p.private_showcases}<p class="muted">Ajoute {p.name} en ami(e) pour voir ses vitrines.</p>
  {:else if !p.showcases.length}<p class="muted">{p.me ? "Tu n'as pas encore de vitrine : elles se créent sur wiki-pick.com, dans ton profil." : `${p.name} n'expose encore aucune carte.`}</p>
  {:else}{#each p.showcases as v}<section class="vit"><header><b class="serif">{v.name}</b><small class="muted">{v.cards.length} / {p.slots}</small></header>
    <div class="vgrid">{#each v.cards as c}<Card card={c} onclick={() => openCard(c)} />{/each}</div></section>{/each}{/if}

  <div class="chead"><h2 class="sec">{p.me ? 'Ma collection' : 'Sa collection'}</h2>{#if friendish && total}<small class="muted">{plural(total, 'carte différente', 'cartes différentes')}</small>{/if}</div>
  {#if !friendish}<Empty title="Collection réservée aux ami(e)s" text={`Ajoute ${p.name} en ami(e) pour voir toute sa collection et lui proposer des échanges.`} />
  {:else}
    <div class="tools"><label class="search"><Icon name="search" /><input type="search" placeholder="Chercher une carte…" bind:value={q} oninput={search} /></label>
      <select aria-label="Ordre" bind:value={order} onchange={() => { page = 0; loadCards(); }}><option value="">Plus rares d'abord</option><option value="asc">Plus communes d'abord</option></select></div>
    <div class="grid" class:dim={loadingCards}>
      {#each cards as x (x.card.cid + (x.card.shiny ? '*' : ''))}<Card card={{ ...x.card, copies: x.n }} onclick={() => openCard(x.card)} />{:else}{#if !loadingCards}<Empty title="Aucune carte" text={q ? 'Aucune carte ne correspond.' : "Rien n'a encore été collectionné."} />{/if}{/each}
    </div>
    {#if pages > 1}<div class="pager"><button class="btn small" disabled={page <= 0} onclick={() => go_page(-1)}>← Précédent</button><span class="muted num">Page {page + 1} / {fmt(pages)}</span><button class="btn small" disabled={page >= pages - 1} onclick={() => go_page(1)}>Suivant →</button></div>{/if}
  {/if}
{/if}

<style>
  .head { display: flex; gap: 16px; align-items: center; padding: 18px; border-radius: var(--rad-xl); background: radial-gradient(80% 140% at 0% 0%, rgba(120, 150, 230, .10), transparent 60%), rgba(255, 255, 255, .02); border: 1px solid var(--line); }
  .id { min-width: 0; display: grid; gap: 3px; } h2 { font-size: 26px; line-height: 1.1; overflow-wrap: anywhere; } h2 .pill { margin-left: 8px; vertical-align: middle; }
  .bio { font-size: 16px; font-style: italic; color: #d7dce5; margin-top: 4px; white-space: pre-wrap; }
  .link { padding: 0; background: none; border: 0; color: var(--text); font-weight: 600; text-decoration: underline; text-underline-offset: 3px; cursor: pointer; }
  .acts { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
  .st { display: grid; padding: 12px; background: linear-gradient(180deg, rgba(255, 255, 255, .035), rgba(255, 255, 255, .012)); border: 1px solid var(--line); border-radius: var(--rad-m); }
  .st b { font-size: 22px; font-weight: 500; line-height: 1.1; } .st span { font-size: 12px; color: var(--muted); } .st.hero b { color: #fff5dd; } .st.legend b { color: var(--r-L); }
  .vit { margin-bottom: 12px; padding: 14px; background: rgba(255, 255, 255, .02); border: 1px solid var(--line); border-radius: var(--rad-l); }
  .vit header { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; } .vit b { font-size: 17px; }
  .vgrid, .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } .grid.dim { opacity: .45; transition: opacity .2s; }
  .chead { display: flex; align-items: baseline; gap: 12px; }
  .tools { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; } .tools select { width: 190px; }
  .search { flex: 1; min-width: 200px; display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 14px; color: var(--faint); background: var(--ink-2); border: 1px solid var(--line-2); border-radius: 12px; }
  .search input { flex: 1; min-width: 0; background: none; border: 0; outline: 0; color: var(--text); font: 16px var(--sans); }
  .pager { display: flex; align-items: center; justify-content: center; gap: 14px; margin-top: 20px; }
  @media (min-width: 700px) { .stats { grid-template-columns: repeat(7, 1fr); } .vgrid, .grid { grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 16px; } .head { padding: 24px; gap: 22px; } }
</style>
