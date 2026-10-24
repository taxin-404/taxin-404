#!/usr/bin/env python3
"""Fill the EXTERNAL block in README.md with every project you contribute to
(repos you do NOT own). Works from what GitHub itself counts as your contributions,
so nothing has to be added by hand."""
import json, os, re, subprocess
from collections import defaultdict
from pathlib import Path

USER = os.environ.get("GH_USER", "taxin-404")
SHOW_TIMELINE = False          # True = also list individual PRs under the cards
HIDE = set()                   # repos to leave out, e.g. {"someowner/somerepo"}


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def fmt_stars(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)


def is_own(repo):
    return repo.split("/")[0].lower() == USER.lower()


def stars(repo):
    try:
        return int(gh("api", f"repos/{repo}", "--jq", ".stargazers_count").strip())
    except Exception:
        return 0


def commits(repo):
    try:
        out = gh("api", f"repos/{repo}/contributors?per_page=100", "--paginate",
                 "--jq", f'.[] | select(.login=="{USER}") | .contributions')
        return sum(int(x) for x in out.split())
    except Exception:
        return 0


# 1) repos where your commits were ACCEPTED (they're on the project's default branch),
#    excluding your own repos. Rejected / still-open PRs never count.
query = """query($login:String!){user(login:$login){
  repositoriesContributedTo(first:100, includeUserRepositories:false,
    contributionTypes:[COMMIT],
    orderBy:{field:STARGAZERS, direction:DESC}){
    nodes{nameWithOwner stargazerCount isPrivate}}}}"""
repos = {}
try:
    data = json.loads(gh("api", "graphql", "-f", f"query={query}", "-f", f"login={USER}"))
    for n in data["data"]["user"]["repositoriesContributedTo"]["nodes"]:
        if not n["isPrivate"] and not is_own(n["nameWithOwner"]):
            repos[n["nameWithOwner"]] = n["stargazerCount"]
except Exception as e:
    print("graphql lookup failed:", e)

# 2) merged PRs (for per-project PR counts, and the optional timeline)
prs = json.loads(gh("search", "prs", "--author", USER, "--merged", "--limit", "200",
                    "--json", "repository,title,url,closedAt,number"))
prs = [p for p in prs if not is_own(p["repository"]["nameWithOwner"])]

# 3) optional manual list for PRs the maintainer landed themselves
extra_file = Path(".github/extra-contributions.txt")
if extra_file.exists():
    seen = {p["url"] for p in prs}
    for line in extra_file.read_text(encoding="utf-8").splitlines():
        url = line.split("#")[0].strip()
        m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", url)
        if not m or url in seen or is_own(m.group(1)):
            continue
        try:
            d = json.loads(gh("pr", "view", url, "--json", "title,closedAt,url,number"))
        except Exception:
            continue
        prs.append({"repository": {"nameWithOwner": m.group(1)}, "title": d["title"],
                    "url": d["url"], "number": d["number"],
                    "closedAt": d.get("closedAt") or "1970-01-01T00:00:00Z", "landed": True})

prs.sort(key=lambda p: p["closedAt"], reverse=True)
by_repo = defaultdict(list)
for p in prs:
    by_repo[p["repository"]["nameWithOwner"]].append(p)
for r in by_repo:
    if r not in repos:
        repos[r] = stars(r)

for r in HIDE:
    repos.pop(r, None)

rows = sorted(((r, s, len(by_repo.get(r, [])), commits(r)) for r, s in repos.items()),
              key=lambda x: (-x[1], x[0]))
total_stars = sum(s for _, s, _, _ in rows)

out = []
if not rows:
    out.append("_No external contributions yet._")
else:
    out.append('<div align="center">\n')
    out.append(f"![Projects](https://img.shields.io/badge/projects-{len(rows)}-1793d1?style=for-the-badge&logo=github&logoColor=white)")
    if prs:
        out.append(f"![PRs](https://img.shields.io/badge/PRs_landed-{len(prs)}-2ea44f?style=for-the-badge&logo=git&logoColor=white)")
    out.append(f"![Reach](https://img.shields.io/badge/combined_reach-{fmt_stars(total_stars)}_stars-e3b341?style=for-the-badge&logo=starship&logoColor=white)")
    out.append("\n</div>\n")

    out.append('<h3 align="center">🚀 Projects I\'ve contributed to:</h3>\n')
    out.append('<div align="center">\n')
    out.append("<table>")
    for i in range(0, len(rows), 2):
        out.append("<tr>")
        for repo, s, n_prs, n_commits in rows[i:i + 2]:
            owner = repo.split("/")[0]
            badges = f'<img src="https://img.shields.io/github/stars/{repo}?style=flat-square&logo=github&color=1793d1"/>'
            if n_prs:
                badges += f' <img src="https://img.shields.io/badge/PRs-{n_prs}-2ea44f?style=flat-square"/>'
            if n_commits:
                badges += f' <img src="https://img.shields.io/badge/commits-{n_commits}-8957e5?style=flat-square"/>'
            out.append(
                f'<td width="50%" valign="top">\n'
                f'<a href="https://github.com/{repo}"><img src="https://github.com/{owner}.png?size=96" width="56" align="left" alt="{owner}"/></a>'
                f'&nbsp;<a href="https://github.com/{repo}"><b>{repo}</b></a><br/>\n'
                f'&nbsp;{badges}\n'
                f'</td>'
            )
        if len(rows[i:i + 2]) == 1:
            out.append('<td width="50%"></td>')
        out.append("</tr>")
    out.append("</table>\n")
    out.append("</div>\n")

    if SHOW_TIMELINE and prs:
        out.append("### 🕑 Timeline\n")
        for p in prs[:8]:
            tag = " · _landed upstream_" if p.get("landed") else ""
            out.append(f"- `{p['closedAt'][:10]}` [{p['title']}]({p['url']}) · **{p['repository']['nameWithOwner']}**{tag}")

block = "\n".join(out)
readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
new = re.sub(r"(<!--EXTERNAL_START-->).*?(<!--EXTERNAL_END-->)",
             lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", text, flags=re.DOTALL)
badge = (f"![Contributed to](https://img.shields.io/badge/contributed_to-{len(rows)}_projects-1793d1"
         "?style=for-the-badge&logo=github&logoColor=white)")
new = re.sub(r"(<!--BADGE_START-->).*?(<!--BADGE_END-->)",
             lambda m: f"{m.group(1)}{badge}{m.group(2)}", new, flags=re.DOTALL)
readme.write_text(new, encoding="utf-8")
