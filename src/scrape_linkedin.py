"""Scrape LinkedIn job search results into per-job markdown files.

Usage:
    python -m src.scrape_linkedin               # all roles in config.yaml
    python -m src.scrape_linkedin --role scada  # one role

First run: a Chromium window opens. Sign in to LinkedIn manually, then press
Enter in the terminal. Cookies persist in data/state/chrome_profile.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import yaml
from playwright.sync_api import Page, TimeoutError, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
SETTINGS = CONFIG["settings"]


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[-\s]+", "-", s)[:80] or "untitled"


def scroll_job_list(page: Page, max_jobs: int) -> None:
    seen, stable = 0, 0
    while seen < max_jobs and stable < 3:
        cards = page.locator("li.scaffold-layout__list-item, div.job-card-container")
        count = cards.count()
        if count == seen:
            stable += 1
        else:
            stable, seen = 0, count
        if count == 0:
            page.wait_for_timeout(SETTINGS["scroll_pauses_ms"])
            continue
        try:
            cards.nth(min(count - 1, max_jobs - 1)).scroll_into_view_if_needed()
        except Exception:
            pass
        page.wait_for_timeout(SETTINGS["scroll_pauses_ms"])


def extract_card(card) -> dict:
    def text_or(sel: str) -> str:
        try:
            return card.locator(sel).first.inner_text(timeout=1500).strip()
        except Exception:
            return ""

    title = text_or("a.job-card-list__title, a.job-card-container__link strong, .job-card-list__title--link")
    company = text_or(
        "span.job-card-container__primary-description, .artdeco-entity-lockup__subtitle, .job-card-container__company-name"
    )
    location = text_or(
        "li.job-card-container__metadata-item, .artdeco-entity-lockup__caption, .job-card-container__metadata-item"
    )
    href = ""
    try:
        href = card.locator("a.job-card-container__link, a.job-card-list__title").first.get_attribute("href") or ""
    except Exception:
        pass
    if href.startswith("/"):
        href = "https://www.linkedin.com" + href
    return {"title": title, "company": company, "location": location, "url": href.split("?")[0]}


def extract_jd(page: Page) -> tuple[str, bool]:
    jd = ""
    for sel in [
        "div.jobs-description__container",
        "div.jobs-description-content__text",
        "article.jobs-description__container",
    ]:
        try:
            jd = page.locator(sel).first.inner_text(timeout=4000).strip()
            if jd:
                break
        except Exception:
            continue
    easy_apply = False
    try:
        label = page.locator("button.jobs-apply-button").first.inner_text(timeout=2000).strip().lower()
        easy_apply = "easy apply" in label
    except Exception:
        pass
    return jd, easy_apply


def format_md(meta: dict) -> str:
    head = "\n".join(
        f"{k}: {meta.get(k, '')}"
        for k in ["title", "company", "location", "url", "easy_apply", "role_key", "scraped_at"]
    )
    return f"---\n{head}\n---\n\n{meta['jd']}\n"


def scrape_role(page: Page, role_key: str, role_cfg: dict) -> list[dict]:
    role_dir = ROOT / SETTINGS["output_dir"] / role_key
    role_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for url in role_cfg["search_urls"]:
        print(f"[{role_key}] opening {url}")
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        scroll_job_list(page, SETTINGS["max_jobs_per_search"])
        cards = page.locator("li.scaffold-layout__list-item, div.job-card-container")
        n = min(cards.count(), SETTINGS["max_jobs_per_search"])
        print(f"[{role_key}] found {n} cards")
        for i in range(n):
            card = cards.nth(i)
            try:
                card.scroll_into_view_if_needed()
                meta = extract_card(card)
                if not meta["title"]:
                    continue
                card.click()
                page.wait_for_timeout(1200)
                jd, easy_apply = extract_jd(page)
                if not jd:
                    continue
                meta.update(
                    easy_apply=easy_apply,
                    jd=jd,
                    role_key=role_key,
                    scraped_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                )
                slug = f"{slugify(meta['company'])}--{slugify(meta['title'])}"
                fpath = role_dir / f"{slug}.md"
                fpath.write_text(format_md(meta), encoding="utf-8")
                results.append({**{k: meta[k] for k in meta if k != "jd"}, "path": str(fpath.relative_to(ROOT))})
                print(f"  saved {slug}")
            except Exception as e:
                print(f"  skip card {i}: {e}")
    return results


def run(role_filter: str | None) -> None:
    user_data = ROOT / SETTINGS["user_data_dir"]
    user_data.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            headless=SETTINGS["headless"],
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        if "login" in page.url or "authwall" in page.url or "checkpoint" in page.url:
            input("\nSign in to LinkedIn in the browser window, then press Enter here...\n")

        all_results: list[dict] = []
        for key, cfg in CONFIG["roles"].items():
            if role_filter and key != role_filter:
                continue
            all_results.extend(scrape_role(page, key, cfg))
        ctx.close()

    summary = ROOT / SETTINGS["output_dir"] / "_index.json"
    summary.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nDone. {len(all_results)} jobs saved. Index: {summary}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", help="role key from config.yaml (omit for all)")
    args = ap.parse_args()
    run(args.role)
