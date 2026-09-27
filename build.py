#!/usr/bin/env python3
"""Build the opera log site from data/operas.csv into _site/index.html.

No dependencies beyond the Python standard library. Run: python3 build.py
"""
import csv
import html
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "operas.csv"
OUT = ROOT / "_site"
TOP_N = 10


def parse_date(s):
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognised date {s!r} (use YYYY-MM-DD)")


WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
# Columns checked for near-duplicate spellings, e.g. "La Boheme" vs "La Bohème".
CHECKED = ("OperaName", "Composer", "OperaCompany", "Venue")


def load():
    with open(DATA, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]
        rows = []
        for fields in reader:
            line = reader.line_num
            fields = [v.strip() for v in fields]
            # Rows pasted from the spreadsheet still have its DayOfWeek column
            # after Date; drop it; the weekday is derived from the date.
            if len(fields) > len(header) and len(fields) > 1 and fields[1].lower() in WEEKDAYS:
                del fields[1]
            r = dict(zip(header, fields))
            if not r.get("Date") or not r.get("OperaName"):
                continue
            try:
                r["date"] = parse_date(r["Date"])
            except ValueError as e:
                raise SystemExit(f"{DATA.name} line {line}: {e}")
            r["line"] = line
            rows.append(r)
    rows.sort(key=lambda r: (r["date"], r.get("Time", "")), reverse=True)
    return rows


def fold(s):
    """Lower-case, strip accents and punctuation, collapse spaces."""
    s = unicodedata.normalize("NFKD", s.casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def warn_near_duplicates(rows):
    """Warn when differently spelled values would fold to the same name.

    They are counted separately in the charts, which is almost always a typo.
    Printed as GitHub Actions annotations so they show on the workflow run.
    """
    found = 0
    for col in CHECKED:
        groups = {}
        for r in rows:
            if r.get(col):
                groups.setdefault(fold(r[col]), {}).setdefault(r[col], []).append(r["line"])
        for spellings in groups.values():
            if len(spellings) < 2:
                continue
            found += 1
            detail = "; ".join(
                f'"{name}" (line{"s" if len(ls) > 1 else ""} {", ".join(map(str, sorted(ls)))})'
                for name, ls in sorted(spellings.items())
            )
            line = min(min(ls) for ls in spellings.values())
            print(f"::warning file=data/operas.csv,line={line}::{col} spelled differently: {detail}")
    return found


e = html.escape


def bar_chart(title, counts, unit="performance"):
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    shown, rest = items[:TOP_N], items[TOP_N:]
    peak = shown[0][1] if shown else 1
    rows = []
    for name, n in shown:
        tip = f"{name}: {n} {unit}{'s' if n != 1 else ''}"
        rows.append(
            f'<li title="{e(tip)}"><span class="lbl">{e(name)}</span>'
            f'<span class="track"><span class="bar" style="width:calc((100% - 2em) * {n / peak:.4f})"></span>'
            f'<span class="val">{n}</span></span></li>'
        )
    if rest:
        rows.append(f'<li class="more">+ {len(rest)} more</li>')
    return f'<section class="card"><h2>{e(title)}</h2><ol class="bars">{"".join(rows)}</ol></section>'


def year_chart(rows):
    counts = Counter(r["date"].year for r in rows)
    years = range(min(counts), max(counts) + 1)
    peak = max(counts.values())
    cols = []
    for y in years:
        n = counts.get(y, 0)
        tip = f"{y}: {n} performance{'s' if n != 1 else ''}"
        cols.append(
            f'<div class="col" title="{e(tip)}">'
            f'<span class="val">{n or ""}</span>'
            f'<span class="stick" style="height:{n / peak * 100:.1f}%"></span>'
            f'<span class="yr">{"’" + str(y)[2:]}</span></div>'
        )
    return (
        '<section class="card wide"><h2>Performances per year</h2>'
        f'<div class="cols">{"".join(cols)}</div></section>'
    )


def listing(rows):
    out = []
    year = None
    for r in rows:
        if r["date"].year != year:
            if year is not None:
                out.append("</ol>")
            year = r["date"].year
            out.append(f'<h3 class="year">{year}</h3><ol class="log">')
        d = r["date"]
        when = d.strftime("%A, %-d %B %Y")
        if r.get("Time"):
            when += f' · {r["Time"][:5]}'
        alt = f' <span class="alt">({e(r["AlternateTitle"])})</span>' if r.get("AlternateTitle") else ""
        company, venue = r.get("OperaCompany", ""), r.get("Venue", "")
        place = company if not venue or venue == company else " · ".join(x for x in (company, venue) if x)
        meta = [x for x in (r.get("Language"), place) if x]
        if r.get("Seats"):
            meta.append(f'Seat {r["Seats"]}')
        out.append(
            f'<li><time datetime="{d.isoformat()}">{e(when)}</time>'
            f'<div class="title">{e(r["OperaName"])}{alt}</div>'
            f'<div class="composer">{e(r.get("Composer", ""))}</div>'
            f'<div class="meta">{e(" · ".join(meta))}</div></li>'
        )
    out.append("</ol>")
    return "".join(out)


def stats(rows):
    tiles = [
        (len(rows), "performances"),
        (len({r["OperaName"] for r in rows}), "different operas"),
        (len({r["Composer"] for r in rows if r.get("Composer")}), "composers"),
        (len({r["OperaCompany"] for r in rows if r.get("OperaCompany")}), "companies"),
    ]
    return "".join(f'<div class="stat"><b>{n}</b><span>{label}</span></div>' for n, label in tiles)


CSS = """
:root{--bg:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--line:#e6e5e0;--track:#f1f0ec;--accent:#8c1c3a;--bar:#2a78d6;}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--card:#1c1c1b;--ink:#f5f5f2;--ink2:#c3c2b7;--muted:#8f8e86;--line:#2e2e2c;--track:#262625;--accent:#e0869c;--bar:#3987e5;}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:960px;margin:0 auto;padding:32px 16px 64px}
header h1{font-family:Georgia,"Times New Roman",serif;font-weight:normal;font-size:2.4rem;margin:0;color:var(--accent)}
header p{margin:4px 0 0;color:var(--ink2)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat b{display:block;font-size:1.8rem;font-weight:600;line-height:1.1;font-variant-numeric:tabular-nums}
.stat span{color:var(--ink2);font-size:.9rem}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.card.wide{grid-column:1/-1}
.card h2{font-size:1rem;margin:0 0 12px;font-weight:600}
.bars{list-style:none;margin:0;padding:0}
.bars li{display:grid;grid-template-columns:minmax(0,42%) minmax(0,1fr);align-items:center;gap:10px;padding:3px 0}
.bars .lbl{font-size:.88rem;color:var(--ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right}
.bars .track{display:flex;align-items:center;gap:6px;min-width:0}
.bars .bar{display:block;height:14px;min-width:4px;background:var(--bar);border-radius:0 4px 4px 0}
.bars .val{font-size:.82rem;color:var(--ink2);font-variant-numeric:tabular-nums}
.bars li:hover .lbl{color:var(--ink)}
.bars li.more{display:block;font-size:.82rem;color:var(--muted);padding-top:8px}
.cols{display:flex;align-items:stretch;gap:2px;height:170px;padding-top:4px}
.col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;min-width:0}
.col .stick{width:100%;max-width:24px;background:var(--bar);border-radius:4px 4px 0 0}
.col .val{font-size:.75rem;color:var(--ink2);font-variant-numeric:tabular-nums;min-height:1.2em}
.col .yr{font-size:.7rem;color:var(--muted);border-top:1px solid var(--line);width:100%;text-align:center;padding-top:2px;margin-top:2px}
.col:hover .stick{filter:brightness(1.15)}
h2.section{font-family:Georgia,serif;font-weight:normal;font-size:1.6rem;margin:40px 0 0}
h3.year{font-size:1.1rem;margin:28px 0 8px;padding-bottom:4px;border-bottom:1px solid var(--line);color:var(--accent)}
.log{list-style:none;margin:0;padding:0}
.log li{padding:10px 0;border-bottom:1px solid var(--line)}
.log li:last-child{border-bottom:0}
.log time{font-size:.8rem;color:var(--muted)}
.log .title{font-family:Georgia,serif;font-size:1.25rem;line-height:1.3}
.log .alt{color:var(--ink2);font-style:italic;font-size:1rem}
.log .composer{color:var(--ink2)}
.log .meta{font-size:.85rem;color:var(--muted)}
footer{margin-top:40px;color:var(--muted);font-size:.8rem}
@media (max-width:680px){.grid{grid-template-columns:minmax(0,1fr)}.stats{grid-template-columns:repeat(2,1fr)}header h1{font-size:1.9rem}.col .yr{font-size:.6rem}.col .val{font-size:.65rem}}
"""


def page(rows):
    first, last = rows[-1]["date"], rows[0]["date"]
    operas = Counter(r["OperaName"] for r in rows)
    composers = Counter(r["Composer"] for r in rows if r.get("Composer"))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Opera Log</title>
<meta name="description" content="Every opera I've attended, {first.year}–{last.year}.">
<style>{CSS}</style>
</head>
<body>
<main>
<header><h1>Opera Log</h1><p>Every opera I've attended, {first.year}–{last.year}.</p></header>
<div class="stats">{stats(rows)}</div>
<div class="grid">
{bar_chart("Most-seen operas", operas)}
{bar_chart("Most-seen composers", composers)}
{year_chart(rows)}
</div>
<h2 class="section">Performances</h2>
{listing(rows)}
<footer>Last updated {date.today().strftime("%-d %B %Y")}.</footer>
</main>
</body>
</html>
"""


def main():
    rows = load()
    if not rows:
        raise SystemExit("No performances found in data/operas.csv")
    warn_near_duplicates(rows)
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page(rows), encoding="utf-8")
    print(f"Wrote {OUT / 'index.html'} ({len(rows)} performances)")


if __name__ == "__main__":
    main()
