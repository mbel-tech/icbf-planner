# -*- coding: utf-8 -*-
"""
Parse the ICBF 2026 detailed schedule PDF into clean structured data
-> icbf_schedule.json  ({ "meta": {...}, "entries": [...] })

Source of truth is the conference website. On each run this script tries to
discover and download the *latest* "Detailed-ICBF-2026-Schedule-<Month>-<D>-<Year>"
PDF, and falls back to the copy bundled in ./schedule_cache/ if the network is
unavailable. The PDF's own text layer is clean UTF-8 (parsed directly, no OCR).

Usage:
  python icbf_parse.py            # discover + download latest, else bundled
  python icbf_parse.py --offline  # skip network, use bundled fallback
  python icbf_parse.py --pdf FILE # parse an explicit local PDF
  python icbf_parse.py --force    # ignore the ETag cache, re-download
"""
import re, json, sys, ssl, time, hashlib, argparse, datetime, unicodedata, subprocess
from pathlib import Path
from collections import Counter
import urllib.request, urllib.error
import pypdf

HERE = Path(__file__).resolve().parent
OUT = HERE / "icbf_schedule.json"
CACHE = HERE / "schedule_cache"
BUNDLED = CACHE / "Detailed-ICBF-2026-Schedule-July-3-2026-FINAL-w-logo.pdf"

# discovery
UPLOADS_DIR = "https://icbf2026.com/wp-content/uploads/2026/07/"
PROGRAM_URL = "https://icbf2026.com/program/"
UA = "Mozilla/5.0 (ICBF-planner build script)"
SCHED_RE = re.compile(
    r'Detailed-ICBF-\d{4}-Schedule-(?P<mon>[A-Za-z]+)-(?P<day>\d{1,2})-(?P<year>\d{4})', re.I)

# ---------------------------------------------------------------- structure
SESSIONS = sorted({
    "STRESS I", "STRESS II", "GROWTH", "CHANGE I", "CHANGE II", "ANCIENT FISHES",
    "MOTION I", "MOTION II", "NEURO", "TOXICOLOGY", "DEVELOPMENT", "IMMUNOLOGY",
    "EVOLUTION", "IONS I", "IONS II", "AQUACULTURE", "WELFARE", "REPRODUCTION",
    "ADVANCES", "RESPIRATION", "POLAR", "TROPICAL", "SENSING", "CARDIO",
    "DEEP BLUE", "DIGESTION", "INVASIVE", "MECHANISMS",
}, key=len, reverse=True)
SESS_ALT = '|'.join(re.escape(s) for s in SESSIONS)
SESS_START_RE = re.compile(r'^(?:' + SESS_ALT + r')\b')

DAYINFO = {
    "13": ("Mon Jul 13", "2026-07-13", "Monday"),
    "14": ("Tue Jul 14", "2026-07-14", "Tuesday"),
    "15": ("Wed Jul 15", "2026-07-15", "Wednesday"),
    "16": ("Thu Jul 16", "2026-07-16", "Thursday"),
}
WD_NUM = {"Monday": "13", "Tuesday": "14", "Wednesday": "15", "Thursday": "16"}

TIME_RE = re.compile(r'^\s*(\d{1,2}):(\d{2})\b(.*)$')
FIXED_RE = re.compile(r'\b(BREAK|LUNCH|POSTER\s*SESSION|POSTER|FREE\s*AFTERNOON|END)\b', re.I)
ROOM_RE = re.compile(r'IRC\s*([0-9])', re.I)
SEATS_RE = re.compile(r'\((\d+)\s*seats?\)', re.I)
# surname = a capitalized token, optionally followed by a generational suffix
# (Jr./Sr./II/III/IV) so "Negrete Jr., Benjamin" splits correctly rather than
# leaving "Negrete" stranded on the title. The suffix is required-adjacent, so
# a capitalized title word before the surname (e.g. "…Amazon Val, Adalberto")
# is NOT absorbed.
PRES_RE_SINGLE = re.compile(
    r'([A-ZÀ-Ý][A-Za-zÀ-ÿ\'’.\-]+(?:\s+(?:Jr|Sr|II|III|IV)\.?)?),\s+([A-ZÀ-Ý][^,]*?)\s*$')

# Entries whose title/presenter cannot be split reliably by the general
# heuristic (multiple co-presenters written "Name, Org/Role"). Keyed by
# (day, room, time). Because those keys shift when the schedule is revised,
# each override carries an `expect` fragment: if the freshly-parsed presenter
# no longer contains it, the override is SKIPPED with a loud warning instead
# of silently rewriting the wrong talk.
MANUAL_OVERRIDES = {
    ("Mon Jul 13", "IRC 2", "08:30"): dict(
        expect="MacKinlay",
        title="Welcome to ICBF 2026 and the plenary sessions",
        presenter="Don MacKinlay, DFO SEP, Colin Brauner, Co-Chairs"),
    ("Mon Jul 13", "IRC 2", "08:45"): dict(
        expect="Eliason",
        title='American Fisheries Society, Physiology section “Award of Excellence” introduction',
        presenter="Erika Eliason, AFS Physiology President"),
    ("Mon Jul 13", "IRC 2", "09:00"): dict(
        expect="Brauner",
        title="“Award of Excellence Lecture: Adaptations and acclimation to the environment "
              "in fishes: Integrating basic and applied research",
        presenter="Colin Brauner, UBC Zoology"),
    ("Mon Jul 13", "IRC 2", "09:45"): dict(
        expect="Tresguerres",
        title="From shark gills to coral reefs: Discovering mechanisms and developing solutions",
        presenter="Martin Tresguerres, UC San Diego"),
    ("Wed Jul 15", "IRC 4", "14:30"): dict(
        expect="Planas",
        title="Closing remarks",
        presenter="Planas, Josep, Bobe, Julien, MacKenzie, Simon"),
    ("Thu Jul 16", "IRC 4", "11:45"): dict(
        expect="MacCormack",
        title="Acclimation to mild static and cyclic hypoxia reduces cardiac thermal tolerance "
              "in brook char (Salvelinus fontinalis); potential contribution of novel "
              "lactoylated amino acids",
        presenter="MacCormack, Tyson"),
    # `expect` here is a TITLE fragment, not the surname: the general parser
    # truncates "Bauer Reid"->"Reid" / "Tamarit Castro"->"Castro" (the very bug
    # these overrides fix), so a surname fragment would fail its own guard.
    ("Thu Jul 16", "IRC 3", "09:30"): dict(
        expect="Developmental acclimation to local thermal",
        title="Developmental acclimation to local thermal environments shapes physiological "
              "and hormonal warming responses in anemone-associated reef fish",
        presenter="Bauer Reid, Heather"),
    ("Thu Jul 16", "IRC 3", "10:00"): dict(
        expect="European plaice",
        title="Seasonal thermal tolerance, growth and acclimation capacity in newly settled "
              "European plaice (Pleuronectes platessa) from Swedish coastal nursery habitats",
        presenter="Tamarit Castro, Elena"),
}


# ================================================================ networking
def _http_get(url, extra_headers=None, timeout=30):
    """GET via urllib; on any failure retry once with curl (Win10+ ships curl).
    Returns (status, headers_dict, body_bytes). Raises on total failure."""
    headers = {"User-Agent": UA}
    if extra_headers:
        headers.update(extra_headers)
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=headers)
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
        except urllib.error.HTTPError as e:
            return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, b""
        except Exception as e:  # noqa: BLE001 - network/TLS/timeout
            last = e
            time.sleep(0.6 * (attempt + 1))
    # curl fallback (proven to work in restricted TLS environments)
    try:
        cmd = ["curl", "-sS", "-L", "--max-time", str(timeout), url]
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
        body = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        if body:
            return 200, {}, body
    except Exception as e:  # noqa: BLE001
        last = e
    raise last if last else RuntimeError("http get failed")


def _candidates_from_html(html, base):
    """Return [(date, url)] for Detailed-Schedule PDFs linked in HTML."""
    out = []
    for m in re.finditer(r'''(?:href|src)=["']([^"']+?\.pdf)["']''', html, re.I):
        href = m.group(1)
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://icbf2026.com" + href
        elif not href.lower().startswith("http"):
            href = base.rstrip("/") + "/" + href
        sm = SCHED_RE.search(href)
        if not sm:
            continue
        try:
            d = datetime.datetime.strptime(
                f"{sm.group('mon')} {sm.group('day')} {sm.group('year')}", "%B %d %Y").date()
        except ValueError:
            try:
                d = datetime.datetime.strptime(
                    f"{sm.group('mon')} {sm.group('day')} {sm.group('year')}", "%b %d %Y").date()
            except ValueError:
                continue
        out.append((d, href))
    return out


def discover_latest_url():
    """Best-effort discovery of the newest Detailed-Schedule PDF URL."""
    # 1) try a directory listing (403 today, but free if ever enabled)
    for src in (UPLOADS_DIR, PROGRAM_URL):
        try:
            status, _, body = _http_get(src)
            if status != 200 or not body:
                print(f"  discovery: {src} -> HTTP {status}")
                continue
            cands = _candidates_from_html(body.decode("utf-8", "replace"), src)
            if cands:
                cands.sort(reverse=True)
                print(f"  discovery: {src} -> {len(cands)} candidate(s), "
                      f"newest {cands[0][0].isoformat()}")
                return cands[0][1]
            print(f"  discovery: {src} -> no Detailed-Schedule links")
        except Exception as e:  # noqa: BLE001
            print(f"  discovery: {src} -> {type(e).__name__}: {e}")
    return None


def fetch_pdf(url, force=False):
    """Download `url` into schedule_cache with ETag caching + integrity checks.
    Returns (path, was_cached_bool). Raises on any hard failure."""
    CACHE.mkdir(exist_ok=True)
    fname = url.rsplit("/", 1)[-1].split("?")[0]
    dest = CACHE / fname
    meta = CACHE / (fname + ".meta.json")
    prev = {}
    if meta.exists():
        try:
            prev = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prev = {}
    headers = {}
    if dest.exists() and prev.get("etag") and not force:
        headers["If-None-Match"] = prev["etag"]
    status, hdrs, body = _http_get(url, extra_headers=headers)
    if status == 304 and dest.exists():
        print(f"  fetch: 304 Not Modified -> cached {fname}")
        return dest, True
    if status != 200 or not body:
        raise RuntimeError(f"download {url} -> HTTP {status}")
    ctype = (hdrs.get("content-type") or "").lower()
    if "pdf" not in ctype and not body[:5] == b"%PDF-":
        raise RuntimeError(f"not a PDF (content-type={ctype!r}, magic={body[:5]!r})")
    if not body.startswith(b"%PDF-"):
        raise RuntimeError(f"bad PDF magic bytes: {body[:5]!r}")
    sha = hashlib.sha256(body).hexdigest()
    dest.write_bytes(body)
    meta.write_text(json.dumps({
        "etag": hdrs.get("etag"), "last_modified": hdrs.get("last-modified"),
        "sha256": sha, "url": url, "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }, indent=1), encoding="utf-8")
    print(f"  fetch: downloaded {fname} ({len(body)} bytes, sha {sha[:12]}…)")
    return dest, False


def resolve_source(args):
    """Return (pdf_path, source_url_or_None) honoring CLI flags + fallback chain."""
    if args.pdf:
        p = Path(args.pdf)
        if not p.exists():
            sys.exit(f"--pdf not found: {p}")
        print(f"Source: explicit --pdf {p}")
        return p, None
    if not args.offline:
        url = discover_latest_url()
        if url:
            try:
                path, cached = fetch_pdf(url, force=args.force)
                print(f"Source: {'cached' if cached else 'downloaded'} {url}")
                return path, url
            except Exception as e:  # noqa: BLE001
                print(f"  fetch failed ({type(e).__name__}: {e}) — falling back to bundled")
        else:
            print("  discovery failed — falling back to bundled")
    else:
        print("Source: --offline, using bundled fallback")
    if not BUNDLED.exists():
        sys.exit(f"No source available and bundled fallback missing: {BUNDLED}")
    print(f"Source: bundled {BUNDLED.name}")
    return BUNDLED, None


# ================================================================ parsing
def clean(s):
    return re.sub(r'\s+', ' ', s).strip()


def polish(s):
    s = re.sub(r'(\w)-\s+(\w)', r'\1-\2', s)   # rejoin hyphen-wrapped words
    s = re.sub(r'\bCO\s*2\b', 'CO₂', s)
    s = re.sub(r'\bO\s*2\b', 'O₂', s)
    return s.strip(' .,-')


def strip_lead(line):
    return re.sub(r'^\s*\d{1,2}:\d{2}\s*', '', line).strip()


def header_session(line):
    m = SESS_START_RE.match(strip_lead(line))
    return m.group(0).upper() if m else None


def extract_pdf_lines(pdf_path):
    reader = pypdf.PdfReader(str(pdf_path))
    lines = []
    for page in reader.pages:
        # NFKC folds ligatures (ﬁ→fi, ﬀ→ff, ﬂ→fl) and sub/superscripts that the
        # PDF font layer emits; polish() re-applies CO₂/O₂ afterwards.
        text = unicodedata.normalize("NFKC", page.extract_text())
        page_lines = text.splitlines()
        for i, ln in enumerate(page_lines):
            if re.fullmatch(r'\s*\d{1,3}\s*', ln) and (i == 0 or page_lines[i - 1].strip() == ''):
                continue  # standalone page-number footer
            lines.append(ln)
    return lines, len(reader.pages)


def split_title_presenter_single(text):
    text = clean(text)
    best = None
    for m in PRES_RE_SINGLE.finditer(text):
        best = m
    if best and best.start() > 0:
        return text[:best.start()].strip(' .,-'), best.group(0).strip()
    return text, ""


NO_COMMA_FALLBACKS = []


def split_title_presenter_multi(raw_lines):
    lines = [clean(l) for l in raw_lines]
    lines = [l for l in lines if l]
    if not lines:
        return "", ""
    if len(lines) == 1:
        return split_title_presenter_single(lines[0])
    comma_idxs = [i for i, l in enumerate(lines) if ',' in l]
    if comma_idxs:
        ci = comma_idxs[-1]
        if ci == len(lines) - 1:
            lead_title, lead_pres = split_title_presenter_single(lines[ci])
            if lead_pres:
                title = ' '.join(lines[:ci] + [lead_title]).strip(' .,-') if lead_title else \
                    ' '.join(lines[:ci]).strip(' .,-')
                presenter = lead_pres
            else:
                title = ' '.join(lines[:ci]).strip(' .,-')
                presenter = lines[ci].strip()
        else:
            title = ' '.join(lines[:ci]).strip(' .,-')
            presenter = ' '.join(lines[ci:]).strip()
        if ci == 0:
            NO_COMMA_FALLBACKS.append(('comma-on-first-line', lines))
    else:
        title = ' '.join(lines[:-1]).strip(' .,-')
        presenter = lines[-1].strip()
        NO_COMMA_FALLBACKS.append(('no-comma', lines))
    return title, presenter


OVERRIDE_WARNINGS = []
OVERRIDE_APPLIED = set()


def parse_block(lines, entries):
    day_num = weekday = room = seats = None
    header_end = 0
    for i, ln in enumerate(lines):
        low = ln.lower()
        if 'time' in low and 'title' in low:
            header_end = i + 1
            break
        m = re.search(r'july\s*(\d{1,2})', ln, re.I)
        if m:
            day_num = m.group(1)
        for wd in WD_NUM:
            if wd.lower() in low:
                weekday = wd
        rm = ROOM_RE.search(ln)
        if rm:
            room = f"IRC {rm.group(1)}"
            sm = SEATS_RE.search(ln)
            if sm:
                seats = int(sm.group(1))
        header_end = i + 1
    if day_num is None and weekday:
        day_num = WD_NUM[weekday]
    label, isodate, wd = DAYINFO.get(day_num, ("?", "?", weekday or "?"))
    room = room or "IRC ?"

    body = lines[header_end:]
    session_at, cs = [], None
    for ln in body:
        hs = header_session(ln)
        if hs:
            cs = hs
        session_at.append(cs)

    seg_starts = [i for i, ln in enumerate(body) if TIME_RE.match(ln)]
    for si, start in enumerate(seg_starts):
        end = seg_starts[si + 1] if si + 1 < len(seg_starts) else len(body)
        first = body[start]
        m = TIME_RE.match(first)
        hh, mm, rest = int(m.group(1)), m.group(2), m.group(3)
        time_s = f"{hh:02d}:{mm}"
        session = session_at[start]
        raw_seg = [rest] + body[start + 1:end]

        fx = FIXED_RE.search(first)
        if fx:
            kind = fx.group(1).upper()
            t = ('break' if kind.startswith('BREAK') else 'lunch' if kind.startswith('LUNCH')
                 else 'poster' if kind.startswith('POSTER') else 'free' if kind.startswith('FREE')
                 else 'end')
            if t == 'end':
                continue
            entries.append(dict(day=label, date=isodate, weekday=wd, room=room, seats=seats,
                                session=session, time=time_s, title=clean(' '.join(raw_seg)),
                                presenter="", type=t))
            continue

        rem_sess = header_session(first)
        if rem_sess:
            raw_seg[0] = re.sub(r'^\s*' + re.escape(rem_sess) + r'\b', '', raw_seg[0]).strip()

        title, presenter = split_title_presenter_multi(raw_seg)
        if not title and not presenter:
            continue
        title, presenter = polish(title), polish(presenter)

        okey = (label, room, time_s)
        ov = MANUAL_OVERRIDES.get(okey)
        if ov:
            frag = ov.get("expect", "")
            if frag and frag.lower() not in presenter.lower() and frag.lower() not in title.lower():
                OVERRIDE_WARNINGS.append(
                    f"SKIPPED override {okey}: expected '{frag}' but parsed presenter="
                    f"{presenter!r} title={title[:50]!r}")
            else:
                title, presenter = ov["title"], ov["presenter"]
                OVERRIDE_APPLIED.add(okey)

        typ = 'plenary' if session is None else 'talk'
        entries.append(dict(day=label, date=isodate, weekday=wd, room=room, seats=seats,
                            session=session, time=time_s, title=title, presenter=presenter, type=typ))


def carry_continued(entries):
    prev_by_room = {}
    for e in entries:
        if e['type'] in ('talk', 'plenary'):
            low = e['title'].strip().lower()
            if low.startswith('(continued') or low in ('(cont.)', 'continued'):
                base = prev_by_room.get(e['room'])
                if base:
                    e['title'] = f"(continued) {base[0]}"
                    if not e['presenter']:
                        e['presenter'] = base[1]
            else:
                prev_by_room[e['room']] = (e['title'], e['presenter'])


# ================================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip network, use bundled PDF")
    ap.add_argument("--pdf", help="parse an explicit local PDF instead of discovering")
    ap.add_argument("--force", action="store_true", help="ignore ETag cache, re-download")
    args = ap.parse_args()

    print("Resolving schedule source…")
    pdf_path, source_url = resolve_source(args)

    raw, n_pages = extract_pdf_lines(pdf_path)
    blocks, cur = [], None
    for ln in raw:
        if re.match(r'^\s*Date:', ln, re.I):
            cur = [ln]
            blocks.append(cur)
        elif cur is not None:
            cur.append(ln)

    entries = []
    for blk in blocks:
        parse_block(blk, entries)
    carry_continued(entries)

    # schedule_date from filename if we can
    sm = SCHED_RE.search(pdf_path.name)
    sched_date = None
    if sm:
        for fmt in ("%B %d %Y", "%b %d %Y"):
            try:
                sched_date = datetime.datetime.strptime(
                    f"{sm.group('mon')} {sm.group('day')} {sm.group('year')}", fmt).date().isoformat()
                break
            except ValueError:
                pass

    pdf_bytes = pdf_path.read_bytes()
    talks = [e for e in entries if e['type'] in ('talk', 'plenary')]
    meta = {
        "source_url": source_url,
        "filename": pdf_path.name,
        "schedule_date": sched_date,
        "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "pages": n_pages,
        "talk_count": len(talks),
        "generator": "icbf_parse.py",
    }

    # -------- sanity summary --------
    print(f"\nParsed: {pdf_path.name}   schedule_date={sched_date}   pages={n_pages}")
    print(f"Total entries: {len(entries)}   choosable talks: {len(talks)}")
    by_day = Counter(e['day'] for e in talks)
    for d in ("Mon Jul 13", "Tue Jul 14", "Wed Jul 15", "Thu Jul 16"):
        rooms = sorted({e['room'] for e in talks if e['day'] == d})
        print(f"  {d}: {by_day.get(d,0)} talks  rooms={rooms}")
    empties = [e for e in talks if not e['title'] or not e['presenter']]
    print(f"Empty title/presenter rows: {len(empties)}")
    for e in empties:
        print(f"    [{e['day']} {e['room']} {e['time']}] title={e['title'][:50]!r} pres={e['presenter']!r}")

    bellio = [e for e in talks if 'bellio' in (e['presenter'] or '').lower()]
    print(f"Bellio talks: {len(bellio)}")
    for e in bellio:
        print(f"    {e['day']} {e['room']} {e['time']} - {e['title'][:55]}")

    print(f"Overrides applied: {len(OVERRIDE_APPLIED)} / {len(MANUAL_OVERRIDES)}")
    unmatched = set(MANUAL_OVERRIDES) - OVERRIDE_APPLIED - {
        k for k in MANUAL_OVERRIDES if any(w.startswith(f"SKIPPED override {k}") for w in OVERRIDE_WARNINGS)}
    for k in unmatched:
        OVERRIDE_WARNINGS.append(f"UNUSED override {k}: no matching (day,room,time) in this schedule")
    if OVERRIDE_WARNINGS:
        print("!! OVERRIDE WARNINGS:")
        for w in OVERRIDE_WARNINGS:
            print("   " + w)

    lig = [c for c in "".join(e['title'] + e['presenter'] for e in entries) if c in "ﬁﬂﬀﬃﬄ"]
    if lig:
        print(f"!! WARNING: {len(lig)} ligature chars still present in output")

    # heuristic red flags for mis-split names (surname is a bare suffix, or the
    # title ends in a lone capitalized word that looks like a leaked surname)
    suspicious = []
    for e in talks:
        p = e.get('presenter') or ''
        sur = p.split(',')[0].strip()
        if sur in ('Jr', 'Jr.', 'Sr', 'Sr.', 'II', 'III', 'IV'):
            suspicious.append((e, f"surname is suffix {sur!r}"))
        elif re.search(r'\s[A-ZÀ-Ý][a-zà-ÿ]+$', e.get('title') or '') and len(sur) <= 3:
            suspicious.append((e, "title ends in capitalized word + very short surname"))
    if suspicious:
        print(f"!! {len(suspicious)} suspicious name split(s):")
        for e, why in suspicious:
            print(f"   [{e['day']} {e['room']} {e['time']}] {why}: pres={e['presenter']!r} title=…{e['title'][-30:]!r}")

    OUT.write_text(json.dumps({"meta": meta, "entries": entries}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == '__main__':
    main()
