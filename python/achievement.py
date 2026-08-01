"""
achievement.py -- generates assets/achievement.svg: an arcade "achievements
unlocked" screen driven by your real GitHub stats (stars, followers,
profile views, repos). Same visual universe as contribution_shooter.py.

Data sources:
  stars / followers / repos  -> GitHub GraphQL API (needs ACCESS_TOKEN,
                                 same token as status.py / stats2.py)
  profile views               -> komarev.com's badge SVG, parsed for the
                                 number it displays (there is no GitHub
                                 API for this -- komarev's badge is the
                                 only source of truth)

IMPORTANT: fetching the komarev badge counts as a profile view and
increments it (it's a hit counter, not a read-only stat). Running this
on a schedule will add a small number of "views" from the workflow
itself -- that's an inherent tradeoff of reading a counter this way,
not a bug in this script.

There is no real API for the github-profile-trophy rankings (they're
computed by a private percentile-ranking algorithm on their server), so
this does NOT attempt to reproduce those specific badges. Instead it
defines its own achievement thresholds against your real numbers.

Run as: python achievement.py
Writes: assets/achievement.svg
"""

import os
import re

import requests

USERNAME = "Arish0limbu"
TOKEN = os.environ["ACCESS_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
GRAPHQL_URL = "https://api.github.com/graphql"
KOMAREV_URL = f"https://komarev.com/ghpvc/?username={USERNAME}"
OUT_FILE = "assets/achievement.svg"


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


def fetch_stars_followers_repos():
    query = """
    query($login:String!){
      user(login:$login){
        followers { totalCount }
        repositories(first:100, ownerAffiliations:[OWNER]) {
          totalCount
          nodes { stargazerCount }
        }
      }
    }
    """
    user = github_query(query, {"login": USERNAME})["user"]
    if user is None:
        raise RuntimeError(
            f"GitHub returned no user for login={USERNAME!r}. "
            "Check USERNAME matches your GitHub login exactly, and "
            "that ACCESS_TOKEN is valid."
        )
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    return {
        "stars": stars,
        "followers": user["followers"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
    }


def fetch_profile_views():
    """Fetch komarev's badge SVG and parse the view count out of it."""
    resp = requests.get(KOMAREV_URL, timeout=15)
    resp.raise_for_status()
    svg_text = resp.text

    # komarev renders a shields.io-style badge; the count is the digits
    # in the rightmost <text> element(s). Grab all digit runs and take
    # the longest one (the count), since smaller numbers can appear in
    # font-size/x attributes.
    candidates = re.findall(r">([\d,]{1,})<", svg_text)
    candidates = [c.replace(",", "") for c in candidates if c.replace(",", "").isdigit()]
    if not candidates:
        print("Warning: could not parse a view count out of komarev's badge; using 0.")
        return 0
    return int(max(candidates, key=len))


# --------------------------------------------------------------------------
# Achievement definitions
# --------------------------------------------------------------------------
# Each achievement: (key, label, sub, icon_fn, and -- for BASE achievements
# only -- unlocked_fn(stats) -> bool).
#
# Icons are built from simple shapes (no external assets / no copyrighted
# icon sets), consistent with the pixel-art style used elsewhere.
#
# HAT TRICK and COLLECTOR are "meta" achievements: they unlock based on
# how many *other* achievements are unlocked, not on a raw stat. That
# means they can't be evaluated the same way as the base achievements --
# see compute_unlocked() below for how the circularity is resolved.

def icon_star(unlocked):
    c = "#ffd24d" if unlocked else "#3a3550"
    return f'<path d="M12 2 L14.5 8.5 L21 9 L16 13.5 L17.5 20 L12 16.5 L6.5 20 L8 13.5 L3 9 L9.5 8.5 Z" fill="{c}"/>'


def icon_people(unlocked):
    c = "#4df1ff" if unlocked else "#3a3550"
    return (
        f'<circle cx="8" cy="8" r="3.2" fill="{c}"/>'
        f'<circle cx="16" cy="8" r="3.2" fill="{c}"/>'
        f'<path d="M2 20c0-4 3-6.5 6-6.5s6 2.5 6 6.5" fill="{c}"/>'
        f'<path d="M12 20c0-3.5 2.5-6 6-6s6 2.5 6 6" fill="{c}" opacity="0.85"/>'
    )


def icon_eye(unlocked):
    c = "#ff8a4d" if unlocked else "#3a3550"
    return (
        f'<path d="M1 12s4.5-7 11-7 11 7 11 7-4.5 7-11 7-11-7-11-7Z" fill="none" stroke="{c}" stroke-width="2"/>'
        f'<circle cx="12" cy="12" r="3.4" fill="{c}"/>'
    )


def icon_repo(unlocked):
    c = "#9dff8f" if unlocked else "#3a3550"
    return (
        f'<rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="{c}" stroke-width="2"/>'
        f'<line x1="3" y1="9" x2="21" y2="9" stroke="{c}" stroke-width="2"/>'
    )


def icon_rocket(unlocked):
    c = "#ff5f56" if unlocked else "#3a3550"
    return (
        f'<path d="M12 2c3 2 5 6 5 11 0 2-.5 4-1.5 6h-7C7.5 17 7 15 7 13c0-5 2-9 5-11Z" '
        f'fill="{c}"/>'
        f'<circle cx="12" cy="10" r="2" fill="#0a0710"/>'
        f'<path d="M7 15l-3 5 4-2" fill="{c}"/>'
        f'<path d="M17 15l3 5-4-2" fill="{c}"/>'
    )


def icon_crown(unlocked):
    c = "#d9b3ff" if unlocked else "#3a3550"
    return f'<path d="M2 18h20l-2-9-5 4-3-7-3 7-5-4Z" fill="{c}"/>'


def icon_trio(unlocked):
    """Three little medals, for HAT TRICK (3+ badges unlocked)."""
    c = "#ffb84d" if unlocked else "#3a3550"
    return (
        f'<circle cx="6" cy="9" r="3.4" fill="{c}"/><path d="M4.2 11.5l1.8 3 1.8-3" fill="{c}"/>'
        f'<circle cx="12" cy="6" r="3.8" fill="{c}"/><path d="M10 9.2l2 3.4 2-3.4" fill="{c}"/>'
        f'<circle cx="18" cy="9" r="3.4" fill="{c}"/><path d="M16.2 11.5l1.8 3 1.8-3" fill="{c}"/>'
    )


def icon_trophy(unlocked):
    """A trophy, for COLLECTOR (unlock everything else)."""
    c = "#ff4de0" if unlocked else "#3a3550"
    return (
        f'<path d="M7 3h10v2a5 5 0 0 1-10 0V3Z" fill="{c}"/>'
        f'<path d="M7 4c-3 0-4 2-4 4s1.5 4 4 4v-2c-1.3 0-2-1-2-2s.5-2 2-2V4Z" fill="{c}"/>'
        f'<path d="M17 4c3 0 4 2 4 4s-1.5 4-4 4v-2c1.3 0 2-1 2-2s-.5-2-2-2V4Z" fill="{c}"/>'
        f'<rect x="11" y="10" width="2" height="4" fill="{c}"/>'
        f'<rect x="8" y="15" width="8" height="2" rx="1" fill="{c}"/>'
        f'<rect x="6" y="18" width="12" height="2" rx="1" fill="{c}"/>'
    )


# The 8 "base" achievements: each unlocks directly off a real stat.
BASE_ACHIEVEMENTS = [
    dict(key="first_light", label="FIRST LIGHT", sub="Ship 1+ repo",
         unlocked=lambda s: s["repos"] >= 1, icon=icon_repo),
    dict(key="stargazer", label="STARGAZER", sub="Earn 5+ stars",
         unlocked=lambda s: s["stars"] >= 5, icon=icon_star),
    dict(key="open_source", label="OPEN SOURCE", sub="Earn 25+ stars",
         unlocked=lambda s: s["stars"] >= 25, icon=icon_star),
    dict(key="community", label="COMMUNITY", sub="10+ followers",
         unlocked=lambda s: s["followers"] >= 10, icon=icon_people),
    dict(key="known_dev", label="KNOWN DEV", sub="50+ followers",
         unlocked=lambda s: s["followers"] >= 50, icon=icon_crown),
    dict(key="on_the_map", label="ON THE MAP", sub="100+ profile views",
         unlocked=lambda s: s["views"] >= 100, icon=icon_eye),
    dict(key="viral", label="VIRAL", sub="1,000+ profile views",
         unlocked=lambda s: s["views"] >= 1000, icon=icon_eye),
    dict(key="builder", label="BUILDER", sub="Ship 10+ repos",
         unlocked=lambda s: s["repos"] >= 10, icon=icon_rocket),
]

# The 2 "meta" achievements: unlocked based on how many *other*
# achievements are unlocked, not off a stat directly.
META_ACHIEVEMENTS = [
    dict(key="hat_trick", label="HAT TRICK", sub="Unlock 3+ badges", icon=icon_trio),
    dict(key="collector", label="COLLECTOR", sub="Unlock 10+ badges", icon=icon_trophy),
]

# Full ordered list -- this is what controls grid position (row-major,
# left-to-right, top-to-bottom).
ACHIEVEMENTS = BASE_ACHIEVEMENTS + META_ACHIEVEMENTS


def compute_unlocked(stats):
    """Return {key: bool} for every achievement, base and meta alike.

    This is the part the old script got wrong: HAT TRICK / COLLECTOR
    need to know how many badges are unlocked, but "how many badges are
    unlocked" isn't defined until every badge (including HAT TRICK /
    COLLECTOR themselves) has been evaluated -- a circular dependency.

    We break the cycle by evaluating in two passes:
      1. All 8 base achievements are evaluated directly off `stats`.
      2. HAT TRICK unlocks once 3+ of those base achievements are
         unlocked -- it never looks at itself or at COLLECTOR.
      3. COLLECTOR unlocks once all 9 *other* achievements (8 base +
         HAT TRICK) are unlocked -- it never looks at itself, so there's
         no self-reference.
    """
    unlocked = {a["key"]: a["unlocked"](stats) for a in BASE_ACHIEVEMENTS}

    base_count = sum(unlocked.values())
    unlocked["hat_trick"] = base_count >= 3

    others_count = base_count + (1 if unlocked["hat_trick"] else 0)
    unlocked["collector"] = others_count >= len(ACHIEVEMENTS) - 1  # everything else unlocked

    return unlocked


# --------------------------------------------------------------------------
# SVG rendering
# --------------------------------------------------------------------------

COLS = 5
CARD_W = 124
CARD_H = 108
GAP = 10
LEFT_PAD = 16
TOP_PAD = 72


def fmt(n):
    return f"{n:,}"


def build_svg(stats):
    unlocked_map = compute_unlocked(stats)
    total = len(ACHIEVEMENTS)
    unlocked_count = sum(unlocked_map.values())

    rows = -(-total // COLS)  # ceil div
    grid_w = COLS * CARD_W + (COLS - 1) * GAP
    width = LEFT_PAD * 2 + grid_w
    grid_h = rows * CARD_H + (rows - 1) * GAP
    height = TOP_PAD + grid_h + 16

    parts = []
    parts.append(
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
    )
    parts.append(
        """
  <defs>
    <linearGradient id="achBezel" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#2a1b3d"/>
      <stop offset="100%" stop-color="#120a1c"/>
    </linearGradient>
    <radialGradient id="unlockGlow" cx="50%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#4df1ff" stop-opacity="0.20"/>
      <stop offset="100%" stop-color="#4df1ff" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="shimmerGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="45%" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.35"/>
      <stop offset="55%" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="barFill" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#2ee6ff"/>
      <stop offset="100%" stop-color="#4df1ff"/>
    </linearGradient>
    <clipPath id="cardClip">
      <rect x="0.5" y="0.5" width=\""""
        + str(CARD_W - 1)
        + """\" height=\""""
        + str(CARD_H - 1)
        + """\" rx="8"/>
    </clipPath>
  </defs>
"""
    )
    parts.append(
        """
  <style>
    .screen { fill: #05060a; }
    .hud-label { font: 9px 'SFMono-Regular', Consolas, monospace; fill: #6e5a8a; letter-spacing: 1px; }
    .hud-value { font: bold 16px 'SFMono-Regular', Consolas, monospace; fill: #4df1ff; }
    .card-locked { fill: #0d1017; stroke: #23202f; }
    .card-unlocked { fill: #12101f; stroke: #4df1ff; }
    .label-locked { font: bold 9px 'SFMono-Regular', Consolas, monospace; fill: #4a4560; letter-spacing: 0.5px; }
    .label-unlocked { font: bold 9px 'SFMono-Regular', Consolas, monospace; fill: #e8f6ff; letter-spacing: 0.5px; }
    .sub-locked { font: 8px 'SFMono-Regular', Consolas, monospace; fill: #38334a; }
    .sub-unlocked { font: 8px 'SFMono-Regular', Consolas, monospace; fill: #8b93b8; }
  </style>
"""
    )

    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="url(#achBezel)"/>')
    parts.append(f'<rect x="4" y="4" width="{width - 8}" height="{height - 8}" rx="6" class="screen"/>')

    # ---- HUD: profile views / stars / followers, + progress ----
    hud_items = [
        ("PROFILE VIEWS", fmt(stats["views"])),
        ("STARS", fmt(stats["stars"])),
        ("FOLLOWERS", fmt(stats["followers"])),
    ]
    hud_col_w = (width - LEFT_PAD * 2) / 3
    for i, (label, value) in enumerate(hud_items):
        x = LEFT_PAD + i * hud_col_w
        parts.append(f'<text x="{x}" y="26" class="hud-label">{label}</text>')
        parts.append(f'<text x="{x}" y="46" class="hud-value">{value}</text>')
    parts.append(
        f'<text x="{width - LEFT_PAD}" y="26" text-anchor="end" class="hud-label">'
        f'{unlocked_count}/{total} UNLOCKED'
        f'<animate attributeName="opacity" values="0.55;1;0.55" dur="2.4s" repeatCount="indefinite"/>'
        f'</text>'
    )
    parts.append(f'<line x1="{LEFT_PAD}" y1="56" x2="{width - LEFT_PAD}" y2="56" stroke="#23202f" stroke-width="1"/>')

    # ---- progress bar ----
    track_w = width - LEFT_PAD * 2
    fill_w = track_w * (unlocked_count / total) if total else 0
    parts.append(f'<rect x="{LEFT_PAD}" y="60" width="{track_w}" height="3" rx="1.5" fill="#1a1726"/>')
    parts.append(f'<rect x="{LEFT_PAD}" y="60" width="{fill_w:.1f}" height="3" rx="1.5" fill="url(#barFill)"/>')

    # ---- achievement grid ----
    unlocked_index = 0  # counts only *unlocked* cards, for animation stagger
    for idx, ach in enumerate(ACHIEVEMENTS):
        row, col = divmod(idx, COLS)
        x = LEFT_PAD + col * (CARD_W + GAP)
        y = TOP_PAD + row * (CARD_H + GAP)
        unlocked = unlocked_map[ach["key"]]
        card_cls = "card-unlocked" if unlocked else "card-locked"
        label_cls = "label-unlocked" if unlocked else "label-locked"
        sub_cls = "sub-unlocked" if unlocked else "sub-locked"

        icon_size = 26
        icon_x = (CARD_W - icon_size) / 2
        cx = CARD_W / 2

        parts.append(f'<g transform="translate({x},{y})">')

        if unlocked:
            i = unlocked_index
            border_begin = 0.45 + i * 0.3
            shimmer_begin = 0.6 + i * 0.5
            icon_begin = 0.5 + i * 0.3
            sparkle1_begin = 0.9 + i * 0.3
            sparkle2_begin = 1.5 + i * 0.3

            parts.append(f'<rect x="0" y="0" width="{CARD_W}" height="{CARD_H}" rx="8" fill="url(#unlockGlow)"/>')
            parts.append(
                f'<rect x="0.5" y="0.5" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="8" '
                f'class="{card_cls}" stroke-width="1.2">'
                f'<animate attributeName="stroke-opacity" values="0.6;1;0.6" dur="2.6s" '
                f'begin="{border_begin:.2f}s" repeatCount="indefinite"/></rect>'
            )
            parts.append('<g clip-path="url(#cardClip)">')
            parts.append(
                f'<rect x="-40" y="-10" width="60" height="{CARD_H + 20}" fill="url(#shimmerGrad)">'
                f'<animateTransform attributeName="transform" type="translate" '
                f'values="0,0; 200,0; 200,0" keyTimes="0;0.5;1" dur="3.2s" '
                f'begin="{shimmer_begin:.2f}s" repeatCount="indefinite"/></rect>'
            )
            parts.append('</g>')
            parts.append(f'<g transform="translate({icon_x:.1f},14) scale({icon_size / 24:.3f})">')
            parts.append(
                f'<animateTransform attributeName="transform" type="scale" values="1;1.1;1" '
                f'additive="sum" dur="2.6s" begin="{icon_begin:.2f}s" repeatCount="indefinite"/>'
            )
            parts.append(ach["icon"](unlocked))
            parts.append('</g>')
            parts.append(
                f'<path d="M{CARD_W - 28} 12l1.3 3 3 .3-2.3 2 .7 3-2.7-1.7-2.7 1.7 .7-3-2.3-2 3-.3z" '
                f'fill="#9dff8f" opacity="0">'
                f'<animate attributeName="opacity" values="0;1;0" dur="1.8s" '
                f'begin="{sparkle1_begin:.2f}s" repeatCount="indefinite"/></path>'
            )
            parts.append(
                f'<path d="M16 88l.9 2 2 .2-1.5 1.4.5 2-1.9-1.1-1.9 1.1.5-2-1.5-1.4 2-.2z" '
                f'fill="#4df1ff" opacity="0">'
                f'<animate attributeName="opacity" values="0;1;0" dur="1.8s" '
                f'begin="{sparkle2_begin:.2f}s" repeatCount="indefinite"/></path>'
            )
            unlocked_index += 1
        else:
            parts.append(
                f'<rect x="0.5" y="0.5" width="{CARD_W - 1}" height="{CARD_H - 1}" rx="8" '
                f'class="{card_cls}" stroke-width="1.2"/>'
            )
            parts.append(f'<g transform="translate({icon_x:.1f},14) scale({icon_size / 24:.3f})">')
            parts.append(ach["icon"](unlocked))
            parts.append('</g>')

        parts.append(f'<text x="{cx}" y="72" text-anchor="middle" class="{label_cls}">{ach["label"]}</text>')
        parts.append(f'<text x="{cx}" y="86" text-anchor="middle" class="{sub_cls}">{ach["sub"]}</text>')
        if not unlocked:
            parts.append(f'<text x="{cx}" y="98" text-anchor="middle" class="sub-locked">LOCKED</text>')

        parts.append('</g>')

    parts.append('</svg>')
    return '\n'.join(parts)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    if not os.path.exists("assets"):
        raise FileNotFoundError("assets/ directory not found.")

    print("Fetching stars / followers / repos...")
    stats = fetch_stars_followers_repos()

    print("Fetching profile views (this also counts as one view)...")
    stats["views"] = fetch_profile_views()

    print("Stats:", stats)

    svg = build_svg(stats)
    with open(OUT_FILE, "w") as f:
        f.write(svg)

    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
