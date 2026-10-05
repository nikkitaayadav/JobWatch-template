import re, json, sys, time, urllib.parse, urllib.request, html
from datetime import datetime, timezone, timedelta
from filters import F
KW = F["google_keywords"]
SINCE = sys.argv[2] if len(sys.argv) > 2 else None
cutoff = datetime.fromisoformat(SINCE).replace(tzinfo=timezone.utc) if SINCE else datetime.now(timezone.utc) - timedelta(days=7)
BASE = "https://www.google.com/about/careers/applications/jobs/results?location=United%20States&sort_by=date" + "".join(f"&target_level={l}" for l in F["google_levels"])
def strip(x):
    if not x or not isinstance(x, list) or len(x) < 2 or not x[1]: return ""
    t = re.sub(r"<li>", "\n- ", x[1]); t = re.sub(r"<h3>(.*?)</h3>", r"\n\1\n", t)
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
jobs = {}
for kw in KW:
    for page in range(1, 11):
        url = f"{BASE}&q={urllib.parse.quote(kw)}&page={page}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", h, re.S)
        d = json.loads(m.group(1)); rows = d[0] or []
        old = 0
        for j in rows:
            ts = datetime.fromtimestamp(j[12][0], timezone.utc) if j[12] else None
            if ts and ts < cutoff: old += 1; continue
            jid = j[0]
            if jid in jobs: jobs[jid]["keywords"].append(kw); continue
            slug = re.sub(r"[^a-z0-9]+", "-", j[1].lower()).strip("-")
            jobs[jid] = {"id": jid, "title": j[1], "published": ts.isoformat() if ts else None,
                "locations": [l[0] for l in (j[9] or [])],
                "url": f"https://www.google.com/about/careers/applications/jobs/results/{jid}-{slug}",
                "min_quals": strip(j[19]) or strip(j[4]), "all_quals": strip(j[4]),
                "responsibilities": strip(j[3]), "about": strip(j[10]), "keywords": [kw]}
        if not rows or old == len(rows) or len(rows) < 20: break
        time.sleep(0.5)
    print(f"{kw}: total unique so far {len(jobs)}", file=sys.stderr)
json.dump(list(jobs.values()), open(sys.argv[1], "w"), indent=1)
print(len(jobs))
