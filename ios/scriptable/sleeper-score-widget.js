// Sleeper Score — Dark, Avatars, Legacy-JS Compatible (Scriptable)
// Widget original del que nace la app de ios/. Se guarda aquí tal cual para
// poder comparar: la app hace lo mismo con las mismas llamadas a Sleeper.

var LEAGUE_ID = "1263745758830530560";
var ROSTER_ID = 1;
var ACCENT_HEX = "#6EE7B7"; // mint

// ====== UTILS ======
function hex(c){ return new Color(c); }
function fmt(n){
  if (n === undefined || n === null) return "0.0";
  var num = Number(n);
  if (isNaN(num)) num = 0;
  return num.toFixed(1);
}
function nowHM(){
  var d = new Date();
  var h = d.getHours();
  var m = d.getMinutes();
  if (h < 10) h = "0" + h;
  if (m < 10) m = "0" + m;
  return h + ":" + m;
}
async function getJSON(url){
  var r = new Request(url);
  r.timeoutInterval = 10;
  return await r.loadJSON();
}
async function loadImage(url){
  try {
    var r = new Request(url);
    r.timeoutInterval = 10;
    return await r.loadImage();
  } catch(e){
    return null;
  }
}
function clamp(n,min,max){
  return Math.max(min, Math.min(max, n));
}
function ell(s,n){
  if (!s) return "";
  return s.length > n ? s.slice(0, n-1) + "…" : s;
}

// ====== DATA ======
async function fetchData(){
  var state = await getJSON("https://api.sleeper.app/v1/state/nfl");
  var week = (state && state.display_week) ? state.display_week : state.week;

  var league = await getJSON("https://api.sleeper.app/v1/league/" + LEAGUE_ID);
  var users = await getJSON("https://api.sleeper.app/v1/league/" + LEAGUE_ID + "/users");
  var rosters = await getJSON("https://api.sleeper.app/v1/league/" + LEAGUE_ID + "/rosters");
  var matchups = await getJSON("https://api.sleeper.app/v1/league/" + LEAGUE_ID + "/matchups/" + week);

  // find "me" by roster_id
  var me = null;
  for (var i=0; i<matchups.length; i++){
    if (matchups[i].roster_id === ROSTER_ID){ me = matchups[i]; break; }
  }
  if (!me) throw new Error("Your roster_id wasn't found for this week.");

  // find opponent: same matchup_id, different roster_id
  var opp = null;
  for (var j=0; j<matchups.length; j++){
    var m = matchups[j];
    if (m.matchup_id === me.matchup_id && m.roster_id !== ROSTER_ID){ opp = m; break; }
  }

  // roster_id -> owner_id
  var rosterToOwner = {};
  for (var k=0; k<rosters.length; k++){
    var r = rosters[k];
    rosterToOwner[r.roster_id] = r.owner_id;
  }

  // user_id -> {name, avatarUrl}
  var userMap = {};
  for (var u=0; u<users.length; u++){
    var usr = users[u];
    var teamName = (usr.metadata && usr.metadata.team_name) ? usr.metadata.team_name :
                   (usr.display_name ? usr.display_name : "Team");
    var avatarUrl = usr.avatar ? ("https://sleepercdn.com/avatars/" + usr.avatar) : null;
    userMap[usr.user_id] = { name: teamName, avatarUrl: avatarUrl };
  }

  var myOwnerId = rosterToOwner[me.roster_id];
  var myUser = userMap[myOwnerId] || {name: "You", avatarUrl: null};

  var oppUser = {name: "Opponent", avatarUrl: null};
  if (opp){
    var oppOwnerId = rosterToOwner[opp.roster_id];
    oppUser = userMap[oppOwnerId] || {name: "Opponent", avatarUrl: null};
  }

  var myPts = (me.points !== undefined && me.points !== null) ? Number(me.points) : 0;
  var oppPts = opp ? ((opp.points !== undefined && opp.points !== null) ? Number(opp.points) : 0) : 0;

  // starters count (without .filter(Boolean))
  var myStarted = 0;
  if (me.starters && me.starters.length){
    for (var a=0; a<me.starters.length; a++){ if (me.starters[a]) myStarted++; }
  }
  var oppStarted = 0;
  if (opp && opp.starters && opp.starters.length){
    for (var b=0; b<opp.starters.length; b++){ if (opp.starters[b]) oppStarted++; }
  }

  var myAvatar = myUser.avatarUrl ? await loadImage(myUser.avatarUrl) : null;
  var oppAvatar = oppUser.avatarUrl ? await loadImage(oppUser.avatarUrl) : null;

  return {
    leagueName: league && league.name ? league.name : "Sleeper League",
    week: week,
    myName: myUser.name,
    myAvatar: myAvatar,
    oppName: oppUser.name,
    oppAvatar: oppAvatar,
    myPts: myPts,
    oppPts: oppPts,
    myStarted: myStarted,
    oppStarted: oppStarted
  };
}

// ====== BAR DRAW ======
function drawBar(share, width, height, bg){
  var ctx = new DrawContext();
  ctx.size = new Size(width, height);
  ctx.opaque = false;
  ctx.respectScreenScale = true;

  var bgPath = new Path();
  bgPath.addRoundedRect(new Rect(0,0,width,height), height/2, height/2);
  ctx.setFillColor(new Color(bg || "#3a3a3c"));
  ctx.addPath(bgPath); ctx.fillPath();

  var w = Math.round(clamp(share, 0, 1) * width);
  var fgPath = new Path();
  fgPath.addRoundedRect(new Rect(0,0,w,height), height/2, height/2);
  ctx.setFillColor(hex(ACCENT_HEX));
  ctx.addPath(fgPath); ctx.fillPath();

  return ctx.getImage();
}

// ====== SMALL ======
function addNameWithAvatar(parent, name, imgObj, size, font){
  var s = parent.addStack();
  s.centerAlignContent();
  if (imgObj){
    var im = s.addImage(imgObj);
    im.imageSize = new Size(size, size);
    im.cornerRadius = size/2;
    s.addSpacer(6);
  } else {
    var sf = SFSymbol.named("person.crop.circle");
    var im2 = s.addImage(sf.image);
    im2.imageSize = new Size(size, size);
    im2.tintColor = Color.lightGray();
    s.addSpacer(6);
  }
  var t = s.addText(ell(name, 14));
  t.font = font;
  t.textColor = Color.white();
}

function buildSmall(w, d){
  w.setPadding(10,14,10,14);
  var row = w.addStack(); row.layoutHorizontally(); row.addSpacer();
  var col = row.addStack(); col.layoutVertically(); col.centerAlignContent();

  // League
  var league = col.addText(ell(d.leagueName, 14));
  league.font = Font.mediumSystemFont(10);
  league.textColor = Color.lightGray();

  col.addSpacer(2);

  // My team (avatar + name)
  addNameWithAvatar(col, d.myName, d.myAvatar, 16, Font.semiboldSystemFont(11));

  // My score
  var myScore = col.addText(fmt(d.myPts));
  myScore.font = Font.boldSystemFont(20);
  myScore.textColor = Color.white();

  col.addSpacer(3);

  // Bar
  var total = d.myPts + d.oppPts;
  var share = total > 0 ? (d.myPts / total) : 0.5;
  var barW = 160, barH = 6;
  var barImg = col.addImage(drawBar(share, barW, barH, "#3a3a3c"));
  barImg.imageSize = new Size(barW, barH);

  col.addSpacer(3);

  // Opponent (avatar + name)
  addNameWithAvatar(col, d.oppName, d.oppAvatar, 16, Font.semiboldSystemFont(11));

  // Opponent score
  var oppScore = col.addText(fmt(d.oppPts));
  oppScore.font = Font.boldSystemFont(20);
  oppScore.textColor = Color.white();

  row.addSpacer();
}

// ====== MEDIUM/LARGE ======
function buildBig(w, d, fam){
  w.setPadding(10,12,10,12);

  // Header
  var h = w.addStack(); h.centerAlignContent();
  var trophy = SFSymbol.named("trophy.fill");
  var img = h.addImage(trophy.image); img.imageSize = new Size(16,16); img.tintColor = hex(ACCENT_HEX);
  h.addSpacer(6);
  var title = h.addText(ell(d.leagueName, fam==="medium" ? 26 : 40));
  title.font = Font.mediumSystemFont(12); title.textColor = Color.white();
  w.addSpacer(4);

  // Columns
  var row = w.addStack();

  var left = row.addStack(); left.layoutVertically();
  var myHead = left.addStack(); myHead.centerAlignContent();
  if (d.myAvatar){
    var a = myHead.addImage(d.myAvatar); a.imageSize = new Size(18,18); a.cornerRadius = 9;
  } else {
    var sf = SFSymbol.named("person.crop.circle"); var a2 = myHead.addImage(sf.image); a2.imageSize = new Size(18,18); a2.tintColor = Color.lightGray();
  }
  myHead.addSpacer(6);
  var you = myHead.addText(ell(d.myName, fam==="medium" ? 12 : 18)); you.font = Font.semiboldSystemFont(12); you.textColor = Color.white();
  var ys = left.addText(fmt(d.myPts)); ys.font = Font.boldSystemFont(28); ys.textColor = Color.white();

  row.addSpacer();

  var right = row.addStack(); right.layoutVertically();
  var oppHead = right.addStack(); oppHead.centerAlignContent();
  if (d.oppAvatar){
    var b = oppHead.addImage(d.oppAvatar); b.imageSize = new Size(18,18); b.cornerRadius = 9;
  } else {
    var sf2 = SFSymbol.named("person.crop.circle"); var b2 = oppHead.addImage(sf2.image); b2.imageSize = new Size(18,18); b2.tintColor = Color.lightGray();
  }
  oppHead.addSpacer(6);
  var opp = oppHead.addText(ell(d.oppName, fam==="medium" ? 12 : 18)); opp.font = Font.semiboldSystemFont(12); opp.textColor = Color.white();
  var os = right.addText(fmt(d.oppPts)); os.font = Font.boldSystemFont(28); os.textColor = Color.white();

  w.addSpacer(6);

  // Diff pill
  var diff = d.myPts - d.oppPts;
  var pill = w.addStack(); pill.centerAlignContent(); pill.setPadding(3,8,3,8); pill.cornerRadius = 8; pill.backgroundColor = new Color("#2a2a2b");
  var sign = diff > 0 ? "+" : "";
  var dt = pill.addText(sign + diff.toFixed(1)); dt.font = Font.mediumSystemFont(12); dt.textColor = diff>=0 ? hex(ACCENT_HEX) : Color.red();

  w.addSpacer(6);

  // Bar
  var total2 = d.myPts + d.oppPts;
  var share2 = total2 > 0 ? (d.myPts / total2) : 0.5;
  var barW2 = fam==="large" ? 560 : 320, barH2 = 8;
  var bar = drawBar(share2, barW2, barH2, "#3a3a3c");
  var bi = w.addImage(bar); bi.imageSize = new Size(barW2, barH2);

  w.addSpacer(4);

  // Footer
  var f = w.addStack();
  var leftF = f.addText("Week " + d.week); leftF.font = Font.systemFont(11); leftF.textColor = Color.lightGray();
  f.addSpacer();
  var midF = f.addText("Starters " + d.myStarted + ":" + d.oppStarted); midF.font = Font.systemFont(11); midF.textColor = Color.lightGray();
  f.addSpacer();
  var rightF = f.addText("Updated " + nowHM()); rightF.font = Font.systemFont(11); rightF.textColor = Color.lightGray();
}

// ====== BUILD WIDGET ======
async function makeWidget(){
  var d = await fetchData();
  var w = new ListWidget();

  var g = new LinearGradient();
  g.colors = [new Color("#161618"), new Color("#0d0d0f")];
  g.locations = [0,1];
  w.backgroundGradient = g;

  w.url = "https://sleeper.app/leagues/" + LEAGUE_ID + "/matchup/" + d.week;

  var fam = config.widgetFamily || "medium";
  if (fam === "small") buildSmall(w, d);
  else buildBig(w, d, fam);

  return w;
}

var w = await makeWidget();
Script.setWidget(w);
Script.complete();
