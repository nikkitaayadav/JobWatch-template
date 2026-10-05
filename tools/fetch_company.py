"""Fetch new US postings for one company: python3 tools/fetch_company.py <company> <out.json> <since YYYY-MM-DD> [seen file]

Companies: amazon, microsoft, apple, salesforce, adobe, cisco.
Every posting comes back as one record with the same keys (id, title, published, locations, url,
min_quals, all_quals, responsibilities, skill_hits, auto_skip, auto_skip_reason). IDs already in the
seen file are left out, so detail pages are only requested for postings not processed before.
"""
import re, json, sys, time, html, urllib.request, urllib.error
from filters import F, skills
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
# Core skill terms (config/filters.json). "AI", "ML", "automation" and "analytics" alone appear in most big-tech boilerplate,
# so a posting passes the screen only with a core term in its title or 2+ distinct core terms in its text.
SKILLS = skills()  # config/filters.json skill_terms
GATE = re.compile(r"(\(U\.?S\.? Citizen\)|\b(TS/SCI|security clearance|clearance (is )?required|active (secret|top secret)|polygraph|U\.?S\.? citizen(ship)? (is )?required|must be a U\.?S\.? citizen)\b)", re.I)
INTERN = re.compile(r"\b(intern|internship|co-op)\b", re.I)

def req(url, data=None, tries=4):
    for i in range(tries):
        try:
            h = {"User-Agent": UA, "Accept": "application/json, text/html"}
            if data is not None: h["Content-Type"] = "application/json"
            r = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=h)
            return urllib.request.urlopen(r, timeout=40).read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < tries - 1: time.sleep(5 * (i + 1)); continue
            raise
def getj(url, data=None): return json.loads(req(url, data))

def clean(t):
    t = re.sub(r"<li[^>]*>", "\n- ", t or ""); t = re.sub(r"<(p|br|h\d)[^>]*>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t\xa0]+", " ", t)).strip()

def record(id, title, published, locations, url, min_q, pref_q, resp):
    min_q, pref_q, resp = clean(min_q), clean(pref_q), clean(resp)
    hits = sorted({m.group(0).lower() for m in SKILLS.finditer(" ".join([title, min_q, pref_q, resp]))})
    years = [int(y) for y in re.findall(r"(\d{1,2})\+? years", min_q)]
    reason = ""
    max_years = F.get("skip_if_min_years_at_least")
    if F.get("skip_internships") and INTERN.search(title): reason = "auto-screen: internship"
    elif F.get("skip_clearance_or_citizenship") and GATE.search(title + " " + min_q + " " + resp): reason = "auto-screen: requires security clearance or US citizenship (hard drop)"
    elif not SKILLS.search(title) and len(hits) < 2: reason = "auto-screen: no core skills from filters.json in role text"
    elif max_years and years and min(years) >= max_years: reason = f"auto-screen: minimum qualifications require {min(years)}+ years (hard gap)"
    return {"id": str(id), "title": title.strip(), "published": published, "locations": locations, "url": url,
            "min_quals": min_q, "all_quals": (min_q + "\n" + pref_q).strip(), "responsibilities": resp,
            "skill_hits": hits, "auto_skip": bool(reason), "auto_skip_reason": reason}

# ---------- Amazon (amazon.jobs search.json, newest first, quals included in the list) ----------
def amazon(cutoff, seen):
    out, off = [], 0
    while off < 3000:
        d = getj(f"https://www.amazon.jobs/en/search.json?base_query=&country=USA&sort=recent&result_limit=100&offset={off}")
        jobs = d.get("jobs", [])
        if not jobs: break
        old = 0
        for j in jobs:
            ts = datetime.strptime(re.sub(r"\s+", " ", j["posted_date"]), "%B %d, %Y").replace(tzinfo=timezone.utc)
            if ts < cutoff: old += 1; continue
            if j["id_icims"] in seen: continue
            out.append(record(j["id_icims"], j["title"], ts.date().isoformat(), [j.get("normalized_location") or j.get("location", "")],
                "https://www.amazon.jobs" + j["job_path"], j.get("basic_qualifications"), j.get("preferred_qualifications"), j.get("description")))
        if old == len(jobs): break
        off += 100; time.sleep(0.5)
    return out

# ---------- Microsoft (apply.careers.microsoft.com, Eightfold; 10 per page, details per job) ----------
def microsoft(cutoff, seen):
    out, start = [], 0
    while start < 1500:
        d = getj(f"https://apply.careers.microsoft.com/api/pcsx/search?domain=microsoft.com&query=&location=United%20States&start={start}&sort_by=timestamp")["data"]
        ps = d.get("positions", [])
        if not ps: break
        old = 0
        for p in ps:
            ts = datetime.fromtimestamp(p["postedTs"], timezone.utc)
            if ts < cutoff: old += 1; continue
            jid = str(p.get("displayJobId") or p["id"])
            if jid in seen: continue
            time.sleep(1)
            x = getj(f"https://apply.careers.microsoft.com/api/pcsx/position_details?position_id={p['id']}&domain=microsoft.com&hl=en")["data"]
            text = x.get("jobDescription", "")
            q = re.split(r"(?i)<b>\s*Qualifications\s*</b>", text, maxsplit=1)
            quals = q[1] if len(q) > 1 else ""
            mq = re.split(r"(?i)Preferred Qualifications", quals, maxsplit=1)
            out.append(record(jid, p["name"], ts.date().isoformat(), p.get("standardizedLocations") or p.get("locations", []),
                x.get("publicUrl") or "https://apply.careers.microsoft.com" + p.get("positionUrl", ""),
                mq[0], mq[1] if len(mq) > 1 else "", q[0]))
        if old == len(ps): break
        start += 10; time.sleep(1.5)
    return out

# ---------- Apple (jobs.apple.com, data embedded in the page) ----------
def apple_page(url):
    m = re.search(r'__staticRouterHydrationData = JSON\.parse\((".*?")\);', req(url), re.S)
    return json.loads(json.loads(m.group(1)))["loaderData"]
def apple(cutoff, seen):
    out = []
    for page in range(1, 40):
        ld = apple_page(f"https://jobs.apple.com/en-us/search?sort=newest&location=united-states-USA&page={page}")
        rs = ld["search"]["searchResults"]
        if not rs: break
        old = 0
        for r in rs:
            ts = datetime.fromisoformat(r["postDateInGMT"][:19]).replace(tzinfo=timezone.utc)
            if ts < cutoff: old += 1; continue
            jid = r["positionId"]
            if jid in seen or r.get("managedPipelineRole") in (True, "True"): continue  # pipeline = evergreen retail roles
            url = f"https://jobs.apple.com/en-us/details/{jid}/{r['transformedPostingTitle']}"
            time.sleep(0.7)
            jd = apple_page(url)["jobDetails"]["jobsData"]
            out.append(record(jid, r["postingTitle"], ts.date().isoformat(),
                [", ".join(x for x in (l.get("city"), l.get("stateProvince")) if x) or l.get("countryName", "") for l in r.get("locations", [])],
                url, jd.get("minimumQualifications"), jd.get("preferredQualifications"), (jd.get("description") or "") + "\n" + (jd.get("responsibilities") or "")))
        if old == len(rs): break
        time.sleep(0.7)
    return out

# ---------- Workday tenants (Salesforce, Adobe, Cisco); list is newest first ----------
WORKDAY = {"salesforce": ("salesforce.wd12", "salesforce", "External_Career_Site"),
           "adobe": ("adobe.wd5", "adobe", "external_experienced"),
           "cisco": ("cisco.wd5", "cisco", "Cisco_Careers")}
def days_ago(s):
    s = s.lower()
    if "today" in s: return 0
    if "yesterday" in s: return 1
    m = re.search(r"(\d+)\+? days", s)
    return int(m.group(1)) if m else 99
def workday(company, cutoff, seen):
    host, tenant, site = WORKDAY[company]
    base = f"https://{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
    max_age = (datetime.now(timezone.utc) - cutoff).days + 1
    out, off = [], 0
    while off < 2000:
        d = getj(base + "/jobs", {"limit": 20, "offset": off, "searchText": "", "appliedFacets": {}})
        js = d.get("jobPostings", [])
        if not js: break
        old = 0
        for j in js:
            if days_ago(j.get("postedOn", "")) > max_age: old += 1; continue
            jid = (j.get("bulletFields") or [j["externalPath"].rsplit("_", 1)[-1]])[0]
            if jid in seen: continue
            time.sleep(0.4)
            x = getj(base + j["externalPath"])["jobPostingInfo"]
            locs = [x.get("location", "")] + (x.get("additionalLocations") or [])
            country = (x.get("country") or {}).get("descriptor", "")
            if "United States" not in country and not any(re.search(r"\b(US|USA|United States)\b|, [A-Z]{2}\b", l or "") for l in locs): continue
            text = x.get("jobDescription", "")
            out.append(record(jid, x["title"], x.get("startDate") or "", locs,
                x.get("externalUrl") or f"https://{host}.myworkdayjobs.com/{site}{j['externalPath']}", "", "", text))
        if old == len(js): break
        off += 20; time.sleep(0.5)
    return out

if __name__ == "__main__":
    company, path, since = sys.argv[1].lower(), sys.argv[2], sys.argv[3]
    seen = set()
    if len(sys.argv) > 4:
        try: seen = {l.split("|")[0].strip() for l in open(sys.argv[4]) if "|" in l and l.split("|")[0].strip().isalnum()}
        except FileNotFoundError: pass
    cutoff = datetime.fromisoformat(since).replace(tzinfo=timezone.utc)
    fn = {"amazon": amazon, "microsoft": microsoft, "apple": apple}.get(company)
    jobs = fn(cutoff, seen) if fn else workday(company, cutoff, seen)
    uniq = list({j["id"]: j for j in jobs}.values())
    json.dump(uniq, open(path, "w"), indent=1)
    s = sum(j["auto_skip"] for j in uniq)
    print(f"{company}: {len(uniq)} new postings, {len(uniq) - s} with skill overlap, {s} auto-skip")
