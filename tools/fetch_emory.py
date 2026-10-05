import re, json, sys, time, html, urllib.request
from datetime import datetime, timezone, timedelta
# careers.emory.edu (Jibe) lists Emory University and Emory Healthcare together.
# Pages through every posting newest-first until it passes `since`.
SINCE = sys.argv[2] if len(sys.argv) > 2 else None
cutoff = datetime.fromisoformat(SINCE).replace(tzinfo=timezone.utc) if SINCE else datetime.now(timezone.utc) - timedelta(days=7)
API = "https://careers.emory.edu/api/jobs?page={}&limit=100&sortBy=posted_date&descending=true"
# Skill terms checked against title + responsibilities (the role text, without benefits/EEO boilerplate).
# A posting with none of these (config/filters.json emory_skill_terms) is marked for auto-skip.
from filters import skills
SKILLS = skills("emory_skill_terms")
def clean(t):
    t = re.sub(r"<li[^>]*>", "\n- ", t or ""); t = re.sub(r"<(p|br)[^>]*>", "\n", t)
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(re.sub(r"<[^>]+>", "", t))).strip()
def parse(s): return datetime.fromisoformat(s.replace("+0000", "+00:00"))
def section(text, start, ends):
    m = re.search(start + r"(?P<body>.*?)(?=" + "|".join(ends) + r"|$)", text, re.S)
    return m.group("body").strip(" :") if m else ""
jobs, page = {}, 1
while page <= 30:
    req = urllib.request.Request(API.format(page), headers={"User-Agent": "Mozilla/5.0"})
    rows = [r["data"] for r in json.load(urllib.request.urlopen(req, timeout=30))["jobs"]]
    old = 0
    for j in rows:
        ts = parse(j["posted_date"])
        if ts < cutoff: old += 1; continue
        jid = str(j["req_id"])
        if jid in jobs: continue
        text = clean(j.get("responsibilities") or j.get("description"))
        hits = sorted({m.group(0).lower() for m in SKILLS.finditer(j["title"] + " " + text)})
        jobs[jid] = {"id": jid, "org": j.get("hiring_organization", ""), "title": j["title"],
            "published": ts.isoformat(), "locations": [j.get("full_location") or j.get("city", "")],
            "url": f"https://careers.emory.edu/jobs/{jid}", "apply_url": j.get("apply_url", ""),
            "category": j.get("category", ""), "employment_type": j.get("employment_type", ""),
            "min_quals": section(text, r"MINIMUM QUALIFICATIONS", [r"PREFERRED QUALIFICATIONS", r"Emory is an equal"]),
            "all_quals": section(text, r"(?:PREFERRED |REQUIRED )?QUALIFICATIONS", [r"Emory is an equal"]),
            "responsibilities": text, "skill_hits": hits, "auto_skip": not hits}
    if not rows or old == len(rows) or len(rows) < 100: break
    page += 1; time.sleep(0.5)
json.dump(list(jobs.values()), open(sys.argv[1], "w"), indent=1)
n = len(jobs); s = sum(j["auto_skip"] for j in jobs.values())
print(f"{n} postings, {n - s} with skill overlap, {s} auto-skip")
