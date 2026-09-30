// Y a-t-il quelque chose à réclamer ? (série du jour, quête accomplie, bienvenue, succès) : pour la pastille du menu.
export function rewardsReady(app) {
  const rw = app.rewards || {}, me = app.me || {};
  return !!((rw.streak && rw.streak.ready)
    || (rw.quests || []).some((q) => q.finished && !q.claimed && !q.locked)
    || (rw.welcome || []).some((w) => w.finished && !w.claimed)
    || me.succes > 0);
}
