# job-agent

Semi-automated job search + application helper for two roles (SCADA, Controls).
You stay in the loop on every submit — the script handles discovery, ranking,
and form pre-fill.

## One-time setup

Open PowerShell or cmd:

```
cd "C:\Users\SRKONAB\OneDrive - Chubb\Desktop\job-agent"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## Workflow

### 1. Scrape jobs from LinkedIn

```
python -m src.scrape_linkedin
```

First run: a Chromium window opens. Sign in to LinkedIn manually, then press
Enter in the terminal. Login persists in `data/state/chrome_profile`, so future
runs skip this.

Output: per-job markdown files in `data/jobs/<role>/` and an index at
`data/jobs/_index.json`.

### 2. Rank jobs by keyword match

```
python -m src.score
```

Output: `data/ranked.csv` — open in Excel, sort by `score` descending.

### 3. Tailor resume + cover letter (do this in Claude Code)

Paste this into Claude Code (this chat), replacing the path:

> Tailor my resume and write a cover letter for the JD at
> `data/jobs/scada/<slug>.md`. Use the SCADA resume as the base. Save tailored
> versions to `applications/<slug>/`.

Claude reads the JD, picks the right resume, writes tailored versions.

### 4. Apply (semi-auto)

```
:: Single URL
python -m src.apply --url "https://www.linkedin.com/jobs/view/..." --role scada

:: From a scraped job file (role inferred from path)
python -m src.apply --path "data\jobs\scada\some-company--scada-engineer.md"

:: Walk top 5 from ranked.csv, one at a time
python -m src.apply --top 5
```

The browser opens, the script clicks Easy Apply if available, fills fields
matching `profile.json`, attaches the right resume, and walks Next/Continue
until it hits the Submit step. **You inspect and click Submit.**

For external ATS (Workday, Greenhouse, iCIMS, Taleo, etc.) the script
pre-fills what it can and pauses. Field labels vary, so review every field
before submitting.

## Files

- `config.yaml` — roles, search URLs, keywords, resume paths
- `profile.json` — personal info used for form pre-fill (edit me to adjust)
- `data/jobs/<role>/<slug>.md` — scraped job descriptions
- `data/ranked.csv` — keyword-scored ranking
- `applications/<slug>/` — tailored resumes + cover letters (Claude writes here)

## Adjusting

- **Add a new role:** add it under `roles:` in `config.yaml` with its own
  resume path, search URLs, and keyword list.
- **Add more LinkedIn searches for a role:** add URLs under that role's
  `search_urls:` list.
- **Change personal data:** edit `profile.json`. Used by `apply.py` form fill.
- **Scrape more/fewer jobs per search:** `settings.max_jobs_per_search`.

## Reality check

- LinkedIn ToS prohibits fully automated applications. This script keeps you
  in the submit loop on purpose.
- LinkedIn detects aggressive scraping. Keep `max_jobs_per_search` modest
  (default 30) and don't run the scraper hourly.
- LinkedIn DOM selectors change. If scraping breaks, the selector lists in
  `src/scrape_linkedin.py` (`extract_card`, `extract_jd`) are where to look.
- Each ATS has different field names. Pre-fill covers ~70% of fields; the
  rest are manual before submit.
