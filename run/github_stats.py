"""Fetch and shape GitHub stats for the profile cards.

Scope: the account's own repositories plus every repository of the organizations
the user belongs to (whatever the token can read), so stars and language sizes
cover the account and its organizations. Adapted from ggbdpq/github_stats.py.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

USERNAME = "zhongruan0522"
GRAPHQL = "https://api.github.com/graphql"

# $repoCursor / $orgCursor page the two heavy connections; the rest of the user
# node comes back on every page and is simply ignored on continuation pages.
USER_QUERY = """query($login: String!, $repoCursor: String, $orgCursor: String) { user(login: $login) {
  followers { totalCount }
  organizations(first: 100, after: $orgCursor) {
    pageInfo { hasNextPage endCursor }
    nodes { login }
  }
  pullRequests(states: MERGED, first: 100) {
    totalCount
    nodes { repository { nameWithOwner } }
  }
  repositories(ownerAffiliations: OWNER, isFork: false, first: 100, after: $repoCursor) {
    totalCount
    pageInfo { hasNextPage endCursor }
    nodes { stargazerCount languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
  }
  contributionsCollection { totalCommitContributions contributionCalendar { totalContributions } }
  repositoriesContributedTo(first: 1) { totalCount }
} }"""

ORG_QUERY = """query($login: String!, $cursor: String) { organization(login: $login) {
  repositories(isFork: false, first: 100, after: $cursor) {
    totalCount
    pageInfo { hasNextPage endCursor }
    nodes { stargazerCount languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } }
  }
} }"""

NON_CODE = {"CSS", "SCSS", "HTML", "PLpgSQL", "Shell", "Dockerfile", "Makefile",
            "Markdown", "Batchfile", "PowerShell", "INI", "TSQL"}
# co-authored-by patch scanning only looks back this far (matches the "last year" rows)
PATCH_SCAN_WINDOW = timedelta(days=365)


def _headers(token, username):
    return {"Authorization": f"Bearer {token}", "User-Agent": f"{username}-profile"}


def _open(token, username, url, data=None):
    request = urllib.request.Request(url, data=data, headers=_headers(token, username))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response), response.headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"GitHub API {url} failed: HTTP {exc.code}: {detail}") from exc


def graphql(token, username, query, variables):
    payload, _ = _open(token, username, GRAPHQL,
                       json.dumps({"query": query, "variables": variables}).encode())
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error for {variables}: {payload['errors']}")
    return payload["data"]


def fetch_user(token, username):
    """User node plus own repositories and organization logins, fully paginated."""
    data = graphql(token, username, USER_QUERY, {"login": username})
    if data["user"] is None:
        raise RuntimeError(f"user {username} not found")
    user = data["user"]

    repos = list(user["repositories"]["nodes"])
    conn = user["repositories"]
    while conn["pageInfo"]["hasNextPage"]:
        conn = graphql(token, username, USER_QUERY,
                       {"login": username, "repoCursor": conn["pageInfo"]["endCursor"]}
                       )["user"]["repositories"]
        repos.extend(conn["nodes"])

    orgs = [node["login"] for node in user["organizations"]["nodes"]]
    conn = user["organizations"]
    while conn["pageInfo"]["hasNextPage"]:
        conn = graphql(token, username, USER_QUERY,
                       {"login": username, "orgCursor": conn["pageInfo"]["endCursor"]}
                       )["user"]["organizations"]
        orgs.extend(node["login"] for node in conn["nodes"])
    return user, repos, orgs


def fetch_org_repos(token, username, org_login):
    """All repositories of one organization the token can read."""
    data = graphql(token, username, ORG_QUERY, {"login": org_login})
    if data["organization"] is None:
        raise RuntimeError(f"organization {org_login} is not readable with this token")
    conn = data["organization"]["repositories"]
    repos = list(conn["nodes"])
    while conn["pageInfo"]["hasNextPage"]:
        data = graphql(token, username, ORG_QUERY,
                       {"login": org_login, "cursor": conn["pageInfo"]["endCursor"]})
        conn = data["organization"]["repositories"]
        repos.extend(conn["nodes"])
    return conn["totalCount"], repos


def third_party_repos(repo_counts, username, org_logins):
    """Merged-PR repos owned by someone else: not the user, not their organizations."""
    own = {username.lower()} | {login.lower() for login in org_logins}
    return [name for name in repo_counts if name.split("/")[0].lower() not in own]


def count_patches(commits, pr_shas):
    """Commits landed outside GitHub's merge flow and outside the author's own merged
    PRs — a maintainer can push a PR head verbatim (committer stays the author), which
    is a PR landing, not a patch."""
    return sum(1 for c in commits
               if c["commit"]["committer"]["email"] != "noreply@github.com"
               and c["sha"] not in pr_shas)


def count_coauthored(commits, username, pr_numbers=(), pr_shas=()):
    """Commits by OTHERS crediting `username` via a Co-authored-by trailer — the
    maintainer's own landing of the author's patch. Commits referencing one of the
    author's merged PR numbers are squashes of those PRs (already in the PR row)."""
    n = 0
    for c in commits:
        if username.lower() in c["commit"]["author"]["email"].lower():
            continue
        if c["sha"] in pr_shas:
            continue
        msg = c["commit"]["message"]
        if not any(line.lower().startswith("co-authored-by:") and username.lower() in line.lower()
                   for line in msg.splitlines()):
            continue
        if any(f"#{num}" in msg for num in pr_numbers):
            continue
        n += 1
    return n


def merged_pr_refs(token, username, repo):
    """Numbers and commit SHAs of the author's merged PRs in `repo`."""
    query = urllib.parse.quote(f"is:pr is:merged author:{username} repo:{repo}")
    payload, _ = _open(token, username,
                       f"https://api.github.com/search/issues?q={query}")
    numbers = [item["number"] for item in payload["items"]]
    shas = set()
    for number in numbers:
        commits, _ = _open(token, username,
                           f"https://api.github.com/repos/{repo}/pulls/{number}/commits?per_page=100")
        shas.update(c["sha"] for c in commits)
    return numbers, shas


def _get_commits(token, username, repo, query, max_pages=20):
    """All commits matching `query`, following Link pagination up to max_pages."""
    out, url = [], f"https://api.github.com/repos/{repo}/commits?{query}&per_page=100"
    for _ in range(max_pages):
        page, headers = _open(token, username, url)
        out.extend(page)
        m = re.search(r'<([^>]+)>; rel="next"', headers.get("Link", ""))
        if not m or len(page) < 100:
            return out
        url = m.group(1)
    return out


def fetch_patches(token, username, repos, since):
    """Upstream-applied patch commits per third-party repo: default-branch commits
    authored by `username` (applied by hand, outside merge flow and own PRs) plus
    commits by others crediting them via Co-authored-by. Returns {nameWithOwner: count}."""
    counts = {}
    for repo in repos:
        authored = _get_commits(token, username, repo, f"author={username}")
        all_commits = _get_commits(token, username, repo, f"since={since}")
        has_direct = any(c["commit"]["committer"]["email"] != "noreply@github.com" for c in authored)
        credited = count_coauthored(all_commits, username)
        if not has_direct and not credited:
            continue
        numbers, shas = merged_pr_refs(token, username, repo)
        n = count_patches(authored, shas) + count_coauthored(all_commits, username, set(numbers), shas)
        if n:
            counts[repo] = n
    return counts


def _languages(repos):
    """Top languages by code size across all given repos, ggbdpq-style."""
    sizes = Counter()
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes["Other" if name in NON_CODE else name] += edge["size"]
    total = sum(sizes.values()) or 1
    top = [(name, size) for name, size in sizes.most_common()
           if name != "Other" and size / total >= 0.005][:7]
    other = total - sum(size for _, size in top)
    languages = [(name, round(size / total * 100, 1)) for name, size in top]
    languages.append(("Other", round(other / total * 100, 1)))
    return languages


def fetch_data(token, username=USERNAME):
    """All numbers behind the cards: account + organizations scope."""
    user, user_repos, org_logins = fetch_user(token, username)
    org_repos, org_repo_total = [], 0
    for login in org_logins:
        total, nodes = fetch_org_repos(token, username, login)
        org_repo_total += total
        org_repos.extend(nodes)
    all_repos = [*user_repos, *org_repos]

    calendar = user["contributionsCollection"]
    repo_counts = Counter(node["repository"]["nameWithOwner"]
                          for node in user["pullRequests"]["nodes"] if node["repository"])
    since = (datetime.now(timezone.utc) - PATCH_SCAN_WINDOW).strftime("%Y-%m-%dT%H:%M:%SZ")
    patch_counts = fetch_patches(token, username,
                                 third_party_repos(repo_counts, username, org_logins), since)
    patches_by_repo = sorted(((name.split("/")[-1], count) for name, count in patch_counts.items() if count),
                             key=lambda item: (-item[1], item[0]))
    return {
        "contributions": calendar["contributionCalendar"]["totalContributions"],
        "commits": calendar["totalCommitContributions"],
        "merged_prs": user["pullRequests"]["totalCount"],
        "patches_by_repo": patches_by_repo,
        "repositories": user["repositories"]["totalCount"] + org_repo_total,
        "stars": sum(node["stargazerCount"] for node in all_repos),
        "contributed_to": user["repositoriesContributedTo"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "languages": _languages(all_repos),
    }
