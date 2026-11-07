"""Render a cached, four-card Seattle rental-market snapshot.

This module never makes network requests. The daily shortlist reads one small JSON file
that is refreshed separately by update_market_pulse.py.
"""
import html
import json
import math
from datetime import datetime
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "market_pulse.json"

CARD_CONFIG = (
    ("rent_growth", "Rent growth", "percent", "Zillow ZORI", "https://www.zillow.com/research/data/"),
    ("vacancy", "Rental vacancy", "percent", "Apartment List", "https://www.apartmentlist.com/research/category/data-rent-estimates"),
    ("time_to_lease", "Time to lease", "days", "Apartment List", "https://www.apartmentlist.com/research/category/data-rent-estimates"),
    ("concessions", "Rental concessions", "percent", "Apartment List", "https://www.apartmentlist.com/research/category/data-rent-estimates"),
)

MARKET_PULSE_CSS = """
    .market-pulse { margin: 0 0 26px; }
    .market-pulse-header { display:flex; flex-wrap:wrap; gap:8px 16px; justify-content:space-between; align-items:baseline; margin-bottom:12px; }
    .market-pulse h2 { font-size:23px; margin:0; }
    .market-pulse-subtitle { color:var(--muted); font-size:13px; }
    .market-pulse-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
    .market-pulse-card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px; min-width:0; }
    .market-pulse-title { color:var(--text); font-size:15px; font-weight:700; margin-bottom:9px; }
    .market-pulse-value { font-size:28px; line-height:1.15; font-weight:700; color:var(--accent); }
    .market-pulse-geo { color:var(--muted); font-size:12px; margin-top:3px; }
    .market-pulse-comp { font-size:12px; min-height:33px; margin-top:7px; }
    .market-pulse-plot { margin:5px 0 0; }
    .market-pulse-plot svg { display:block; width:100%; height:48px; }
    .market-pulse-axis { display:flex; justify-content:space-between; font-size:11px; color:var(--muted); margin-top:1px; }
    .market-pulse-legend { font-size:11px; margin-top:4px; color:var(--muted); }
    .market-pulse-sea { color:#327c73; }
    .market-pulse-us { color:#6d7478; }
    .market-pulse-source { font-size:11px; color:var(--muted); margin-top:8px; }
    .market-pulse-source a { color:var(--accent); }
    .market-pulse-note { font-size:12px; color:var(--muted); margin:9px 0 0; }
    @media (max-width:1000px) { .market-pulse-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media (max-width:540px) { .market-pulse-grid { grid-template-columns:1fr; } }
"""


def load_market_cache(path=CACHE_PATH):
    """Return an empty mapping on missing, broken, or invalid local cache."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def clean_series(card, key):
    """Ignore malformed entries rather than display invented or unsafe data."""
    raw = card.get("series", []) if isinstance(card, dict) else []
    if not isinstance(raw, list):
        return []
    result = []
    for point in raw:
        if not isinstance(point, dict):
            continue
        month = point.get("month")
        sea = point.get("seattle")
        if not isinstance(month, str) or len(month) != 7 or month[4] != "-":
            continue
        if isinstance(sea, bool) or not isinstance(sea, (int, float)) or not math.isfinite(sea):
            continue
        item = {"month": month, "seattle": float(sea)}
        us = point.get("us")
        if key == "rent_growth" and isinstance(us, (float, int)) and not isinstance(us, bool) and math.isfinite(us):
            item["us"] = float(us)
        result.append(item)
    return sorted({p["month"]: p for p in result}.values(), key=lambda p: p["month"])[-13:]


def format_metric(value, unit, signed=False):
    if value is None:
        return "—"
    if unit == "days":
        return f"{value:.0f} days"
    return f"{value:+.1f}%" if signed else f"{value:.1f}%"


def change_description(series, unit):
    if len(series) < 2:
        return "Year-over-year comparison unavailable"
    last = series[-1]
    previous = next(
        (p for p in series if p["month"] == f"{int(last['month'][:4])-1}{last['month'][4:]}"),
        None,
    )
    if previous is None:
        return "Year-over-year comparison unavailable"
    difference = last["seattle"] - previous["seattle"]
    if unit == "days":
        return f"Seattle: {difference:+.0f} days vs. last year"
    return f"Seattle: {difference:+.1f} percentage points YoY"


def sparkline(series, include_us):
    """Inline SVG, using one scale for Seattle and U.S. when both are plotted."""
    points = series[-12:]
    if len(points) < 2:
        return '<div class="market-pulse-plot" aria-label="Trend unavailable">12-month trend unavailable</div>'
    values = [p["seattle"] for p in points]
    if include_us:
        values += [p["us"] for p in points if "us" in p]
    lower, upper = min(values), max(values)
    if lower == upper:
        lower -= 1
        upper += 1
    width, height = 210, 44

    def coords(field):
        return " ".join(
            f"{i * width / (len(points)-1):.1f},{(height - 4 - (p[field]-lower)/(upper-lower)*(height-8)):.1f}"
            for i, p in enumerate(points)
            if field in p
        )

    sea_line = coords("seattle")
    us_points = [p for p in points if "us" in p]
    us_line = ""
    if include_us and len(us_points) == len(points):
        us_line = f'<polyline points="{coords("us")}" fill="none" stroke="#6d7478" stroke-width="2" stroke-dasharray="4 4" />'
    first, last = html.escape(points[0]["month"]), html.escape(points[-1]["month"])
    return (
        '<div class="market-pulse-plot">'
        f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" role="img" aria-label="Monthly trends from {first} to {last}">'
        f'{us_line}<polyline points="{sea_line}" fill="none" stroke="#327c73" stroke-width="2.5" /></svg>'
        f'<div class="market-pulse-axis"><span>{first}</span><span>{last}</span></div>'
        '</div>'
    )


def render_card(key, label, unit, source, source_url, data):
    series = clean_series(data.get(key, {}), key)
    latest = series[-1] if series else None
    value = latest["seattle"] if latest else None
    month = html.escape(latest["month"]) if latest else "Not available"
    main_value = format_metric(value, unit, signed=(key == "rent_growth"))
    if key == "rent_growth" and latest and "us" in latest:
        national = latest["us"]
        diff = value - national
        comparison = (
            f'U.S. overall: <strong>{format_metric(national, unit, signed=True)} YoY</strong>'
            f'<div>Seattle vs. U.S.: {diff:+.1f} percentage points</div>'
        )
    else:
        comparison = change_description(series, unit) if latest else "No cached observations yet"
    legend = (
        '<div class="market-pulse-legend">'
        '<span class="market-pulse-sea">● Seattle metro</span> · '
        '<span class="market-pulse-us">┄ U.S.</span></div>'
        if key == "rent_growth" and latest and "us" in latest
        else '<div class="market-pulse-legend">● Seattle metro</div>'
    )
    return (
        '<article class="market-pulse-card">'
        f'<div class="market-pulse-title">{html.escape(label)}</div>'
        f'<div class="market-pulse-value">{main_value}</div>'
        f'<div class="market-pulse-geo">Seattle–Tacoma–Bellevue metro · {month}</div>'
        f'<div class="market-pulse-comp">{comparison}</div>'
        f'{sparkline(series, key == "rent_growth")}{legend}'
        f'<div class="market-pulse-source">Source: <a href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(source)}</a></div>'
        '</article>'
    )


def render_market_pulse(path=CACHE_PATH):
    """Four cards; missing data is explicitly missing, never sample data."""
    data = load_market_cache(path)
    cards = data.get("cards", {})
    if not isinstance(cards, dict):
        cards = {}
    tiles = "\n".join(render_card(*spec, cards) for spec in CARD_CONFIG)
    return (
        '<section class="market-pulse" aria-labelledby="market-pulse-title">'
        '<div class="market-pulse-header"><h2 id="market-pulse-title">Seattle Market Pulse</h2>'
        '<span class="market-pulse-subtitle">Seattle–Tacoma–Bellevue metro · Monthly observations · Data refreshed separately</span></div>'
        f'<div class="market-pulse-grid">{tiles}</div>'
        '<p class="market-pulse-note">Vacancy, time to lease and concessions primarily reflect professionally managed rentals. '
        'Concessions = share advertising incentives worth at least one month of rent. '
        'Each card shows its own latest available data month.</p>'
        '</section>'
    )
