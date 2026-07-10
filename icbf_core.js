/* ICBF 2026 Schedule Builder — shared core (no DOM rendering).
   Owns the data, the pick rules, persistence, navigation state and the PDF/print
   export. UIs (desktop / mobile) register a render callback via subscribe(); every
   state change calls notify(), which refreshes derived data then re-renders.
   SCHEDULE ({meta,entries} or a bare array) and window.jspdf are injected by build. */
(function (global) {
  "use strict";

  var RAW = global.SCHEDULE || [];
  var META = (RAW && !Array.isArray(RAW) && RAW.meta) ? RAW.meta : null;
  var DATA = (RAW && !Array.isArray(RAW) && RAW.entries) ? RAW.entries : RAW;
  DATA.forEach(function (e, i) { e.id = i; });

  var DAY_ORDER = ["Mon Jul 13", "Tue Jul 14", "Wed Jul 15", "Thu Jul 16"];
  var ALL_DAYS = DAY_ORDER.filter(function (d) {
    return DATA.some(function (e) { return e.day === d; });
  });

  var state = {
    days: ALL_DAYS.slice(), picks: {}, step: 0, screen: "start",
    presenterMode: null, myName: "", myTalkIds: [], uiSearching: false
  };
  var STREAM = [], CHOICES = [];
  var subscriber = null;

  // ---------- helpers ----------
  function mins(t) { var p = t.split(":"); return (+p[0]) * 60 + (+p[1]); }
  function byId(id) { return DATA[id]; }
  function key(slot) { return slot.day + "__" + slot.time; }
  function isTalk(e) { return e.type === "talk" || e.type === "plenary"; }
  function isFixed(e) { return ["break", "lunch", "poster", "free"].indexOf(e.type) >= 0; }
  function isMine(e) { return state.myTalkIds.indexOf(e.id) >= 0; }

  function normName(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  function findMatches(query) {
    var qTokens = normName(query).split(/[\s,]+/).filter(Boolean);
    if (!qTokens.length) return [];
    return DATA.filter(function (e) {
      if (!isTalk(e)) return false;
      var p = normName(e.presenter);
      return qTokens.every(function (t) { return p.indexOf(t) >= 0; });
    });
  }

  function daySlots(day) {
    var es = DATA.filter(function (e) { return e.day === day; });
    var times = [];
    es.forEach(function (e) { if (times.indexOf(e.time) < 0) times.push(e.time); });
    times.sort(function (a, b) { return mins(a) - mins(b); });
    return times.map(function (t) {
      var at = es.filter(function (e) { return e.time === t; });
      var talks = at.filter(isTalk);
      var fixed = at.filter(isFixed);
      var own = talks.filter(isMine)[0] || null;
      var kind = own ? "own" : talks.length >= 2 ? "choice" : talks.length === 1 ? "single" : "fixed";
      return { day: day, time: t, at: at, talks: talks, fixed: fixed, own: own, kind: kind };
    });
  }

  function buildStream() {
    STREAM = []; CHOICES = [];
    state.days.forEach(function (day) {
      STREAM.push({ t: "day", day: day });
      daySlots(day).forEach(function (slot) {
        if (slot.kind === "own") STREAM.push({ t: "auto", item: { type: "own", slot: slot, talk: slot.own } });
        else if (slot.kind === "single") STREAM.push({ t: "auto", item: { type: "single", slot: slot, talk: slot.talks[0] } });
        else if (slot.kind === "choice") STREAM.push({ t: "choice", slot: slot });
        var seen = {};
        slot.fixed.forEach(function (f) {
          if (!seen[f.type]) { seen[f.type] = 1; STREAM.push({ t: "auto", item: { type: "fixed", slot: slot, item: f } }); }
        });
      });
    });
    CHOICES = STREAM.filter(function (e) { return e.t === "choice"; });
    if (state.step >= CHOICES.length) state.step = Math.max(0, CHOICES.length - 1);
    return CHOICES;
  }

  function assemble() {
    var out = [];
    STREAM.forEach(function (ev) {
      if (ev.t === "day") out.push({ type: "dayhead", day: ev.day });
      else if (ev.t === "auto") out.push(ev.item);
      else if (ev.t === "choice") {
        var p = state.picks[key(ev.slot)];
        if (p && p.kept.length) {
          out.push({ type: "choice", slot: ev.slot, kept: p.kept.map(byId), star: p.star.slice() });
        }
      }
    });
    return out;
  }

  function bannersFor(step) {
    var idx = STREAM.indexOf(CHOICES[step]);
    var prev = step > 0 ? STREAM.indexOf(CHOICES[step - 1]) : -1;
    return STREAM.slice(prev + 1, idx);
  }
  function dayAgenda(day) {
    return assemble().filter(function (it) {
      if (it.type === "dayhead") return false;
      return (it.slot ? it.slot.day : null) === day;
    });
  }

  function hashHue(s) { var h = 0; for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360; return h; }
  function sessColor(s) {
    if (!s) return { bg: "#eef1f6", fg: "#3a4256", bar: "#8892a6" };
    var h = hashHue(s);
    return { bg: "hsl(" + h + " 68% 94%)", fg: "hsl(" + h + " 55% 32%)", bar: "hsl(" + h + " 62% 55%)" };
  }

  // ---------- persistence ----------
  function save() {
    try {
      localStorage.setItem("icbf_planner_v1", JSON.stringify({
        days: state.days, picks: state.picks,
        presenterMode: state.presenterMode, myName: state.myName, myTalkIds: state.myTalkIds
      }));
    } catch (e) {}
  }
  function load() {
    try {
      var s = JSON.parse(localStorage.getItem("icbf_planner_v1"));
      if (s && s.days) { state.days = s.days.filter(function (d) { return ALL_DAYS.indexOf(d) >= 0; }); state.picks = s.picks || {}; }
      if (s) {
        state.presenterMode = s.presenterMode || null;
        state.myName = s.myName || "";
        state.myTalkIds = (s.myTalkIds || []).filter(function (id) { return DATA[id]; });
      }
    } catch (e) {}
    if (!state.days.length) state.days = ALL_DAYS.slice();
  }

  // ---------- pick logic ----------
  function pick(slot) { var k = key(slot); return (state.picks[k] = state.picks[k] || { kept: [], star: [] }); }
  function toggleKeep(slot, id) {
    var p = pick(slot), i = p.kept.indexOf(id);
    if (i >= 0) { p.kept.splice(i, 1); var j = p.star.indexOf(id); if (j >= 0) p.star.splice(j, 1); }
    else { if (p.kept.length >= 3) { flash("You can keep up to 3 talks per slot — unkeep one first."); return; } p.kept.push(id); }
    save(); notify();
  }
  function toggleStar(slot, id) {
    var p = pick(slot), j = p.star.indexOf(id);
    if (j >= 0) p.star.splice(j, 1);
    else {
      if (p.kept.indexOf(id) < 0) { if (p.kept.length >= 3) { flash("Max 3 kept — unkeep one to star another."); return; } p.kept.push(id); }
      p.star.push(id);
    }
    save(); notify();
  }
  function skipSlot(slot) { var p = pick(slot); p.kept = []; p.star = []; save(); next(); }

  // ---------- navigation ----------
  function next() { if (state.step < CHOICES.length - 1) { state.step++; state.screen = "play"; notify(); } else goReview(); }
  function back() { if (state.step > 0) { state.step--; state.screen = "play"; notify(); } else goStart(); }
  function goStart() { state.screen = "start"; notify(); }
  function goPlay(step) { if (typeof step === "number") state.step = step; state.screen = "play"; notify(); }
  function goReview() { state.screen = "review"; notify(); }
  function startOver() { state.picks = {}; state.step = 0; save(); goStart(); }

  function toggleDay(d) {
    var i = state.days.indexOf(d);
    if (i >= 0) state.days.splice(i, 1); else state.days.push(d);
    state.days.sort(function (a, c) { return ALL_DAYS.indexOf(a) - ALL_DAYS.indexOf(c); });
    save(); notify();
  }
  function setPresenterMode(m) { state.presenterMode = m; if (m === "no") state.myTalkIds = []; save(); notify(); }
  function setSearching(b) { state.uiSearching = b; notify(); }
  function setMyName(s) { state.myName = s; save(); }
  function confirmMyTalks(ids) { state.myTalkIds = ids.slice(); state.uiSearching = false; save(); notify(); }

  function countChoices() { return CHOICES.length; }
  function hasPicks() { return Object.keys(state.picks).some(function (k) { return state.picks[k].kept.length; }); }
  function currentSlot() { return CHOICES.length ? CHOICES[state.step].slot : null; }
  function choiceIndexForKey(k) {
    for (var i = 0; i < CHOICES.length; i++) { if (key(CHOICES[i].slot) === k) return i; }
    return -1;
  }

  // ---------- toast ----------
  function flash(msg) {
    if (typeof document === "undefined") return;
    var t = document.getElementById("toast"); if (!t) return;
    t.textContent = msg; t.className = "toast show";
    clearTimeout(flash._h); flash._h = setTimeout(function () { t.className = "toast"; }, 2200);
  }
  function esc(s) {
    return (s == null ? "" : String(s)).replace(/[&<>"]/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c];
    });
  }

  // ---------- print (shared #printArea) ----------
  var FIXLBL = { break: "Break", lunch: "Lunch", poster: "Poster session", free: "Free afternoon" };
  function prow(t, c) { return '<div class="prow"><span class="pt">' + esc(t) + '</span><span class="pc">' + c + '</span></div>'; }
  function renderPrintArea() {
    var pa = document.getElementById("printArea");
    if (!pa) return;
    var ag = assemble();
    var h = '<h1>My ICBF 2026 Schedule</h1>';
    ag.forEach(function (it) {
      if (it.type === "dayhead") { h += '<h2>' + esc(it.day) + '</h2>'; return; }
      var t = it.slot ? it.slot.time : "";
      if (it.type === "own") h += prow(t, "<b>Your talk</b> — " + esc(it.talk.room) + ": " + esc(it.talk.title));
      else if (it.type === "single") h += prow(t, esc(it.talk.title) + " — <i>" + esc(it.talk.presenter || it.talk.room) + "</i>");
      else if (it.type === "fixed") h += prow(t, "<i>" + esc(FIXLBL[it.item.type]) + "</i>");
      else if (it.type === "choice") {
        var opts = it.kept.map(function (tk) {
          var s = it.star.indexOf(tk.id) >= 0 ? "★ " : "";
          return s + esc(tk.room) + ": " + esc(tk.title) + " — <i>" + esc(tk.presenter || "") + "</i>";
        }).join("<br>");
        h += prow(t, (it.kept.length > 1 ? "<u>choose one</u><br>" : "") + opts);
      }
    });
    pa.innerHTML = h;
  }
  function printSchedule() { renderPrintArea(); window.print(); }

  // ---------- PDF ----------
  function pdfSafe(s) {
    return String(s == null ? "" : s)
      .replace(/[₀₁₂₃₄₅₆₇₈₉]/g, function (d) { return String("₀₁₂₃₄₅₆₇₈₉".indexOf(d)); })
      .replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]/g, function (d) { return String("⁰¹²³⁴⁵⁶⁷⁸⁹".indexOf(d)); })
      .replace(/[“”]/g, '"').replace(/[‘’]/g, "'").replace(/★/g, "*");
  }
  function buildPDF() {
    if (!(global.jspdf && global.jspdf.jsPDF)) return null;
    var jsPDF = global.jspdf.jsPDF;
    var doc = new jsPDF({ unit: "pt", format: "a4" });
    var M = 42, W = doc.internal.pageSize.getWidth(), PH = doc.internal.pageSize.getHeight();
    var TX = M + 52, TW = W - TX - M, y = M;
    function need(h) { if (y + h > PH - M) { doc.addPage(); y = M; } }
    doc.setFont("helvetica", "bold").setFontSize(20).text("My ICBF 2026 Schedule", M, y); y += 20;
    doc.setFont("helvetica", "normal").setFontSize(9).setTextColor(130)
      .text("International Congress on the Biology of Fish 2026 · generated " + new Date().toLocaleDateString(), M, y);
    doc.setTextColor(20); y += 18;

    assemble().forEach(function (it) {
      if (it.type === "dayhead") {
        need(40); y += 10;
        doc.setFont("helvetica", "bold").setFontSize(14).text(pdfSafe(it.day), M, y); y += 6;
        doc.setDrawColor(190).line(M, y, W - M, y); y += 14; return;
      }
      var t = it.slot ? it.slot.time : "";
      var lines = [], own = false;
      if (it.type === "own") { own = true; lines = ["Your talk — " + it.talk.room, it.talk.title]; }
      else if (it.type === "single") { lines = [it.talk.title, (it.talk.presenter || it.talk.room)]; }
      else if (it.type === "fixed") { lines = [FIXLBL[it.item.type]]; }
      else if (it.type === "choice") {
        if (it.kept.length > 1) lines.push("Choose one:");
        it.kept.forEach(function (tk) {
          var s = it.star.indexOf(tk.id) >= 0 ? "* " : "";
          lines.push(s + tk.room + ": " + tk.title);
          if (tk.presenter) lines.push("   " + tk.presenter);
        });
      }
      var wrapped = [];
      lines.forEach(function (ln) {
        var bold = own || ln.indexOf("Choose one") === 0;
        doc.setFont("helvetica", bold ? "bold" : "normal").setFontSize(10);
        doc.splitTextToSize(pdfSafe(ln), TW).forEach(function (w) { wrapped.push({ txt: w, bold: bold }); });
      });
      var h = wrapped.length * 13 + 6;
      need(h);
      doc.setFont("helvetica", "bold").setFontSize(10).setTextColor(it.type === "fixed" ? 150 : 20).text(pdfSafe(t), M, y + 10);
      wrapped.forEach(function (w, i) {
        doc.setFont("helvetica", w.bold ? "bold" : "normal").setFontSize(10)
          .setTextColor(it.type === "fixed" ? 150 : own ? 30 : 40)
          .text(w.txt, TX, y + 10 + i * 13);
      });
      doc.setTextColor(20);
      y += h;
    });
    return doc;
  }
  var PDF_NAME = "My-ICBF-2026-Schedule.pdf";
  function downloadPDF() {
    var doc = buildPDF();
    if (!doc) { flash("PDF library not loaded — using Print instead."); return printSchedule(); }
    doc.save(PDF_NAME);
  }
  function openPDF() {  // iOS Safari: save() is unreliable; open a blob so the share sheet works
    var doc = buildPDF();
    if (!doc) { flash("PDF library not loaded — using Print instead."); return printSchedule(); }
    try { window.open(doc.output("bloburl"), "_blank"); }
    catch (e) { doc.save(PDF_NAME); }
  }

  // ---------- wiring ----------
  function subscribe(fn) { subscriber = fn; }
  function notify() { buildStream(); if (subscriber) subscriber(); }
  function init() { load(); buildStream(); if (subscriber) subscriber(); }

  global.ICBFCore = {
    // data / queries
    DATA: DATA, META: META, ALL_DAYS: ALL_DAYS, state: state,
    daySlots: daySlots, buildStream: buildStream, assemble: assemble, bannersFor: bannersFor,
    dayAgenda: dayAgenda, sessColor: sessColor, findMatches: findMatches, byId: byId, key: key,
    pick: pick, currentSlot: currentSlot, countChoices: countChoices, hasPicks: hasPicks,
    choiceIndexForKey: choiceIndexForKey, renderPrintArea: renderPrintArea, FIXLBL: FIXLBL,
    // actions
    toggleKeep: toggleKeep, toggleStar: toggleStar, skipSlot: skipSlot,
    next: next, back: back, goStart: goStart, goPlay: goPlay, goReview: goReview, startOver: startOver,
    toggleDay: toggleDay, setPresenterMode: setPresenterMode, setSearching: setSearching,
    setMyName: setMyName, confirmMyTalks: confirmMyTalks,
    // io
    downloadPDF: downloadPDF, openPDF: openPDF, printSchedule: printSchedule,
    esc: esc, flash: flash,
    subscribe: subscribe, notify: notify, init: init
  };
})(typeof window !== "undefined" ? window : globalThis);
