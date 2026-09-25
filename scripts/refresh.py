#!/usr/bin/env python3
"""Generate the live OPEN-SOURCE section for NextGenAI Labs' org profile.

Pure standard library. Reads NextGenAI Labs' public GitHub repos and renders a
'live' block between the LIVE markers in profile/README.md. Designed to run in
a GitHub Actions workflow (hourly) that commits the output back; also runs
locally with GH_TOKEN set (e.g. `GH_TOKEN=$(gh auth token) python3 scripts/refresh.py`).
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ORG = "nextgenai-labs"
START = "<!-- LIVE:START -->"
END = "<!-- LIVE:END -->"
SKIP = {".github"}  # profile-hosting repo is infrastructure, not a product

TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

COLORS = {
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Python": "#3776ab",
    "Rust": "#dea584",
    "Go": "#00ADD8",
    "Java": "#b07219",
    "C++": "#f34b7d",
    "C": "#555555",
    "C#": "#178600",
    "Shell": "#89e051",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Jupyter Notebook": "#DA5B0B",
    "Dockerfile": "#384d54",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
    "Astro": "#ff5a03",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Kotlin": "#A97BFF",
    "Swift": "#F05138",
    "Solidity": "#AA6746",
}
FALLBACK = "#8b949e"
EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U0001F900-\U0001F9FF"
    "\U00002600-\U000027BF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F1E6-\U0001F1FF"
    "\u200d\u20e3"
    "]"
)


def _request(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nextgenai-profile-refresh",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    try:
        with urlopen(Request(url, headers=headers), timeout=30) as r:
            return json.load(r)
    except HTTPError as exc:
        print(f"warning: {url} -> {exc.code}", file=sys.stderr)
        return None
    except URLError as exc:
        print(f"warning: {url} -> {exc.reason}", file=sys.stderr)
        return None


def _lang_hex(name: str) -> str:
    return COLORS.get(name or "", FALLBACK).lstrip("#")


def _esc(text: str, limit: int = 0) -> str:
    if not text:
        return ""
    text = str(text).strip().replace("\n", " ").replace("\r", " ")
    text = EMOJI.sub("", text)
    text = text.replace("|", "\\|").replace("`", "'").replace("<", "&lt;").replace(">", "&gt;")
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def main():
    repos = (
        _request(f"https://api.github.com/orgs/{ORG}/repos?per_page=100&type=public&sort=updated")
        or []
    )
    repos = [r for r in repos if not r.get("fork") and r.get("name") not in SKIP]
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total_stars = sum(int(r.get("stargazers_count") or 0) for r in repos)

    # latest commit message per repo (the public roster is tiny: 3-4 repos)
    for repo in repos:
        full_name = repo.get("full_name", "")
        latest = "—"
        if full_name:
            data = _request(f"https://api.github.com/repos/{full_name}/commits?per_page=1")
            if data:
                latest = (data[0].get("commit") or {}).get("message", "—").splitlines()[0]
        repo["_latest"] = latest

    # language mix
    lang_totals = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_totals[lang] = lang_totals.get(lang, 0) + 1
    total_langs = sum(lang_totals.values()) or 1
    top_langs = sorted(lang_totals.items(), key=lambda kv: -kv[1])

    # most starred
    starred = sorted(repos, key=lambda r: int(r.get("stargazers_count") or 0), reverse=True)[:4]
    starred = [r for r in starred if int(r.get("stargazers_count") or 0) > 0]

    lines = []
    lines.append("**Live status — auto-refreshed hourly by GitHub Actions** · last run "
                 f"`{now_ts}`")
    lines.append("")
    lines.append(f"![Repos](https://img.shields.io/badge/Public_repos-{len(repos)}-34d399?"
                 "style=for-the-badge) "
                 f"![Stars](https://img.shields.io/badge/Total_stars-{total_stars}-6c8cff?style=for-the-badge)")
    lines.append("")

    lines.append("**Open-source repos**")
    lines.append("")
    lines.append("| | Repo | Stars | Language | Description | Latest |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for repo in sorted(repos, key=lambda r: r.get("pushed_at") or "", reverse=True):
        lang = repo.get("language")
        dot = (f"<img width=14 src='https://img.shields.io/badge/%E2%80%8B-%E2%80%8B-"
               f"%23{_lang_hex(lang)}' title='{_esc(lang)}'>")
        lines.append(
            f"| {dot} | [{repo.get('name')}](https://github.com/{repo.get('full_name')}) "
            f"| {repo.get('stargazers_count') or 0} "
            f"| `{_esc(lang, 18)}` "
            f"| {_esc(repo.get('description'), 72)} "
            f"| {_esc(repo.get('_latest'), 40)} |"
        )

    if starred:
        lines.append("")
        lines.append("**Most starred**")
        lines.append("")
        lines.append("| Repo | Stars | Description |")
        lines.append("| --- | --- | --- |")
        for repo in starred:
            name = repo.get("name")
            desc = _esc(repo.get("description"), 90) or "—"
            lines.append(f"| [{name}](https://github.com/{repo.get('full_name')}) | "
                         f"{repo.get('stargazers_count')} | {desc} |")

    if top_langs:
        lines.append("")
        lines.append("**Language mix**")
        lines.append("")
        lines.append("```")
        for lang, count in top_langs:
            share = count / total_langs
            bar = "█" * round(share * 24)
            lines.append(f"{lang:<16} {share * 100:4.0f}%  {bar}")
        lines.append("```")
    lines.append("")
    lines.append(
        "_Refreshed every hour by [update-profile.yml](.github/workflows/update-profile.yml) "
        "— GitHub-native · no third party · covers public repos only._"
    )

    block = "\n".join(lines)

    readme_path = Path(__file__).resolve().parent.parent / "profile" / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    if START not in text:
        print("LIVE markers not found in profile/README.md", file=sys.stderr)
        sys.exit(1)
    before, _, after = text.partition(START)
    _, _, tail = after.partition(END)
    new_text = before + START + "\n\n" + block + "\n\n" + END + tail
    readme_path.write_text(new_text, encoding="utf-8")
    print(f"profile README updated (public repos={len(repos)}, stars={total_stars})")


if __name__ == "__main__":
    main()