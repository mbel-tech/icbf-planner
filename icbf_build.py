# -*- coding: utf-8 -*-
"""
Assemble the two self-contained planner files from shared parts:
  - icbf_schedule.json   parsed schedule ({meta, entries})
  - icbf_core.js         shared logic + state + PDF export (no DOM)
  - icbf_ui_desktop.js   desktop renderer   -> icbf-planner.html
  - icbf_ui_mobile.js    touch-first renderer -> icbf-planner-mobile.html
  - jspdf.min.js         vendored jsPDF (one-click offline PDF)

Run:  python icbf_build.py            # build both
      python icbf_build.py desktop    # build only one
      python icbf_build.py mobile
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD_DIR = HERE / "build"  # untracked scratch output (see build_artifact_fragment)

data = (HERE / "icbf_schedule.json").read_text(encoding="utf-8")
core = (HERE / "icbf_core.js").read_text(encoding="utf-8")
jspdf_path = HERE / "jspdf.min.js"
if not jspdf_path.exists():
    raise SystemExit(
        "jspdf.min.js not found next to icbf_build.py -- download it from "
        "https://github.com/parallax/jsPDF/releases (umd/jspdf.umd.min.js) and place it here."
    )
jspdf = jspdf_path.read_text(encoding="utf-8", errors="replace")

# --------------------------------------------------------------- desktop CSS
CSS_DESKTOP = r"""
:root{
  --ink:#12232e; --muted:#607080; --line:#e2e8ef; --bg:#f4f7fa; --card:#ffffff;
  --teal:#0e7c86; --teal2:#0b6169; --gold:#e0a800; --own:#8e44ad; --follow:#4a5fc1; --shadow:0 2px 10px rgba(20,40,60,.08);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
#app{max-width:1080px;margin:0 auto;padding:22px 18px 60px}
button{font:inherit;cursor:pointer;border:0;border-radius:9px;padding:9px 14px;background:#eef2f6;color:var(--ink);transition:.12s}
button:hover{filter:brightness(.97)}
.primary{background:var(--teal);color:#fff;font-weight:600}
.primary:hover{background:var(--teal2)}
.primary.big{padding:12px 22px;font-size:16px}
.ghost{background:#fff;border:1px solid var(--line)}
.link{background:none;color:var(--teal);padding:6px 4px;text-decoration:underline}
.muted{color:var(--muted);font-size:13.5px}
.start h1{font-size:30px;margin:.2em 0 .3em}
.start .lead{max-width:760px;color:#33475b}
.daypick{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 20px}
.daybtn{border:2px solid var(--line);background:#fff;padding:12px 18px;font-weight:600;border-radius:12px}
.daybtn.on{border-color:var(--teal);background:#e6f4f5;color:var(--teal2)}
.daybtn::before{content:"○ ";opacity:.5}
.daybtn.on::before{content:"● ";opacity:1}
.presenter-block{margin:16px 0 22px;padding:16px 18px;background:#fff;border:1px solid var(--line);border-radius:12px}
.presenter-block h3{margin:0 0 10px;font-size:16px}
.yn{display:flex;gap:10px;flex-wrap:wrap}
.ynbtn{border:2px solid var(--line);background:#fff;padding:11px 18px;font-weight:600;border-radius:12px}
.ynbtn:hover{border-color:var(--teal)}
.link2{color:var(--teal);text-decoration:underline;cursor:pointer}
.presenter-block p{margin:0}
.presenter-summary p{font-size:14px}
.chiprow{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.chip{display:inline-flex;align-items:center;gap:6px;background:#eef0fb;color:var(--follow);border:1px solid #dadffa;
  border-radius:99px;padding:6px 6px 6px 12px;font-size:12.5px;font-weight:600}
.chip i{font-weight:400;opacity:.8;font-style:normal}
.chip button{background:none;padding:2px 6px;border-radius:99px;color:var(--follow);font-size:11px}
.chip button:hover{background:#dadffa}
.searchrow{display:flex;gap:10px;margin:4px 0}
.nameinput{flex:1;padding:10px 12px;border:1px solid var(--line);border-radius:9px;font-size:14px;font:inherit}
.searchresults{margin-top:12px;display:flex;flex-direction:column;gap:10px}
.matchlist{display:flex;flex-direction:column;gap:8px}
.matchrow{display:flex;gap:10px;align-items:flex-start;background:#f7fafb;border:1px solid var(--line);border-radius:9px;padding:9px 11px;font-size:13px;cursor:pointer}
.matchrow input{margin-top:3px;flex:0 0 auto}
.matchrow i{color:var(--muted)}
.searchresults .primary,.searchresults .ghost{align-self:flex-start;margin-right:8px}
.bar{display:flex;align-items:center;gap:14px;margin-bottom:16px}
.prog{flex:1}
.progbar{height:8px;background:#e6ecf2;border-radius:99px;overflow:hidden}
.progbar i{display:block;height:100%;background:linear-gradient(90deg,var(--teal),#3bb7c2);transition:.25s}
.prog span{font-size:12.5px;color:var(--muted)}
.playwrap{display:grid;grid-template-columns:1fr 300px;gap:22px;align-items:start}
@media(max-width:820px){.playwrap{grid-template-columns:1fr}.side{order:-1}}
.dayband{font-weight:800;font-size:18px;color:var(--teal2);margin:6px 0 4px;padding-top:6px;border-top:2px solid var(--line)}
.banner{font-size:13px;padding:8px 12px;border-radius:8px;margin:6px 0;background:#eef2f6;color:#42566a}
.banner em{color:#8ea0b2;font-style:normal;font-size:12px}
.banner.own{background:#f5ecfb;color:var(--own);font-weight:600}
.banner.plen{background:#fff6e0;color:#8a6d00}
.banner.fix{background:#eef2f6}
.slothead{display:flex;justify-content:space-between;align-items:baseline;margin:14px 0 8px}
.slothead .when{font-size:20px;font-weight:800}
.slothead .kept{font-size:13px;color:var(--muted);background:#eef2f6;padding:4px 10px;border-radius:99px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.card{position:relative;background:var(--card);border:1px solid var(--line);border-left:5px solid var(--bar,#8892a6);
  border-radius:12px;padding:12px 12px 10px;box-shadow:var(--shadow);cursor:pointer;transition:.12s}
.card:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(20,40,60,.13)}
.card.kept{outline:2.5px solid var(--teal);outline-offset:0}
.card.star{box-shadow:0 0 0 2px var(--gold) inset,var(--shadow)}
.cardtop{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:6px}
.room{font-size:12px;font-weight:700;color:#45586b}
.tagrow{display:flex;gap:6px;align-items:center}
.followtag{font-size:11px;background:#eef0fb;color:var(--follow);border-radius:99px;padding:2px 7px;font-weight:700}
.tag{font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:99px;white-space:nowrap;text-transform:uppercase;letter-spacing:.03em}
.card .title{font-size:14px;font-weight:600;line-height:1.35;margin-bottom:5px}
.card .pres{font-size:12.5px;color:var(--muted);font-style:italic}
.acts{display:flex;gap:8px;margin-top:10px}
.keepbtn{flex:1;background:#eef2f6;font-weight:600;padding:7px}
.keepbtn.on{background:var(--teal);color:#fff}
.starbtn{width:40px;font-size:16px;background:#fff;border:1px solid var(--line);color:#b9a24a}
.starbtn.on{background:var(--gold);color:#fff;border-color:var(--gold)}
.nav{display:flex;justify-content:space-between;margin-top:18px}
.side{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 14px;position:sticky;top:12px;max-height:82vh;overflow:auto;box-shadow:var(--shadow)}
.side h4{margin:.1em 0 .5em;font-size:14px;color:var(--teal2)}
.agenda{font-size:12.5px}
.arow{display:flex;gap:8px;padding:5px 0;border-top:1px dashed #edf1f5}
.arow .t{flex:0 0 40px;font-weight:700;color:#45586b}
.arow .c{flex:1}
.arow.fix .c{color:var(--muted);font-style:italic}
.arow.own .c{color:var(--own)}
.arow .opt{padding:2px 0}
.arow .cue{display:inline-block;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--gold);font-weight:800;margin-bottom:2px}
.arow i{color:var(--muted)}
.rvhead{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:8px}
.rvhead h2{margin:0;flex:1;font-size:24px}
.rvacts{display:flex;gap:10px;flex-wrap:wrap}
.rvbody{background:#fff;border:1px solid var(--line);border-radius:14px;padding:8px 20px 20px;box-shadow:var(--shadow)}
.rvday h3{color:var(--teal2);border-bottom:2px solid var(--line);padding-bottom:6px;margin:22px 0 6px}
.rvbody .arow{padding:9px 0;border-top:1px solid #eef1f5}
.rvbody .arow .t{flex:0 0 60px;font-size:15px}
.rvbody .choice.many{background:#fffdf3;border-radius:8px}
.editable{cursor:pointer}
.editable:hover{background:#f0fafb}
.toast{position:fixed;left:50%;bottom:26px;transform:translateX(-50%) translateY(20px);opacity:0;pointer-events:none;
  background:#12232e;color:#fff;padding:11px 18px;border-radius:10px;font-size:13.5px;transition:.2s;z-index:50;box-shadow:0 6px 20px rgba(0,0,0,.25)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.modal-back{position:fixed;inset:0;z-index:40;background:rgba(10,20,30,0);transition:background .18s;
  display:flex;align-items:center;justify-content:center;padding:20px}
.modal-back.show{background:rgba(10,20,30,.45)}
.modal-panel{position:relative;background:#fff;border-radius:16px;max-width:560px;width:100%;max-height:82vh;overflow:auto;
  padding:22px 24px 24px;box-shadow:0 20px 60px rgba(0,0,0,.3);transform:translateY(10px);opacity:0;transition:.18s}
.modal-back.show .modal-panel{transform:translateY(0);opacity:1}
.modal-close{position:absolute;top:14px;right:14px;background:#eef2f6;width:32px;height:32px;padding:0;border-radius:99px;font-size:14px}
#printArea{display:none}
@media print{
  #app,.toast{display:none!important}
  #printArea{display:block;color:#000;font-size:11pt}
  #printArea h1{font-size:18pt;margin:0 0 4pt}
  #printArea h2{font-size:14pt;margin:14pt 0 3pt;border-bottom:1px solid #999;page-break-after:avoid}
  .prow{display:flex;gap:10pt;padding:3pt 0;border-bottom:1px dotted #ccc;page-break-inside:avoid}
  .prow .pt{flex:0 0 46pt;font-weight:bold}
  .prow .pc u{color:#a07500}
}
"""

# ---------------------------------------------------------------- mobile CSS
CSS_MOBILE = r"""
:root{
  --ink:#12232e; --muted:#5d6b7a; --line:#e2e8ef; --bg:#f4f7fa; --card:#fff;
  --teal:#0e7c86; --teal2:#0b6169; --gold:#e0a800; --own:#8e44ad; --follow:#4a5fc1;
  --shadow:0 2px 10px rgba(20,40,60,.08); --barh:calc(64px + env(safe-area-inset-bottom));
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);touch-action:manipulation;
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  overflow-x:hidden}
#app{max-width:640px;margin:0 auto;min-height:100vh}
button{font:inherit;cursor:pointer;border:0;border-radius:12px;background:#eef2f6;color:var(--ink)}
.m-primary{background:var(--teal);color:#fff;font-weight:700;padding:14px 16px;font-size:16px;min-height:48px}
.m-ghost{background:#fff;border:1px solid var(--line);padding:13px 14px;min-height:48px}
.m-wide{display:block;width:100%;margin-top:10px}
.m-link{color:var(--teal);text-decoration:underline}
.m-muted{color:var(--muted);font-size:14px}

/* start */
.m-start{padding:20px 16px 20px}
.m-start h1{font-size:26px;margin:.1em 0 .35em}
.m-lead{color:#33475b;font-size:15px}
.m-start h3{font-size:16px;margin:18px 0 8px}
.m-daypick{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.m-daybtn{border:2px solid var(--line);background:#fff;padding:15px 10px;font-weight:700;border-radius:14px;min-height:52px}
.m-daybtn.on{border-color:var(--teal);background:#e6f4f5;color:var(--teal2)}
.m-daybtn.on::before{content:"● "}
.m-switch{margin:6px 0 14px;padding:14px 15px;background:#eef7f8;border:1px solid #cfe6e8;border-radius:14px}
.m-switch-h{font-weight:700;font-size:15px;color:var(--teal2);margin-bottom:9px}
.m-switch-btn{display:block;width:100%;background:#fff;border:1.5px solid var(--teal);color:var(--teal2);
  font-weight:700;padding:13px;border-radius:12px;min-height:48px;font-size:15px}
.m-switch-btn:active{background:var(--teal);color:#fff}
.m-presenter{margin:8px 0 6px;padding:15px;background:#fff;border:1px solid var(--line);border-radius:14px}
.m-presenter h3{margin:0 0 10px}
.m-presenter p{margin:0}
.m-choice-btn{display:block;width:100%;border:2px solid var(--line);background:#fff;padding:15px;font-weight:600;border-radius:14px;margin-bottom:10px;text-align:left;min-height:52px}
.m-choice-btn:active{border-color:var(--teal)}
.m-nameinput{display:block;width:100%;padding:14px;border:1px solid var(--line);border-radius:12px;font:inherit;font-size:16px;margin-bottom:10px}
.m-results{margin-top:12px}
.m-matchrow{display:flex;gap:12px;align-items:flex-start;background:#f7fafb;border:1px solid var(--line);border-radius:12px;padding:13px;font-size:14px;margin-bottom:10px}
.m-matchrow input{width:22px;height:22px;margin-top:2px;flex:0 0 auto}
.m-matchrow i{color:var(--muted)}
.m-chiprow{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 12px}
.m-chip{display:inline-flex;align-items:center;gap:6px;background:#eef0fb;color:var(--follow);border:1px solid #dadffa;
  border-radius:99px;padding:7px 7px 7px 13px;font-size:13px;font-weight:600}
.m-chip i{font-weight:400;opacity:.8;font-style:normal}
.m-chip button{background:none;padding:4px 8px;border-radius:99px;color:var(--follow);font-size:12px;min-height:0}
.m-chip button:active{background:#dadffa}

/* play */
.m-top{position:sticky;top:0;z-index:5;background:var(--bg);padding:12px 16px 8px;padding-top:calc(12px + env(safe-area-inset-top))}
.m-progbar{height:7px;background:#e6ecf2;border-radius:99px;overflow:hidden}
.m-progbar i{display:block;height:100%;background:linear-gradient(90deg,var(--teal),#3bb7c2);transition:.25s}
.m-topmeta{display:flex;justify-content:space-between;align-items:center;font-size:13px;color:var(--muted);margin-top:6px;gap:8px}
.m-daytag{font-weight:700;color:var(--teal2)}
.m-followbtn{background:#eef0fb;color:var(--follow);font-weight:700;font-size:13px;padding:6px 12px;border-radius:99px;min-height:0}
.m-scroll{padding:6px 16px var(--barh);min-height:calc(100vh - 120px)}
.m-dayband{font-weight:800;font-size:16px;color:var(--teal2);margin:8px 0 4px}
.m-when{font-size:20px;font-weight:800;margin:10px 2px 12px}
.m-banner{font-size:14px;padding:11px 13px;border-radius:11px;margin:8px 0;background:#eef2f6;color:#42566a;line-height:1.4}
.m-banner.own{background:#f5ecfb;color:var(--own);font-weight:600}
.m-banner.plen{background:#fff6e0;color:#8a6d00}
.m-card{position:relative;background:var(--card);border:1px solid var(--line);border-left:6px solid var(--bar,#8892a6);
  border-radius:15px;padding:14px;box-shadow:var(--shadow);margin-bottom:13px}
.m-card.kept{outline:3px solid var(--teal)}
.m-card.star{box-shadow:0 0 0 2.5px var(--gold) inset,var(--shadow)}
.m-cardtop{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:7px}
.m-room{font-size:13px;font-weight:700;color:#45586b}
.m-tagrow{display:flex;gap:6px;align-items:center}
.m-followtag{font-size:11px;background:#eef0fb;color:var(--follow);border-radius:99px;padding:3px 8px;font-weight:700}
.m-tag{font-size:11px;font-weight:700;padding:3px 9px;border-radius:99px;text-transform:uppercase;letter-spacing:.03em}
.m-title{font-size:16px;font-weight:600;line-height:1.35;margin-bottom:6px}
.m-pres{font-size:14px;color:var(--muted);font-style:italic}
.m-acts{display:flex;gap:10px;margin-top:12px}
.m-keep{flex:1;background:#eef2f6;font-weight:700;padding:13px;border-radius:12px;min-height:48px;font-size:15px}
.m-keep.on{background:var(--teal);color:#fff}
.m-star{width:56px;min-height:48px;font-size:22px;background:#fff;border:1px solid var(--line);color:#b9a24a;border-radius:12px}
.m-star.on{background:var(--gold);color:#fff;border-color:var(--gold)}
.m-skip{display:block;width:100%;background:#fff;border:1px dashed var(--line);color:var(--muted);padding:13px;border-radius:12px;margin-top:6px;min-height:48px}
.m-scrollpad{height:10px}

/* bottom bar */
.m-bottombar{position:fixed;left:0;right:0;bottom:0;z-index:20;background:rgba(255,255,255,.96);
  backdrop-filter:blur(8px);border-top:1px solid var(--line);padding:10px 14px;padding-bottom:calc(10px + env(safe-area-inset-bottom))}
.m-bottombar-in{max-width:640px;margin:0 auto;display:flex;gap:10px;align-items:center}
.m-bottombar-in>.m-primary,.m-bottombar-in>.m-ghost{flex:1;margin-top:0}
.m-bottombar-in.play{gap:12px}
.m-navbtn{width:56px;min-height:52px;font-size:20px;font-weight:700;background:#eef2f6;border-radius:14px}
.m-navbtn.primary{background:var(--teal);color:#fff}
.m-kept-pill{flex:1;min-height:52px;background:#eef2f6;border-radius:14px;font-weight:600;font-size:14px;color:#43586b}

/* agenda sheet */
.m-sheet-back{position:fixed;inset:0;z-index:40;background:rgba(10,20,30,0);transition:background .2s;display:flex;align-items:flex-end}
.m-sheet-back.show{background:rgba(10,20,30,.45)}
.m-sheet{width:100%;max-height:82vh;overflow:auto;background:#fff;border-radius:20px 20px 0 0;padding:10px 18px calc(20px + env(safe-area-inset-bottom));
  transform:translateY(100%);transition:transform .22s;box-shadow:0 -6px 24px rgba(0,0,0,.2)}
.m-sheet-back.show .m-sheet{transform:translateY(0)}
.m-sheet-grab{width:42px;height:5px;background:#d3dbe3;border-radius:99px;margin:2px auto 10px}
.m-sheet h4{margin:.2em 0 .6em;color:var(--teal2)}
.m-agenda{font-size:14px}
.m-arow{display:flex;gap:10px;padding:9px 0;border-top:1px solid #eef1f5}
.m-arow .t{flex:0 0 46px;font-weight:700;color:#45586b}
.m-arow .c{flex:1}
.m-arow.fix .c{color:var(--muted);font-style:italic}
.m-arow.own .c{color:var(--own)}
.m-arow .opt{padding:2px 0}
.m-arow .cue{display:inline-block;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--gold);font-weight:800}
.m-arow i{color:var(--muted)}
.m-arow.editable{cursor:pointer}
.m-arow.editable:active{background:#f0fafb}

/* review */
.m-rvtop{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;align-items:center;gap:12px;
  padding:12px 16px;padding-top:calc(12px + env(safe-area-inset-top))}
.m-rvtop h2{margin:0;font-size:20px;flex:1}
.m-rvbody{padding:4px 16px}
.m-rvday h3{color:var(--teal2);border-bottom:2px solid var(--line);padding-bottom:6px;margin:18px 0 4px}

.toast{position:fixed;left:50%;bottom:calc(var(--barh) + 12px);transform:translateX(-50%) translateY(20px);opacity:0;pointer-events:none;
  background:#12232e;color:#fff;padding:12px 18px;border-radius:12px;font-size:14px;transition:.2s;z-index:60;max-width:88%;text-align:center;box-shadow:0 6px 20px rgba(0,0,0,.28)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
#printArea{display:none}
@media print{
  #app,.toast,.m-bottombar{display:none!important}
  #printArea{display:block;color:#000;font-size:11pt}
  #printArea h1{font-size:18pt;margin:0 0 4pt}
  #printArea h2{font-size:14pt;margin:14pt 0 3pt;border-bottom:1px solid #999;page-break-after:avoid}
  .prow{display:flex;gap:10pt;padding:3pt 0;border-bottom:1px dotted #ccc;page-break-inside:avoid}
  .prow .pt{flex:0 0 46pt;font-weight:bold}
  .prow .pc u{color:#a07500}
}
"""

# Both output files are self-contained AND carry both UIs, so either one can switch
# between the desktop and mobile experience in place. They differ only in which UI
# they default to. A tiny shell enables one stylesheet + mounts one UI at a time;
# the shared core keeps state in memory + localStorage, so switching never loses picks.
HEAD = (
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    '<meta name="theme-color" content="#0e7c86">'
    '<meta name="mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-capable" content="yes">'
)

SHELL = r"""
(function () {
  var DEFAULT_UI = "__DEFAULT_UI__";
  var cssD = document.getElementById("css-desktop");
  var cssM = document.getElementById("css-mobile");
  function apply(name) {
    if (!window.ICBF_UIS || !window.ICBF_UIS[name]) name = DEFAULT_UI;
    var isM = name === "mobile";
    cssM.disabled = !isM; cssD.disabled = isM;
    document.body.className = isM ? "ui-mobile" : "ui-desktop";
    var appEl = document.getElementById("app");
    if (appEl) appEl.innerHTML = "";
    window.ICBF_ACTIVE_UI = name;
    window.ICBF_UIS[name].mount();
  }
  window.ICBFSwitchUI = function (name) {
    if (!window.ICBF_UIS || !window.ICBF_UIS[name] || name === window.ICBF_ACTIVE_UI) return;
    try { localStorage.setItem("icbf_ui_pref", name); } catch (e) {}
    apply(name);
    window.scrollTo(0, 0);
  };
  var pref = null;
  try { pref = localStorage.getItem("icbf_ui_pref"); } catch (e) {}
  var hash = (location.hash || "").replace("#", "");
  var start = (hash === "desktop" || hash === "mobile") ? hash : (pref || DEFAULT_UI);
  function boot() { apply(start); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
"""

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
__HEAD__
<title>__TITLE__</title>
<style id="css-desktop">__CSS_DESKTOP__</style>
<style id="css-mobile">__CSS_MOBILE__</style>
</head>
<body>
<div id="app"></div>
<div id="printArea"></div>
<div id="toast" class="toast"></div>
<script>__JSPDF__</script>
<script>window.SCHEDULE = __DATA__;</script>
<script>__CORE__</script>
<script>__UI_DESKTOP__</script>
<script>__UI_MOBILE__</script>
<script>__SHELL__</script>
</body>
</html>
"""

ui_desktop = (HERE / "icbf_ui_desktop.js").read_text(encoding="utf-8")
ui_mobile = (HERE / "icbf_ui_mobile.js").read_text(encoding="utf-8")


def build(target):
    # "desktop" is kept only as an optional dev/debug build (defaults to the desktop
    # UI on load) -- it is NOT part of the normal build and is not distributed.
    # The single shipped file is icbf-planner-mobile.html: it bundles both UIs and
    # opens on mobile by default, with an in-page switch to the desktop experience.
    if target == "desktop":
        title, default_ui, out_name = "ICBF 2026 — Build Your Schedule (dev build)", "desktop", "icbf-planner.html"
    else:
        title, default_ui, out_name = "ICBF 2026 — Planner", "mobile", "icbf-planner-mobile.html"
    out = (HTML
           .replace("__HEAD__", HEAD).replace("__TITLE__", title)
           .replace("__CSS_DESKTOP__", CSS_DESKTOP).replace("__CSS_MOBILE__", CSS_MOBILE)
           .replace("__JSPDF__", jspdf).replace("__DATA__", data).replace("__CORE__", core)
           .replace("__UI_DESKTOP__", ui_desktop).replace("__UI_MOBILE__", ui_mobile)
           .replace("__SHELL__", SHELL.replace("__DEFAULT_UI__", default_ui)))
    dest = HERE / out_name
    dest.write_text(out, encoding="utf-8")
    print(f"Wrote {dest}  ({len(out)//1024} KB, default UI: {default_ui})")


def build_site():
    """Emit a GitHub-Pages-ready, installable, OFFLINE-capable PWA into docs/
    (GitHub Pages is configured to serve straight from that folder). index.html
    is the same self-contained planner (mobile default) plus a web-app manifest,
    iOS home-screen meta, and a service worker that caches the shell so it runs
    with no connection after the first visit."""
    site = HERE / "docs"
    (site / "icons").mkdir(parents=True, exist_ok=True)

    pwa_head = (HEAD
        + '<link rel="manifest" href="manifest.webmanifest">'
        + '<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">'
        + '<link rel="icon" href="icons/favicon-64.png">'
        + '<meta name="apple-mobile-web-app-title" content="ICBF 2026">'
        + '<meta name="application-name" content="ICBF 2026">'
        + '<meta name="description" content="Build your personal ICBF 2026 conference schedule.">')

    sw_reg = ('<script>if("serviceWorker" in navigator){'
              'window.addEventListener("load",function(){'
              'navigator.serviceWorker.register("sw.js").catch(function(){});});}</script>')

    body = HTML.split("</head>", 1)[1]  # reuse the same <body> payload
    page = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            + pwa_head + "<title>ICBF 2026 — Planner</title>\n"
            + '<style id="css-desktop">' + CSS_DESKTOP + "</style>\n"
            + '<style id="css-mobile">' + CSS_MOBILE + "</style>\n</head>"
            + body.replace("</body>", sw_reg + "</body>"))
    page = (page.replace("__JSPDF__", jspdf).replace("__DATA__", data).replace("__CORE__", core)
            .replace("__UI_DESKTOP__", ui_desktop).replace("__UI_MOBILE__", ui_mobile)
            .replace("__SHELL__", SHELL.replace("__DEFAULT_UI__", "mobile")))
    (site / "index.html").write_text(page, encoding="utf-8")

    manifest = (
        '{\n'
        '  "name": "ICBF 2026 Schedule Planner",\n'
        '  "short_name": "ICBF 2026",\n'
        '  "description": "Build your personal ICBF 2026 conference schedule.",\n'
        '  "start_url": ".",\n'
        '  "scope": ".",\n'
        '  "display": "standalone",\n'
        '  "orientation": "portrait",\n'
        '  "background_color": "#f4f7fa",\n'
        '  "theme_color": "#0e7c86",\n'
        '  "icons": [\n'
        '    { "src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },\n'
        '    { "src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }\n'
        '  ]\n'
        '}\n')
    (site / "manifest.webmanifest").write_text(manifest, encoding="utf-8")

    # Bump CACHE when the app changes so returning visitors pull the new shell.
    import hashlib
    ver = hashlib.sha1(page.encode("utf-8")).hexdigest()[:10]
    sw = (
        'const CACHE = "icbf-' + ver + '";\n'
        'const ASSETS = ["./","./index.html","./manifest.webmanifest",'
        '"./icons/icon-192.png","./icons/icon-512.png",'
        '"./icons/apple-touch-icon.png","./icons/favicon-64.png"];\n'
        'self.addEventListener("install", e => {\n'
        '  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));\n'
        '});\n'
        'self.addEventListener("activate", e => {\n'
        '  e.waitUntil(caches.keys().then(ks => Promise.all(\n'
        '    ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));\n'
        '});\n'
        'self.addEventListener("fetch", e => {\n'
        '  if (e.request.method !== "GET") return;\n'
        '  e.respondWith(caches.match(e.request).then(hit =>\n'
        '    hit || fetch(e.request).then(res => {\n'
        '      const copy = res.clone();\n'
        '      caches.open(CACHE).then(c => c.put(e.request, copy)).catch(()=>{});\n'
        '      return res;\n'
        '    }).catch(() => caches.match("./index.html"))\n'
        '  ));\n'
        '});\n')
    (site / "sw.js").write_text(sw, encoding="utf-8")

    nojekyll = site / ".nojekyll"          # let GitHub Pages serve files as-is
    nojekyll.write_text("", encoding="utf-8")

    print(f"Wrote {site}\\index.html  ({len(page)//1024} KB)  cache={ver}")
    print(f"  + manifest.webmanifest, sw.js, .nojekyll  (icons via icbf_icons.py)")


def build_artifact_fragment():
    # Anthropic's Artifact tool wraps the file in its own <!doctype>/<head>/<body>,
    # so this omits those outer tags (keeps <title>, <style>, <script>, and #app)
    # while reusing the exact same CSS/JS payload as the real distributable.
    frag = ("<title>ICBF 2026 — Planner</title>"
            "<style>" + CSS_DESKTOP + CSS_MOBILE + "</style>"
            '<div id="app"></div><div id="printArea"></div><div id="toast" class="toast"></div>'
            "<script>" + jspdf + "</script>"
            "<script>window.SCHEDULE = " + data + ";</script>"
            "<script>" + core + "</script>"
            "<script>" + ui_desktop + "</script>"
            "<script>" + ui_mobile + "</script>"
            "<script>" + SHELL.replace("__DEFAULT_UI__", "mobile") + "</script>")
    BUILD_DIR.mkdir(exist_ok=True)
    dest = BUILD_DIR / "icbf_artifact_fragment.html"
    dest.write_text(frag, encoding="utf-8")
    print(f"Wrote {dest}  ({len(frag)//1024} KB)")
    return dest


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "mobile"
    if which in ("desktop", "both"):
        build("desktop")
    if which in ("mobile", "both"):
        build("mobile")
    if which == "artifact":
        build_artifact_fragment()
    if which in ("site", "both"):
        build_site()
