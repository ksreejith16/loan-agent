"""Open job pages in a logged-in browser, one at a time. The user applies and
submits manually for each, then presses Enter in the terminal to load the next.

Usage:
    python -m src.apply --url <linkedin-job-url>
    python -m src.apply --path "data/jobs/scada/<slug>.md"
    python -m src.apply --top 5
    python -m src.apply --top all
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
SETTINGS = CONFIG["settings"]


def url_from_md(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("url:"):
            return line.split(":", 1)[1].strip()
    return ""


def open_jobs(jobs: list[tuple[str, str]]) -> None:
    user_data = ROOT / SETTINGS["user_data_dir"]
    user_data.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            headless=False,
            viewport={"width": 1400, "height": 900},
            accept_downloads=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        total = len(jobs)
        for i, (label, url) in enumerate(jobs, 1):
            print(f"\n[{i}/{total}] {label}")
            print(f"  {url}")
            try:
                page.goto(url, wait_until="domcontentloaded")
            except Exception as e:
                print(f"  load error: {e}")
            ans = input("  apply in the browser, then Enter for next (q to quit): ").strip().lower()
            if ans == "q":
                break
        ctx.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="single job URL")
    ap.add_argument("--path", help="path to a scraped .md job file")
    ap.add_argument("--top", help="N or 'all' — open from ranked.csv in score order")
    args = ap.parse_args()

    if args.url:
        open_jobs([(args.url, args.url)])
        return
    if args.path:
        url = url_from_md(Path(args.path))
        if not url:
            ap.error(f"no URL found in {args.path}")
        open_jobs([(args.path, url)])
        return
    if args.top:
        ranked = ROOT / SETTINGS["ranked_csv"]
        with ranked.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if args.top != "all":
            try:
                rows = rows[: int(args.top)]
            except ValueError:
                ap.error("--top must be an integer or 'all'")
        jobs = [(f"[{r['score']}%] {r['company']} - {r['title']}", r["url"]) for r in rows]
        open_jobs(jobs)
        return
    ap.error("provide --url, --path, or --top")


if __name__ == "__main__":
    main()
