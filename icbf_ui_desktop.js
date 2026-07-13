/* ICBF 2026 — desktop UI. Renders against window.ICBFCore; all logic lives in core. */
(function (global) {
  "use strict";
  var C = global.ICBFCore;
  var app;

  function el(html) { var d = document.createElement("div"); d.innerHTML = html; return d.firstElementChild; }
  var esc = C.esc;

  // Wraps `input` with a live-suggestions dropdown (search-as-you-type) fed by
  // C.suggestNames. Selecting a suggestion fills the input and runs onPick(name).
  function attachAutocomplete(input, onPick) {
    var wrap = el('<div class="ac-wrap"></div>');
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var dd = el('<div class="ac-dropdown"></div>');
    wrap.appendChild(dd);
    function hide() { dd.innerHTML = ""; dd.style.display = "none"; }
    function show() {
      var names = C.suggestNames(input.value);
      dd.innerHTML = "";
      if (!names.length) { hide(); return; }
      names.forEach(function (name) {
        var item = el('<div class="ac-item">' + esc(name) + '</div>');
        item.onclick = function () { input.value = name; hide(); onPick(name); };
        dd.appendChild(item);
      });
      dd.style.display = "block";
    }
    input.addEventListener("input", show);
    input.addEventListener("focus", show);
    input.addEventListener("blur", function () { setTimeout(hide, 150); });
    return wrap;
  }

  // Rendered under a zero-result search: fuzzy "did you mean" name chips.
  function didYouMeanRow(query, onPick) {
    var names = C.didYouMean(query);
    if (!names.length) return null;
    var row = el('<div class="dym-row"><span class="dym-label">Did you mean:</span></div>');
    names.forEach(function (name) {
      var chip = el('<button class="dym-chip">' + esc(name) + '</button>');
      chip.onclick = function () { onPick(name); };
      row.appendChild(chip);
    });
    return row;
  }

  function render() {
    var s = C.state.screen;
    if (s === "start") return renderStart();
    if (s === "play") return renderPlay();
    return renderReview();
  }

  // ---------------- start ----------------
  function renderStart() {
    app.innerHTML = "";
    var box = el('<div class="start"></div>');
    box.appendChild(el('<h1>🐟 ICBF 2026 — Build Your Schedule</h1>'));
    box.appendChild(el('<p class="lead">Step through each timeslot and pick the parallel talks you want to see. '
      + 'For every slot you may <b>keep up to 3</b> talks (decide later which to attend) and <b>★ star</b> the must-not-miss ones. '
      + 'Breaks, lunches, posters and plenaries are added automatically.</p>'));
    box.appendChild(presenterBlock());
    box.appendChild(followBlock());
    box.appendChild(el('<h3>Which days are you attending?</h3>'));
    var dp = el('<div class="daypick"></div>');
    C.ALL_DAYS.forEach(function (d) {
      var on = C.state.days.indexOf(d) >= 0;
      var b = el('<button class="daybtn ' + (on ? "on" : "") + '">' + esc(d) + '</button>');
      b.onclick = function () { C.toggleDay(d); };
      dp.appendChild(b);
    });
    box.appendChild(dp);
    var go = el('<button class="primary big">Start planning →</button>');
    go.onclick = function () { if (!C.state.days.length) return C.flash("Pick at least one day."); C.goPlay(0); };
    box.appendChild(go);
    box.appendChild(el('<p class="muted">' + C.countChoices() + ' slots need a decision across the days you chose. '
      + 'You can jump to your final schedule at any time.</p>'));
    if (C.hasPicks()) {
      var r = el('<button class="link">View my schedule so far →</button>'); r.onclick = C.goReview; box.appendChild(r);
    }
    var ph = el('<p class="muted">📱 On your phone? <a href="#" class="link2">Switch to the mobile version →</a></p>');
    ph.querySelector("a").onclick = function (e) { e.preventDefault(); if (window.ICBFSwitchUI) window.ICBFSwitchUI("mobile"); };
    box.appendChild(ph);
    var meta = C.META;
    if (meta && meta.schedule_date)
      box.appendChild(el('<p class="muted">Schedule version: ' + esc(meta.schedule_date)
        + (meta.talk_count ? ' · ' + meta.talk_count + ' talks' : '') + '</p>'));
    app.appendChild(box);
  }

  function presenterBlock() {
    var st = C.state;
    var wrap = el('<div class="presenter-block"></div>');

    if (st.presenterMode === null) {
      wrap.appendChild(el('<h3>Are you presenting a talk at ICBF 2026?</h3>'));
      var row = el('<div class="yn"></div>');
      var yes = el('<button class="ynbtn">🎤 Yes, I’m presenting</button>');
      yes.onclick = function () { st.uiSearching = true; C.setPresenterMode("yes"); };
      var no = el('<button class="ynbtn">No, just attending</button>');
      no.onclick = function () { st.uiSearching = false; C.setPresenterMode("no"); };
      row.appendChild(yes); row.appendChild(no);
      wrap.appendChild(row);
      return wrap;
    }
    if (st.presenterMode === "no") {
      var p = el('<p class="muted">Not presenting — <a href="#" class="link2">actually, I am presenting →</a></p>');
      p.querySelector("a").onclick = function (e) { e.preventDefault(); st.presenterMode = "yes"; C.setSearching(true); };
      wrap.appendChild(p);
      return wrap;
    }
    // yes + already picked
    if (!st.uiSearching && st.myTalkIds.length) {
      var slots = st.myTalkIds.map(C.byId).map(function (t) { return t.day + " " + t.time + " · " + t.room; }).join("; ");
      var line = el('<p>🎤 Auto-booking <b>' + st.myTalkIds.length + '</b> talk'
        + (st.myTalkIds.length > 1 ? "s" : "") + (st.myName ? ' for <b>' + esc(st.myName) + '</b>' : "")
        + ': <span class="muted">' + esc(slots) + '</span> — <a href="#" class="link2">edit</a></p>');
      line.querySelector("a").onclick = function (e) { e.preventDefault(); C.setSearching(true); };
      wrap.appendChild(el('<div class="presenter-summary"></div>')).appendChild(line);
      return wrap;
    }
    // search
    wrap.appendChild(el('<h3>What’s your name, as printed in the program?</h3>'));
    var searchRow = el('<div class="searchrow"></div>');
    var input = el('<input type="text" class="nameinput" placeholder="e.g. Bellio, Martina — or just your surname">');
    input.value = st.myName || "";
    var btn = el('<button class="primary">Find my talk(s)</button>');
    searchRow.appendChild(input); searchRow.appendChild(btn);
    wrap.appendChild(searchRow);
    var resultsBox = el('<div class="searchresults"></div>');
    wrap.appendChild(resultsBox);

    function runSearch(overrideName) {
      var q = (overrideName != null ? overrideName : input.value).trim();
      input.value = q;
      C.setMyName(q);
      resultsBox.innerHTML = "";
      if (!q) return;
      var matches = C.findMatches(q);
      if (!matches.length) {
        resultsBox.appendChild(el('<p class="muted">No talks found matching “' + esc(q)
          + '”. Check the spelling, or try just your surname.</p>'));
        var dym = didYouMeanRow(q, runSearch);
        if (dym) resultsBox.appendChild(dym);
        return;
      }
      resultsBox.appendChild(el('<p class="muted">Found ' + matches.length + ' match'
        + (matches.length > 1 ? "es" : "") + ' — untick any that aren’t yours:</p>'));
      var list = el('<div class="matchlist"></div>');
      var checks = [];
      matches.forEach(function (m) {
        var r = el('<label class="matchrow"><input type="checkbox" checked><span></span></label>');
        checks.push({ cb: r.querySelector("input"), id: m.id });
        r.querySelector("span").innerHTML = "<b>" + esc(m.day) + " " + esc(m.time) + "</b> · " + esc(m.room)
          + "<br>" + esc(m.title) + "<br><i>" + esc(m.presenter) + "</i>";
        list.appendChild(r);
      });
      resultsBox.appendChild(list);
      var confirm = el('<button class="primary">✓ These are my talks</button>');
      confirm.onclick = function () { C.confirmMyTalks(checks.filter(function (c) { return c.cb.checked; }).map(function (c) { return c.id; })); };
      resultsBox.appendChild(confirm);
      var skip = el('<button class="ghost">None of these — skip</button>');
      skip.onclick = function () { C.confirmMyTalks([]); };
      resultsBox.appendChild(skip);
    }
    btn.onclick = function () { runSearch(); };
    attachAutocomplete(input, runSearch);
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") runSearch(); });
    if (st.myName) runSearch();
    return wrap;
  }

  function followBlock() {
    var wrap = el('<div class="presenter-block"></div>');
    wrap.appendChild(el('<h3>👥 Follow specific speakers</h3>'));
    wrap.appendChild(el('<p class="muted">Search a name — their talks get kept &amp; starred wherever they '
      + 'present, even in slots you’ve already decided. Unfollowing removes their talks from your picks too.</p>'));

    var chips = el('<div class="chiprow"></div>');
    function renderChips() {
      chips.innerHTML = "";
      C.state.followed.forEach(function (f) {
        var chip = el('<span class="chip">👥 ' + esc(f.name) + ' <i>(' + f.talkIds.length + ')</i> '
          + '<button aria-label="Unfollow">✕</button></span>');
        chip.querySelector("button").onclick = function () { C.removeFollowed(f.id); renderChips(); };
        chips.appendChild(chip);
      });
    }
    renderChips();
    wrap.appendChild(chips);

    var searchRow = el('<div class="searchrow"></div>');
    var input = el('<input type="text" class="nameinput" placeholder="Speaker name — e.g. Wood, Chris">');
    var btn = el('<button class="primary">Find talks</button>');
    searchRow.appendChild(input); searchRow.appendChild(btn);
    wrap.appendChild(searchRow);
    var resultsBox = el('<div class="searchresults"></div>');
    wrap.appendChild(resultsBox);

    function runSearch(overrideName) {
      var q = (overrideName != null ? overrideName : input.value).trim();
      input.value = q;
      resultsBox.innerHTML = "";
      if (!q) return;
      var matches = C.findMatches(q);
      if (!matches.length) {
        resultsBox.appendChild(el('<p class="muted">No talks found for “' + esc(q) + '”.</p>'));
        var dym = didYouMeanRow(q, runSearch);
        if (dym) resultsBox.appendChild(dym);
        return;
      }
      resultsBox.appendChild(el('<p class="muted">Found ' + matches.length + ' match'
        + (matches.length > 1 ? "es" : "") + ' — untick any that aren’t them:</p>'));
      var list = el('<div class="matchlist"></div>');
      var checks = [];
      matches.forEach(function (m) {
        var r = el('<label class="matchrow"><input type="checkbox" checked><span></span></label>');
        checks.push({ cb: r.querySelector("input"), id: m.id });
        r.querySelector("span").innerHTML = "<b>" + esc(m.day) + " " + esc(m.time) + "</b> · " + esc(m.room)
          + "<br>" + esc(m.title) + "<br><i>" + esc(m.presenter) + "</i>";
        list.appendChild(r);
      });
      resultsBox.appendChild(list);
      var confirm = el('<button class="primary">＋ Follow &amp; add their talks</button>');
      confirm.onclick = function () {
        var ids = checks.filter(function (c) { return c.cb.checked; }).map(function (c) { return c.id; });
        if (!ids.length) return C.flash("Pick at least one talk first.");
        var res = C.addFollowed(q, ids);
        var msg = res.applied.length + " talk" + (res.applied.length === 1 ? "" : "s") + " added";
        if (res.already.length) msg += " · " + res.already.length + " already in your schedule";
        if (res.overflow.length) msg += " · " + res.overflow.length + " didn’t fit (3 already kept there)";
        C.flash(msg);
        input.value = ""; resultsBox.innerHTML = "";
        renderChips();
      };
      resultsBox.appendChild(confirm);
    }
    btn.onclick = function () { runSearch(); };
    attachAutocomplete(input, runSearch);
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") runSearch(); });
    return wrap;
  }

  // ---------------- follow modal (reachable from play + review) ----------------
  var followModalOpen = false, followModalRoot = null;
  function toggleFollowModal(v) {
    followModalOpen = (v === undefined) ? !followModalOpen : !!v;
    renderFollowModal();
  }
  function renderFollowModal() {
    if (!followModalRoot) {
      followModalRoot = document.createElement("div");
      followModalRoot.id = "followModalRoot";
      document.body.appendChild(followModalRoot);
    }
    followModalRoot.innerHTML = "";
    if (!followModalOpen) return;
    var back = el('<div class="modal-back"></div>');
    back.onclick = function (e) { if (e.target === back) toggleFollowModal(false); };
    var panel = el('<div class="modal-panel"></div>');
    var closeBtn = el('<button class="modal-close" aria-label="Close">✕</button>');
    closeBtn.onclick = function () { toggleFollowModal(false); };
    panel.appendChild(closeBtn);
    panel.appendChild(followBlock());
    back.appendChild(panel);
    followModalRoot.appendChild(back);
    requestAnimationFrame(function () { back.classList.add("show"); });
  }
  function followBtn() {
    var n = C.state.followed.length;
    var b = el('<button class="ghost">👥 Speakers' + (n ? ' (' + n + ')' : '') + '</button>');
    b.onclick = function () { toggleFollowModal(true); };
    return b;
  }

  // ---------------- play ----------------
  function renderPlay() {
    if (!C.countChoices()) return C.goReview();
    var slot = C.currentSlot();
    var p = C.pick(slot);
    var step = C.state.step, n = C.countChoices();
    app.innerHTML = "";

    var bar = el('<div class="bar"></div>');
    bar.appendChild(el('<button class="ghost">◀ Back</button>')).onclick = C.back;
    bar.appendChild(el('<div class="prog"><div class="progbar"><i style="width:' + ((step + 1) / n * 100) + '%"></i></div>'
      + '<span>Slot ' + (step + 1) + ' of ' + n + '</span></div>'));
    bar.appendChild(followBtn());
    bar.appendChild(el('<button class="primary">Finish & review ✓</button>')).onclick = C.goReview;
    app.appendChild(bar);

    var wrap = el('<div class="playwrap"></div>');
    var main = el('<div class="main"></div>');
    C.bannersFor(step).forEach(function (ev) {
      if (ev.t === "day") main.appendChild(el('<div class="dayband">' + esc(ev.day) + '</div>'));
      else if (ev.t === "auto") main.appendChild(autoBanner(ev.item));
    });
    main.appendChild(el('<div class="slothead"><span class="when">' + esc(slot.day) + ' · ' + esc(slot.time) + '</span>'
      + '<span class="kept">Kept ' + p.kept.length + ' / 3</span></div>'));

    var grid = el('<div class="grid"></div>');
    slot.talks.forEach(function (tk) {
      var kept = p.kept.indexOf(tk.id) >= 0, star = p.star.indexOf(tk.id) >= 0, followed = C.isFollowedTalk(tk.id);
      var c = C.sessColor(tk.session);
      var card = el('<div class="card ' + (kept ? "kept" : "") + (star ? " star" : "") + '" style="--bar:' + c.bar + '"></div>');
      card.appendChild(el('<div class="cardtop"><span class="room">' + esc(tk.room) + (tk.seats ? ' · ' + tk.seats + ' seats' : "") + '</span>'
        + '<span class="tagrow">' + (followed ? '<span class="followtag">👥</span>' : "")
        + '<span class="tag" style="background:' + c.bg + ';color:' + c.fg + '">' + esc(tk.session || "General") + '</span></span></div>'));
      card.appendChild(el('<div class="title">' + esc(tk.title) + '</div>'));
      card.appendChild(el('<div class="pres">' + esc(tk.presenter || "") + '</div>'));
      var acts = el('<div class="acts"></div>');
      var kb = el('<button class="keepbtn ' + (kept ? "on" : "") + '">' + (kept ? "✓ Kept" : "＋ Keep") + '</button>');
      kb.onclick = function (ev) { ev.stopPropagation(); C.toggleKeep(slot, tk.id); };
      var sb = el('<button class="starbtn ' + (star ? "on" : "") + '" title="Must-see">' + (star ? "★" : "☆") + '</button>');
      sb.onclick = function (ev) { ev.stopPropagation(); C.toggleStar(slot, tk.id); };
      acts.appendChild(kb); acts.appendChild(sb);
      card.appendChild(acts);
      card.onclick = function () { C.toggleKeep(slot, tk.id); };
      grid.appendChild(card);
    });
    main.appendChild(grid);

    var nav = el('<div class="nav"></div>');
    var sk = el('<button class="ghost">Skip this slot</button>'); sk.onclick = function () { C.skipSlot(slot); };
    var nx = el('<button class="primary">' + (step < n - 1 ? "Next ▶" : "Done — review ✓") + '</button>'); nx.onclick = C.next;
    nav.appendChild(sk); nav.appendChild(nx);
    main.appendChild(nav);
    wrap.appendChild(main);

    var side = el('<div class="side"></div>');
    side.appendChild(el('<h4>Your ' + esc(slot.day) + '</h4>'));
    var list = el('<div class="agenda"></div>');
    C.dayAgenda(slot.day).forEach(function (it) { list.appendChild(agendaRow(it)); });
    side.appendChild(list);
    wrap.appendChild(side);
    app.appendChild(wrap);
  }

  function autoBanner(item) {
    if (item.type === "own")
      return el('<div class="banner own">🎤 Your talk — ' + esc(item.slot.time) + ' · ' + esc(item.talk.room)
        + ': “' + esc(item.talk.title) + '” <em>added automatically</em></div>');
    if (item.type === "single")
      return el('<div class="banner plen">★ ' + esc(item.slot.time) + ' · ' + esc(item.talk.room)
        + ': ' + esc(item.talk.title) + ' <em>(single track — added)</em></div>');
    var lbl = { break: "☕ Break", lunch: "🍽 Lunch", poster: "🖼 Poster session", free: "🚌 Free afternoon" }[item.item.type];
    return el('<div class="banner fix">' + lbl + ' · ' + esc(item.item.time) + ' <em>added automatically</em></div>');
  }

  function agendaRow(it) {
    if (it.type === "own")
      return el('<div class="arow own"><span class="t">' + esc(it.slot.time) + '</span>'
        + '<span class="c"><b>🎤 Your talk</b> — ' + esc(it.talk.room) + '<br>' + esc(it.talk.title) + '</span></div>');
    if (it.type === "single")
      return el('<div class="arow"><span class="t">' + esc(it.slot.time) + '</span>'
        + '<span class="c">' + esc(it.talk.title) + '<br><i>' + esc(it.talk.presenter || it.talk.room) + '</i></span></div>');
    if (it.type === "fixed") {
      var lbl = C.FIXLBL[it.item.type];
      return el('<div class="arow fix"><span class="t">' + esc(it.slot.time) + '</span><span class="c">' + lbl + '</span></div>');
    }
    var starset = it.star;
    var inner = it.kept.map(function (tk) {
      var s = (starset.indexOf(tk.id) >= 0 ? "★ " : "") + (C.isFollowedTalk(tk.id) ? "👥 " : "");
      return '<div class="opt">' + s + esc(tk.room) + ' — ' + esc(tk.title) + '<br><i>' + esc(tk.presenter || "") + '</i></div>';
    }).join("");
    var many = it.kept.length > 1 ? ' many' : '';
    return el('<div class="arow choice' + many + '"><span class="t">' + esc(it.slot.time) + '</span>'
      + '<span class="c">' + (it.kept.length > 1 ? '<span class="cue">choose one</span>' : "") + inner + '</span></div>');
  }

  // ---------------- review ----------------
  function renderReview() {
    app.innerHTML = "";
    var head = el('<div class="rvhead"></div>');
    head.appendChild(el('<button class="ghost">◀ Keep editing</button>')).onclick = function () { C.goPlay(0); };
    head.appendChild(el('<h2>My ICBF 2026 Schedule</h2>'));
    var acts = el('<div class="rvacts"></div>');
    acts.appendChild(followBtn());
    acts.appendChild(el('<button class="primary big">⬇ Download PDF</button>')).onclick = C.downloadPDF;
    acts.appendChild(el('<button class="ghost">🖨 Print</button>')).onclick = C.printSchedule;
    var rs = el('<button class="link">↺ Start over</button>');
    rs.onclick = function () { if (confirm("Clear all picks and start over?")) C.startOver(); };
    acts.appendChild(rs);
    head.appendChild(acts);
    app.appendChild(head);

    var ag = C.assemble();
    var body = el('<div class="rvbody"></div>');
    var cur = null;
    ag.forEach(function (it) {
      if (it.type === "dayhead") { cur = el('<div class="rvday"><h3>' + esc(it.day) + '</h3></div>'); body.appendChild(cur); return; }
      if (!cur) { cur = el('<div class="rvday"></div>'); body.appendChild(cur); }
      var row = agendaRow(it);
      if (it.type === "choice") {
        row.classList.add("editable");
        row.title = "Click to change this pick";
        (function (slotKey) {
          row.onclick = function () { var i = C.choiceIndexForKey(slotKey); if (i >= 0) C.goPlay(i); };
        })(C.key(it.slot));
      }
      cur.appendChild(row);
    });
    if (!ag.some(function (i) { return i.type !== "dayhead"; }))
      body.appendChild(el('<p class="muted">Nothing selected yet. Go back and keep some talks.</p>'));
    app.appendChild(body);
    C.renderPrintArea();
  }

  function boot() {
    app = document.getElementById("app");
    C.subscribe(render);
    C.init();
  }
  global.ICBF_UIS = global.ICBF_UIS || {};
  global.ICBF_UIS.desktop = { mount: boot, render: render };
})(typeof window !== "undefined" ? window : globalThis);
