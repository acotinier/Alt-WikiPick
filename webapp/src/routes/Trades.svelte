<script>
  // Les échanges entre amis : reçues, envoyées, historique. Accepter, refuser, annuler, contre-proposer : chaque action se confirme.
  import { call } from '../lib/api.js';
  import { ago, fmt, plural } from '../lib/format.js';
  import { collectionChanged, nowSrv, on, openCard, openTrade, refreshMeSoon, run, setSkew, toast } from '../lib/store.svelte.js';
  import Card from '../ui/Card.svelte';
  import ConfirmButton from '../ui/ConfirmButton.svelte';
  import Empty from '../ui/Empty.svelte';
  import Icon from '../ui/Icon.svelte';
  import Seg from '../ui/Seg.svelte';
  import Sheet from '../ui/Sheet.svelte';

  const STATUS = { pending: 'En attente', accepted: 'Accepté', declined: 'Refusé', cancelled: 'Annulé', invalid: 'Annulé : cartes indisponibles', countered: 'Remplacé par une contre-proposition' };
  const EMPTY = { received: 'Aucune proposition reçue. Quand un joueur te propose un échange, il apparaît ici.', sent: 'Aucune proposition en attente.', history: 'Aucun échange terminé.' };
  let box = $state('received'), trades = $state.raw([]), loading = $state(true), seq = 0, pick = $state(false), friends = $state([]);

  async function load() {
    const mine = ++seq;
    const r = await call('load_trades', box);
    if (mine !== seq) return;
    loading = false;
    if (!r.ok) { toast(r.error || 'Échanges indisponibles', 'error'); return; }
    setSkew(r.now); trades = r.trades;
  }
  $effect(() => { box; loading = true; load(); });
  $effect(() => on('trade', () => load()));
  $effect(() => { const h = (e) => { box = e.detail; }; addEventListener('altwp:trades-changed', h); return () => removeEventListener('altwp:trades-changed', h); });

  const after = (msg) => () => { toast(msg, 'good'); collectionChanged(); refreshMeSoon(); load(); };
  const accept = (t) => run(() => call('trade_action', 'accept', t.id), after('Échange conclu : les cartes ont changé de main.'));
  const decline = (t) => run(() => call('trade_action', 'decline', t.id), after('Proposition refusée.'));
  const cancel = (t) => run(() => call('trade_action', 'cancel', t.id), after('Proposition annulée.'));
  const summary = (t) => `Proposition de ${t.other} : tu donnes ${plural(t.give.length, 'carte')}${t.give_coins ? ` et ${fmt(t.give_coins)} Wikiki` : ''}, tu reçois ${plural(t.get.length, 'carte')}${t.get_coins ? ` et ${fmt(t.get_coins)} Wikiki` : ''}.`;
  async function newTrade() { const r = await call('friends_get'); if (r.ok) { friends = r.friends; pick = true; } else toast(r.error || "Liste d'amis indisponible", 'error'); }
</script>

<div class="top"><Seg items={[['received', 'Reçues'], ['sent', 'Envoyées'], ['history', 'Historique']]} value={box} onchange={(b) => (box = b)} />
  <button class="btn primary small" onclick={newTrade}><Icon name="plus" />Nouvel échange</button></div>
<p class="muted fine">Les échanges se font entre amis. Chaque action demande une confirmation.</p>

{#if loading && !trades.length}<div class="skeleton" style="height:200px"></div>
{:else if !trades.length}<Empty title="Aucun échange" text={EMPTY[box]} />
{:else}
  <div class="list">
    {#each trades as t (t.id)}
      <article class="trade">
        <header><div><b class="serif">{t.incoming ? `${t.other} te propose un échange` : `Ta proposition à ${t.other}`}</b><small class="muted">{ago(t.created, nowSrv())}{t.closed ? `, terminé ${ago(t.closed, nowSrv())}` : ''}</small></div>
          {#if STATUS[t.status]}<span class="pill st {t.status}">{STATUS[t.status]}</span>{/if}</header>
        {#if t.message}<p class="msg serif">« {t.message} »</p>{/if}
        {#if !t.valid}<p class="warn">Une des cartes n'est plus disponible : cet échange ne peut plus être conclu.</p>{/if}
        <div class="cols">
          {#each [['Tu donnes', t.give, t.give_coins], ['Tu reçois', t.get, t.get_coins]] as [title, cards, coins], k}
            {#if k}<span class="swap"><Icon name="swap" /></span>{/if}
            <div class="col"><h3 class="eyebrow">{title}</h3>
              <div class="cards">{#each cards as c}<div class="c"><Card card={c} mini onclick={() => openCard(c)} /></div>{:else}{#if !coins}<small class="muted">Rien</small>{/if}{/each}</div>
              {#if coins}<span class="price serif"><Icon name="coin" />{fmt(coins)}</span>{/if}</div>
          {/each}
        </div>
        {#if t.status === 'pending'}
          <div class="row">
            {#if t.incoming}
              <ConfirmButton variant="primary" small label="Accepter l'échange" confirm="Confirmer l'échange" disabled={!t.valid} onconfirm={() => accept(t)} />
              <button class="btn small" onclick={() => openTrade(t.other, t.id, summary(t))}>Contre-proposer</button>
              <ConfirmButton variant="danger" small label="Refuser" confirm="Confirmer le refus" onconfirm={() => decline(t)} />
            {:else}<ConfirmButton variant="danger" small label="Annuler ma proposition" confirm="Confirmer l'annulation" onconfirm={() => cancel(t)} />{/if}
          </div>
        {/if}
      </article>
    {/each}
  </div>
{/if}

<Sheet open={pick} onclose={() => (pick = false)} title="Échanger avec qui ?">
  {#if !friends.length}<Empty title="Pas encore d'amis" text="Les échanges se font entre amis : ajoute-en depuis l'onglet Amis." />
  {:else}<div class="list">{#each friends as f}<button class="item fr" onclick={() => { pick = false; openTrade(f.name); }}><b class="serif">{f.name}</b>{#if f.fav}<small class="muted">favori</small>{/if}</button>{/each}</div>{/if}
</Sheet>

<style>
  .top { display: flex; gap: 10px; align-items: center; justify-content: space-between; flex-wrap: wrap; } .top :global(.seg) { flex: 1; }
  .fine { font-size: 12.5px; margin: 10px 2px 14px; }
  .trade { display: grid; gap: 12px; padding: 16px; background: linear-gradient(180deg, rgba(255, 255, 255, .03), rgba(255, 255, 255, .01)); border: 1px solid var(--line); border-radius: var(--rad-xl); }
  header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; } header b { font-size: 18px; display: block; } header small { font-size: 12.5px; }
  .st.pending { color: var(--ivory); border-color: rgba(241, 232, 212, .35); } .st.accepted { color: var(--good); border-color: color-mix(in srgb, var(--good) 45%, transparent); }
  .st.declined, .st.cancelled, .st.invalid { color: #ff8d97; border-color: color-mix(in srgb, var(--bad) 40%, transparent); }
  .msg { font-size: 17px; font-style: italic; color: #cfd5df; }
  .warn { padding: 9px 14px; border-left: 3px solid var(--warn); background: color-mix(in srgb, var(--warn) 8%, transparent); border-radius: 0 8px 8px 0; }
  .cols { display: flex; flex-wrap: wrap; gap: 14px 22px; align-items: flex-start; }
  .col h3 { margin-bottom: 8px; } .cards { display: flex; flex-wrap: wrap; gap: 7px; } .c { width: 54px; }
  .swap { align-self: center; display: grid; place-items: center; width: 36px; height: 36px; border: 1px solid var(--line); border-radius: 50%; color: var(--muted); }
  .price { display: inline-flex; align-items: center; gap: 6px; margin-top: 8px; font-size: 18px; font-weight: 600; } .price :global(.i) { color: var(--gold); font-size: 14px; }
  .fr { width: 100%; justify-content: space-between; cursor: pointer; font: inherit; color: inherit; text-align: left; } .fr b { font-size: 17px; }
</style>
