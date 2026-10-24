#!/usr/bin/env python3
"""Rewrite the EXTERNAL block in README.md with merged PRs to repos NOT owned by USER."""
import json, os, re, subprocess
from collections import defaultdict
from pathlib import Path

USER = os.environ.get("GH_USER", "taxin-404")
MAX_RECENT = 10


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


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


rows = sorted(((r, v, stars(r)) for r, v in by_repo.items()), key=lambda x: (-x[2], -len(x[1])))

out = [f"**{len(prs)} merged PRs across {len(by_repo)} projects**\n"]

if rows:
    out += ["| Project | ⭐ | Merged PRs |", "|---|---:|---:|"]
    for repo, v, s in rows:
        out.append(f"| [{repo}](https://github.com/{repo}) | {s:,} | {len(v)} |")

    out += ["", "### 🕑 Recently merged", ""]
    for p in prs[:MAX_RECENT]:
        repo = p["repository"]["nameWithOwner"]
        date = p["closedAt"][:10]
        title = p["title"].replace("|", "\\|")
        out.append(f"- `{date}` [{title}]({p['url']}) · **{repo}**")
else:
    out.append("_No merged external PRs yet._")

block = "\n".join(out)
readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
new = re.sub(
    r"(<!--EXTERNAL_START-->).*?(<!--EXTERNAL_END-->)",
    lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}",
    text, flags=re.DOTALL,
)
readme.write_text(new, encoding="utf-8")
