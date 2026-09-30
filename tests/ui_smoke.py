"""Smoke test de l'interface : Chromium (Playwright) + fausse API pywebview.
Usage : pip install playwright && playwright install chromium && python tests/ui_smoke.py
(Pas de vraie fenêtre pywebview ni de réseau : vérifie seulement le rendu et la logique JS.)"""
import json, random, re, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from wikipick.parse import RARITY_ORDER, compute_stats
from playwright.sync_api import sync_playwright

random.seed(1)
names = {"C":"Commune","PC":"Inhabituelle","R":"Rare","SR":"Épique","UR":"Exceptionnelle","L":"Légendaire","M":"Mythique","EXC":"Exclusive"}
weights = [("C",60),("PC",25),("R",8),("SR",4),("UR",2),("L",0.8),("M",0.2)]
cards=[]
for i in range(300):
    r = random.choices([w[0] for w in weights],[w[1] for w in weights])[0]
    copies = random.choice([1,1,1,1,2,3,9])
    cards.append({"cid":f"fr:Carte_{i}","name":f"Carte de test numéro {i} <b>x</b>","desc":"description <img src=x onerror=alert(1)>","img":None,
      "rarity":r,"reads":random.randint(1,20000000),"nl":1,"lang":"fr","locked":i%50==0,"ids":list(range(1000+i*10,1000+i*10+copies)),"free_ids":[] if i%50==0 else list(range(1000+i*10,1000+i*10+copies)),"locked_ids":[],"copies":copies,"tags":[7] if i%5==0 else [],"shiny":i%40==0,"url":f"https://fr.wikipedia.org/wiki/Carte_{i}"})
rarest = names[min({c["rarity"] for c in cards}, key=RARITY_ORDER.index)]
data={"ok":True,"me":{"id":1,"name":"Joueur","coins":1629,"packs":3,"packReserve":3,"packMax":10,"next":423,"avatar":None,"pro":False},
 "rank":{"rank":232,"total":6898,"points":14374,"cards":300,"toNext":15,"nextName":"rival"},
 "tags":[{"id":7,"name":"Acteur","color":"#fff"}],"names":names,"cards":cards,"stats":compute_stats(cards,names)}

stub = """
window.__calls=[]; window.__logged=__LOGGED__; window.__cache=__CACHE__; window.__delay=__DELAY__;
window.__prefs=__PREFS__; window.__packs=[]; window.__watch=[]; window.__actions=[]; window.__bids={}; window.__recycled=[]; window.__bidDelay=0;
window.__events=[]; window.__state='live'; window.__now=Math.floor(Date.now()/1000); window.__notifs=[];
const D = __DATA__;
const INFO = {odds:{M:0.1,L:0.5,UR:2,SR:8,R:30,PC:70,C:100}, bank:{C:1,PC:3,R:10,SR:40,UR:100,L:500,M:2000}, shinyOdds:0.2, perPack:5};
const copy = (o) => JSON.parse(JSON.stringify(o));
const cardOf = (cid, name, r) => ({cid, name, desc:'', img:null, rarity:r, reads:5000, shiny:false, copies:1, locked:false, tags:[], ids:[], url:null, new:false});
const REW = {quests:[{title:'Ouvre 3 paquets',what:'Trois paquets dans la journée',done:1,goal:3,finished:false,claimed:false,locked:false,next:3600,gain:50,packs:false},
  {title:'Mini <b>x</b>',what:'',done:1,goal:1,finished:true,claimed:false,locked:false,next:3600,gain:2,packs:true}],
  welcome:[{code:'b1',title:'Premier paquet',what:'',done:1,goal:1,finished:true,claimed:false,gain:20},{code:'b2',title:'Premier échange',what:'',done:0,goal:1,finished:false,claimed:false,gain:30}],
  streak:{open:true,wait:0,ready:false,day:3,done:2,next:5000,start:0,days:[1,2,3,4,5,6,7].map(n=>({kind:n===7?'carte':n===5?'dore':'wikiki',text:n===7?'Une carte <b>rare</b>':n+'0 Wikiki',n:1,card:n===7?cardOf('fr:S7','Grand prix','L'):null}))},
  guild_chat:{guild:3,last:10,seen:8}};
const auc = (id, over) => Object.assign({id, card:cardOf('fr:E'+id, 'Enchère <b>x</b> '+id, 'SR'), lot:null, price:100+id, min:110+id, bids:2,
  leader:'bob<i>', seller:'eve', mine:false, leading:false, ends_at:window.__now+300, status:'live'}, over||{});
const AUC = () => [auc(11), auc(12, {card:null, lot:{n:3, name:'Lot <u>test</u>', cards:[cardOf('fr:L1','Première du lot','R')]}, ends_at:window.__now+40, leader:'ann'}),
                   auc(13, {mine:true, ends_at:window.__now+10, bids:0, leader:''})];
window.pywebview={api:{
 status:async()=>({logged_in:window.__logged}),
 cache_get:async()=>window.__cache ? {ok:true,data:copy(D)} : {ok:false},
 load_me:async()=>{window.__calls.push('load_me');return {ok:true,me:copy(window.__me||D.me),names:D.names,info:INFO,rewards:copy(window.__rewards||REW)}},
 conversations_get:async()=>{window.__calls.push('conversations');const now=window.__now;return {ok:true,conversations:[{name:'ami <b>x</b>',avatar:null,fav:true,blocked:false,last:'salut <i>toi</i>',mine:false,unread:2,created:now-60},
   {name:'zoé',avatar:null,fav:false,blocked:false,last:'ok',mine:true,unread:0,created:now-3600}]};},
 thread_get:async(n)=>{window.__calls.push('thread:'+n);return {ok:true,thread:{with:n,avatar:null,friend:true,blocked:'',messages:[{id:1,mine:false,text:'Salut <b>toi</b>'},{id:2,mine:true,text:'Coucou'}]}};},
 message_send:async(to,t)=>{window.__calls.push('msg:'+to+':'+t);return {ok:true};},
 friends_list:async()=>({ok:true,friends:[{name:'ami <b>x</b>',avatar:null,fav:true},{name:'zoé',avatar:null,fav:false}],incoming:[{name:'nouveau',avatar:null,fav:false}],outgoing:[{name:'attente',avatar:null,fav:false}]}),
 players_search:async(q)=>{window.__calls.push('players:'+q);return {ok:true,users:[{name:'trouvé <b>x</b>',avatar:null,me:false,relation:''},{name:'Joueur',avatar:null,me:true,relation:''}]};},
 friend_action:async(a,n)=>{window.__calls.push('friend:'+a+':'+n);return {ok:true,relation:a==='accept'?'friends':''};},
 friend_favorite:async(n,on)=>{window.__calls.push('fav:'+n+':'+on);return {ok:true};},
 profile_get:async(n)=>{window.__calls.push('profile:'+(n||''));return {ok:true,profile:{me:!n,blocked:'',name:n||'Joueur',avatar:null,created:1780000000,bio:'Ma bio <b>x</b>',
   stats:{cards:737,distinct:300,legend:1,sales:4},relation:n?'friends':'',friends:3,rank:{rank:232,total:6898,points:14374},guild:{id:3,tag:'WIKI',name:'Encyclo <i>'},
   showcases:[{id:1,name:'Mes <b>belles</b>',cards:[cardOf('fr:V1','Vitrine 1','L')]}],slots:5,max:3,private_showcases:false}};},
 player_cards:async(n,page,q)=>{window.__calls.push('pcards:'+n+':'+page+':'+q);return {ok:true,page,pages:2,total:120,cards:[{card:cardOf('fr:PC'+page,'Sa carte <b>'+page+'</b>','SR'),n:2}]};},
 guilds_get:async()=>{window.__calls.push('guilds');return {ok:true,mine:3,guilds:[{id:3,rank:1,tag:'WIKI',name:'Encyclo <i>',color:'#e0a030',leader:'Ada',descr:'Les meilleurs',members:12,score:90000,applied:false},
   {id:4,rank:2,tag:'ZZ',name:'Autre',color:'',leader:'Bob',descr:'',members:3,score:100,applied:false}]};},
 guild_get:async(id)=>{window.__calls.push('guild:'+id);const now=window.__now,mine=id===3;return {ok:true,guild:{id,name:mine?'Encyclo <i>':'Autre',tag:mine?'WIKI':'ZZ',descr:'Desc',color:'#e0a030',rank:1,count:2,score:90000,leader:'Ada',
   max_members:50,is_member:mine,is_manager:mine,is_leader:mine,applied:false,
   members:[{name:'Ada',me:false,leader:true,officer:false,total:900,joined:now-86400},{name:'Joueur',me:true,leader:false,officer:false,total:10,joined:now-3600},{name:'Bob',me:false,leader:false,officer:true,total:50,joined:now-600}],
   applications:[{name:'Zoé',created:now-60}],
   feed:mine?[{id:9,name:'Ada',card:cardOf('fr:GF','Légendaire <b>x</b>','L'),ts:now-100,likes:2,liked:false,points:900,comments:[{id:1,name:'Bob',text:'Bravo <b>!</b>',ts:now-50,can_delete:false}]}]:[],
   chat:mine?[{id:1,uid:5,name:'Ada',text:'Salut <i>la guilde</i>',ts:now-30},{id:2,uid:1,name:'Joueur',text:'Hello',ts:now-10}]:[]}};},
 guild_action:async(a,arg,text)=>{window.__calls.push('gact:'+a+':'+JSON.stringify(arg===undefined?null:arg)+':'+JSON.stringify(text===undefined?null:text));return {ok:true,liked:true,dissolved:false};},
 guild_chat_seen:async()=>{window.__calls.push('gseen');return {ok:true};},
 achievements_get:async()=>{window.__calls.push('ach');return {ok:true,earned:3,total:50,won:300,to_claim:20,locked:false,families:['Collection'],items:[
   {code:'c10',family:'Collection',title:'10 cartes <b>x</b>',what:'Posséder 10 cartes',done:10,goal:10,finished:true,claimed:false,gain:20},
   {code:'c100',family:'Collection',title:'100 cartes',what:'',done:50,goal:100,finished:false,claimed:false,gain:100},{code:'c1',family:'Collection',title:'Première',what:'',done:1,goal:1,finished:true,claimed:true,gain:5}]};},
 claim:async(kind,key)=>{window.__calls.push('claim:'+kind+':'+JSON.stringify(key===undefined?null:key));return {ok:true,titles:['Récompense <b>x</b>'],gain:20,packs:false,gift:false,day:3,text:'Un paquet doré',kind:'dore'};},
 load_card:async(cid)=>{window.__calls.push('load_card:'+cid);return {ok:true,extract:'Un long extrait <b>x</b> de l article. '+'Une phrase de plus. '.repeat(40),
   mine:[{id:5001,for_sale:false,state:'free',shiny:false,via:'enchere',ts:1790000000,price:250,from:'bob<i>',lot:false},{id:5002,for_sale:false,state:'locked',shiny:false,via:'paquet',ts:1780000000,price:null,from:'',lot:false}],
   wished:true,friends:['ami1','ami2'],guild:['g1'],friend_wishes:['ami3'],auctions:[auc(31,{ends_at:window.__now+120})]};},
 export_collection:async()=>{window.__calls.push('export');return {ok:true,path:'C:/Users/x/Downloads/wikipick-collection.csv',count:300};},

 _w:(label)=>{window.__actions.unshift({ts:Date.now()/1000,action:label,ok:true,error:null});},
 actions_get:async()=>({ok:true,actions:copy(window.__actions)}),
 auction_get:async(id)=>{window.__calls.push('auction_get:'+id);const bid=window.__bids[id];
   return {ok:true,auction:auc(id,{price:bid||100+id,leader:bid?'Joueur':'bob',leading:!!bid,mine:id===13||id===21,bids:bid?3:(id===13?0:2),min:(bid||100+id)+10})};},
 bid:async(id,amount)=>{window.__calls.push('bid:'+id+':'+amount);await new Promise(r=>setTimeout(r,window.__bidDelay||0));window.__bids[id]=amount;
   window.pywebview.api._w('Mise '+amount+' sur '+id);return {ok:true,extended:false,ends_at:0};},
 auction_create:async(c,p,d)=>{window.__calls.push('auction_create:'+c+':'+p+':'+d);window.pywebview.api._w('Enchère lancée '+c);return {ok:true};},
 auction_cancel:async(id)=>{window.__calls.push('auction_cancel:'+id);window.pywebview.api._w('Enchère annulée '+id);return {ok:true};},
 auction_price:async(id,p)=>{window.__calls.push('auction_price:'+id+':'+p);return {ok:true};},
 trade_action:async(a,id)=>{window.__calls.push('trade:'+a+':'+id);window.pywebview.api._w('Échange '+id+' '+a);return {ok:true};},
 trade_send:async(to,give,take,gc,tc,msg,counter)=>{window.__calls.push('tradesend:'+JSON.stringify([to,give,take,gc,tc,msg,counter]));return {ok:true};},
 friends_get:async()=>({ok:true,friends:[{name:'ami <b>x</b>',fav:true},{name:'zoé',fav:false}],incoming:[],outgoing:[]}),
 user_cards:async(n)=>{window.__calls.push('user_cards:'+n);return {ok:true,groups:[{card:cardOf('fr:T1','Leur carte <b>x</b>','SR'),ids:[9001,9002]},{card:cardOf('fr:T2','Autre','C'),ids:[9003]}]};},
 recycle:async(ids)=>{window.__calls.push('recycle:'+ids.length+':'+ids[0]);window.__recycled.push(...ids);window.pywebview.api._w('Recyclage '+ids.length);
   return {ok:true,gain:ids.length===1?500:ids.length*2,sold:ids.length,locked:0};},
 corbeille_get:async()=>({ok:true,price:4,minutes:20,items:[{id:801,card:cardOf('fr:D1','Recyclée 1','C'),left:600},{id:802,card:cardOf('fr:D2','Recyclée 2','R'),left:60}]}),
 corbeille_restore:async(ids,all)=>{window.__calls.push('restore:'+JSON.stringify(ids)+':'+all);return {ok:true,restored:all?2:1,cost:all?8:4};},
 corbeille_empty:async()=>{window.__calls.push('empty');return {ok:true,erased:2};},
 card_lock:async(id,cid,sh,on)=>{window.__calls.push('lock:'+id+':'+on);return {ok:true,locked:on};},
 card_for_sale:async(id,on)=>{window.__calls.push('forsale:'+id+':'+on);return {ok:true,n:3};},
 wish_set:async(cid,on,card)=>{window.__calls.push('wish:'+cid+':'+on);return {ok:true,wished:on};},
 pro_market:async(cid,r,sh)=>{window.__calls.push('pro_market:'+cid);const n=window.__now;
   return {ok:true,live:1,stats:{n:3,last:120,avg:100,min:80,max:120},rarity:{n:9,last:500,avg:400,min:100,max:900},
     sales:[{ts:n-259200,price:80,title:''},{ts:n-172800,price:100,title:''},{ts:n-86400,price:120,title:''}],rsales:[{ts:n-86400,price:500,title:'Autre carte'},{ts:n-3600,price:300,title:'Encore une'}]};},
 open_gold_pack:async()=>{window.__calls.push('open_gold');return {ok:true,me:{id:1,name:'Joueur',coins:1629,packs:3,packReserve:3,packMax:10,paquetOr:0,next:500,avatar:null,pro:false},
   cards:[{cid:'fr:G1',name:'Dorée 1',desc:'',img:null,rarity:'L',reads:9000,shiny:false,new:true,copies:1,locked:false,tags:[],ids:[1],url:null},
          {cid:'fr:G2',name:'Dorée 2',desc:'',img:null,rarity:'C',reads:9,shiny:false,new:false,copies:1,locked:false,tags:[],ids:[2],url:null}]};},
 prefs_get:async()=>({ok:true,prefs:copy(window.__prefs)}),
 prefs_set:async(k,v)=>{window.__calls.push('pref:'+k+'='+v);window.__prefs[k]=v;return {ok:true}},
 pack_history:async()=>{window.__calls.push('pack_history');return {ok:true,packs:window.__packs.slice().reverse()}},
 watch_get:async()=>({ok:true,list:window.__watch.slice()}),
 watch_set:async(cid,name,on)=>{window.__calls.push('watchcard:'+cid+':'+on);window.__watch=window.__watch.filter(w=>w.cid!==cid);if(on)window.__watch.push({cid,name});return {ok:true,list:window.__watch.slice()}},
 load_collection:async()=>{window.__calls.push('load_collection');await new Promise(r=>setTimeout(r,window.__delay));
   return {ok:true,rank:D.rank,tags:D.tags,cards:copy(D.cards),stats:D.stats}},
 start_login:async()=>{window.__calls.push('start_login');return {ok:true}},
 login_state:async()=>({state:'pending'}),
 import_cookie_header:async(h)=>({ok:false,error:'Ces cookies ne donnent pas de session valide.'}),
 pack_challenge:async()=>{window.__calls.push('pack_challenge');const sq=(f)=>({viewBox:'0 0 40 40',shapes:[{tag:'path',attrs:{d:'M7 7h26v26H7z',fill:f,transform:'rotate(8 20 20)'}}]});
   return {ok:true,challenge:{id:'ZheyznhTbvnkI4we',consigne:'Clique sur la goutte <b>x</b>',choix:[sq('#ef6f8d'),{viewBox:'0 0 40 40',shapes:[{tag:'path',attrs:{d:'M20 3c8 10 12 15 12 20a12 12 0 01-24 0c0-5 4-10 12-20z',fill:'#40bd8f'}}]},sq('#a78bfa'),null,sq('#40bd8f'),sq('#4aa7e6')]}};},
 open_pack:async(defi,rep)=>{window.__calls.push('open_pack');if(defi!==undefined&&defi!==null)window.__calls.push('open_pack_proof:'+defi+':'+rep);window.__packs.push({ts:Date.now()/1000,cards:[{cid:'fr:A',name:'Nouvelle <b>x</b>',rarity:'SR',reads:32580,img:null,shiny:false,new:true},{cid:'fr:B',name:'Commune',rarity:'C',reads:88,img:null,shiny:false,new:false}]});return {ok:true,me:{id:1,name:'Joueur',coins:1629,packs:2,packReserve:2,packMax:10,next:500,avatar:null,pro:false},
   cards:[{cid:'fr:A',name:'Nouvelle <b>x</b>',desc:'',img:null,rarity:'SR',reads:32580,shiny:false,new:true,copies:1,locked:false,tags:[],ids:[1],url:null},
          {cid:'fr:B',name:'Commune',desc:'',img:null,rarity:'C',reads:88,shiny:false,new:false,copies:1,locked:false,tags:[],ids:[2],url:null}]}},
 pack_seen:async()=>{window.__calls.push('pack_seen');return {ok:true}},
 start_stream:async()=>{window.__calls.push('start_stream');return {ok:true}},
 stop_stream:async()=>{window.__calls.push('stop_stream');return {ok:true}},
 stream_watch_market:async(on)=>{window.__calls.push('watch:'+on);return {ok:true}},
 poll_events:async()=>({ok:true,state:window.__state,events:window.__events.splice(0)}),
 load_notifications:async()=>{window.__calls.push('load_notifications');return {ok:true,items:copy(window.__notifs),unread:0,now:window.__now}},
 read_notifications:async()=>{window.__calls.push('read_notifications');return {ok:true}},
 load_market:async(scope,page,q,r,tri,kind)=>{window.__calls.push('load_market:'+[scope,page,q,r.join(),tri,kind].join(':'));
   const now=window.__now, b=page*100;
   if(scope==='purchases'||scope==='ventes') return {ok:true,history:true,page,pages:page===0?2:1,total:12,sum:4200,now,items:[
     {card:cardOf('fr:P'+page,'Achat <b>x</b> '+page,'SR'),lot:null,price:250,sold:scope==='ventes',who:'bob<i>',ts:now-7200},
     {card:null,lot:{n:2,name:'Lot <u>fini</u>',cards:[cardOf('fr:L2','Dans le lot','C')]},price:80,sold:scope==='ventes',who:'ann',ts:now-90000}]};
   if(scope==='mine') return {ok:true,items:[auc(21,{mine:true,bids:1})],page:0,pages:1,total:1,now};
   if(scope==='bidding') return {ok:true,items:[auc(22,{leading:true}),auc(23,{mine:true})],page:0,pages:1,total:2,now};
   return {ok:true,page,pages:2,total:6,now,items:[auc(b+11), auc(b+12,{card:null,lot:{n:3,name:'Lot <u>test</u>',cards:[cardOf('fr:L1','Première du lot','R')]},ends_at:now+40,leader:'ann'}),
     auc(b+13,{mine:true,ends_at:now+10,bids:0,leader:''})]};},
 load_trades:async(box)=>{window.__calls.push('load_trades:'+box);const now=window.__now;
   if(box==='history') return {ok:true,now,trades:[]};
   return {ok:true,now,trades:[
     {id:5,incoming:true,other:'ami <b>x</b>',give:[cardOf('fr:G','Donnée','R')],get:[cardOf('fr:H','Reçue','SR'),cardOf('fr:I','Autre','C')],give_coins:0,get_coins:50,status:'pending',message:'Salut <i>toi</i>',valid:true,created:now-120,closed:0},
     {id:7,incoming:false,other:'yann',give:[cardOf('fr:K','Proposée','R')],get:[cardOf('fr:M','Espérée','SR')],give_coins:0,get_coins:0,status:'pending',message:'',valid:true,created:now-30,closed:0},
     {id:6,incoming:false,other:'zoé',give:[cardOf('fr:J','Envoyée','PC')],get:[],give_coins:10,get_coins:0,status:'declined',message:'',valid:false,created:now-3600,closed:now-60}]};},
 load_ranking:async(period)=>{window.__calls.push('load_ranking:'+period);
   const row=(rank,name,me,pts)=>({rank,name,guild:rank===1?'ABC':'',me,chroma:2,mythic:1,legend:3,ultra:4,cards:99,points:pts});
   return {ok:true,points:{M:5000,L:900,UR:300,SR:100,R:30,PC:10,C:3},chroma_points:12000,rule:period==='tout'?'':'acquis',reset_in:90000,
     top:[row(1,'Ada <b>x</b>',false,12345),row(2,'Joueur',period!=='tout',11000),row(3,'Bob',false,9000)]};},
 combat_info:async()=>{window.__calls.push('combat_info');const n=window.__now;return {ok:true,left:window.__cbLeft??4,total:5,next:n+900,window:1800,size:3,wait:60,prep:120,
   opponents:[{name:'ami <b>x</b>',online:true,fighting:false,cards:40,fav:true},{name:'busy',online:true,fighting:true,cards:40,fav:false},{name:'dort',online:false,fighting:false,cards:40,fav:false},{name:'novice',online:true,fighting:false,cards:1,fav:false}],
   history:[{me:2,them:1,defended:false,opponent:'bob<i>',gain:30,when:n-600},{me:0,them:2,defended:true,opponent:'ann',gain:0,when:n-4000}],
   chests:window.__chest??1,chest_all:5,chest_left:3};},
 combat_state:async()=>({ok:true,defi:null}),
 combat_decks:async()=>({ok:true,decks:copy(window.__decks||[])}),
 combat_deck_save:async(id,name,cards)=>{window.__calls.push('deck_save:'+id+':'+name+':'+cards.length);window.__decks=[{id:9,name,complete:true,ids:cards,cards:cards.map(i=>cardOf('fr:D'+i,'Deck '+i,'R'))}];return {ok:true,decks:copy(window.__decks)};},
 combat_deck_delete:async(id)=>{window.__calls.push('deck_del:'+id);window.__decks=[];return {ok:true,decks:[]};},
 combat_challenge:async(name)=>{window.__calls.push('challenge:'+name);return {ok:true,defi:{id:77,state:'attente',expire:window.__now+60,launched:true,opponent:name,my_ready:false,opp_ready:false,team:[]}};},
 combat_answer:async(id,ok)=>{window.__calls.push('answer:'+id+':'+ok);return {ok:true,defi:ok?{id,state:'prepa',expire:window.__now+120,launched:false,opponent:'rival <i>',my_ready:false,opp_ready:false,team:[]}:null};},
 combat_choice:async(id,cards)=>{window.__calls.push('choice:'+id+':'+cards.length);return {ok:true};},
 combat_team:async(id,cards)=>{window.__calls.push('team:'+id+':'+cards.length);
   const h=(by,d,a,b,crit)=>({by,damage:d,crit:!!crit,spell:'epee',spell_name:'',hp_a:a,hp_b:b});
   const rd=(w)=>({hp_a:200,hp_b:200,left_a:w==='a'?80:0,left_b:w==='a'?0:80,hits:[h('a',100,200,100),h('b',60,140,100),h('a',100,140,0,true)],sequential:false,winner:w,ko:true});
   const t=(n)=>[0,1,2].map(i=>cardOf('fr:F'+n+i,n+' carte <b>'+i+'</b>','SR'));
   return {ok:true,waiting:false,duel:{me:'Joueur',opponent:'rival <i>',team_a:t('A'),team_b:t('B'),rounds:[rd('a'),rd('b'),rd('a')],won:true,score_a:2,score_b:1,gain:45,left:3,total:5}};},
 combat_cancel:async(id)=>{window.__calls.push('cancel:'+id);return {ok:true};},
 combat_chest:async()=>{window.__calls.push('chest');return {ok:true,kind:'wikiki',n:120,left:0,card:cardOf('fr:CH','Trouvaille <b>x</b>','R')};},
 users_search:async(q)=>{window.__calls.push('users:'+q);return {ok:true,users:[{name:'trouvé <b>x</b>',online:true}]};},
 logout:async()=>({ok:true}), open_url:async(u)=>{window.__calls.push('open '+u);return {ok:true}}
}};
"""
out = Path(tempfile.mkdtemp(prefix="wikipick_ui_"))
print("screenshots ->", out)
calls = lambda pg, name: pg.evaluate("window.__calls").count(name)

with sync_playwright() as p:
    b = p.chromium.launch()
    def page(logged=True, cache=False, delay=300, width=1300, prefs=None):
        pg = b.new_page(viewport={"width":width,"height":850})
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: errs.append("DIALOG:"+d.message))
        pg.add_init_script(stub.replace("__LOGGED__", "true" if logged else "false").replace("__CACHE__", "true" if cache else "false")
                           .replace("__DELAY__", str(delay)).replace("__PREFS__", json.dumps(prefs or {})).replace("__DATA__", json.dumps(data)))
        pg.goto((ROOT / "desktop" / "web" / "index.html").as_uri())
        return pg, errs

    # --- connexion
    pg, errs = page(logged=False); pg.wait_for_timeout(500)
    assert pg.is_visible("#login") and not pg.is_visible("#app")
    pg.click("#btn-login"); pg.wait_for_timeout(200); assert 'start_login' in pg.evaluate("window.__calls")
    pg.click("summary"); pg.fill("#cookie-text","a=b"); pg.click("#btn-cookie"); pg.wait_for_timeout(200)
    print("login msg:", pg.inner_text("#login-msg")); pg.screenshot(path=str(out/"login.png")); print("login errs:", errs)

    # --- démarrage sans cache : l'appli s'affiche tout de suite avec des cartes fantômes, puis les vraies cartes
    pg, errs = page(delay=900); pg.wait_for_timeout(450)
    assert pg.is_visible("#app") and pg.locator(".card.sk").count() > 0, "cartes fantômes attendues"
    assert pg.inner_text("#me-packs") == "3/10" and pg.is_visible("#sync")
    pg.screenshot(path=str(out/"loading.png"))
    pg.wait_for_timeout(1500)
    assert pg.locator(".card.sk").count() == 0 and pg.locator("#grid .card").count() == 60
    assert pg.input_value("#f-sort") == "rarity", "tri par défaut = rareté"
    first = pg.locator("#grid .card .rar").first.inner_text()
    assert first == rarest, (first, rarest)
    print("count label:", pg.inner_text("#f-count"), "| première carte:", first)

    # --- démarrage avec cache : les cartes sont là avant la fin du chargement réseau
    pg2, errs2 = page(cache=True, delay=1200); pg2.wait_for_timeout(300)
    assert pg2.locator("#grid .card").count() == 60 and pg2.locator(".card.sk").count() == 0
    assert pg2.inner_text("#sync") == "Synchronisation…"  # le minuteur, lui, revient dès que le profil frais arrive
    pg2.screenshot(path=str(out/"cache.png")); pg2.wait_for_timeout(1700)
    assert pg2.inner_text("#sync") in ("À jour", "") and pg2.is_visible("#me-timer")
    assert calls(pg2, "load_collection") == 1 and not errs2
    pg2.close()

    # --- collection
    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(500)
    print("after scroll:", pg.locator("#grid .card").count())
    pg.evaluate("window.scrollTo(0,0)")
    pg.fill("#f-search","numéro 12"); pg.wait_for_timeout(200); print("search 'numéro 12':", pg.locator("#grid .card").count())
    pg.fill("#f-search",""); pg.check("#f-dups"); pg.wait_for_timeout(200); print("dups only:", pg.locator("#grid .card").count()); pg.uncheck("#f-dups")
    pg.click("#f-rarities .chip >> nth=0"); pg.wait_for_timeout(200); print("first rarity chip:", pg.locator("#grid .card").count()); pg.click("#f-rarities .chip >> nth=0")
    pg.select_option("#f-tag","7"); pg.wait_for_timeout(200); print("tag Acteur:", pg.locator("#grid .card").count()); pg.select_option("#f-tag","")
    pg.screenshot(path=str(out/"collection.png"))
    cid0 = pg.evaluate("S.filtered[0].cid")
    pg.locator("#grid .card").first.click(); pg.wait_for_timeout(300); assert pg.is_visible("#modal")
    ex = pg.inner_text("#sheet-extra").replace(chr(0xa0), " ")
    assert "Un long extrait <b>x</b> de l article." in ex, "l'extrait Wikipédia reste du texte"
    assert "Tes exemplaires (2)" in ex and "Achetée 250 Wikiki aux enchères à bob<i>" in ex and "Obtenue dans un paquet le " in ex
    assert "Chez tes amis : ami1, ami2" in ex and "Dans ta guilde : g1" in ex and "Ton ami la souhaite : ami3" in ex and "Dans ta liste de souhaits sur le site." in ex
    assert "Aux enchères en ce moment (1)" in ex and re.search(r"\b[12]:\d\d\b", pg.locator("#sheet-extra .timer").inner_text())
    assert pg.locator("#sheet-extra .extract").evaluate("n => !n.classList.contains('open')") and pg.locator("#sheet-extra >> text=Lire la suite").count() == 1
    pg.click("#sheet-extra >> text=Lire la suite"); assert pg.locator("#sheet-extra >> text=Réduire").count() == 1
    assert pg.locator("#sheet-extra b, #sheet-extra i").count() == 0, "aucun HTML venu du site dans la fiche"
    assert pg.locator("#sheet-extra button").count() >= 2 and pg.locator("#sheet-extra .actions").count() == 1
    assert calls(pg, "load_card:" + cid0) == 1
    assert "Lectures" in pg.inner_text("#modal-body") and pg.locator("#modal-body dt").count() >= 2
    pg.screenshot(path=str(out/"sheet.png"))
    pg.keyboard.press("Escape"); assert pg.evaluate("document.activeElement.classList.contains('card')"), "le focus revient à la carte ouverte"
    pg.locator("#grid .card").first.click(); pg.wait_for_timeout(200)
    assert calls(pg, "load_card:" + cid0) == 1, "une fiche rouverte dans la minute ne rappelle pas le site"
    pg.keyboard.press("Escape")
    pg.locator("#grid .card").first.click(); pg.wait_for_timeout(200); assert pg.is_visible("#modal")
    pg.route("https://upload.wikimedia.org/**", lambda route: route.abort())
    pg.evaluate("document.body.append(Object.assign(cardNode({name: 'Zed', rarity: 'C', reads: 1, copies: 1, locked: false, tags: [], img: 'https://upload.wikimedia.org/absente.jpg'}, null), {id: 'probe'}))")
    pg.wait_for_timeout(400); assert pg.locator("#probe .initial").inner_text() == "Z", "image refusée : l'initiale de la carte"
    pg.evaluate("document.getElementById('probe').remove()")
    pg.screenshot(path=str(out/"modal.png")); pg.click("text=Ouvrir sur Wikipédia"); print("calls:", [c for c in pg.evaluate("window.__calls") if c.startswith("open ")]); pg.keyboard.press("Escape")
    assert not pg.is_visible("#modal")

    # --- minuteur : 423 s au chargement, relecture du profil à zéro, "Réserve pleine" quand la réserve est pleine
    assert re.fullmatch(r"[67]:\d\d", pg.inner_text("#me-timer-t")), pg.inner_text("#me-timer-t")
    loads = calls(pg, "load_me")
    pg.evaluate("window.__me = {id:1,name:'Joueur',coins:1629,packs:4,packReserve:4,packMax:10,next:600,avatar:null,pro:false}")
    pg.evaluate("S.data.me.next = 1; S.meAt = Date.now() - 6000"); pg.wait_for_timeout(1500)
    assert calls(pg, "load_me") == loads + 1 and pg.inner_text("#me-packs") == "4/10"
    assert re.fullmatch(r"(9|10):\d\d", pg.inner_text("#me-timer-t")), pg.inner_text("#me-timer-t")
    pg.evaluate("S.data.me.packReserve = 10; tickPacks()"); assert pg.inner_text("#me-timer-t") == "Réserve pleine"
    pg.evaluate("window.__me = null; S.data.me.packReserve = 3; S.data.me.packs = 3; renderHeader()")

    # --- paquets : un clic ouvre un seul paquet, les cartes arrivent face cachée, de la plus commune à la plus rare
    pg.click("[data-tab=packs]"); assert pg.is_visible("#pack") and pg.inner_text("#pk-count") == "3 paquets en réserve"
    assert pg.inner_text("#pk-next").startswith("Prochain paquet dans")
    pg.mouse.move(650, 380); pg.wait_for_timeout(100); pg.screenshot(path=str(out/"packs-idle.png"))
    collections = calls(pg, "load_collection")
    pg.click("#btn-open"); pg.wait_for_timeout(1400)
    assert pg.is_visible("#reveal") and not pg.is_visible("#packs-idle")
    assert pg.locator(".pcard").count() == 2 and pg.locator(".pcard.open").count() == 0 and pg.inner_text("#me-packs") == "2/10"
    assert calls(pg, "open_pack") == 1 and calls(pg, "pack_seen") == 1
    assert "Commune" in pg.locator(".pcard").first.text_content(), "la commune d'abord"
    pg.locator(".pcard").first.click(); pg.wait_for_timeout(200)
    assert pg.locator(".pcard.open").count() == 1 and pg.inner_text("#pk-progress") == "1 sur 2 retournée"
    pg.screenshot(path=str(out/"packs-reveal.png"))
    pg.click("#btn-flip-all"); pg.wait_for_timeout(900)
    assert pg.locator(".pcard.open").count() == 2 and pg.is_visible("#pk-end") and not pg.is_visible("#btn-flip-all")
    assert "2 cartes, dont 1 nouvelle" in pg.inner_text("#pk-summary"), pg.inner_text("#pk-summary")
    assert pg.locator("#pk-cards b").count() == 0, "le HTML d'un nom de carte doit rester du texte"
    pg.screenshot(path=str(out/"packs-done.png"))
    # « Ouvrir un autre paquet » : un nouveau clic = un nouveau paquet, sans relire la collection entre les deux
    pg.click("#btn-again"); pg.wait_for_timeout(1400)
    assert calls(pg, "open_pack") == 2 and calls(pg, "load_collection") == collections and pg.locator(".pcard.open").count() == 0
    pg.click("#btn-flip-all"); pg.wait_for_timeout(900); pg.click("#btn-done"); pg.wait_for_timeout(700)
    assert pg.is_visible("#pack") and not pg.is_visible("#reveal") and calls(pg, "load_collection") == collections + 1
    # journal local des paquets : chance mesurée contre les chances annoncées, derniers paquets, fiche au clic
    pg.wait_for_timeout(400)
    assert pg.is_visible("#pk-journal") and "2 paquets ouverts avec l'appli" in pg.inner_text("#pj-sum") and pg.locator(".pj-row").count() == 2
    assert pg.locator(".thumb.mini").count() == 4 and pg.locator(".thumb.mini.new").count() == 2
    lk = pg.inner_text("#pj-luck"); assert "Ta chance, mesurée" in lk and "Épique" in lk and "2 sur 2" in lk and "attendu : 0,2" in lk and "attendu : < 0,1" in lk and "Chromatique" in lk
    assert pg.locator(".lk").count() == 6, "M, L, UR, SR, R et chromatique : les raretés presque certaines sont omises"
    pg.locator(".thumb.mini").first.click(); pg.wait_for_timeout(150); assert pg.is_visible("#modal")
    pg.keyboard.press("Escape"); pg.screenshot(path=str(out/"journal.png"), full_page=True)
    pg.click("#btn-open"); pg.wait_for_timeout(1400); assert not pg.is_visible("#pk-journal"), "le journal se range pendant l'ouverture d'un paquet"
    pg.click("#btn-flip-all"); pg.wait_for_timeout(900); pg.click("#btn-done"); pg.wait_for_timeout(600)
    assert "3 paquets ouverts" in pg.inner_text("#pj-sum")

    # --- temps réel : indicateur, notification, cloche
    assert calls(pg, "start_stream") == 1 and pg.inner_text("#live-t") == "En direct"
    pg.click("[data-tab=collection]")
    pg.evaluate("window.__me = {id:1,name:'Joueur',coins:1629,packs:3,packReserve:3,packMax:10,next:423,unread:1,unreadMsg:2,trades:1,avatar:null,pro:False}".replace("False", "false"))
    note = {"id": 9, "type": "outbid", "text": "Quelqu'un a surenchéri <b>x</b>", "kind": "bad", "link": "auction:5"}
    pg.evaluate("window.__notifs = [{id:9,type:'outbid',text:\"Quelqu'un a surenchéri <b>x</b>\",tone:'bad',link:'',read:false,created:window.__now},"
                "{id:1,type:'won',text:'Enchère remportée',tone:'good',link:'',read:true,created:window.__now-3600}]")
    pg.evaluate("window.__events.push(%s)" % json.dumps({"event": "notify", "data": note}))
    pg.wait_for_timeout(1700)
    assert pg.is_visible("#toast") and "surenchéri" in pg.inner_text("#toast") and "bad" in pg.get_attribute("#toast", "class")
    assert pg.locator("#toast b").count() == 0 and pg.inner_text("#bell-n") == "1"
    pg.click("#btn-bell"); pg.wait_for_timeout(300)
    assert pg.is_visible("#bell-panel") and pg.locator(".nitem").count() == 2 and pg.locator(".nitem.unread").count() == 1
    assert "2 messages non lus" in pg.inner_text("#bell-foot") and "1 échange en attente" in pg.inner_text("#bell-foot")
    assert pg.locator("#bell-list b").count() == 0
    pg.screenshot(path=str(out/"bell.png"))
    pg.click("#btn-read-all"); pg.wait_for_timeout(200)
    assert calls(pg, "read_notifications") == 1 and not pg.is_visible("#bell-n") and pg.locator(".nitem.unread").count() == 0
    assert pg.is_visible("#bell-panel")
    pg.mouse.click(3, 400); pg.wait_for_timeout(100); assert not pg.is_visible("#bell-panel"), "clic en dehors : la cloche se ferme"

    # --- marché en direct (lecture seule)
    pg.click("[data-tab=market]"); pg.wait_for_timeout(500)
    assert "watch:true" in pg.evaluate("window.__calls") and "load_market:live:0:::fin:" in pg.evaluate("window.__calls")
    assert pg.locator("#mgrid .offer").count() == 3 and pg.inner_text("#m-count") == "3 enchères affichées" and pg.is_visible("#m-more")
    assert "3 chargées sur 6" in pg.inner_text("#m-note")
    assert pg.locator(".lotbadge").inner_text() == "Lot de 3 cartes"
    t11 = pg.locator("#mgrid .offer[data-id='11'] .timer").inner_text()
    assert re.fullmatch(r"[45]:\d\d", t11), t11
    assert "hot" in pg.locator("#mgrid .offer[data-id='13'] .timer").get_attribute("class")
    assert pg.locator("#mgrid .offer").first.get_attribute("data-id") == "13", "tri par défaut : fin la plus proche d'abord"
    assert pg.locator("#mgrid b, #mgrid u").count() == 0, "le HTML d'un nom d'enchère ou de lot doit rester du texte"
    assert pg.locator("#mgrid .offer[data-id='11'] .bid").count() == 1 and pg.locator("#mgrid .offer[data-id='13'] .bid").count() == 0, "on ne mise pas sur sa propre enchère"
    pg.screenshot(path=str(out/"market.png"))
    # défilement continu : l'écran n'est pas plein, la page suivante se charge toute seule, une seule fois
    pg.wait_for_timeout(2000)
    assert calls(pg, "load_market:live:1:::fin:") == 1 and pg.locator("#mgrid .offer").count() == 6 and not pg.is_visible("#m-more")
    assert "6 chargées sur 6" in pg.inner_text("#m-note")
    bid = {"what": "bid", "id": 11, "price": 150, "leader": "zoé", "leaderId": 99, "endsAt": 0, "min": 160, "extended": True}
    pg.evaluate("window.__events.push(%s)" % json.dumps({"event": "auction", "data": bid}))
    pg.wait_for_timeout(1300)
    tile = pg.locator("#mgrid .offer[data-id='11']")
    assert "150" in tile.locator(".price").inner_text() and "en tête : zoé" in tile.locator(".seller").inner_text()
    assert "bump" in tile.get_attribute("class") and tile.locator(".xtag").inner_text() == "Prolongation"
    end = {"what": "end", "id": 12, "sold": True, "price": 90, "winnerId": 1}
    collections = calls(pg, "load_collection")
    pg.evaluate("window.__events.push(%s)" % json.dumps({"event": "auction", "data": end}))
    pg.wait_for_timeout(1300)
    lot = pg.locator("#mgrid .offer[data-id='12']")
    assert "fini" in lot.get_attribute("class") and "Adjugé à ann" in lot.inner_text() and lot.locator(".timer").inner_text() == "Terminé"
    # sur le marché, une enchère terminée disparaît quelques secondes après (8 s), sans laisser de trou dans les compteurs
    before = int(pg.inner_text("#m-count").split()[0])
    pg.wait_for_timeout(8600)  # jusqu'à 1 s de sondage + 8 s de délai + le fondu
    assert pg.locator("#mgrid .offer[data-id='12']").count() == 0, "l'enchère terminée doit disparaître du marché"
    assert int(pg.inner_text("#m-count").split()[0]) == before - 1
    assert calls(pg, "load_collection") == collections + 1, "une enchère gagnée relit la collection"

    # vue liste : un en-tête, une ligne par enchère, tri au clic sur les colonnes (relu côté serveur)
    pg.click("#m-views [data-view=list]"); pg.wait_for_timeout(200)
    assert "list" in pg.get_attribute("#mgrid", "class") and pg.locator("#mgrid .arow.head").count() == 1
    assert pg.evaluate("[...document.querySelectorAll('#mgrid .arow')].every(r => r.scrollWidth <= r.clientWidth + 1)"), "les colonnes de la liste ne débordent pas"
    assert pg.locator("#mgrid .arow:not(.head)").count() == 5 and pg.locator("#mgrid .arow:not(.head) .bid").count() >= 1
    pg.screenshot(path=str(out/"market-list.png"))
    pg.click("#mgrid .arow.head .pr"); pg.wait_for_timeout(500)
    assert "load_market:live:0:::prixbas:" in pg.evaluate("window.__calls") and "↑" in pg.locator(".arow.head .pr").inner_text()
    pg.click("#mgrid .arow.head .pr"); pg.wait_for_timeout(500)
    assert "load_market:live:0:::prix:" in pg.evaluate("window.__calls")
    assert "113" in pg.locator("#mgrid .arow:not(.head) .pr").first.inner_text(), "prix décroissant : le plus cher d'abord"
    pg.wait_for_timeout(1800)  # la page suivante arrive
    # filtres sur ce qui est chargé : aucun rechargement serveur
    loads = sum(c.startswith("load_market") for c in pg.evaluate("window.__calls"))
    pg.check("#m-nobid"); pg.wait_for_timeout(150); assert pg.locator("#mgrid .arow:not(.head)").count() == 2
    pg.fill("#m-max", "150"); pg.wait_for_timeout(500); assert pg.locator("#mgrid .arow:not(.head)").count() == 1
    pg.select_option("#m-end", "60"); pg.wait_for_timeout(150); assert pg.locator("#mgrid .arow:not(.head)").count() == 1
    pg.select_option("#m-end", "0"); pg.select_option("#m-kind", "lots"); pg.wait_for_timeout(500)
    assert sum(c.startswith("load_market") for c in pg.evaluate("window.__calls")) == loads + 1, "le type est filtré par le serveur"
    pg.click("#m-reset"); pg.wait_for_timeout(400)
    assert not pg.is_checked("#m-nobid") and pg.input_value("#m-max") == "" and pg.input_value("#m-kind") == ""
    # petite grille : plus de cartes à l'écran
    pg.click("#m-views [data-view=dense]"); pg.wait_for_timeout(200)
    assert "g-s" in pg.get_attribute("#mgrid", "class") and pg.locator("#mgrid .card").count() >= 3
    pg.screenshot(path=str(out/"market-dense.png"))
    pg.click("#m-views [data-view=grid]")
    # mes ventes / mes mises : les deux autres vues du site, chargées en une fois
    pg.select_option("#m-sort", "fin"); pg.wait_for_timeout(300)
    pg.click("#m-scopes [data-scope=mine]"); pg.wait_for_timeout(400)
    assert "load_market:mine:0:::fin:" in pg.evaluate("window.__calls")
    assert pg.locator("#mgrid .offer").count() == 1 and "Ta carte" in pg.inner_text("#mgrid") and not pg.is_visible("#m-more")
    assert pg.inner_text("#m-count") == "1 enchère affichée"
    pg.click("#m-scopes [data-scope=bidding]"); pg.wait_for_timeout(400)
    assert pg.locator("#mgrid .offer").count() == 1 and "Tu es en tête" in pg.inner_text("#mgrid"), "mes propres ventes sont exclues de « mes mises »"
    pg.screenshot(path=str(out/"market-bidding.png"))
    # achetées / vendues : l'historique, page par page, sans échéance ni « sans mise »
    pg.click("#m-scopes [data-scope=purchases]"); pg.wait_for_timeout(400)
    assert "load_market:purchases:0:::fin:" in pg.evaluate("window.__calls") and pg.locator("#mgrid .offer").count() == 2
    assert "hist" in pg.get_attribute("#tab-market", "class") and not pg.is_visible("#m-end") and not pg.is_visible("#m-nobid")
    assert "il y a 2 h" in pg.locator("#mgrid .offer .timer").first.inner_text() and "Acheté à bob<i>" in pg.inner_text("#mgrid")
    assert "12" in pg.inner_text("#m-note") and "4 200" in pg.inner_text("#m-note").replace("\u202f", " ").replace("\xa0", " ") and "date" in pg.locator("#m-sort option").first.inner_text()
    assert pg.locator("#mgrid .offer.fini").count() == 0, "un achat passé n'est pas grisé"
    pg.wait_for_timeout(1800); assert pg.locator("#mgrid .offer").count() == 4, "la page suivante de l'historique se charge au défilement"
    pg.click("#m-scopes [data-scope=ventes]"); pg.wait_for_timeout(400)
    assert "load_market:ventes:0:::fin:" in pg.evaluate("window.__calls") and "Vendu à bob<i>" in pg.inner_text("#mgrid")
    assert pg.inner_text("#m-count").endswith("ventes affichées")
    pg.click("#m-views [data-view=list]"); pg.wait_for_timeout(150)
    assert "Date" in pg.locator("#mgrid .arow.head").inner_text() and "Vendu à bob<i>" in pg.inner_text("#mgrid")
    pg.screenshot(path=str(out/"market-history.png")); pg.click("#m-views [data-view=grid]")
    pg.click("#m-scopes [data-scope=live]"); pg.wait_for_timeout(2200)
    # recherche et raretés : relues côté serveur
    pg.fill("#m-search", "zzz"); pg.wait_for_timeout(700); assert "load_market:live:0:zzz::fin:" in pg.evaluate("window.__calls")
    pg.click("#m-rarities .chip >> nth=0"); pg.wait_for_timeout(300); assert "load_market:live:0:zzz:M:fin:" in pg.evaluate("window.__calls")
    pg.wait_for_timeout(1800)
    # coupure du flux : l'indicateur le dit, puis la reprise relit les notifications et le marché
    pg.evaluate("window.__state = 'down'"); pg.wait_for_timeout(1300)
    assert pg.inner_text("#live-t") == "Reconnexion…" and "down" in pg.get_attribute("#live", "class")
    notifs, markets = calls(pg, "load_notifications"), sum(c.startswith("load_market") for c in pg.evaluate("window.__calls"))
    pg.evaluate("window.__state = 'live'; window.__events.push({event:'resync',data:{}})")
    pg.wait_for_function("window.__calls.filter(c => c === 'load_notifications').length > %d" % notifs, timeout=4000)
    assert sum(c.startswith("load_market") for c in pg.evaluate("window.__calls")) == markets + 1
    assert calls(pg, "load_notifications") == notifs + 1 and pg.inner_text("#live-t") == "En direct"
    pg.click("[data-tab=collection]"); pg.wait_for_timeout(200); assert "watch:false" in pg.evaluate("window.__calls")

    # menu du compte
    pg.click("#btn-user"); assert pg.is_visible("#user-menu") and pg.locator("#user-menu button").count() == 8
    pg.keyboard.press("Escape"); assert not pg.is_visible("#user-menu")
    pg.click("#btn-user"); pg.mouse.click(3, 400); assert not pg.is_visible("#user-menu")
    loads = calls(pg, "load_collection"); pg.click("#btn-user"); pg.click("#btn-refresh"); pg.wait_for_timeout(700)
    assert not pg.is_visible("#user-menu") and calls(pg, "load_collection") == loads + 1

    # export CSV de la collection (fichier local, rien n'est envoyé)
    pg.click("#btn-user"); pg.click("#btn-export"); pg.wait_for_timeout(200)
    assert calls(pg, "export") == 1 and "Collection exportée (300 cartes)" in pg.inner_text("#toast") and "wikipick-collection.csv" in pg.inner_text("#toast")
    assert not pg.is_visible("#user-menu")
    # préférences mémorisées côté Python
    pg.select_option("#f-sort", "name"); pg.wait_for_timeout(100); assert "pref:collection_sort=name" in pg.evaluate("window.__calls")
    pg.select_option("#f-sort", "rarity")
    # cartes surveillées : bouton dans la fiche, panneau du marché, alerte en direct, liste locale
    cid = pg.evaluate("S.filtered[0].cid"); wname = pg.evaluate("S.filtered[0].name")
    pg.locator("#grid .card").first.click(); pg.wait_for_timeout(150)
    assert pg.locator("[data-watch]").inner_text() == "Surveiller aux enchères"
    pg.click("[data-watch]"); pg.wait_for_timeout(150)
    assert ("watchcard:%s:true" % cid) in pg.evaluate("window.__calls") and pg.locator("[data-watch]").inner_text() == "Ne plus surveiller"
    pg.keyboard.press("Escape")
    alert = {"what": "new", "id": 99, "cid": cid}
    pg.evaluate("window.__events.push(%s)" % json.dumps({"event": "auction", "data": alert})); pg.wait_for_timeout(1500)
    assert "vient d'être mise aux enchères" in pg.inner_text("#toast") and pg.evaluate("LV.localUnread") == 1
    pg.click("#btn-bell"); pg.wait_for_timeout(200)
    assert "vient d'être mise aux enchères" in pg.locator("#bell-list .nitem").first.inner_text(); pg.mouse.click(3, 400)
    pg.evaluate("window.__events.push(%s)" % json.dumps({"event": "auction", "data": {"what": "new", "id": 100, "cid": "fr:Autre"}})); pg.wait_for_timeout(1300)
    assert pg.evaluate("LV.localUnread") == 1, "une carte non surveillée ne déclenche rien"
    pg.click("[data-tab=market]"); pg.wait_for_timeout(300)
    assert pg.inner_text("#m-watch-n") == "1"; pg.click("#m-watch"); assert pg.is_visible("#watch-panel") and pg.locator("#watch-list .nitem.watch").count() == 1
    pg.click("#watch-list >> text=Voir sur le marché"); pg.wait_for_timeout(500)
    assert not pg.is_visible("#watch-panel") and pg.input_value("#m-search") == wname and any(c.startswith("load_market:live:0:%s:" % wname) for c in pg.evaluate("window.__calls"))
    pg.click("#m-watch"); pg.click("#watch-list >> text=Retirer"); pg.wait_for_timeout(200)
    assert ("watchcard:%s:false" % cid) in pg.evaluate("window.__calls") and pg.inner_text("#watch-list").startswith("Aucune carte surveillée")
    pg.keyboard.press("Escape"); pg.click("[data-tab=collection]")
    # recherche rapide (Ctrl+K) et raccourcis clavier
    pg.keyboard.press("Control+k"); assert pg.is_visible("#quick") and pg.locator("#q-list .qitem").count() == 12
    pg.fill("#q-input", "numéro 12"); pg.wait_for_timeout(100)
    assert "Carte de test numéro 12" in pg.locator("#q-list .qitem b").first.inner_text()
    pg.keyboard.press("ArrowDown"); pg.keyboard.press("ArrowUp"); pg.keyboard.press("Enter"); pg.wait_for_timeout(150)
    assert not pg.is_visible("#quick") and pg.is_visible("#modal"); pg.keyboard.press("Escape")
    pg.keyboard.press("Control+k"); pg.fill("#q-input", "march"); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    assert pg.is_visible("#tab-market") and not pg.is_visible("#quick")
    pg.click("[data-tab=collection]"); pg.keyboard.press("4"); pg.wait_for_timeout(200); assert pg.is_visible("#tab-trades"), "raccourci clavier : 4 = Échanges"
    pg.click("[data-tab=collection]"); pg.fill("#f-search", "4"); assert pg.is_visible("#tab-collection"), "taper un chiffre dans un champ ne change pas d'onglet"; pg.fill("#f-search", "")
    # son : préférence mémorisée, aperçu à l'activation
    pg.click("#btn-user"); assert pg.inner_text("#sound-t") == "Sons : désactivés"
    pg.click("#btn-sound"); pg.wait_for_timeout(150)
    assert "pref:sound=true" in pg.evaluate("window.__calls") and pg.inner_text("#sound-t") == "Sons : activés"
    pg.click("#btn-sound"); assert "pref:sound=false" in pg.evaluate("window.__calls"); pg.keyboard.press("Escape")

    # échanges (lecture seule) : reçues, envoyées, historique ; la pastille de l'onglet vient du profil
    assert pg.inner_text("#tab-trades-n") == "1"
    pg.click("[data-tab=trades]"); pg.wait_for_timeout(400)
    assert "load_trades:received" in pg.evaluate("window.__calls") and pg.locator(".trade").count() == 3
    txt = pg.inner_text("#t-list")
    assert "ami <b>x</b> te propose un échange" in txt and "« Salut <i>toi</i> »" in txt and "Ta proposition à zoé" in txt
    assert "En attente" in txt and "Refusé" in txt and "cet échange ne peut plus être conclu" in txt
    assert pg.locator(".trade").first.locator(".tcards .card").count() == 3 and "Tu donnes" in txt and "Tu reçois" in txt
    assert pg.locator("#t-list button").count() == 4, "trois boutons sur la proposition reçue, un sur ma proposition en attente, aucun sur l'échange terminé"
    pg.screenshot(path=str(out/"trades.png"))
    pg.click("#t-boxes [data-box=history]"); pg.wait_for_timeout(300)
    assert "load_trades:history" in pg.evaluate("window.__calls") and "Aucun échange terminé" in pg.inner_text("#t-list")
    n = calls(pg, "load_trades:history"); pg.evaluate("window.__events.push({event:'trade',data:{what:'new'}})"); pg.wait_for_timeout(1500)
    assert calls(pg, "load_trades:history") == n + 1, "un événement d'échange relit la liste affichée"

    # classement
    pg.click("[data-tab=rank]"); pg.wait_for_timeout(400)
    assert "load_ranking:tout" in pg.evaluate("window.__calls") and pg.locator(".rrow:not(.head)").count() == 3
    assert "#232" in pg.inner_text("#r-me") and "15 points pour dépasser rival" in pg.inner_text("#r-me")
    assert "Mythique 5" in pg.inner_text("#r-rule") and "Chromatique 12" in pg.inner_text("#r-rule")
    assert "Ada <b>x</b>" in pg.inner_text("#r-table")
    pg.screenshot(path=str(out/"rank.png"))
    pg.click("#r-periods [data-period=semaine]"); pg.wait_for_timeout(400)
    assert "load_ranking:semaine" in pg.evaluate("window.__calls") and pg.locator(".rrow.me").count() == 1
    assert "Remise à zéro dans 1 j 1 h" in pg.inner_text("#r-rule") and "#2" in pg.inner_text("#r-me")
    # session expirée pendant le flux : retour à la connexion, flux arrêté
    pg.evaluate("window.__events.push({event:'expired',data:{}})"); pg.wait_for_timeout(1400)
    assert pg.is_visible("#login") and calls(pg, "stop_stream") >= 1

    print("app errs (temps réel):", errs); assert not errs
    # --- statistiques (nouvelle page : la session précédente a été coupée)
    pg, errs = page(); pg.wait_for_timeout(1500)
    pg.click("[data-tab=stats]"); pg.wait_for_timeout(200); pg.screenshot(path=str(out/"stats.png"), full_page=True)
    assert pg.locator(".fig").count() == 6
    bank = {"C": 1, "PC": 3, "R": 10, "SR": 40, "UR": 100, "L": 500, "M": 2000}
    expected = sum((c["copies"] - 1) * bank[c["rarity"]] for c in cards if not c["locked"] and not c["shiny"] and c["copies"] > 1)
    fig = pg.locator(".fig", has_text="Doublons recyclables").inner_text().replace(chr(0xa0), " ")
    assert f"{expected:,}".replace(",", " ") + " Wikiki" in fig and "hors verrouillées et chromatiques" in fig, (expected, fig)
    # préférences restaurées au démarrage : tri de la collection, vue et tri du marché, son
    pp, errp = page(prefs={"collection_sort": "reads", "market_view": "list", "market_sort": "prix", "sound": True}); pp.wait_for_timeout(1500)
    assert pp.input_value("#f-sort") == "reads" and pp.inner_text("#sound-t") == "Sons : activés"
    pp.click("[data-tab=market]"); pp.wait_for_timeout(500)
    assert "list" in pp.get_attribute("#mgrid", "class") and pp.input_value("#m-sort") == "prix" and "load_market:live:0:::prix:" in pp.evaluate("window.__calls")
    assert not errp

    # ================= écritures manuelles : page à part, l'état du faux serveur repart de zéro =================
    pw, errw = page(); pw.wait_for_timeout(1500)
    W = lambda name: calls(pw, name)
    toast = lambda: pw.inner_text("#toast")

    # --- miser : deux pressions, jamais avant la seconde ; la confirmation retombe seule ; une action à la fois
    pw.click("[data-tab=market]"); pw.wait_for_timeout(2400)
    btn = pw.locator("#mgrid .offer[data-id='11'] .bid")
    assert btn.inner_text() == "Miser 121" and pw.locator("#mgrid .offer[data-id='13'] .bid").count() == 0
    pw.screenshot(path=str(out/"w-market.png"))
    btn.click(); pw.wait_for_timeout(80)
    assert btn.inner_text() == "Confirmer : miser 121 Wikiki" and W("bid:11:121") == 0, "première pression : rien ne part"
    pw.wait_for_timeout(5000); assert btn.inner_text() == "Miser 121" and W("bid:11:121") == 0, "la confirmation retombe seule"
    btn.click(); pw.wait_for_timeout(80); btn.click(); pw.wait_for_timeout(700)
    assert W("bid:11:121") == 1 and "Mise placée : tu es en tête." in toast()
    assert W("auction_get:11") == 1 and "Tu es en tête" in pw.locator("#mgrid .offer[data-id='11']").inner_text() and pw.locator("#mgrid .offer[data-id='11'] .bid").count() == 0
    pw.evaluate("window.__bidDelay = 900")
    a, b2 = pw.locator("#mgrid .offer[data-id='12'] .bid"), pw.locator("#mgrid .offer[data-id='112'] .bid")
    a.click(); a.click(); pw.wait_for_timeout(100); b2.click(); b2.click(); pw.wait_for_timeout(150)
    assert "Une action est déjà en cours." in toast() and W("bid:12:122") == 1 and W("bid:112:222") == 0, "une seule action à la fois"
    pw.wait_for_timeout(1200); pw.evaluate("window.__bidDelay = 0")
    own = pw.locator("#mgrid .offer[data-id='13']")
    own.locator(".priceedit input").fill("0"); own.locator(".priceedit button").click(); pw.wait_for_timeout(100)
    assert "au moins 1 Wikiki" in toast() and W("auction_price:13:0") == 0, "saisie invalide : refusée avant toute confirmation"
    own.locator(".priceedit input").fill("55"); own.locator(".priceedit button").click(); pw.wait_for_timeout(500)
    assert W("auction_price:13:55") == 1 and "Mise de départ changée : 55 Wikiki." in toast()
    cancel = pw.locator("#mgrid .offer[data-id='13'] button.danger")
    cancel.click(); pw.wait_for_timeout(80); assert "Confirmer l'annulation" in cancel.inner_text() and W("auction_cancel:13") == 0
    cancel.click(); pw.wait_for_timeout(500)
    assert W("auction_cancel:13") == 1 and pw.locator("#mgrid .offer[data-id='13']").count() == 0 and "annulée" in toast()

    # --- la fiche d'une carte : recycler, mettre aux enchères, verrouiller, mettre de côté, souhaits, miser
    pw.click("[data-tab=collection]"); pw.wait_for_timeout(300)
    cidw = pw.evaluate("S.filtered[0].cid")
    pw.locator("#grid .card").first.click(); pw.wait_for_timeout(500)
    rec = pw.locator("[data-act=recycle]")
    assert "Recycler · +500 Wikiki" in rec.inner_text()
    rec.click(); pw.wait_for_timeout(80)
    assert "Vraiment ? Ta légendaire contre 500 Wikiki" in rec.inner_text() and W("recycle:1:5001") == 0
    rec.click(); pw.wait_for_timeout(600)
    assert W("recycle:1:5001") == 1 and "Carte recyclée : +500 Wikiki" in toast() and W("load_card:" + cidw) == 2, "la fiche se relit après l'action"
    form = pw.locator(".auctform"); go = pw.locator("[data-act=auction]")
    form.locator("input").fill("0"); go.click(); pw.wait_for_timeout(100)
    assert "au moins 1 Wikiki" in toast() and W("auction_create:5001:0:10m") == 0 and "Confirmer" not in go.inner_text()
    form.locator("input").fill("77"); form.locator("select").select_option("1h")
    go.click(); pw.wait_for_timeout(80)
    assert "Confirmer : lancer à 77 Wikiki" in go.inner_text() and W("auction_create:5001:77:1h") == 0
    go.click(); pw.wait_for_timeout(500); assert W("auction_create:5001:77:1h") == 1
    pw.locator("[data-act=lock]").click(); pw.wait_for_timeout(500); assert W("lock:5001:true") == 1
    pw.locator("[data-act=unlock]").click(); pw.wait_for_timeout(500); assert W("lock:5002:false") == 1
    pw.locator("[data-act=forsale]").click(); pw.wait_for_timeout(500); assert W("forsale:5001:true") == 1
    pw.locator("[data-act=wish]").click(); pw.wait_for_timeout(500); assert ("wish:%s:false" % cidw) in pw.evaluate("window.__calls")
    mb = pw.locator(".mauc .bid"); assert mb.inner_text() == "Miser 141"
    mb.click(); pw.wait_for_timeout(80); mb.click(); pw.wait_for_timeout(500); assert W("bid:31:141") == 1
    pw.screenshot(path=str(out/"actions.png")); pw.keyboard.press("Escape")

    # --- échanges : accepter (confirmation), refuser, annuler, contre-proposer, proposer
    pw.click("[data-tab=trades]"); pw.wait_for_timeout(600)
    assert pw.locator(".trade").count() == 3 and pw.locator("#t-list button").count() == 4
    pw.screenshot(path=str(out/"w-trades.png"))
    acc = pw.locator(".trade >> nth=0").locator("button.primary")
    acc.click(); pw.wait_for_timeout(80); assert "Confirmer l'échange" in acc.inner_text() and W("trade:accept:5") == 0
    acc.click(); pw.wait_for_timeout(600); assert W("trade:accept:5") == 1 and "Échange conclu" in toast()
    pw.locator(".trade >> nth=0").locator("button.danger").click(); pw.wait_for_timeout(500); assert W("trade:decline:5") == 1
    mine7 = pw.locator(".trade >> nth=1").locator("button.danger")
    mine7.click(); pw.wait_for_timeout(80); assert "Confirmer l'annulation" in mine7.inner_text() and W("trade:cancel:7") == 0
    mine7.click(); pw.wait_for_timeout(500); assert W("trade:cancel:7") == 1
    pw.locator(".trade >> nth=0").locator("button", has_text="Contre-proposer").click(); pw.wait_for_timeout(600)
    assert pw.is_visible("#dialog") and "Contre-proposition à ami <b>x</b>" in pw.inner_text("#dialog-body h2") and W("user_cards:ami <b>x</b>") == 1
    assert pw.locator("#tc-grid-take .card").count() == 2 and pw.locator("#tc-grid-give .card").count() == 60, "60 cartes affichées, le reste à la demande"
    pw.screenshot(path=str(out/"w-composer.png"))
    pw.locator("#tc-grid-take .card").first.click(); pw.locator("#tc-grid-give .card").first.click(); pw.wait_for_timeout(100)
    assert pw.locator("#tc-grid-take .card.picked").count() == 1 and pw.inner_text("#tc-n-take") == "1" and pw.inner_text("#tc-n-give") == "1"
    pw.locator("#tc-grid-take .card").first.click(); pw.wait_for_timeout(50)
    assert pw.inner_text("#tc-n-take") == "2", "un deuxième clic ajoute un autre exemplaire du même groupe"
    pw.locator("#tc-grid-take .card").first.click(); pw.locator("#tc-grid-take .card").first.click(); pw.wait_for_timeout(50)
    assert pw.inner_text("#tc-n-take") == "1" or pw.inner_text("#tc-n-take") == "0"
    pw.fill("#tc-coins-give", "5"); pw.fill("#tc-msg", "Deal ?")
    give_id = pw.evaluate("TC.give[0].id"); take_ids = pw.evaluate("TC.take.map(x => x.id)")
    if not take_ids:
        pw.locator("#tc-grid-take .card").first.click(); take_ids = pw.evaluate("TC.take.map(x => x.id)")
    send = pw.locator("#dialog-body .composer button.primary")
    send.click(); pw.wait_for_timeout(80)
    assert "Confirmer : envoyer à ami <b>x</b> (1 carte contre 1 carte)" in send.inner_text() and W("tradesend:" + __import__("json").dumps(["ami <b>x</b>", [give_id], take_ids, 5, 0, "Deal ?", 5], separators=(",", ":"))) == 0
    send.click(); pw.wait_for_timeout(600)
    sent_calls = [c for c in pw.evaluate("window.__calls") if c.startswith("tradesend:")]
    assert len(sent_calls) == 1 and __import__("json").loads(sent_calls[0][10:]) == ["ami <b>x</b>", [give_id], take_ids, 5, 0, "Deal ?", 5]
    assert not pw.is_visible("#dialog") and "Contre-proposition envoyée" in toast()
    pw.click("#t-new"); pw.wait_for_timeout(400)
    assert pw.locator("#dialog .frow").count() == 2 and "ami <b>x</b>" in pw.inner_text("#dialog"); pw.locator("#dialog .frow").first.click(); pw.wait_for_timeout(500)
    empty_send = pw.locator("#dialog-body .composer button.primary"); empty_send.click(); pw.wait_for_timeout(100)
    assert "L'échange est vide" in toast() and "Confirmer" not in empty_send.inner_text()
    pw.keyboard.press("Escape"); assert not pw.is_visible("#dialog")

    # --- corbeille, doublons, journal
    pw.click("#btn-user"); pw.click("#btn-corb"); pw.wait_for_timeout(500)
    assert pw.locator(".corbslot").count() == 2 and "20 minutes" in pw.inner_text("#dialog-body")
    pw.screenshot(path=str(out/"w-corbeille.png"))
    pw.locator(".corbslot button").first.click(); pw.wait_for_timeout(500); assert W("restore:[801]:false") == 1
    allb = pw.locator("#dialog-body .row button.primary"); allb.click(); pw.wait_for_timeout(80)
    assert "Confirmer : 8 Wikiki" in allb.inner_text() and W("restore:null:true") == 0; allb.click(); pw.wait_for_timeout(500); assert W("restore:null:true") == 1
    emp = pw.locator("#dialog-body .row button.danger"); emp.click(); pw.wait_for_timeout(80); assert "effacer 2 cartes pour de bon" in emp.inner_text() and W("empty") == 0
    emp.click(); pw.wait_for_timeout(500); assert W("empty") == 1; pw.keyboard.press("Escape")
    bank = {"C": 1, "PC": 3, "R": 10, "SR": 40, "UR": 100, "L": 500, "M": 2000}
    spare = {}
    for c in cards:
        if not c["shiny"] and c["copies"] > 1 and c["free_ids"]:
            spare.setdefault(c["rarity"], []).extend(c["free_ids"][1:])
    exp_ids = set(spare.get("C", []) + spare.get("PC", []))
    exp_gain = sum(len(spare.get(k, [])) * bank[k] for k in ("C", "PC"))
    pw.click("[data-tab=stats]"); pw.wait_for_timeout(300); pw.click("text=Recycler les doublons…"); pw.wait_for_timeout(300)
    gob = pw.locator("#dialog-body .row button.danger")
    assert gob.inner_text() == "Recycler %d cartes · +%d Wikiki" % (len(exp_ids), exp_gain), (gob.inner_text(), len(exp_ids), exp_gain)
    assert pw.locator(".duprow input:checked").count() == 2 and not pw.inner_text(".dupsum").strip()
    pw.screenshot(path=str(out/"w-dups.png"))
    rare_box = pw.locator(".duprow", has_text="Épique").locator("input"); rare_box.check(); pw.wait_for_timeout(80)
    assert "Attention" in pw.inner_text(".dupsum"); rare_box.uncheck(); pw.wait_for_timeout(80)
    gob.click(); pw.wait_for_timeout(80); assert "Confirmer : %d cartes" % len(exp_ids) in gob.inner_text() and pw.evaluate("window.__recycled.length") == 1, "rien de plus n'est parti avant la seconde pression"
    gob.click(); pw.wait_for_timeout(1500)
    rec_calls = [c for c in pw.evaluate("window.__calls") if c.startswith("recycle:") and c != "recycle:1:5001"]
    assert len(rec_calls) == -(-len(exp_ids) // 50) and set(pw.evaluate("window.__recycled")) - {5001} == exp_ids and len(pw.evaluate("window.__recycled")) - 1 == len(exp_ids), "par paquets de 50, chaque exemplaire une seule fois"
    assert "Récupérables 20 minutes" in toast()
    pw.click("#btn-user"); pw.click("#btn-actlog"); pw.wait_for_timeout(300)
    assert pw.locator(".arow2").count() >= 10 and "Recyclage" in pw.inner_text("#dialog-body") and pw.locator(".arow2.bad").count() == 0; pw.keyboard.press("Escape")

    # --- paquet doré : seulement si le profil l'indique ; WIKI-PRO : seulement si le profil est abonné
    pw.click("[data-tab=packs]"); pw.wait_for_timeout(300)
    assert not pw.is_visible("#btn-gold")
    pw.evaluate("S.data.me.paquetOr = 1; renderHeader()")
    assert pw.inner_text("#btn-gold") == "Ton paquet doré offert · 20 cartes"
    pw.click("#btn-gold"); pw.wait_for_timeout(1500)
    assert W("open_gold") == 1 and pw.locator(".pcard").count() == 2 and W("open_pack") == 0
    pw.click("#btn-flip-all"); pw.wait_for_timeout(700); pw.click("#btn-done"); pw.wait_for_timeout(500)
    assert not pw.is_visible("#btn-gold"), "plus de paquet doré une fois ouvert"
    # vérification « es-tu un robot ? » : la question du site s'affiche, rien ne part avant le clic du joueur
    pw.evaluate("S.data.me.defi = 1; renderHeader()")
    pw.click("#btn-open"); pw.wait_for_timeout(400)
    assert pw.is_visible("#dialog") and "Clique sur la goutte <b>x</b>" in pw.inner_text("#dialog-body") and W("open_pack") == 0
    assert pw.locator(".defi-c").count() == 6 and pw.locator(".defi-c svg path").count() == 5 and pw.locator(".defi-c:disabled").count() == 1
    assert pw.locator("#dialog-body b").count() == 0, "la consigne reste du texte"
    pw.screenshot(path=str(out/"w-defi.png"))
    pw.keyboard.press("Escape"); pw.wait_for_timeout(200)
    assert not pw.is_visible("#dialog") and W("open_pack") == 0 and not pw.evaluate("PK.opening"), "Échap : on renonce, rien n'est envoyé"
    pw.click("#btn-open"); pw.wait_for_timeout(400)
    pw.click("#dialog-body button >> text=Une autre question"); pw.wait_for_timeout(400)
    assert W("pack_challenge") == 3 and pw.is_visible("#dialog")
    pw.click(".defi-c[data-rep='1']"); pw.wait_for_timeout(1500)
    assert W("open_pack_proof:ZheyznhTbvnkI4we:1") == 1 and W("open_pack") == 1 and pw.is_visible("#reveal") and not pw.is_visible("#dialog")
    pw.click("#btn-flip-all"); pw.wait_for_timeout(700); pw.click("#btn-done"); pw.wait_for_timeout(500)
    pw.click("[data-tab=collection]"); pw.wait_for_timeout(200)
    pw.locator("#grid .card").nth(1).click(); pw.wait_for_timeout(500)
    assert "réservé aux abonnés WIKI-PRO" in pw.inner_text("#pro-extra") and not [c for c in pw.evaluate("window.__calls") if c.startswith("pro_market")], "rien n'est demandé au site sans abonnement"
    pw.keyboard.press("Escape"); pw.evaluate("S.data.me.pro = true; SHEETS.clear()")
    pw.locator("#grid .card").nth(1).click(); pw.wait_for_timeout(700)
    pro = pw.inner_text("#pro-extra")
    assert "Vue du marché (WIKI-PRO)" in pro and "Moyenne" in pro and "100" in pro and pw.locator("#pro-extra svg.chart").count() == 1
    pw.locator("#pro-extra button", has_text="Toutes les").click(); pw.wait_for_timeout(150)
    assert "Autre carte" in pw.inner_text("#pro-extra") and len([c for c in pw.evaluate("window.__calls") if c.startswith("pro_market")]) == 1
    pw.screenshot(path=str(out/"pro.png")); pw.keyboard.press("Escape")

    # --- arène : défier, composer, invitation, decks, Mini-Pack, duel rejoué
    pw.click("[data-tab=arena]"); pw.wait_for_timeout(500)
    lob = pw.inner_text("#cb-body")
    assert "Combats disponibles : 4 / 5" in lob and "★ ami <b>x</b>" in lob
    assert pw.locator("#cb-body .cbplayer").count() == 4 and pw.locator("#cb-body .cbplayer button", has_text="Affronter").count() == 1, "seul le joueur libre est défiable"
    assert "Pas prêt" in lob and "Hors ligne" in lob and "Victoire" in lob and "Défaite" in lob and "Un Mini-Pack t'attend" in lob
    assert pw.locator("#cb-body .cbplayer b b").count() == 0, "pas de HTML injecté"
    pw.screenshot(path=str(out/"c-lobby.png"))
    # Mini-Pack : un clic = un coffre
    pw.locator("#cb-chest button", has_text="Ouvrir le Mini-Pack").click(); pw.wait_for_timeout(500)
    assert W("chest") == 1 and "+120" in pw.inner_text("#cb-chest") and "Trouvaille <b>x</b>" in pw.inner_text("#cb-chest")
    # recherche de joueur
    pw.fill("#cb-body input[type=search]", "tro"); pw.wait_for_timeout(600)
    assert W("users:tro") == 1 and "trouvé <b>x</b>" in pw.inner_text("#cb-res")
    # défier : un clic, puis l'attente
    pw.locator("#cb-body .cbplayer button", has_text="Affronter").first.click(); pw.wait_for_timeout(400)
    assert W("challenge:ami <b>x</b>") == 1 and "En attente de ami <b>x</b>" in pw.inner_text("#cb-body")
    # l'autre accepte (événement du flux) : on compose
    pw.evaluate("window.__events.push({event:'combat',data:{what:'accepte',id:77,nom:'ami <b>x</b>',expire:window.__now+120}})"); pw.wait_for_timeout(1600)
    assert "Ton équipe, 0 / 3" in pw.inner_text("#cb-body") and pw.locator("#cb-body button", has_text="Valider mon équipe").is_disabled()
    for i in range(3):
        pw.locator("#cb-grid .card").nth(i).click(); pw.wait_for_timeout(60)
    pw.wait_for_timeout(500)
    assert "Ton équipe, 3 / 3" in pw.inner_text("#cb-body") and W("choice:77:3") >= 1 and not pw.locator("#cb-body button", has_text="Valider mon équipe").is_disabled()
    pw.locator("#cb-grid .card").nth(5).click(); pw.wait_for_timeout(80)
    assert "Ton équipe, 3 / 3" in pw.inner_text("#cb-body"), "une quatrième carte est refusée"
    pw.evaluate("window.__events.push({event:'combat',data:{what:'choix',id:77,cards:[{cid:'fr:X1',name:'Sienne <b>x</b>',rarity:'UR',reads:1,img:null}]}})"); pw.wait_for_timeout(1300)
    assert "Sienne <b>x</b>" in pw.inner_text("#cb-adv") and pw.locator("#cb-adv b").count() == 0
    pw.evaluate("window.__events.push({event:'combat',data:{what:'pret',id:77}})"); pw.wait_for_timeout(1300)
    assert "a validé son équipe" in pw.inner_text("#cb-advstate")
    pw.screenshot(path=str(out/"c-prep.png"))
    pw.locator("#cb-body button", has_text="Valider mon équipe").click(); pw.wait_for_timeout(700)
    assert W("team:77:3") == 1 and pw.locator("#arena").count() == 1
    pw.wait_for_timeout(1200); pw.screenshot(path=str(out/"c-duel.png"))
    pw.locator("#arActs button").click(); pw.wait_for_timeout(2500)
    end = pw.inner_text("#arEnd")
    assert "Victoire" in end and "2 – 1" in end and "+45" in end and pw.locator("#arena b b").count() == 0
    pw.screenshot(path=str(out/"c-end.png"))
    pw.locator("#arEnd button", has_text="Retour à l'arène").click(); pw.wait_for_timeout(500)
    assert "Combats disponibles" in pw.inner_text("#cb-body")
    # invitation reçue : bannière visible depuis n'importe quel onglet, refus puis acceptation
    pw.click("[data-tab=stats]"); pw.wait_for_timeout(200)
    pw.evaluate("window.__events.push({event:'combat',data:{what:'defi',id:88,expire:window.__now+60,from:'rival <i>'}})"); pw.wait_for_timeout(1500)
    assert pw.is_visible("#cb-invite") and "rival <i> te défie" in pw.inner_text("#cb-invite") and pw.is_visible("#tab-arena-dot")
    pw.screenshot(path=str(out/"c-invite.png"))
    pw.locator("#cb-invite button", has_text="Refuser").click(); pw.wait_for_timeout(500)
    assert W("answer:88:false") == 1 and not pw.is_visible("#cb-invite")
    pw.evaluate("window.__events.push({event:'combat',data:{what:'defi',id:89,expire:window.__now+60,from:'rival <i>'}})"); pw.wait_for_timeout(1500)
    pw.locator("#cb-invite button", has_text="Accepter le combat").click(); pw.wait_for_timeout(700)
    assert W("answer:89:true") == 1 and "Équipe de rival <i>" in pw.inner_text("#cb-body")
    ab = pw.locator("#cb-body button", has_text="Abandonner"); ab.click(); pw.wait_for_timeout(100)
    assert W("cancel:89") == 0, "abandonner demande confirmation"
    pw.locator("#cb-body button[class*=danger]").click(); pw.wait_for_timeout(500)
    assert W("cancel:89") == 1 and "Combats disponibles" in pw.inner_text("#cb-body")
    # decks : création (nom obligatoire), suppression avec confirmation
    pw.locator("#cb-body button", has_text="Mes decks").click(); pw.wait_for_timeout(400)
    pw.locator("#cb-body button", has_text="Nouveau deck").click(); pw.wait_for_timeout(300)
    assert pw.locator("#cb-body button", has_text="Enregistrer le deck").is_disabled()
    for i in range(3):
        pw.locator("#cb-body .cbpick .card").nth(i).click(); pw.wait_for_timeout(60)
    pw.fill("#cb-body input.field[maxlength]", "Mes <b>forts</b>")
    pw.locator("#cb-body button", has_text="Enregistrer le deck").click(); pw.wait_for_timeout(500)
    assert W("deck_save:0:Mes <b>forts</b>:3") == 1 and "Mes <b>forts</b>" in pw.inner_text("#cb-body")
    pw.screenshot(path=str(out/"c-decks.png"))
    d = pw.locator("#cb-body button[class*=danger]"); d.click(); pw.wait_for_timeout(100)
    assert W("deck_del:9") == 0; d.click(); pw.wait_for_timeout(400); assert W("deck_del:9") == 1
    # ================= communauté et récompenses =================
    # --- messagerie : conversations, fil, envoi (Entrée), HTML des autres = texte, message en direct
    pw.click("[data-tab=messages]"); pw.wait_for_timeout(500)
    assert W("conversations") >= 1 and pw.locator("#ms-list .conv").count() == 2 and pw.locator("#ms-list b b, #ms-list i").count() == 0
    assert "salut <i>toi</i>" in pw.inner_text("#ms-list") and pw.inner_text("#page-title") == "Messages"
    pw.locator("#ms-list .conv").first.click(); pw.wait_for_timeout(500)
    assert W("thread:ami <b>x</b>") >= 1 and pw.locator("#ms-body .bub").count() == 2 and pw.locator("#ms-body .bub.mine").count() == 1
    assert "Salut <b>toi</b>" in pw.inner_text("#ms-body") and pw.locator("#ms-body b").count() == 0
    pw.screenshot(path=str(out/"s-messages.png"))
    ta = pw.locator("#ms-thread textarea"); ta.fill("   "); ta.press("Enter"); pw.wait_for_timeout(200)
    assert not [c for c in pw.evaluate("window.__calls") if c.startswith("msg:")], "un message vide ne part pas"
    ta.fill("Bonjour <b>!</b>"); ta.press("Enter"); pw.wait_for_timeout(500)
    assert W("msg:ami <b>x</b>:Bonjour <b>!</b>") == 1 and pw.input_value("#ms-thread textarea") == ""
    n = W("conversations")
    pw.evaluate("window.__events.push({event:'message',data:{from:'zoé'}})"); pw.wait_for_timeout(1400)
    assert W("conversations") == n + 1, "un message en direct relit la liste des conversations"
    pw.fill("#ms-find", "tro"); pw.wait_for_timeout(600)
    assert W("players:tro") == 1 and pw.locator("#ms-found .conv").count() == 2
    pw.locator("#ms-found .conv").first.click(); pw.wait_for_timeout(500); assert W("thread:trouvé <b>x</b>") >= 1

    # --- amis : accepter, favori, retirer (confirmation), chercher et ajouter
    pw.click("[data-tab=friends]"); pw.wait_for_timeout(500)
    assert pw.locator("#fr-main .urow").count() == 4 and "Demandes reçues · 1" in pw.inner_text("#fr-main")
    pw.screenshot(path=str(out/"s-friends.png"))
    pw.locator("#fr-main .urow", has_text="nouveau").locator("button", has_text="Accepter").click(); pw.wait_for_timeout(400)
    assert W("friend:accept:nouveau") == 1 and "maintenant ami(e)s" in pw.inner_text("#toast")
    pw.locator("#fr-main .urow", has_text="ami <b>x</b>").locator(".star").click(); pw.wait_for_timeout(300)
    assert W("fav:ami <b>x</b>:false") == 1
    rm = pw.locator("#fr-main .urow", has_text="zoé").locator("button.danger-text"); rm.click(); pw.wait_for_timeout(80)
    assert W("friend:remove:zoé") == 0 and "Confirmer" in rm.inner_text(); rm.click(); pw.wait_for_timeout(400)
    assert W("friend:remove:zoé") == 1
    pw.fill("#fr-find", "tro"); pw.wait_for_timeout(600)
    assert pw.locator("#fr-found .urow").count() == 2 and pw.locator("#fr-found b b").count() == 0
    pw.locator("#fr-found .urow").first.locator("button", has_text="Ajouter").click(); pw.wait_for_timeout(400)
    assert W("friend:request:trouvé <b>x</b>") == 1

    # --- profils : celui d'un ami (depuis un pseudo), sa collection page par page ; puis le mien depuis le rail
    pw.fill("#fr-find", ""); pw.wait_for_timeout(300)
    pw.locator("#fr-main .who-link", has_text="zoé").first.click(); pw.wait_for_timeout(700)
    assert W("profile:zoé") == 1 and pw.inner_text("#page-title") == "Profil de zoé" and pw.is_visible("#tab-profile")
    txt = pw.inner_text("#pf-body")
    assert "Ma bio <b>x</b>" in txt and "#232" in txt and "[WIKI] Encyclo <i>" in txt and "Mes <b>belles</b>" in txt and pw.locator("#pf-body .vitrine .card").count() == 1
    assert W("pcards:zoé:0:") == 1 and pw.locator("#pf-grid .card").count() == 1 and "Sa carte <b>0</b>" in pw.inner_text("#pf-grid")
    pw.screenshot(path=str(out/"s-profile.png"), full_page=True)
    pw.click("#pf-pager button >> text=Suivant →"); pw.wait_for_timeout(400); assert W("pcards:zoé:1:") == 1
    pw.click("#pf-body button >> text=Message"); pw.wait_for_timeout(500); assert pw.is_visible("#tab-messages") and W("thread:zoé") >= 1
    pw.click("[data-tab=profile]"); pw.wait_for_timeout(600)
    assert W("profile:") == 1 and pw.inner_text("#page-title") == "Profil" and pw.locator("#pf-body button", has_text="Bloquer").count() == 0

    # --- guilde : fil (j'aime, commentaires), tchat (vu, envoi), membres (exclure : confirmation), pastille en direct
    pw.click("[data-tab=stats]"); pw.wait_for_timeout(200)
    assert pw.is_visible("#tab-guild-dot"), "un message de guilde non lu : pastille"
    pw.click("[data-tab=guild]"); pw.wait_for_timeout(600)
    assert W("guilds") >= 1 and W("guild:3") >= 1 and pw.locator(".gf").count() == 1 and "Légendaire <b>x</b>" in pw.inner_text("#gd-body")
    pw.screenshot(path=str(out/"s-guild.png"))
    pw.locator(".gf .pact").first.click(); pw.wait_for_timeout(300)
    assert W("gact:like:9:null") == 1 and pw.locator(".gf .pact.on").count() >= 1
    pw.locator(".gf .pact").nth(1).click(); pw.wait_for_timeout(200)
    assert "Bravo <b>!</b>" in pw.inner_text(".gcom")
    pw.locator(".gcom textarea").fill("Superbe"); pw.locator(".gcom textarea").press("Enter"); pw.wait_for_timeout(500)
    assert W('gact:comment:9:"Superbe"') == 1
    pw.click(".gd-tabs button >> text=Tchat"); pw.wait_for_timeout(400)
    assert W("gseen") == 1 and not pw.is_visible("#tab-guild-dot") and pw.locator("#gd-chat .bub").count() == 2 and pw.locator("#gd-chat i").count() == 0
    pw.screenshot(path=str(out/"s-guild-chat.png"))
    pw.locator(".gd-chatwrap textarea").fill("Hello guilde"); pw.locator(".gd-chatwrap textarea").press("Enter"); pw.wait_for_timeout(500)
    assert W('gact:chat:null:"Hello guilde"') == 1
    pw.click(".gd-tabs button >> text=Membres"); pw.wait_for_timeout(300)
    kick = pw.locator("#gd-tab .grow", has_text="Bob").locator("button.danger-text"); kick.click(); pw.wait_for_timeout(80)
    assert W('gact:kick:"Bob":null') == 0; kick.click(); pw.wait_for_timeout(400); assert W('gact:kick:"Bob":null') == 1
    pw.click(".gd-tabs button >> text=Demandes"); pw.wait_for_timeout(300)
    pw.locator("#gd-tab button", has_text="Accepter").click(); pw.wait_for_timeout(400); assert W('gact:apply/accept:"Zoé":null') == 1
    leave = pw.locator("#gd-body button", has_text="Quitter la guilde"); leave.click(); pw.wait_for_timeout(80)
    assert W("gact:leave:null:null") == 0, "quitter la guilde demande confirmation"
    pw.click("[data-tab=stats]"); pw.wait_for_timeout(200)
    pw.evaluate("window.__events.push({event:'guild',data:{what:'chat',id:3,mid:20,par:5}})"); pw.wait_for_timeout(1400)
    assert pw.is_visible("#tab-guild-dot")

    # --- récompenses : quêtes, bienvenue, série, succès ; réclamer = un clic
    assert pw.is_visible("#tab-rewards-dot"), "une quête accomplie non réclamée : pastille"
    pw.click("[data-tab=rewards]"); pw.wait_for_timeout(600)
    rw = pw.inner_text("#rw-body")
    assert W("ach") >= 1 and "Série de connexion" in rw and pw.locator(".sday").count() == 7 and pw.locator(".sday.done").count() == 2
    assert "Ouvre 3 paquets" in rw and "Mini <b>x</b>" in rw and "Quêtes de bienvenue" in rw and "10 cartes <b>x</b>" in rw and pw.locator("#rw-body b b").count() == 0
    assert "Prochaine récompense dans" in rw
    pw.screenshot(path=str(out/"s-rewards.png"), full_page=True)
    pw.locator(".quest.ready button").click(); pw.wait_for_timeout(400)
    assert W("claim:quete:2") == 1 and "Récompense <b>x</b>" in pw.inner_text("#toast")
    pw.locator(".wrow button", has_text="Réclamer").click(); pw.wait_for_timeout(400); assert W('claim:bienvenue:"b1"') == 1
    pw.locator(".ach.ready button").click(); pw.wait_for_timeout(400); assert W('claim:succes:"c10"') == 1
    pw.evaluate("S.data.rewards.streak.ready = true; renderSocialBadges()"); pw.wait_for_timeout(200)
    pw.locator(".rw-card.streak button", has_text="Récupérer le jour 3").click(); pw.wait_for_timeout(500)
    assert W("claim:serie:null") == 1 and "Jour 3 : Un paquet doré" in pw.inner_text("#toast")
    pw.keyboard.press("8"); pw.wait_for_timeout(300); assert pw.is_visible("#tab-friends"), "raccourci clavier : 8 = Amis"

    assert not errw, errw
    for tab in ("collection", "packs", "market", "trades", "arena", "rank", "stats", "messages", "friends", "guild", "profile", "rewards"):
        pw.click("[data-tab=%s]" % tab); pw.wait_for_timeout(400)
        shown = pw.inner_text("body"); assert "[object" not in shown and "undefined" not in shown and "NaN" not in shown, tab

    # fenêtre à la taille minimale (900 px) : la barre du haut doit tenir
    pn, errn = page(width=900); pn.wait_for_timeout(1500)
    over = pn.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    pn.screenshot(path=str(out/"narrow.png")); assert not over, "défilement horizontal à 900 px"; assert not errn
    for tab in ("collection", "packs", "market", "trades", "arena", "rank", "stats", "messages", "friends", "guild", "profile", "rewards"):
        pg.click("[data-tab=%s]" % tab); pg.wait_for_timeout(500)
        shown = pg.inner_text("body")
        assert "[object" not in shown and "undefined" not in shown and "NaN" not in shown, (tab, [w for w in ("[object", "undefined", "NaN") if w in shown])
    print("html injection nodes (should be 0):", pg.locator("#grid b, #grid img[src=x]").count())
    print("app errs:", errs)
    assert not errs
    b.close()
print("OK")
