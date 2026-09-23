"""
Generate a live daily commit graph for the GitHub profile README.

The graph uses GitHub's GraphQL contributions data and counts commits
specifically (not total contributions). It writes:
    assets/activity-graph.svg
"""

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

USERNAME = "Arish0limbu"
TOKEN = os.environ["ACCESS_TOKEN"]
GRAPHQL_URL = "https://api.github.com/graphql"
OUTPUT = "assets/activity-graph.svg"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      commitContributionsByRepository(first:100) {
        contributions(first:100) {
          nodes {
            occurredAt
            commitCount
          }
        }
      }
    }
  }
}
"""


def github_query(from_date, to_date):
    response = requests.post(
        GRAPHQL_URL,
        json={
            "query": QUERY,
            "variables": {
                "login": USERNAME,
                "from": from_date,
                "to": to_date,
            },
        },
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]["user"]["contributionsCollection"]


def get_daily_commits():
    # Split the year into 31-day windows so each repository stays below the
    # 100-contribution node limit.
    end = datetime.now(timezone.utc).replace(
        hour=23, minute=59, second=59, microsecond=0
    )
    start = (end - timedelta(days=364)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    daily = defaultdict(int)
    window_start = start

    while window_start <= end:
        window_end = min(window_start + timedelta(days=30), end)
        collection = github_query(
            window_start.isoformat().replace("+00:00", "Z"),
            window_end.isoformat().replace("+00:00", "Z"),
        )

        for repo_group in collection["commitContributionsByRepository"]:
            for contribution in repo_group["contributions"]["nodes"]:
                date = contribution["occurredAt"][:10]
                daily[date] += contribution["commitCount"]

        window_start = window_end + timedelta(seconds=1)

    return {
        (start + timedelta(days=i)).strftime("%Y-%m-%d"): daily.get(
            (start + timedelta(days=i)).strftime("%Y-%m-%d"), 0
        )
        for i in range(365)
    }


def esc(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def make_svg(daily):
    width, height = 900, 300
    left, right, top, bottom = 58, 24, 58, 48
    plot_w = width - left - right
    plot_h = height - top - bottom

    dates = list(daily.keys())
    values = list(daily.values())
    total = sum(values)
    max_value = max(values) if values else 1
    max_value = max(1, max_value)

    points = []
    for i, value in enumerate(values):
        x = left + (i / max(1, len(values) - 1)) * plot_w
        y = top + plot_h - (value / max_value) * plot_h
        points.append((x, y))

    path = " ".join(
        ("M" if i == 0 else "L") + f" {x:.2f},{y:.2f}"
        for i, (x, y) in enumerate(points)
    )

    circles = "\n".join(
        f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="2.1" fill="#ffffff" />'
        for x, y in points
    )

    grid = []
    for fraction in (0, 0.5, 1):
        y = top + plot_h * fraction
        label = round(max_value * (1 - fraction))
        grid.append(
            f'  <line x1="{left}" y1="{y:.2f}" x2="{width-right}" '
            f'y2="{y:.2f}" stroke="#00f0ff" stroke-opacity="0.12" />'
        )
        grid.append(
            f'  <text x="{left-10}" y="{y+4:.2f}" text-anchor="end" '
            f'fill="#00f0ff" fill-opacity="0.55" font-size="10" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{label}</text>'
        )

    month_labels = []
    seen = set()
    for i, date_string in enumerate(dates):
        date = datetime.strptime(date_string, "%Y-%m-%d")
        key = (date.year, date.month)
        if key not in seen and (i == 0 or date.day <= 7):
            seen.add(key)
            x = left + (i / max(1, len(dates) - 1)) * plot_w
            month_labels.append(
                f'  <text x="{x:.2f}" y="{height-18}" text-anchor="middle" '
                f'fill="#00f0ff" fill-opacity="0.55" font-size="10" '
                f'font-family="Segoe UI, Helvetica, Arial, sans-serif">'
                f'{esc(date.strftime("%b %Y"))}</text>'
            )

    title = f"{total:,} commits in the last 365 days"

    return f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
xmlns="http://www.w3.org/2000/svg" role="img"
aria-label="{esc(USERNAME)} GitHub commit activity graph">
  <rect width="{width}" height="{height}" rx="10" fill="#0d1117"/>
  <text x="{left}" y="28" fill="#00f0ff" font-size="18" font-weight="600"
font-family="Segoe UI, Helvetica, Arial, sans-serif">{esc(USERNAME)}'s Commit Activity</text>
  <text x="{left}" y="45" fill="#00f0ff" fill-opacity="0.65" font-size="11"
font-family="Segoe UI, Helvetica, Arial, sans-serif">{esc(title)}</text>
{chr(10).join(grid)}
  <path d="{path}" fill="none" stroke="#b967ff" stroke-width="2.2"
stroke-linejoin="round" stroke-linecap="round"/>
{circles}
{chr(10).join(month_labels)}
</svg>
'''


def main():
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    daily = get_daily_commits()
    with open(OUTPUT, "w", encoding="utf-8") as file:
        file.write(make_svg(daily))
    print(f"Updated {OUTPUT}: {sum(daily.values()):,} commits")


if __name__ == "__main__":
    main()
