<script>
  // Ce qu'on peut faire avec un joueur selon votre relation : demander, accepter, refuser, annuler la demande.
  import { call } from '../lib/api.js';
  import { refreshMeSoon, run, toast } from '../lib/store.svelte.js';
  import ConfirmButton from './ConfirmButton.svelte';
  let { name, relation, ondone = () => {} } = $props();
  const act = (action, ok) => () => run(() => call('friend_action', action, name), (r) => {
    toast(r.relation === 'friends' ? `${name} et toi êtes maintenant ami(e)s !` : ok, 'good'); refreshMeSoon(); ondone(r);
  });
</script>

{#if relation === 'friends'}<span class="pill good">Ami(e)</span>
{:else if relation === 'outgoing'}<ConfirmButton small variant="ghost" label="Demande envoyée · annuler" onconfirm={act('remove', 'Demande annulée.')} />
{:else if relation === 'incoming'}
  <ConfirmButton small variant="primary" label="Accepter" onconfirm={act('accept', 'Demande acceptée.')} />
  <ConfirmButton small variant="ghost" label="Refuser" onconfirm={act('decline', 'Demande refusée.')} />
{:else if relation !== 'self'}<ConfirmButton small variant="primary" label="Ajouter en ami(e)" onconfirm={act('request', `Demande d'ami(e) envoyée à ${name}.`)} />{/if}
