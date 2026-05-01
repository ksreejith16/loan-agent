"""Score scraped jobs by keyword overlap with role config; write ranked.csv."""
from __future__ import annotations

import csv
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def parse_md(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    head, _, jd = text.partition("\n---\n")
    meta: dict = {"path": str(path), "jd": jd.strip()}
    for line in head.lstrip("-\n").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def keyword_score(jd: str, keywords: list[str]) -> tuple[int, list[str]]:
    jd_lower = jd.lower()
    hits = [kw for kw in keywords if re.search(rf"\b{re.escape(kw.lower())}\b", jd_lower)]
    pct = round(100 * len(hits) / max(len(keywords), 1))
    return pct, hits


def main() -> None:
    rows: list[dict] = []
    for role_key, role_cfg in CONFIG["roles"].items():
        role_dir = ROOT / CONFIG["settings"]["output_dir"] / role_key
        if not role_dir.exists():
            continue
        for md in sorted(role_dir.glob("*.md")):
            meta = parse_md(md)
            score, hits = keyword_score(meta["jd"], role_cfg["keywords"])
            rows.append(
                {
                    "role": role_key,
                    "score": score,
                    "title": meta.get("title", ""),
                    "company": meta.get("company", ""),
                    "location": meta.get("location", ""),
                    "easy_apply": meta.get("easy_apply", ""),
                    "url": meta.get("url", ""),
                    "matched_keywords": ", ".join(hits),
                    "path": meta["path"],
                }
            )
    rows.sort(key=lambda r: r["score"], reverse=True)
    out = ROOT / CONFIG["settings"]["ranked_csv"]
    out.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        print("No scraped jobs found. Run scrape_linkedin first.")
        return
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
