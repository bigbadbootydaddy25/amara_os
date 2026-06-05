"""
PLOT agent — Metes and bounds parser + plotter.
Parses WV deed calls: N29.41.45W, S12.30.00E etc.
Unit conversions: chains, rods/poles, varas, links, yards → feet.
Shoelace area formula; closure check (green<0.1%, amber<1%, red≥1%).
Backtick lines = reference calls (plotted blue, excluded from area).
Outputs PNG and launches Flask web viewer at localhost:5050.
"""
import logging
import math
import re
from pathlib import Path
from typing import Optional

from deed.config import PARCEL_ID, NOTES_FILE, PLOT_PNG, OUTPUT_DIR

log = logging.getLogger("PLOT")

# Unit conversions → feet
UNIT_MAP = {
    "chains":  66.0,
    "chain":   66.0,
    "ch":      66.0,
    "chs":     66.0,
    "links":   0.66,
    "link":    0.66,
    "lks":     0.66,
    "lk":      0.66,
    "rods":    16.5,
    "rod":     16.5,
    "poles":   16.5,
    "pole":    16.5,
    "perches": 16.5,
    "perch":   16.5,
    "varas":   2.7778,
    "vara":    2.7778,
    "feet":    1.0,
    "foot":    1.0,
    "ft":      1.0,
    "yards":   3.0,
    "yard":    3.0,
    "yds":     3.0,
    "yd":      3.0,
    "meters":  3.28084,
    "meter":   3.28084,
    "m":       3.28084,
}

# Regex for a single bearing+distance call
# Matches: N12.34.56E 10.5 chains  OR  N12°34'56"E 10.5 ch
_BEARING_RE = re.compile(
    r"""
    (?P<ref>`)?                          # optional backtick = reference call
    \s*
    (?P<quad>[NSns])\s*                  # quadrant start N or S
    (?P<deg>\d{1,3})                     # degrees
    (?:[.°\s]\s*(?P<min>\d{1,2}))?      # optional .minutes or °minutes
    (?:[.'\s]\s*(?P<sec>\d{1,2}))?      # optional .seconds or 'seconds
    \s*(?P<dir>[EWew])                   # quadrant end E or W
    \s+
    (?P<dist>[\d.]+)                     # distance
    \s+
    (?P<unit>[a-zA-Z]+)                  # unit
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Also match pure compass headings like "North 10 chains"
_COMPASS_RE = re.compile(
    r"""
    (?P<ref>`)?
    (?P<dir>north|south|east|west|n|s|e|w)
    \s+(?P<dist>[\d.]+)\s+(?P<unit>[a-zA-Z]+)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def run(legal_text: str = "") -> dict:
    log.info("PLOT — Metes & Bounds | parcel %s", PARCEL_ID)

    if not legal_text:
        log.warning("PLOT: no legal description provided — nothing to plot")
        _note("PLOT: no legal description text provided")
        return {
            "agent":    "PLOT",
            "status":   "SKIPPED",
            "reason":   "no_legal_description",
            "plot_png": "",
        }

    calls   = parse_calls(legal_text)
    if not calls:
        msg = "PLOT: no parseable bearing/distance calls found in legal description"
        log.warning(msg)
        _note(msg)
        return {
            "agent":  "PLOT",
            "status": "SKIPPED",
            "reason": "no_calls_parsed",
            "plot_png": "",
        }

    log.info("PLOT: parsed %d calls (%d reference)",
             len(calls), sum(1 for c in calls if c["reference"]))

    points, closure = trace_traverse(calls)
    log.info("PLOT: closure = %.4f ft (%.3f%%)",
             closure["distance_ft"], closure["pct"])
    _note(f"PLOT CLOSURE: {closure['distance_ft']:.4f} ft | {closure['pct']:.3f}%  [{closure['grade']}]")

    area_sqft = shoelace_area([p for p, c in zip(points, calls) if not c["reference"]])
    area_acres = area_sqft / 43560.0
    log.info("PLOT: computed area = %.4f acres (%.0f sq ft)", area_acres, area_sqft)
    _note(f"PLOT AREA: {area_acres:.4f} acres | {area_sqft:.0f} sq ft")

    png_path = _render_plot(calls, points, closure, area_acres)

    return {
        "agent":      "PLOT",
        "status":     "COMPLETE",
        "calls":      len(calls),
        "area_acres": round(area_acres, 4),
        "area_sqft":  round(area_sqft, 0),
        "closure":    closure,
        "plot_png":   str(png_path) if png_path else "",
    }


# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_calls(text: str) -> list[dict]:
    """Return list of call dicts parsed from legal description text."""
    calls = []
    for m in _BEARING_RE.finditer(text):
        deg = float(m.group("deg") or 0)
        mn  = float(m.group("min") or 0)
        sec = float(m.group("sec") or 0)
        bearing_dd = _dms_to_dd(
            m.group("quad").upper(),
            m.group("dir").upper(),
            deg, mn, sec,
        )
        dist_ft = _to_feet(float(m.group("dist")), m.group("unit").lower())
        calls.append({
            "raw":       m.group(0).strip(),
            "bearing":   bearing_dd,
            "dist_ft":   dist_ft,
            "reference": bool(m.group("ref")),
        })

    if not calls:
        # Try pure compass
        for m in _COMPASS_RE.finditer(text):
            d = m.group("dir").upper()[0]
            bearing_map = {"N": 0.0, "S": 180.0, "E": 90.0, "W": 270.0}
            dist_ft = _to_feet(float(m.group("dist")), m.group("unit").lower())
            calls.append({
                "raw":       m.group(0).strip(),
                "bearing":   bearing_map.get(d, 0.0),
                "dist_ft":   dist_ft,
                "reference": bool(m.group("ref")),
            })

    return calls


def _dms_to_dd(quad_start: str, quad_end: str, deg: float, mn: float, sec: float) -> float:
    """Convert bearing in DMS quadrant notation to decimal degrees (0=N, 90=E, 180=S, 270=W)."""
    angle = deg + mn / 60.0 + sec / 3600.0
    if quad_start == "N" and quad_end == "E":
        return angle
    if quad_start == "S" and quad_end == "E":
        return 180.0 - angle
    if quad_start == "S" and quad_end == "W":
        return 180.0 + angle
    if quad_start == "N" and quad_end == "W":
        return 360.0 - angle
    return angle


def _to_feet(dist: float, unit: str) -> float:
    factor = UNIT_MAP.get(unit, 1.0)
    return dist * factor


# ── Traverse ─────────────────────────────────────────────────────────────────

def trace_traverse(calls: list[dict]) -> tuple[list[tuple], dict]:
    """Walk calls from origin (0,0). Returns (points list, closure dict)."""
    x, y = 0.0, 0.0
    points = [(x, y)]
    for c in calls:
        bearing_rad = math.radians(c["bearing"])
        dx = c["dist_ft"] * math.sin(bearing_rad)
        dy = c["dist_ft"] * math.cos(bearing_rad)
        x += dx
        y += dy
        points.append((x, y))

    close_dist = math.hypot(x, y)
    total_dist = sum(c["dist_ft"] for c in calls if not c["reference"])
    pct = (close_dist / total_dist * 100.0) if total_dist else 0.0
    grade = "GREEN" if pct < 0.1 else ("AMBER" if pct < 1.0 else "RED")

    return points, {
        "distance_ft":  round(close_dist, 4),
        "total_dist_ft": round(total_dist, 2),
        "pct":           round(pct, 4),
        "grade":         grade,
        "close_x":       round(x, 4),
        "close_y":       round(y, 4),
    }


def shoelace_area(points: list[tuple]) -> float:
    """Shoelace formula for polygon area in square feet."""
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return abs(area) / 2.0


# ── Rendering ────────────────────────────────────────────────────────────────

def _render_plot(calls: list, points: list, closure: dict, area_acres: float) -> Optional[Path]:
    """Render traverse to PNG. Returns path or None if matplotlib unavailable."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        log.warning("PLOT: matplotlib not installed — skipping PNG render")
        _note("PLOT: matplotlib not available — install with: pip install matplotlib")
        return None

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_aspect("equal")
    ax.set_facecolor("#f8f4e8")
    fig.patch.set_facecolor("#f8f4e8")

    # Separate survey calls from reference calls
    survey_pts = []
    ref_segments = []
    sx, sy = 0.0, 0.0
    for i, c in enumerate(calls):
        x, y = points[i + 1]
        if c["reference"]:
            ref_segments.append(((sx, sy), (x, y)))
        else:
            survey_pts.append((sx, sy))
            sx, sy = x, y
    survey_pts.append((sx, sy))

    # Draw survey traverse (filled polygon)
    if len(survey_pts) >= 3:
        xs = [p[0] for p in survey_pts]
        ys = [p[1] for p in survey_pts]
        ax.fill(xs, ys, alpha=0.15, color="#c8a855", label="Survey boundary")
        ax.plot(xs + [xs[0]], ys + [ys[0]], "k-", linewidth=1.5)

    # Draw reference calls (blue dashed)
    for (x1, y1), (x2, y2) in ref_segments:
        ax.plot([x1, x2], [y1, y2], "b--", linewidth=1.0, alpha=0.7)

    # Closure line (if significant)
    if closure["distance_ft"] > 0.01:
        color = {"GREEN": "green", "AMBER": "orange", "RED": "red"}.get(closure["grade"], "red")
        ax.plot(
            [points[-1][0], points[0][0]],
            [points[-1][1], points[0][1]],
            linestyle=":", color=color, linewidth=2, label=f"Closure {closure['pct']:.3f}%",
        )

    # Origin marker
    ax.plot(0, 0, "k^", markersize=8, zorder=5)
    ax.annotate("POB", (0, 0), textcoords="offset points", xytext=(6, 6), fontsize=8)

    # Labels
    grade_color = {"GREEN": "green", "AMBER": "darkorange", "RED": "red"}.get(closure["grade"], "black")
    ax.set_title(
        f"Parcel {PARCEL_ID} — Metes & Bounds\n"
        f"Area: {area_acres:.4f} ac | "
        f"Closure: {closure['distance_ft']:.3f} ft ({closure['pct']:.3f}%)",
        color="black", fontsize=11,
    )
    ax.set_xlabel("Easting (ft)")
    ax.set_ylabel("Northing (ft)")
    ax.grid(True, linestyle=":", alpha=0.4)

    # Legend
    handles = [
        mpatches.Patch(color="#c8a855", alpha=0.4, label="Survey boundary"),
        plt.Line2D([0], [0], color="blue", linestyle="--", label="Reference call"),
        plt.Line2D([0], [0], color=grade_color, linestyle=":", label=f"Closure [{closure['grade']}]"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(str(PLOT_PNG), dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("PLOT: saved → %s", PLOT_PNG)
    _note(f"PLOT PNG: {PLOT_PNG}")
    return PLOT_PNG


# ── Flask web viewer ──────────────────────────────────────────────────────────

def launch_viewer(plot_result: dict) -> None:
    """Launch Flask viewer at http://localhost:5050 (blocking)."""
    try:
        from flask import Flask, render_template_string, send_file
    except ImportError:
        log.warning("PLOT viewer: flask not installed — skipping web viewer")
        return

    app = Flask(__name__)
    png_path = plot_result.get("plot_png", "")

    HTML = """
    <!DOCTYPE html><html>
    <head><title>Metes & Bounds Plot — {{parcel}}</title>
    <style>body{background:#1a1a1a;color:#e0d5b5;font-family:monospace;padding:20px}
    img{max-width:100%;border:1px solid #555;margin:10px 0}
    .stats{background:#2a2a2a;padding:15px;margin:10px 0;border-left:4px solid #c8a855}
    .GREEN{color:#4caf50} .AMBER{color:#ff9800} .RED{color:#f44336}</style>
    </head>
    <body>
    <h1>Metes & Bounds Plot</h1>
    <h2>Parcel: {{parcel}}</h2>
    <div class="stats">
      <p><b>Area:</b> {{area}} acres</p>
      <p><b>Closure:</b> {{close_ft}} ft ({{close_pct}}%)
         <span class="{{grade}}"> [{{grade}}]</span></p>
      <p><b>Calls parsed:</b> {{calls}}</p>
    </div>
    {% if has_png %}
    <img src="/plot.png" alt="Metes and Bounds Plot">
    {% else %}
    <p><em>No plot image available — matplotlib not installed?</em></p>
    {% endif %}
    </body></html>
    """

    @app.route("/")
    def index():
        return render_template_string(
            HTML,
            parcel=PARCEL_ID,
            area=plot_result.get("area_acres", 0),
            close_ft=plot_result.get("closure", {}).get("distance_ft", 0),
            close_pct=plot_result.get("closure", {}).get("pct", 0),
            grade=plot_result.get("closure", {}).get("grade", "—"),
            calls=plot_result.get("calls", 0),
            has_png=bool(png_path and Path(png_path).exists()),
        )

    @app.route("/plot.png")
    def serve_png():
        if png_path and Path(png_path).exists():
            return send_file(png_path, mimetype="image/png")
        return "No plot available", 404

    log.info("PLOT viewer: http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)


def _note(msg: str) -> None:
    try:
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(NOTES_FILE, "a") as f:
            f.write(f"[PLOT] {msg}\n")
    except Exception:
        pass
