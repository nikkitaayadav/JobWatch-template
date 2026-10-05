# JobWatch

A job-posting monitor run by Claude. Three times a day it checks careers sites (Google, Microsoft, Amazon, Apple, Salesforce, Adobe, Cisco, Emory), reads every new posting, scores it 0–10 against **your skills** (not job titles), and emails you the ones worth applying to, usually within hours of them going live. Matches go into a Google Sheet where you track status from your phone.

It never applies, fills forms or contacts anyone. It only finds and scores.

**You need:** a GitHub account, a Claude account with Claude Code (Pro or Max plan), and a Gmail account.

---

## Setup (about 30–45 minutes, once)

### 1. Make your own private copy
1. On this repo's GitHub page, click **Use this template → Create a new repository**.
2. Name it (e.g. `JobWatch`) and choose **Private**. Your copy will hold your résumé and a sheet password, so it must be private. (Don't use Fork: forks of a public repo can't be private.)
3. Open your new repo in Claude Code (desktop app → Code tab → open the folder after cloning, or `git clone` it yourself).

### 2. Add your profile
In Claude Code, attach your résumé and say:

> Build my `profile/` files from my résumé, following `profile/README.md`. Ask me about anything unclear, and mark tools I only know a little as not held.

Review what it writes. Scoring is only as good as this profile.

### 3. Fill in the settings
Say to Claude:

> Fill in the "About me" section of `CLAUDE.md` (ask me for anything you need), delete the companies I don't want from the Companies table, then rewrite `config/filters.json` to match my profile: search keywords, career levels and skill terms for the kind of roles I'm targeting.

`config/filters.json` matters: the fetchers use it to throw out obviously unrelated postings before Claude reads them. Its starting values are for a **data/analytics** job seeker. If you're in another field and don't change it, you'll get almost no matches.

Google career levels you can use in `google_levels`: `INTERN_AND_APPRENTICE`, `EARLY`, `MID`, `ADVANCED`, `DIRECTOR_PLUS`.

### 4. Create the tracker sheet
1. Create a new Google Sheet (e.g. "JobWatch Tracker").
2. **Extensions → Apps Script**. Delete what's there, paste in all of `tools/sheet_apps_script.gs`.
3. Change `TOKEN` near the top to a long random string (e.g. mash the keyboard for 30 characters). Save.
4. Choose the `setup` function in the toolbar and click **Run**. Approve the permissions (it's your own script; click Advanced → Go to project if Google warns).
5. **Deploy → New deployment → type: Web app**. Execute as **Me**, Who has access **Anyone**. Deploy and copy the web app URL.
6. Put the URL and your token in `config/sheet.json`, and the sheet's own link in the Tracker section of `CLAUDE.md`.

### 5. Test one run by hand
Commit and push your changes, then say to Claude:

> Do a JobWatch run now, following CLAUDE.md.

The first run looks back 3 days and takes a while. Check that you got the emails and that rows appeared in the sheet. If something breaks, tell Claude what happened; it can fix the scripts.

### 6. Connect Gmail and schedule it
1. At claude.ai → Settings → Connectors, connect **Gmail** (it sends the alert emails to you).
2. In Claude Code, say:

> Set up a scheduled cloud routine called "JobWatch (3x daily)" on this repo that follows CLAUDE.md's run procedure at 8am, 2pm and 8pm Central, with the Gmail connector enabled.

Times are in Central (Houston). If you're elsewhere, ask Claude to change the times in `CLAUDE.md` and the routine.

### 7. (Optional) Gmail label
In Gmail, create a filter: Subject contains `[JobWatch]` → apply label "JobWatch".

---

## Day to day
- Emails arrive at 8am / 2pm when there's a strong match, and a summary every evening at 8pm.
- Labels: 🟢 APPLY NOW · 🟡 APPLY + PREP (with what to brush up on) · 🟠 NEAR MISS (your call).
- In the sheet, change **Status** (New → Applied, etc.) and add **Notes**. Don't edit other columns.
- If the evening email ever doesn't come, open the repo in Claude and ask it to check the routine.

## Good to know
- The fetchers read careers sites directly. Sites change their pages, so a fetcher may break now and then; the evening email reports it, and Claude can fix it.
- Some sites' terms of use don't allow automated access. This is for personal, low-volume use only.
- Scheduled runs use your Claude plan's usage. Remove companies you don't care about to keep runs short.
- Sponsorship: if you need a visa, set it in About me and Claude drops postings that refuse sponsorship and marks Emory as cap-exempt. If you don't, those rules are ignored.
