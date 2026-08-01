"""
contribution_shooter.py -- generates assets/contribution_shooter.svg: an
arcade-shooter reskin of the "contribution snake" idea. A pixel ship
sweeps across your real contribution graph, blasting each week's squares,
then loops forever.

Requires the same ACCESS_TOKEN secret as status.py / stats2.py (classic
PAT with at least `read:user` scope -- no repo access needed since this
only reads the public contribution calendar).

Run as: python contribution_shooter.py
Writes: assets/contribution_shooter.svg
"""

import os
from datetime import datetime, timedelta, timezone

import requests

USERNAME = "Arish0limbu"
TOKEN = os.environ["ACCESS_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
GRAPHQL_URL = "https://api.github.com/graphql"
OUT_FILE = "assets/contribution_shooter.svg"


def github_query(query, variables=None):
    response = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
    )
    response.raise_for_status()
    data = response.json()
    if "errors" in data:
        raise Exception(data["errors"])
    return data["data"]


def fetch_calendar():
    """Fetch the last ~365 days of contributions as a week x day grid."""
    to_date = datetime.now(timezone.utc)
    from_date = to_date - timedelta(days=364)

    query = """
    query($login:String!, $from:DateTime!, $to:DateTime!){
      user(login:$login){
        contributionsCollection(from:$from, to:$to){
          contributionCalendar{
            totalContributions
            weeks{
              contributionDays{
                weekday
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    user = github_query(
        query,
        {
            "login": USERNAME,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        },
    )["user"]

    if user is None:
        raise RuntimeError(
            f"GitHub returned no user for login={USERNAME!r}. "
            "Check USERNAME matches your GitHub login exactly, and "
            "that ACCESS_TOKEN is valid."
        )

    calendar = user["contributionsCollection"]["contributionCalendar"]
    total = calendar["totalContributions"]

    weeks = []
    for week in calendar["weeks"]:
        days = [0] * 7
        for day in week["contributionDays"]:
            days[day["weekday"]] = day["contributionCount"]
        weeks.append(days)

    print(f"Fetched {len(weeks)} weeks, {total} total contributions.")
    return weeks, total


# --------------------------------------------------------------------------
# SVG rendering
# --------------------------------------------------------------------------

CELL = 10
GAP = 3
PITCH = CELL + GAP
ROWS = 7
LEFT_PAD = 26
TOP_PAD = 46
SHIP_TRACK_GAP = 26  # space between bottom of grid and ship track
TITLE_H = 30

# Cycle timing: total loop length in seconds. Ship sweeps across most of
# the cycle, then there's a brief pause/reset window before it loops.
CYCLE = 10.0
SWEEP_FRACTION = 0.85


def intensity_color(count):
    if count <= 0:
        return "#10131c"
    if count <= 2:
        return "#1b4b3a"
    if count <= 5:
        return "#2f9e6a"
    if count <= 9:
        return "#4dffb0"
    return "#d9fff0"


def build_svg(weeks, username, total_contributions):
    cols = len(weeks)
    grid_w = cols * PITCH - GAP
    width = max(500, LEFT_PAD * 2 + grid_w)
    grid_h = ROWS * PITCH - GAP
    ship_track_y = TOP_PAD + grid_h + SHIP_TRACK_GAP
    height = ship_track_y + 34

    hit_window_frac = SWEEP_FRACTION / max(cols, 1)

    parts = []
    parts.append(
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
    )

    parts.append(
        """
  <defs>
    <radialGradient id="shipGlow" cx="50%" cy="50%" r="60%">
      <stop offset="0%" stop-color="#ff8a4d" stop-opacity="0.9"/>
      <stop offset="100%" stop-color="#ff8a4d" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="crtBezel" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#2a1b3d"/>
      <stop offset="100%" stop-color="#120a1c"/>
    </linearGradient>
  </defs>
"""
    )

    style = f"""
  <style>
    .cab {{ fill: #0a0710; }}
    .screen {{ fill: #05060a; }}
    .hud {{ font: 10px 'SFMono-Regular', Consolas, monospace; fill: #4df1ff; letter-spacing: 1px; }}
    .hud-dim {{ font: 9px 'SFMono-Regular', Consolas, monospace; fill: #6e5a8a; }}
    .cell {{ animation: hit {CYCLE}s linear infinite; transform-box: fill-box; transform-origin: center; }}
    @keyframes hit {{
      0%   {{ opacity: 1; transform: scale(1); }}
      3%   {{ opacity: 1; transform: scale(1); }}
      5%   {{ opacity: 1; transform: scale(1.6); }}
      8%   {{ opacity: 0; transform: scale(0.15); }}
      97%  {{ opacity: 0; transform: scale(0.15); }}
      100% {{ opacity: 1; transform: scale(1); }}
    }}
    .flash {{ animation: flash {CYCLE}s linear infinite; transform-box: fill-box; transform-origin: center; }}
    @keyframes flash {{
      0%   {{ opacity: 0; }}
      4%   {{ opacity: 0; }}
      5%   {{ opacity: 1; }}
      9%   {{ opacity: 0; }}
      100% {{ opacity: 0; }}
    }}
    .ship {{ animation: sweep {CYCLE}s linear infinite; }}
    @keyframes sweep {{
      0%   {{ transform: translateX(0); opacity: 1; }}
      {SWEEP_FRACTION * 100:.1f}%  {{ transform: translateX({grid_w - 14}px); opacity: 1; }}
      {SWEEP_FRACTION * 100 + 2:.1f}% {{ opacity: 0; }}
      99%  {{ opacity: 0; transform: translateX(0); }}
      100% {{ opacity: 1; transform: translateX(0); }}
    }}
    .beam {{ animation: beam 1.1s ease-in-out infinite; }}
    @keyframes beam {{
      0%, 100% {{ opacity: 0.25; }}
      50% {{ opacity: 0.75; }}
    }}
  </style>
"""
    parts.append(style)

    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="url(#crtBezel)"/>')
    parts.append(f'<rect x="4" y="{TITLE_H}" width="{width - 8}" height="{height - TITLE_H - 4}" rx="6" class="screen"/>')

    parts.append(f'<rect x="4" y="4" width="{width - 8}" height="{TITLE_H - 6}" rx="6" class="cab"/>')
    parts.append(f'<text x="16" y="21" class="hud">1UP {str(total_contributions).rjust(6, "0")}</text>')
    parts.append(f'<text x="{width - 16}" y="21" text-anchor="end" class="hud-dim">{username}.gg</text>')

    parts.append(f'<g transform="translate({LEFT_PAD},{TOP_PAD})">')
    for wi, week in enumerate(weeks):
        delay = -(wi * hit_window_frac * CYCLE)
        x = wi * PITCH
        for di in range(ROWS):
            count = week[di] if di < len(week) else 0
            y = di * PITCH
            color = intensity_color(count)
            if count > 0:
                parts.append(
                    f'<rect class="cell" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                    f'fill="{color}" style="animation-delay:{delay:.3f}s"/>'
                )
                parts.append(
                    f'<rect class="flash" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                    f'fill="#ffffff" style="animation-delay:{delay:.3f}s"/>'
                )
            else:
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}" opacity="0.5"/>'
                )
    parts.append("</g>")

    track_y = ship_track_y
    parts.append(
        f'<line x1="{LEFT_PAD}" y1="{track_y}" x2="{LEFT_PAD + grid_w}" y2="{track_y}" '
        f'stroke="#2a2440" stroke-width="1" stroke-dasharray="2 3"/>'
    )
    parts.append(f'<g class="ship" transform="translate({LEFT_PAD},{track_y - 16})">')
    parts.append('<circle cx="7" cy="10" r="16" fill="url(#shipGlow)"/>')
    parts.append(
        f'<rect class="beam" x="5" y="{-(track_y - TOP_PAD - 6)}" width="3" height="{track_y - TOP_PAD - 6}" '
        f'fill="#4df1ff"/>'
    )
    ship_px = [
        (6, 0, 2, 2), (4, 2, 6, 2), (2, 4, 10, 2), (0, 6, 14, 4),
        (2, 10, 3, 3), (9, 10, 3, 3),
    ]
    for (px, py, pw, ph) in ship_px:
        parts.append(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="#ff5f56"/>')
    parts.append('<rect x="5" y="5" width="4" height="3" fill="#ffe066"/>')
    parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    if not os.path.exists("assets"):
        raise FileNotFoundError("assets/ directory not found.")

    weeks, total = fetch_calendar()
    svg = build_svg(weeks, USERNAME, total)

    with open(OUT_FILE, "w") as f:
        f.write(svg)

    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
