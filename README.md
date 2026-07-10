# 🐟 ICBF 2026 Schedule Planner

A personal-schedule builder for the [26th International Congress on the Biology of Fish](https://icbf2026.com)
(Vancouver, July 13–16, 2026). ICBF runs 6–7 parallel symposium tracks at once — this turns that grid into a
guided, timeslot-by-timeslot picker and exports a clean personal itinerary as a PDF.

**Live app:** https://mbel-tech.github.io/icbf-planner/

Works fully offline once opened once (it's an installable PWA — "Add to Home Screen" on iOS/Android), so it
still works in a conference hall with no wifi.

## Features

- **Pick, don't just browse.** Step through every timeslot; where rooms run parallel talks, keep up to **3**
  you're torn between (they show up in your final schedule as a "choose one" group) and **★ star** the
  must-not-miss ones.
- **Auto-added fixed items.** Breaks, lunches, poster sessions, free afternoons and plenary talks are inserted
  automatically — no decision needed.
- **"Are you presenting?"** Type your name and the app finds your talk(s) in the program and auto-books that
  slot for you, skipping it from the choice screens.
- **One file, both layouts.** Opens on mobile by default; a button on the start screen switches to a wider
  desktop layout in place, with no reload and no lost picks. Your choice is remembered next time.
- **Export.** One-tap PDF of your final schedule (time · room · title · presenter, ★ and "Your talk" marked).
  On iOS, an "Open PDF" fallback opens it in a new tab for the share sheet, since silent downloads are
  unreliable in Safari.
- **Offline-first.** A service worker caches the app shell on first load, so it keeps working with zero
  connection afterward. All data (schedule + PDF generator) is bundled inline — no runtime network calls.

## How the schedule data stays current

ICBF revises the published PDF schedule periodically. `icbf_parse.py` refreshes it automatically:

1. Tries to list the conference site's uploads directory (works if the organizers ever enable indexing).
2. Otherwise scrapes `icbf2026.com/program/` for `Detailed-ICBF-2026-Schedule-<Month>-<Day>-<Year>-*.pdf`
   links and picks the newest by date.
3. Falls back to the copy committed in [`schedule_cache/`](schedule_cache) if the network step fails for any
   reason (offline, site down, layout changed) — a build never breaks because of a bad network day.

Downloads are cached by ETag (cheap `304`s on re-runs) and verified (`%PDF-` magic bytes + `Content-Type`)
before being trusted. The PDF text is also run through Unicode NFKC normalization to fix ligature glyphs
(`ﬁ`, `ﬀ`, `ﬂ`) that some export tools embed — without it, words like "fish" and "effect" silently break.

A handful of rows are genuinely ambiguous for a parser (multi-person "Name, Org" chains with no reliable
comma pattern) and are hand-corrected via `MANUAL_OVERRIDES` in `icbf_parse.py`, each guarded by an
`expect_presenter_contains` check — if a schedule revision shifts that row, the override is skipped with a
loud warning instead of silently rewriting the wrong talk.

## Rebuilding

```
python icbf_parse.py          # re-scrape + re-parse -> icbf_schedule.json
python icbf_icons.py          # regenerate docs/icons/ (only needed if the icon design changes)
python icbf_build.py site     # assemble docs/index.html + manifest + service worker
```

`python icbf_parse.py --offline` skips the network entirely and parses the bundled `schedule_cache/` PDF.
`python icbf_build.py mobile` / `desktop` / `both` also produce standalone single-file builds outside `docs/`
for local testing without a server.

Commit `docs/` and push — GitHub Pages serves directly from `main` / `docs`, so a push is the whole deploy.

## Project layout

```
icbf_parse.py          PDF discovery, download, parse -> icbf_schedule.json
icbf_core.js            shared state, pick rules, PDF export (no DOM)
icbf_ui_desktop.js       desktop renderer
icbf_ui_mobile.js       mobile renderer (touch gestures, bottom sheet, safe-area aware)
icbf_build.py            assembles docs/index.html from the above + jsPDF
icbf_icons.py           generates docs/icons/*
icbf_qr.py              QR code for the live URL
schedule_cache/          bundled fallback PDF + its ETag/hash metadata
docs/                   the built, deployed site (GitHub Pages root)
```

`icbf_core.js` has no DOM code — both UIs render off the same state, pick rules, and PDF generator, so mobile
and desktop can never drift on what a "pick" means.

## Not affiliated with ICBF 2026

This is an independent tool built from the publicly posted schedule PDF, not an official conference product.
