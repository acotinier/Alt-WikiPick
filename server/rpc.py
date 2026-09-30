"""Ce que l'interface web a le droit d'appeler : les méthodes publiques de `Service`, une par une.

Règle : toute nouvelle méthode publique de `Service` doit être rangée ici, soit dans ALLOWED (appelable depuis le
navigateur), soit dans DENIED (réservée au serveur ou au bureau). `test_server.py` échoue sinon : on ne publie jamais
une méthode sans l'avoir décidé."""

ALLOWED = frozenset("""
load_me load_collection cache_get
open_pack open_gold_pack pack_challenge pack_history pack_seen
prefs_get prefs_set watch_get watch_set
load_notifications read_notifications load_market stream_watch_market load_card load_trades load_ranking
actions_get auction_get bid auction_create auction_cancel auction_price trade_action trade_send
recycle corbeille_get corbeille_restore corbeille_empty card_lock card_for_sale wish_set
friends_get user_cards pro_market
combat_info combat_state combat_decks combat_deck_save combat_deck_delete combat_challenge combat_answer
combat_choice combat_team combat_cancel combat_chest users_search
conversations_get thread_get message_send friends_list players_search friend_action friend_favorite
profile_get player_cards guilds_get guild_get guild_chat_seen guild_action achievements_get claim
""".split())

DENIED = frozenset("""
start_stream stop_stream poll_events logout ensure_me export_collection
""".split())
# start/stop/poll : le serveur gère lui-même le flux (voir /api/events). logout : /api/auth/logout.
# export_collection écrit un fichier local : le web utilise /api/export.csv.
