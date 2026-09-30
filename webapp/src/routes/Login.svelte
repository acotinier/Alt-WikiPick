<script>
  import { auth } from '../lib/api.js';
  import { enter } from '../lib/store.svelte.js';
  import Challenge from '../ui/Challenge.svelte';

  let login = $state(''), password = $state(''), step = $state('form'), error = $state(''), busy = $state(false), ch = $state(null);

  async function ask(e) {
    e?.preventDefault();
    if (!login.trim() || !password) return;
    busy = true; error = '';
    const r = await auth.challenge();
    busy = false;
    if (!r.ok) { error = r.error || 'Le site ne répond pas : réessaie.'; return; }
    ch = r; step = 'challenge';
  }
  async function answer(rep) {
    busy = true;
    const r = await auth.login({ pending: ch.pending, login: login.trim(), password, defi: ch.challenge.id, rep });
    busy = false;
    if (r.ok) { password = ''; await enter(r.name); return; }
    error = r.error || 'Connexion impossible.';
    step = 'form'; // une nouvelle question est demandée au prochain essai
  }
</script>

<main>
  <div class="art" aria-hidden="true"><i class="a"></i><i class="b"></i><i class="c"></i></div>
  <section class="card">
    <p class="eyebrow">L'encyclopédie, à collectionner</p>
    <h1 class="serif">Alt<span>·</span>WikiPick</h1>
    {#if step === 'form'}
      <p class="lead">Un client léger et rapide pour <b>wiki-pick.com</b>. Connecte-toi avec ton compte du jeu.</p>
      <form onsubmit={ask}>
        <label>Pseudo ou adresse e-mail<input class="field" bind:value={login} autocomplete="username" autocapitalize="off" spellcheck="false" required /></label>
        <label>Mot de passe<input class="field" type="password" bind:value={password} autocomplete="current-password" required /></label>
        {#if error}<p class="err" role="alert">{error}</p>{/if}
        <button class="btn primary big block" disabled={busy || !login.trim() || !password}>{busy ? 'Un instant…' : 'Se connecter'}</button>
      </form>
      <p class="fine">Tes identifiants sont transmis <b>une seule fois</b> à wiki-pick.com par cette instance, qui n'en garde rien : seule la session est conservée, chiffrée. Héberger sa propre instance, c'est garder la main dessus.</p>
    {:else}
      <p class="lead">Une dernière vérification, demandée par le site.</p>
      <Challenge challenge={ch.challenge} {busy} onanswer={answer} onother={ask} oncancel={() => (step = 'form')} />
    {/if}
  </section>
</main>

<style>
  main { min-height: 100dvh; display: grid; place-items: center; padding: calc(var(--sat) + 24px) 20px calc(var(--sab) + 24px); position: relative; overflow: hidden; }
  .art { position: absolute; inset: 0; pointer-events: none; opacity: .5; }
  .art i { position: absolute; width: 160px; aspect-ratio: 5 / 7; border-radius: 14px; border: 1px solid; filter: blur(.3px); }
  .a { top: 6%; left: -40px; transform: rotate(-16deg); border-color: var(--r-R); box-shadow: 0 0 60px -20px var(--r-R); background: linear-gradient(160deg, #1b2c52, #0c1730); }
  .b { top: 10%; right: -50px; transform: rotate(14deg); border-color: var(--r-L); box-shadow: 0 0 60px -20px var(--r-L); background: linear-gradient(160deg, #1b2c52, #0c1730); }
  .c { bottom: 4%; left: 30%; transform: rotate(8deg); border-color: var(--r-SR); box-shadow: 0 0 60px -20px var(--r-SR); background: linear-gradient(160deg, #1b2c52, #0c1730); }
  .card { position: relative; width: min(420px, 100%); display: grid; gap: 16px; padding: 28px 24px; background: var(--glass); backdrop-filter: blur(20px); border-radius: var(--rad-xl); box-shadow: var(--sh-3); animation: rise .6s var(--ease); }
  h1 { font-size: 46px; line-height: 1; letter-spacing: -.03em; }
  h1 span { color: var(--gold); }
  .lead { color: var(--muted); }
  form { display: grid; gap: 14px; }
  label { display: grid; gap: 6px; font-size: 13px; color: var(--muted); }
  .err { color: #ff8d97; font-size: 14px; }
  .fine { font-size: 12.5px; color: var(--faint); line-height: 1.5; }
  .fine b { color: var(--muted); font-weight: 600; }
</style>
