#!/usr/bin/env python3
"""Rewrite the EXTERNAL block in README.md with merged PRs to repos NOT owned by USER."""
import json, os, re, subprocess
from collections import defaultdict
from pathlib import Path

USER = os.environ.get("GH_USER", "taxin-404")
RECENT_VISIBLE = 6


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def fmt_stars(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def icon(title):
    t = title.lower()
    if t.startswith("feat") or "add" in t:
        return "✨"
    if t.startswith("fix") or "fix" in t or "compliance" in t:
        return "🐛"
    if any(w in t for w in ("readme", "license", "docs", "badge")):
        return "📝"
    return "🔀"


prs = json.loads(gh(
    "search", "prs", "--author", USER, "--merged", "--limit", "200",
    "--json", "repository,title,url,closedAt,number",
))
prs = [p for p in prs if p["repository"]["nameWithOwner"].split("/")[0].lower() != USER.lower()]
prs.sort(key=lambda p: p["closedAt"], reverse=True)

by_repo = defaultdict(list)
for p in prs:
    by_repo[p["repository"]["nameWithOwner"]].append(p)


def stars(repo):
    try:
        return int(gh("api", f"repos/{repo}", "--jq", ".stargazers_count").strip())
    except Exception:
        return 0


repos = sorted(((r, v, stars(r)) for r, v in by_repo.items()), key=lambda x: (-x[2], -len(x[1])))
total_stars = sum(s for _, _, s in repos)

out = []
if not repos:
    out.append("_No merged external PRs yet._")
else:
    # --- headline badges
    out.append('<div align="center">\n')
    out.append(f"![PRs](https://img.shields.io/badge/merged_PRs-{len(prs)}-2ea44f?style=for-the-badge&logo=git&logoColor=white)")
    out.append(f"![Projects](https://img.shields.io/badge/projects-{len(repos)}-1793d1?style=for-the-badge&logo=github&logoColor=white)")
    out.append(f"![Reach](https://img.shields.io/badge/combined_reach-{fmt_stars(total_stars)}_stars-e3b341?style=for-the-badge&logo=starship&logoColor=white)")
    out.append("\n</div>\n")

    # --- project cards, two per row
    out.append("### 🚀 Projects I've contributed to\n")
    out.append("<table>")
    for i in range(0, len(repos), 2):
        out.append("<tr>")
        for repo, v, s in repos[i:i + 2]:
            owner = repo.split("/")[0]
            latest = v[0]["title"].replace("<", "&lt;").replace(">", "&gt;")
            out.append(
                f'<td width="50%" valign="top">\n'
                f'<a href="https://github.com/{repo}"><img src="https://github.com/{owner}.png?size=96" width="56" align="left" alt="{owner}"/></a>'
                f'&nbsp;<a href="https://github.com/{repo}"><b>{repo}</b></a><br/>\n'
                f'&nbsp;<img src="https://img.shields.io/github/stars/{repo}?style=flat-square&logo=github&color=1793d1"/> '
                f'<img src="https://img.shields.io/badge/merged_PRs-{len(v)}-2ea44f?style=flat-square"/><br/>\n'
                f'<sub>↳ {latest}</sub>\n'
                f'</td>'
            )
        if len(repos[i:i + 2]) == 1:
            out.append('<td width="50%"></td>')
        out.append("</tr>")
    out.append("</table>\n")

    # --- timeline, same-day same-repo PRs collapsed into one line
    groups = []
    for p in prs:
        key = (p["repository"]["nameWithOwner"], p["closedAt"][:10])
        if groups and groups[-1]["key"] == key:
            groups[-1]["items"].append(p)
        else:
            groups.append({"key": key, "items": [p]})

    lines = []
    for g in groups:
        repo, date = g["key"]
        items = g["items"]
        if len(items) == 1:
            p = items[0]
            lines.append(f"- `{date}` {icon(p['title'])} [{p['title']}]({p['url']}) · **{repo}**")
        else:
            names = ", ".join(x["title"] for x in items[:2])
            more = f" +{len(items) - 2} more" if len(items) > 2 else ""
            lines.append(f"- `{date}` 🔀 **{len(items)} PRs** merged in **{repo}** ({names}{more})")

    out.append("### 🕑 Timeline\n")
    out.extend(lines[:RECENT_VISIBLE])
    if len(lines) > RECENT_VISIBLE:
        out.append("\n<details>\n<summary>Show older</summary>\n")
        out.extend(lines[RECENT_VISIBLE:])
        out.append("\n</details>")

block = "\n".join(out)
readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
new = re.sub(
    r"(<!--EXTERNAL_START-->).*?(<!--EXTERNAL_END-->)",
    lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}",
    text, flags=re.DOTALL,
)
readme.write_text(new, encoding="utf-8")
