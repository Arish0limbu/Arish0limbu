"""
Fetches live GitHub statistics for USERNAME and writes them into an SVG
template (dark.svg / any file passed on the command line).

Stats written:
    repos, stars, followers, contributed  -> via GitHub GraphQL API
    commits                               -> via GraphQL contributionsCollection
                                              (summed across every year since
                                              account creation)
    lines of code (added / removed)       -> by cloning each of your own,
                                              non-fork repos and running
                                              `git log --numstat`, filtered to
                                              commits authored by you.

A local cache (stats_cache.json) remembers the last commit processed in each
repo so re-runs only scan *new* commits instead of the full history every
time. Commit it alongside the SVG so the cache persists between workflow
runs.
"""

import json
import os
import subprocess
import tempfile

import requests
from lxml import etree

USERNAME = "Arish0limbu"
TOKEN = os.environ["ACCESS_TOKEN"]

# Extra email addresses (comma separated) that appear as commit authors and
# should be counted as "you" for LOC purposes, in addition to your GitHub
# noreply addresses. Set this as a repo secret/variable if you commit under
# a work or personal email too.
EXTRA_EMAILS = {
    e.strip() for e in os.environ.get("EXTRA_EMAILS", "").split(",") if e.strip()
}

# Set to True to also count lines of code in forked repositories.
INCLUDE_FORKS = False

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

GRAPHQL_URL = "https://api.github.com/graphql"
CACHE_FILE = "stats_cache.json"


# --------------------------------------------------------------------------
# GraphQL helpers
# --------------------------------------------------------------------------

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


def get_profile():
    """Basic profile info: id, creation year, emails, and repo list."""
    query = """
    query($login:String!){
      user(login:$login){
        id
        databaseId
        email
        createdAt

        repositories(
          first:100,
          ownerAffiliations:[OWNER]
        ){
          totalCount
          nodes{
            name
            nameWithOwner
            url
            isFork
            stargazerCount
          }
        }

        followers{
          totalCount
        }

        repositoriesContributedTo(
          contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY],
          includeUserRepositories:true
        ){
          totalCount
        }
      }
    }
    """

    return github_query(
        query,
        {"login": USERNAME},
    )["user"]


def get_total_commit_contributions(created_at):
    """Sum totalCommitContributions across every year the account existed.

    GitHub's contributionsCollection only accepts a <=1 year window, so we
    walk year by year from account creation to now.
    """
    start_year = int(created_at[:4])
    from datetime import datetime, timezone

    current_year = datetime.now(timezone.utc).year

    query = """
    query($login:String!, $from:DateTime!, $to:DateTime!){
      user(login:$login){
        contributionsCollection(from:$from, to:$to){
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """

    total = 0
    for year in range(start_year, current_year + 1):
        from_date = f"{year}-01-01T00:00:00Z"
        to_date = f"{year}-12-31T23:59:59Z"

        result = github_query(
            query,
            {"login": USERNAME, "from": from_date, "to": to_date},
        )["user"]["contributionsCollection"]

        # restrictedContributionsCount covers commits to private repos you
        # can't otherwise see stats for; totalCommitContributions covers the
        # rest. Together they mirror the number shown on your profile graph.
        total += result["totalCommitContributions"]
        total += result["restrictedContributionsCount"]

    return total


# --------------------------------------------------------------------------
# Lines-of-code via local git clones
# --------------------------------------------------------------------------

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def build_author_emails(profile):
    emails = set(EXTRA_EMAILS)
    if profile.get("email"):
        emails.add(profile["email"])

    login = USERNAME
    db_id = profile["databaseId"]
    emails.add(f"{login}@users.noreply.github.com")
    emails.add(f"{db_id}+{login}@users.noreply.github.com")
    return emails


def run(cmd, cwd=None):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=True
    )


def clone_repo(url, dest):
    auth_url = url.replace("https://", f"https://x-access-token:{TOKEN}@")
    run(["git", "clone", "--quiet", "--no-tags", auth_url, dest])


def count_loc_for_repo(repo_url, repo_name, dest_dir, author_emails, since_sha):
    """Returns (additions, deletions, commit_count, latest_sha)."""
    clone_repo(repo_url, dest_dir)

    log_range = f"{since_sha}..HEAD" if since_sha else "HEAD"

    try:
        result = run(
            [
                "git", "log", log_range,
                "--no-merges",
                "--pretty=format:__COMMIT__ %H %ae",
                "--numstat",
            ],
            cwd=dest_dir,
        )
    except subprocess.CalledProcessError:
        # since_sha no longer exists (force-push/rebase) - fall back to
        # scanning full history for this repo.
        result = run(
            [
                "git", "log", "HEAD",
                "--no-merges",
                "--pretty=format:__COMMIT__ %H %ae",
                "--numstat",
            ],
            cwd=dest_dir,
        )

    additions = deletions = commit_count = 0
    is_mine = False
    latest_sha = since_sha

    for line in result.stdout.splitlines():
        if line.startswith("__COMMIT__"):
            _, sha, author_email = line.split(" ", 2)
            is_mine = author_email.lower() in {e.lower() for e in author_emails}
            if latest_sha is None:
                latest_sha = sha
            if is_mine:
                commit_count += 1
            continue

        if not line.strip() or not is_mine:
            continue

        parts = line.split("\t")
        if len(parts) != 3:
            continue
        add, dele, _path = parts
        if add.isdigit():
            additions += int(add)
        if dele.isdigit():
            deletions += int(dele)

    head_sha = run(["git", "rev-parse", "HEAD"], cwd=dest_dir).stdout.strip()
    return additions, deletions, commit_count, head_sha


def get_loc_stats(profile, author_emails, cache):
    repos = profile["repositories"]["nodes"]
    if not INCLUDE_FORKS:
        repos = [r for r in repos if not r["isFork"]]

    total_add = cache.get("_totals", {}).get("additions", 0)
    total_del = cache.get("_totals", {}).get("deletions", 0)
    total_commits = cache.get("_totals", {}).get("commits", 0)

    # Recompute totals from per-repo cache to avoid drift, then add deltas.
    total_add = 0
    total_del = 0
    total_commits = 0

    with tempfile.TemporaryDirectory() as tmp:
        for repo in repos:
            name = repo["nameWithOwner"]
            dest = os.path.join(tmp, repo["name"])
            prev = cache.get(name, {})
            since_sha = prev.get("last_sha")

            try:
                add, dele, new_commits, head_sha = count_loc_for_repo(
                    repo["url"], name, dest, author_emails, since_sha
                )
            except subprocess.CalledProcessError as e:
                print(f"Skipping {name}: {e.stderr.strip()[:200]}")
                add, dele, new_commits = 0, 0, 0
                head_sha = since_sha

            cache[name] = {
                "last_sha": head_sha,
                "additions": prev.get("additions", 0) + add,
                "deletions": prev.get("deletions", 0) + dele,
                "commits": prev.get("commits", 0) + new_commits,
            }

            total_add += cache[name]["additions"]
            total_del += cache[name]["deletions"]
            total_commits += cache[name]["commits"]

    cache["_totals"] = {
        "additions": total_add,
        "deletions": total_del,
        "commits": total_commits,
    }

    return total_add, total_del


# --------------------------------------------------------------------------
# SVG writing
# --------------------------------------------------------------------------

def replace(root, element_id, value):
    element = root.find(f".//*[@id='{element_id}']")
    if element is not None:
        element.text = str(value)


def fmt(n):
    return f"{n:,}"


def make_dots(label_with_colon, value_str, block_width):
    """Pad with dots so that `label + dots + value` always adds up to
    exactly `block_width` characters.

    The SVG uses a monospace font, so this keeps whatever comes after
    the value (e.g. "| Stars:", "| Followers:") pinned to a fixed
    column no matter how many digits the value has -- instead of the
    old approach, which used a single global width (40) and compared
    against label words ("Repositories") that didn't match what's
    actually printed in the SVG ("Repos:"), so it drifted every run.
    """
    dots = block_width - len(label_with_colon) - len(value_str)
    if dots < 1:
        dots = 1
    return "." * dots


def update_svg(svg_file, stats):
    tree = etree.parse(svg_file)
    root = tree.getroot()

    replace(root, "repo_data", fmt(stats["repos"]))
    replace(root, "star_data", fmt(stats["stars"]))
    replace(root, "contrib_data", fmt(stats["contributed"]))
    replace(root, "follower_data", fmt(stats["followers"]))
    replace(root, "commit_data", fmt(stats["commits"]))
    replace(root, "loc_data", fmt(stats["loc_add"] + stats["loc_del"]))
    replace(root, "loc_add", fmt(stats["loc_add"]))
    replace(root, "loc_del", fmt(stats["loc_del"]))

    # Block widths are the fixed total character count (label + dots +
    # value) that each field occupies in dark.svg, so text after it
    # ("| Stars:", "| Followers:", etc.) always lines up. These were
    # measured directly from the current dark.svg layout.
    replace(root, "repo_data_dots",
            make_dots("Repos:", fmt(stats["repos"]), 19))
    replace(root, "star_data_dots",
            make_dots("Stars:", fmt(stats["stars"]), 19))
    replace(root, "follower_data_dots",
            make_dots("Followers:", fmt(stats["followers"]), 19))
    replace(root, "commit_data_dots",
            make_dots("Commmits:", fmt(stats["commits"]), 36))
    replace(root, "loc_data_dots",
            make_dots("Lines of Code on GitHub:", fmt(stats["loc_add"] + stats["loc_del"]), 36))

    tree.write(svg_file, encoding="utf-8", xml_declaration=True)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

SVG_FILES = ["assets/dark.svg", "assets/stats.svg"]


def main():
    existing = [f for f in SVG_FILES if os.path.exists(f)]
    missing = [f for f in SVG_FILES if f not in existing]
    for f in missing:
        print(f"Warning: {f} not found, skipping.")
    if not existing:
        raise FileNotFoundError(f"None of {SVG_FILES} were found.")

    print("Fetching profile & repository data...")
    profile = get_profile()

    stars = sum(r["stargazerCount"] for r in profile["repositories"]["nodes"])

    print("Fetching commit contribution totals...")
    commits = get_total_commit_contributions(profile["createdAt"])

    print("Computing lines of code (this can take a while on first run)...")
    author_emails = build_author_emails(profile)
    cache = load_cache()
    loc_add, loc_del = get_loc_stats(profile, author_emails, cache)
    save_cache(cache)

    stats = {
        "repos": profile["repositories"]["totalCount"],
        "stars": stars,
        "followers": profile["followers"]["totalCount"],
        "contributed": profile["repositoriesContributedTo"]["totalCount"],
        "commits": commits,
        "loc_add": loc_add,
        "loc_del": loc_del,
    }

    for svg_file in existing:
        print(f"Updating {svg_file}...")
        update_svg(svg_file, stats)

    print("Done!", stats)


if __name__ == "__main__":
    main()