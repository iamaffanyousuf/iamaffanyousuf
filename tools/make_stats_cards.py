#!/usr/bin/env python3
"""
Generate self-hosted GitHub profile stat cards for README.

Usage:
    PROFILE_USER=iamaffanyousuf python3 tools/make_stats_cards.py

Optional env:
    STATS_TOKEN  - preferred for live GitHub API data
    GITHUB_TOKEN - fallback
"""

import collections
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
README_PATH = os.path.join(ROOT, "README.md")
USER = os.environ.get("PROFILE_USER", "iamaffanyousuf")
TOKEN = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

BG = "#1a1b27"
TITLE = "#70a5fd"
TEXT = "#38bdad"
MUTED = "#8a92b2"

FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Helvetica, Arial, sans-serif"

LANG_COLORS = {
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "Python": "#3572A5",
    "Java": "#b07219",
    "C": "#555555",
    "C++": "#f34b7d",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "C#": "#178600",
    "Dart": "#00B4AB",
    "PHP": "#4F5D95",
    "Shell": "#89e051",
    "Go": "#00ADD8",
    "Rust": "#dea584",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "Ruby": "#701516",
    "Jupyter Notebook": "#DA5B0B",
    "Astro": "#ff5a03",
    "Objective-C": "#438eff",
    "Lua": "#000080",
    "R": "#198CE7",
    "Perl": "#0298c3",
}

SKIP_DIR = re.compile(
    r"(^|/)("
    r"node_modules|vendor|bower_components|third_party|external|"
    r"build|dist|out|bin|obj|\.next|\.nuxt|__pycache__|"
    r"linux|windows|macos|ios|android|Pods|gradle|\.gradle"
    r")(/|$)"
)
SKIP_FILE = re.compile(
    r"(generated_plugin_registrant|\.g\.dart$|\.freezed\.dart$|"
    r"\.min\.(js|css)$|package-lock\.json$)"
)

EXT = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".cs": "C#",
    ".dart": "Dart",
    ".php": "PHP",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".sh": "Shell",
    ".bash": "Shell",
    ".sql": "SQL",
    ".rb": "Ruby",
    ".go": "Go",
    ".rs": "Rust",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".astro": "Astro",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".m": "Objective-C",
    ".ipynb": "Jupyter Notebook",
    ".r": "R",
    ".pl": "Perl",
    ".lua": "Lua",
}

def api(path):
    url = path if path.startswith("http") else "https://api.github.com/" + path
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-stats-card",
    }
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
            return data, r.headers.get("Link", "")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        print(f"  ! {url} -> {exc}", file=sys.stderr)
        return None, ""

def paged(path):
    url = path
    out = []
    while url:
        data, link = api(url)
        if not isinstance(data, list):
            break
        out.extend(data)
        m = re.search(r'<([^>]+)>;\\s*rel="next"', link)
        url = m.group(1) if m else None
    return out

def load_known():
    try:
        with open(os.path.join(OUT, "stats.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}

def search_count(query):
    q = urllib.parse.urlencode({"q": query, "per_page": 1})
    data, _ = api(f"search/issues?{q}")
    if isinstance(data, dict):
        return data.get("total_count")
    return None

def public_repos():
    repos = paged("users/%s/repos?per_page=100&type=owner" % USER)
    return [r for r in repos if not r.get("fork") and not r.get("archived")]

def language_totals(repos):
    totals = collections.Counter()
    for repo in repos:
        repo_name = repo["name"]
        tree, _ = api(f"repos/{USER}/{repo_name}/git/trees/HEAD?recursive=1")
        if not tree or "tree" not in tree:
            continue
        for node in tree["tree"]:
            if node.get("type") != "blob":
                continue
            path = node["path"]
            if SKIP_DIR.search(path) or SKIP_FILE.search(path):
                continue
            filename = path.rsplit("/", 1)[-1]
            ext = filename[filename.rfind("."):].lower() if "." in filename else ""
            lang = EXT.get(ext)
            if lang:
                totals[lang] += int(node.get("size", 0))
    return totals

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def card_open(w, h, title, desc):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" role="img" aria-labelledby="t d">\n'
        '<title id="t">%s</title><desc id="d">%s</desc>\n'
        '<rect x="0.5" y="0.5" width="%s" height="%s" rx="6" fill="%s" stroke="#2c3050"/>\n'
        % (w, h, w, h, esc(title), esc(desc), w - 1, h - 1, BG)
    )

def stats_card(name, values):
    rows = [
        ("Total Stars Earned", values.get("stars")),
        ("Total Commits", values.get("commits")),
        ("Total PRs", values.get("prs")),
        ("Total Issues", values.get("issues")),
        ("Public Repositories", values.get("repos")),
    ]
    rows = [(label, value) for label, value in rows if value is not None]

    w, h = 460, 195
    s = card_open(w, h, "%s's GitHub stats" % name, ", ".join(f"{label} {value}" for label, value in rows))
    s += '<text x="25" y="33" fill="%s" font-family="%s" font-size="16" font-weight="600">%s’s GitHub Stats</text>\n' % (TITLE, FONT, esc(name))
    s += '<line x1="25" y1="45" x2="435" y2="45" stroke="#2c3050"/>\n'

    y = 72
    for label, value in rows:
        s += '<circle cx="30" cy="%d" r="3" fill="%s"/>\n' % (y - 4, TITLE)
        s += '<text x="43" y="%d" fill="%s" font-family="%s" font-size="14">%s</text>\n' % (y, TEXT, FONT, esc(label))
        s += '<text x="435" y="%d" fill="%s" font-family="%s" font-size="14" font-weight="700" text-anchor="end">%s</text>\n' % (y, TEXT, FONT, format(value, ","))
        y += 25

    return s + "</svg>\n"

def langs_card(totals):
    w, h = 360, 195
    items = totals.most_common(6)
    grand = sum(totals.values()) or 1

    s = card_open(w, h, "Most used languages", ", ".join(f"{name} {100 * size / grand:.1f}%" for name, size in items))
    s += '<text x="25" y="33" fill="%s" font-family="%s" font-size="16" font-weight="600">Most Used Languages</text>\n' % (TITLE, FONT)
    s += '<line x1="25" y1="45" x2="335" y2="45" stroke="#2c3050"/>\n'

    bar_x, bar_y, bar_w, bar_h = 25, 60, 310, 9
    s += '<defs><clipPath id="bar"><rect x="%d" y="%d" width="%d" height="%d" rx="%d"/></clipPath></defs>\n' % (bar_x, bar_y, bar_w, bar_h, bar_h // 2)
    s += '<g clip-path="url(#bar)">\n'
    x = float(bar_x)
    for name, value in items:
        seg = bar_w * value / grand
        s += '<rect x="%.2f" y="%d" width="%.2f" height="%d" fill="%s"/>\n' % (x, bar_y, seg + 0.5, bar_h, LANG_COLORS.get(name, MUTED))
        x += seg
    if x < bar_x + bar_w:
        s += '<rect x="%.2f" y="%d" width="%.2f" height="%d" fill="#2c3050"/>\n' % (x, bar_y, bar_x + bar_w - x, bar_h)
    s += "</g>\n"

    for i, (name, value) in enumerate(items):
        col, row = i % 2, i // 2
        lx, ly = 25 + col * 165, 98 + row * 26
        s += '<circle cx="%d" cy="%d" r="5" fill="%s"/>\n' % (lx + 5, ly - 4, LANG_COLORS.get(name, MUTED))
        s += '<text x="%d" y="%d" fill="%s" font-family="%s" font-size="12">%s</text>\n' % (lx + 17, ly, TEXT, FONT, esc(name))
        s += '<text x="%d" y="%d" fill="%s" font-family="%s" font-size="12" text-anchor="end">%.1f%%</text>\n' % (lx + 150, ly, MUTED, FONT, 100 * value / grand)

    return s + "</svg>\n"

def stamp_readme():
    try:
        with open(README_PATH, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return

    out = text
    for name in ("github-stats.svg", "top-langs.svg"):
        path = os.path.join(OUT, name)
        try:
            with open(path, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()[:8]
        except OSError:
            continue
        out = re.sub(r'src=\"assets/%s(\\?h=[0-9a-f]+)?\"' % re.escape(name),
                     'src=\"assets/%s?h=%s\"' % (name, digest), out)

    if out != text:
        with open(README_PATH, "w", encoding="utf-8") as fh:
            fh.write(out)
        print("stamped README with card hashes")

def main():
    os.makedirs(OUT, exist_ok=True)
    known = load_known()

    print(f"Fetching public repositories for {USER}...")
    repos = public_repos()
    if not repos:
        print("No public repositories returned.", file=sys.stderr)
        return 1

    stars = sum(r.get("stargazers_count", 0) for r in repos)
    print(f"  {len(repos)} public repos, {stars} stars")

    user_data, _ = api(f"users/{USER}")
    user_data = user_data or {}
    name = user_data.get("name") or known.get("name") or USER

    values = {
        "stars": stars,
        "repos": len(repos),
        "commits": None,
        "prs": None,
        "issues": None,
        "name": name,
    }

    commits_data, _ = api(f"search/commits?q=author:{USER}&per_page=1")
    if isinstance(commits_data, dict):
        values["commits"] = commits_data.get("total_count")

    values["prs"] = search_count(f"author:{USER} type:pr")
    values["issues"] = search_count(f"author:{USER} type:issue")

    for key in ("commits", "prs", "issues"):
        if values[key] is None and known.get(key) is not None:
            values[key] = known[key]

    totals = language_totals(repos)
    if not totals:
        print("No language data available.", file=sys.stderr)
        return 1

    with open(os.path.join(OUT, "github-stats.svg"), "w", encoding="utf-8") as fh:
        fh.write(stats_card(name, values))
    with open(os.path.join(OUT, "top-langs.svg"), "w", encoding="utf-8") as fh:
        fh.write(langs_card(totals))

    keep = dict(known)
    keep.update({k: v for k, v in values.items() if v is not None})
    with open(os.path.join(OUT, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump(keep, fh, indent=2, sort_keys=True)
        fh.write("\n")

    stamp_readme()
    print("Updated assets/github-stats.svg and assets/top-langs.svg")
    return 0

if __name__ == "__main__":
    sys.exit(main())
