/* ICBF 2026 — mobile UI. Touch-first: one slot per screen, big tap targets,
   sticky bottom action bar, bottom-sheet agenda, swipe navigation. Logic in core. */
(function (global) {
  "use strict";
  var C = global.ICBFCore;
  var app;

  function el(html) { var d = document.createElement("div"); d.innerHTML = html; return d.firstElementChild; }
  var esc = C.esc;

  function render() {
    var s = C.state.screen;
    if (s === "start") return renderStart();
    if (s === "play") return renderPlay();
    return renderReview();
  }

  // ---------------- start ----------------
  function renderStart() {
    app.innerHTML = "";
    var box = el('<div class="m-start"></div>');
    box.appendChild(el('<h1>🐟 ICBF 2026</h1>'));
    box.appendChild(el('<p class="m-lead">Pick the parallel talks you want at each timeslot. '
      + 'Keep up to <b>3</b> per slot, <b>★ star</b> the must-sees. Breaks &amp; plenaries are added for you.</p>'));
    var sw = el('<div class="m-switch">'
      + '<div class="m-switch-h">💻 Using a computer?</div>'
      + '<button class="m-switch-btn">Open the desktop version →</button></div>');
    sw.querySelector("button").onclick = function () { if (window.ICBFSwitchUI) window.ICBFSwitchUI("desktop"); };
    box.appendChild(sw);
    box.appendChild(presenterBlock());
    box.appendChild(el('<h3>Days you’re attending</h3>'));
    var dp = el('<div class="m-daypick"></div>');
    C.ALL_DAYS.forEach(function (d) {
      var on = C.state.days.indexOf(d) >= 0;
      var b = el('<button class="m-daybtn ' + (on ? "on" : "") + '">' + esc(d) + '</button>');
      b.onclick = function () { C.toggleDay(d); };
      dp.appendChild(b);
    });
    box.appendChild(dp);
    var meta = C.META;
    if (meta && meta.schedule_date)
      box.appendChild(el('<p class="m-muted">Schedule version ' + esc(meta.schedule_date)
        + (meta.talk_count ? ' · ' + meta.talk_count + ' talks' : '') + '</p>'));
    app.appendChild(box);

    var barwrap = el('<div class="m-bottombar"></div>');
    var inner = el('<div class="m-bottombar-in"></div>');
    var go = el('<button class="m-primary m-wide">Start planning · ' + C.countChoices() + ' slots →</button>');
    go.onclick = function () { if (!C.state.days.length) return C.flash("Pick at least one day."); C.goPlay(0); };
    inner.appendChild(go);
    if (C.hasPicks()) {
      var r = el('<button class="m-ghost">My schedule</button>'); r.onclick = C.goReview; inner.appendChild(r);
    }
    barwrap.appendChild(inner);
    app.appendChild(barwrap);
  }

  function presenterBlock() {
    var st = C.state;
    var wrap = el('<div class="m-presenter"></div>');
    if (st.presenterMode === null) {
      wrap.appendChild(el('<h3>Are you presenting?</h3>'));
      var yes = el('<button class="m-choice-btn">🎤 Yes, I’m presenting</button>');
      yes.onclick = function () { st.uiSearching = true; C.setPresenterMode("yes"); };
      var no = el('<button class="m-choice-btn">No, just attending</button>');
      no.onclick = function () { st.uiSearching = false; C.setPresenterMode("no"); };
      wrap.appendChild(yes); wrap.appendChild(no);
      return wrap;
    }
    if (st.presenterMode === "no") {
      var p = el('<p class="m-muted">Not presenting — <a href="#" class="m-link">I am presenting →</a></p>');
      p.querySelector("a").onclick = function (e) { e.preventDefault(); st.presenterMode = "yes"; C.setSearching(true); };
      wrap.appendChild(p); return wrap;
    }
    if (!st.uiSearching && st.myTalkIds.length) {
      var slots = st.myTalkIds.map(C.byId).map(function (t) { return t.day + " " + t.time + " · " + t.room; }).join("; ");
      var line = el('<p>🎤 <b>' + st.myTalkIds.length + '</b> own talk'
        + (st.myTalkIds.length > 1 ? "s" : "") + ' auto-booked: <span class="m-muted">' + esc(slots)
        + '</span> — <a href="#" class="m-link">edit</a></p>');
      line.querySelector("a").onclick = function (e) { e.preventDefault(); C.setSearching(true); };
      wrap.appendChild(line); return wrap;
    }
    wrap.appendChild(el('<h3>Your name in the program</h3>'));
    var input = el('<input type="text" class="m-nameinput" placeholder="Surname, First — or just surname">');
    input.value = st.myName || "";
    var btn = el('<button class="m-primary m-wide">Find my talk(s)</button>');
    wrap.appendChild(input); wrap.appendChild(btn);
    var resultsBox = el('<div class="m-results"></div>');
    wrap.appendChild(resultsBox);

    function runSearch() {
      var q = input.value.trim();
      C.setMyName(q);
      resultsBox.innerHTML = "";
      if (!q) return;
      var matches = C.findMatches(q);
      if (!matches.length) {
        resultsBox.appendChild(el('<p class="m-muted">No talks found for “' + esc(q) + '”. Try just your surname.</p>'));
        return;
      }
      resultsBox.appendChild(el('<p class="m-muted">Found ' + matches.length + ' — untick any that aren’t yours:</p>'));
      var checks = [];
      matches.forEach(function (m) {
        var r = el('<label class="m-matchrow"><input type="checkbox" checked><span></span></label>');
        checks.push({ cb: r.querySelector("input"), id: m.id });
        r.querySelector("span").innerHTML = "<b>" + esc(m.day) + " " + esc(m.time) + "</b> · " + esc(m.room)
          + "<br>" + esc(m.title) + "<br><i>" + esc(m.presenter) + "</i>";
        resultsBox.appendChild(r);
      });
      var confirm = el('<button class="m-primary m-wide">✓ These are my talks</button>');
      confirm.onclick = function () { C.confirmMyTalks(checks.filter(function (c) { return c.cb.checked; }).map(function (c) { return c.id; })); };
      resultsBox.appendChild(confirm);
      var skip = el('<button class="m-ghost m-wide">None of these — skip</button>');
      skip.onclick = function () { C.confirmMyTalks([]); };
      resultsBox.appendChild(skip);
    }
    btn.onclick = runSearch;
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); runSearch(); } });
    if (st.myName) runSearch();
    return wrap;
  }

  // ---------------- play ----------------
  function renderPlay() {
    if (!C.countChoices()) return C.goReview();
    var slot = C.currentSlot();
    var p = C.pick(slot);
    var step = C.state.step, n = C.countChoices();
    app.innerHTML = "";

    // top progress
    var top = el('<div class="m-top"></div>');
    top.appendChild(el('<div class="m-progbar"><i style="width:' + ((step + 1) / n * 100) + '%"></i></div>'));
    top.appendChild(el('<div class="m-topmeta"><span>Slot ' + (step + 1) + ' of ' + n + '</span>'
      + '<span class="m-daytag">' + esc(slot.day) + '</span></div>'));
    app.appendChild(top);

    var scroll = el('<div class="m-scroll" id="m-scroll"></div>');
    C.bannersFor(step).forEach(function (ev) {
      if (ev.t === "day") scroll.appendChild(el('<div class="m-dayband">' + esc(ev.day) + '</div>'));
      else if (ev.t === "auto") scroll.appendChild(autoBanner(ev.item));
    });
    scroll.appendChild(el('<div class="m-when">' + esc(slot.time) + ' — choose your talk(s)</div>'));

    slot.talks.forEach(function (tk) {
      var kept = p.kept.indexOf(tk.id) >= 0, star = p.star.indexOf(tk.id) >= 0;
      var c = C.sessColor(tk.session);
      var card = el('<div class="m-card ' + (kept ? "kept" : "") + (star ? " star" : "") + '" style="--bar:' + c.bar + '"></div>');
      card.appendChild(el('<div class="m-cardtop"><span class="m-room">' + esc(tk.room) + (tk.seats ? ' · ' + tk.seats + ' seats' : "") + '</span>'
        + '<span class="m-tag" style="background:' + c.bg + ';color:' + c.fg + '">' + esc(tk.session || "General") + '</span></div>'));
      card.appendChild(el('<div class="m-title">' + esc(tk.title) + '</div>'));
      card.appendChild(el('<div class="m-pres">' + esc(tk.presenter || "") + '</div>'));
      var acts = el('<div class="m-acts"></div>');
      var kb = el('<button class="m-keep ' + (kept ? "on" : "") + '">' + (kept ? "✓ Kept" : "＋ Keep") + '</button>');
      kb.onclick = function (ev) { ev.stopPropagation(); C.toggleKeep(slot, tk.id); };
      var sb = el('<button class="m-star ' + (star ? "on" : "") + '" aria-label="Star must-see">' + (star ? "★" : "☆") + '</button>');
      sb.onclick = function (ev) { ev.stopPropagation(); C.toggleStar(slot, tk.id); };
      acts.appendChild(kb); acts.appendChild(sb);
      card.appendChild(acts);
      scroll.appendChild(card);
    });
    scroll.appendChild(el('<button class="m-skip">Skip this slot — nothing here</button>')).onclick = function () { C.skipSlot(slot); };
    scroll.appendChild(el('<div class="m-scrollpad"></div>'));
    app.appendChild(scroll);
    attachSwipe(scroll);

    // sticky bottom bar
    var bar = el('<div class="m-bottombar"></div>');
    var inner = el('<div class="m-bottombar-in play"></div>');
    var bk = el('<button class="m-navbtn">◀</button>'); bk.onclick = C.back;
    var mid = el('<button class="m-kept-pill">' + p.kept.length + ' / 3 kept · agenda</button>'); mid.onclick = openSheet;
    var nx = el('<button class="m-navbtn primary">' + (step < n - 1 ? "▶" : "✓") + '</button>'); nx.onclick = C.next;
    inner.appendChild(bk); inner.appendChild(mid); inner.appendChild(nx);
    bar.appendChild(inner);
    app.appendChild(bar);
  }

  function autoBanner(item) {
    if (item.type === "own")
      return el('<div class="m-banner own">🎤 Your talk · ' + esc(item.slot.time) + ' · ' + esc(item.talk.room)
        + '<br>' + esc(item.talk.title) + '</div>');
    if (item.type === "single")
      return el('<div class="m-banner plen">★ ' + esc(item.slot.time) + ' · ' + esc(item.talk.room)
        + ' — ' + esc(item.talk.title) + '</div>');
    var lbl = { break: "☕ Break", lunch: "🍽 Lunch", poster: "🖼 Poster session", free: "🚌 Free afternoon" }[item.item.type];
    return el('<div class="m-banner fix">' + lbl + ' · ' + esc(item.item.time) + '</div>');
  }

  // ---------------- agenda bottom sheet ----------------
  function openSheet() {
    var slot = C.currentSlot();
    var day = slot ? slot.day : C.state.days[0];
    var back = el('<div class="m-sheet-back"></div>');
    var sheet = el('<div class="m-sheet"></div>');
    sheet.appendChild(el('<div class="m-sheet-grab"></div>'));
    sheet.appendChild(el('<h4>Your ' + esc(day) + '</h4>'));
    var list = el('<div class="m-agenda"></div>');
    var rows = C.dayAgenda(day);
    if (!rows.length) list.appendChild(el('<p class="m-muted">Nothing kept for this day yet.</p>'));
    rows.forEach(function (it) { list.appendChild(agendaRow(it)); });
    sheet.appendChild(list);
    sheet.appendChild(el('<button class="m-ghost m-wide">Close</button>')).onclick = closeSheet;
    function closeSheet() { back.classList.remove("show"); setTimeout(function () { back.remove(); }, 200); }
    back.onclick = function (e) { if (e.target === back) closeSheet(); };
    back.appendChild(sheet);
    document.body.appendChild(back);
    requestAnimationFrame(function () { back.classList.add("show"); });
  }

  function agendaRow(it) {
    if (it.type === "own")
      return el('<div class="m-arow own"><span class="t">' + esc(it.slot.time) + '</span>'
        + '<span class="c"><b>🎤 Your talk</b> — ' + esc(it.talk.room) + '<br>' + esc(it.talk.title) + '</span></div>');
    if (it.type === "single")
      return el('<div class="m-arow"><span class="t">' + esc(it.slot.time) + '</span>'
        + '<span class="c">' + esc(it.talk.title) + '<br><i>' + esc(it.talk.presenter || it.talk.room) + '</i></span></div>');
    if (it.type === "fixed")
      return el('<div class="m-arow fix"><span class="t">' + esc(it.slot.time) + '</span><span class="c">' + C.FIXLBL[it.item.type] + '</span></div>');
    var inner = it.kept.map(function (tk) {
      var s = it.star.indexOf(tk.id) >= 0 ? "★ " : "";
      return '<div class="opt">' + s + esc(tk.room) + ' — ' + esc(tk.title) + '<br><i>' + esc(tk.presenter || "") + '</i></div>';
    }).join("");
    return el('<div class="m-arow choice"><span class="t">' + esc(it.slot.time) + '</span>'
      + '<span class="c">' + (it.kept.length > 1 ? '<span class="cue">choose one</span>' : "") + inner + '</span></div>');
  }

  // ---------------- review ----------------
  function renderReview() {
    app.innerHTML = "";
    var top = el('<div class="m-rvtop"></div>');
    top.appendChild(el('<button class="m-navbtn">◀</button>')).onclick = function () { C.goPlay(0); };
    top.appendChild(el('<h2>My Schedule</h2>'));
    app.appendChild(top);

    var ag = C.assemble();
    var scroll = el('<div class="m-scroll"></div>');
    var body = el('<div class="m-rvbody"></div>');
    var cur = null;
    ag.forEach(function (it) {
      if (it.type === "dayhead") { cur = el('<div class="m-rvday"><h3>' + esc(it.day) + '</h3></div>'); body.appendChild(cur); return; }
      if (!cur) { cur = el('<div class="m-rvday"></div>'); body.appendChild(cur); }
      var row = agendaRow(it);
      if (it.type === "choice") {
        row.classList.add("editable");
        (function (slotKey) {
          row.onclick = function () { var i = C.choiceIndexForKey(slotKey); if (i >= 0) C.goPlay(i); };
        })(C.key(it.slot));
      }
      cur.appendChild(row);
    });
    if (!ag.some(function (i) { return i.type !== "dayhead"; }))
      body.appendChild(el('<p class="m-muted">Nothing selected yet. Go back and keep some talks.</p>'));
    scroll.appendChild(body);
    scroll.appendChild(el('<div class="m-scrollpad"></div>'));
    app.appendChild(scroll);
    C.renderPrintArea();

    var bar = el('<div class="m-bottombar"></div>');
    var inner = el('<div class="m-bottombar-in"></div>');
    inner.appendChild(el('<button class="m-primary">⬇ Save PDF</button>')).onclick = C.downloadPDF;
    inner.appendChild(el('<button class="m-ghost">Open PDF</button>')).onclick = C.openPDF;
    var rs = el('<button class="m-ghost">↺</button>');
    rs.onclick = function () { if (confirm("Clear all picks and start over?")) C.startOver(); };
    inner.appendChild(rs);
    bar.appendChild(inner);
    app.appendChild(bar);
  }

  // ---------------- swipe ----------------
  function attachSwipe(node) {
    var x0 = 0, y0 = 0, tracking = false;
    node.addEventListener("touchstart", function (e) {
      if (e.touches.length !== 1) return;
      x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; tracking = true;
    }, { passive: true });
    node.addEventListener("touchend", function (e) {
      if (!tracking) return; tracking = false;
      var dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
      if (Math.abs(dx) > 60 && Math.abs(dx) > 1.5 * Math.abs(dy)) {
        if (dx < 0) C.next(); else C.back();
      }
    }, { passive: true });
  }

  function boot() {
    app = document.getElementById("app");
    C.subscribe(render);
    C.init();
  }
  global.ICBF_UIS = global.ICBF_UIS || {};
  global.ICBF_UIS.mobile = { mount: boot, render: render };
})(typeof window !== "undefined" ? window : globalThis);
