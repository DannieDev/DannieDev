"""Genera github-metrics.svg con métricas reales (incluye repos privados) usando METRICS_TOKEN."""
import json, os, sys, urllib.request
from datetime import datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "DannieDev")
TOKEN = os.environ.get("METRICS_TOKEN")
OUT = os.environ.get("OUT", "github-metrics.svg")


def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    return data["data"]


def fetch():
    base = gql(
        """query($u:String!){ user(login:$u){ name createdAt
             repositoriesContributedTo(includeUserRepositories:true,
               contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]){ totalCount } } }""",
        {"u": USER},
    )["user"]
    created = datetime.fromisoformat(base["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    commits = prs = 0
    days = {}
    start = created
    while start < now:
        end = min(start + timedelta(days=365), now)
        c = gql(
            """query($u:String!,$f:DateTime!,$t:DateTime!){ user(login:$u){
                 contributionsCollection(from:$f,to:$t){
                   totalCommitContributions totalPullRequestContributions
                   contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } } } }""",
            {"u": USER, "f": start.isoformat(), "t": end.isoformat()},
        )["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"]
        prs += c["totalPullRequestContributions"]
        for w in c["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = max(days.get(d["date"], 0), d["contributionCount"])
        start = end
    return base, commits, prs, days


def streaks(days):
    best = cur = 0
    for k in sorted(days):
        cur = cur + 1 if days[k] > 0 else 0
        best = max(best, cur)
    today = sorted(days)[-1]
    current, d = 0, datetime.fromisoformat(today)
    if days.get(today, 0) == 0:  # el día de hoy aún no cuenta como racha rota
        d -= timedelta(days=1)
    while days.get(d.date().isoformat(), 0) > 0:
        current += 1
        d -= timedelta(days=1)
    return current, best


def fmt(n):
    return f"{n:,}"


def render(name, commits, repos, prs, cur, best, days, created_year):
    W, H = 840, 330
    bg, card, border = "#0D1117", "#161B22", "#30363D"
    accent, text, muted = "#58A6FF", "#E6EDF3", "#8B949E"
    palette = ["#1C2128", "#1E3A5F", "#1F5FA8", "#3B82F6", "#79C0FF"]

    # heatmap: últimas 53 semanas
    last = datetime.fromisoformat(sorted(days)[-1])
    start = last - timedelta(days=last.weekday() + 1 + 52 * 7)  # domingo
    vals = [days.get((start + timedelta(days=i)).date().isoformat(), 0) for i in range(53 * 7)]
    nz = sorted(v for v in vals if v > 0)
    q = [nz[int(len(nz) * p)] for p in (0.25, 0.5, 0.75)] if nz else [1, 2, 3]
    year_total = sum(vals)
    tiles = [
        (fmt(commits), "Commits totales", f"desde {created_year}, incluye privados"),
        (fmt(repos), "Repositorios", "con contribuciones"),
        (fmt(year_total), "Contribuciones", "en el último año"),
        (f"{best} días", "Mejor racha", f"racha actual: {cur} día{'s' if cur != 1 else ''}"),
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Segoe UI, Ubuntu, Helvetica, Arial, sans-serif">',
        "<style>.f{opacity:0;animation:in .6s ease forwards}@keyframes in{to{opacity:1}}</style>",
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="{bg}" stroke="{border}"/>',
        f'<text x="28" y="44" font-size="20" font-weight="700" fill="{accent}">{name} · Actividad en GitHub</text>',
        f'<text x="{W-28}" y="44" font-size="12" fill="{muted}" text-anchor="end">Actualizado {datetime.now(timezone.utc):%d/%m/%Y}</text>',
    ]
    tw, gap, x0, y0 = 186, 14, 28, 66
    for i, (big, label, sub) in enumerate(tiles):
        x = x0 + i * (tw + gap)
        out += [
            f'<g class="f" style="animation-delay:{i*0.12:.2f}s">',
            f'<rect x="{x}" y="{y0}" width="{tw}" height="92" rx="10" fill="{card}" stroke="{border}"/>',
            f'<rect x="{x}" y="{y0+16}" width="3" height="60" rx="1.5" fill="{accent}"/>',
            f'<text x="{x+18}" y="{y0+40}" font-size="26" font-weight="700" fill="{text}">{big}</text>',
            f'<text x="{x+18}" y="{y0+62}" font-size="13" font-weight="600" fill="{accent}">{label}</text>',
            f'<text x="{x+18}" y="{y0+79}" font-size="11" fill="{muted}">{sub}</text>',
            "</g>",
        ]
    out.append(f'<text x="28" y="190" font-size="13" font-weight="600" fill="{text}">Calendario de contribuciones</text>')
    cs, cg, hx, hy = 12, 3, 28, 202
    for i, v in enumerate(vals):
        d = start + timedelta(days=i)
        if d > last:
            break
        lvl = 0 if v == 0 else 1 + sum(v > t for t in q)
        out.append(f'<rect x="{hx + (i // 7) * (cs + cg)}" y="{hy + (i % 7) * (cs + cg)}" width="{cs}" height="{cs}" rx="2.5" fill="{palette[lvl]}"/>')
    lx = W - 28 - 5 * (cs + cg) - 40
    out.append(f'<text x="{lx-6}" y="{H-14}" font-size="10" fill="{muted}" text-anchor="end">Menos</text>')
    for i, c in enumerate(palette):
        out.append(f'<rect x="{lx + i*(cs+cg)}" y="{H-24}" width="{cs}" height="{cs}" rx="2.5" fill="{c}"/>')
    out.append(f'<text x="{lx + 5*(cs+cg) + 4}" y="{H-14}" font-size="10" fill="{muted}">Más</text>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    if os.environ.get("DEMO"):
        import random
        random.seed(3)
        today = datetime(2026, 10, 3)
        days = {(today - timedelta(days=i)).date().isoformat(): (random.choice([0, 0, 1, 3, 5, 8, 14]) if i < 300 else 0) for i in range(700)}
        svg = render("Daniel Mendoza", 2450, 32, 4, 1, 12, days, 2024)
    else:
        base, commits, prs, days = fetch()
        cur, best = streaks(days)
        svg = render(base["name"] or USER, commits, base["repositoriesContributedTo"]["totalCount"],
                     prs, cur, best, days, base["createdAt"][:4])
    open(OUT, "w").write(svg)
    print("ok", OUT)
