"""Generate black-and-white stats SVGs from public GitHub data (no API token required)."""
import html
import json
import os
import re
import urllib.request
from datetime import date, timedelta

USER = os.environ.get("GH_USER", "Yaiphaba189")
OUT = os.environ.get("OUT_DIR", "assets")
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
FG, MUTED, BG = "#ffffff", "#a1a1aa", "#000000"


def get(url, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats"})
    if accept:
        req.add_header("Accept", accept)
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def contributions():
    page = get(f"https://github.com/users/{USER}/contributions")
    dates = dict((i, d) for d, i in re.findall(r'data-date="([\d-]+)"[^>]*id="(contribution-day-component-[\d-]+)"', page))
    days = {}
    for target, text in re.findall(r'<tool-tip[^>]*for="(contribution-day-component-[\d-]+)"[^>]*>([^<]*)</tool-tip>', page):
        m = re.match(r"(\d+) contribution", text)
        days[date.fromisoformat(dates[target])] = int(m.group(1)) if m else 0
    return dict(sorted(days.items()))


def streaks(days):
    today = date.today()
    counts = [(d, c) for d, c in days.items() if d <= today]
    longest = run = 0
    start = best_start = best_end = None
    for d, c in counts:
        if c > 0:
            if run == 0:
                start = d
            run += 1
            if run > longest:
                longest, best_start, best_end = run, start, d
        else:
            run = 0
    cur, cur_start, d = 0, None, today
    if days.get(d, 0) == 0:
        d -= timedelta(days=1)
    while days.get(d, 0) > 0:
        cur, cur_start = cur + 1, d
        d -= timedelta(days=1)
    return cur, cur_start, longest, best_start, best_end


def fmt(d, year=False):
    return d.strftime("%b %-d, %Y" if year else "%b %-d") if d else "-"


def card(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
            f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" fill="{BG}" stroke="{FG}"/>'
            f'<g font-family="{FONT}">{body}</g></svg>')


def text(x, y, s, size=13, fill=FG, weight="normal", anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}">{html.escape(str(s))}</text>'


def stats_card(days, profile, stars):
    rows = [
        ("Contributions (last year)", sum(days.values())),
        ("Active days", sum(1 for c in days.values() if c)),
        ("Public repositories", profile["public_repos"]),
        ("Stars earned", stars),
        ("Followers", profile["followers"]),
    ]
    body = text(25, 36, f"{USER}'s GitHub Stats", 16, weight="bold")
    for i, (k, v) in enumerate(rows):
        y = 68 + i * 24
        body += text(25, y, k, 13, MUTED) + text(470, y, v, 13, weight="bold", anchor="end")
    return card(495, 195, body)


def streak_card(days):
    total = sum(days.values())
    cur, cur_start, longest, l_start, l_end = streaks(days)
    first, last = next(iter(days)), next(reversed(days))
    col = lambda cx, big, label, sub, ring=False: (
        (f'<circle cx="{cx}" cy="82" r="38" fill="none" stroke="{FG}" stroke-width="4"/>' if ring else "")
        + text(cx, 90 if ring else 92, big, 30, weight="bold", anchor="middle")
        + text(cx, 148, label, 13, weight="bold", anchor="middle")
        + text(cx, 168, sub, 10, MUTED, anchor="middle")
    )
    body = (col(85, total, "Total Contributions", f"{fmt(first, True)} - Present")
            + col(247, cur, "Current Streak", f"{fmt(cur_start)} - Present" if cur else "No active streak", ring=True)
            + col(410, longest, "Longest Streak", f"{fmt(l_start)} - {fmt(l_end)}"))
    sep = "".join(f'<line x1="{x}" y1="30" x2="{x}" y2="165" stroke="{FG}" stroke-opacity="0.35"/>' for x in (165, 330))
    return card(495, 195, body + sep)


def graph(days, span=30):
    recent = list(days.items())[-span:]
    W, H, L, R, T, B = 1000, 320, 60, 30, 60, 50
    ymax = max(4, max(c for _, c in recent))
    ymax += (-ymax) % 2
    px = lambda i: L + i * (W - L - R) / (len(recent) - 1)
    py = lambda v: T + (H - T - B) * (1 - v / ymax)
    body = text(W / 2, 32, f"{USER}'s Contribution Graph", 16, weight="bold", anchor="middle")
    for v in range(0, ymax + 1, max(1, ymax // 4)):
        body += (f'<line x1="{L}" y1="{py(v):.1f}" x2="{W-R}" y2="{py(v):.1f}" stroke="{FG}" stroke-opacity="0.15"/>'
                 + text(L - 10, py(v) + 4, v, 11, MUTED, anchor="end"))
    pts = " ".join(f"{px(i):.1f},{py(c):.1f}" for i, (_, c) in enumerate(recent))
    area = f"{px(0):.1f},{py(0):.1f} {pts} {px(len(recent)-1):.1f},{py(0):.1f}"
    body += f'<polygon points="{area}" fill="{FG}" fill-opacity="0.08"/>'
    body += f'<polyline points="{pts}" fill="none" stroke="{FG}" stroke-width="2" stroke-linejoin="round"/>'
    for i, (d, c) in enumerate(recent):
        body += f'<circle cx="{px(i):.1f}" cy="{py(c):.1f}" r="3.5" fill="{FG}"><title>{d}: {c}</title></circle>'
        body += text(px(i), H - B + 20, d.day, 10.5, MUTED, anchor="middle")
    body += text(W / 2, H - 8, "Days", 11, MUTED, anchor="middle")
    body += f'<text transform="translate(16 {H/2}) rotate(-90)" font-size="11" fill="{MUTED}" text-anchor="middle">Contributions</text>'
    return card(W, H, body)


def main():
    days = contributions()
    profile = json.loads(get(f"https://api.github.com/users/{USER}", "application/vnd.github+json"))
    repos = json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner", "application/vnd.github+json"))
    stars = sum(r["stargazers_count"] for r in repos)
    os.makedirs(OUT, exist_ok=True)
    for name, svg in (("stats", stats_card(days, profile, stars)), ("streak", streak_card(days)), ("graph", graph(days))):
        with open(os.path.join(OUT, f"{name}.svg"), "w") as f:
            f.write(svg)
    print(f"{len(days)} days, {sum(days.values())} contributions")


if __name__ == "__main__":
    main()
