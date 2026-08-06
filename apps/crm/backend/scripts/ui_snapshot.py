"""UI snapshot: open the running local server in Chromium and screenshot
key screens for visual review.

Prereqs: server running at http://127.0.0.1:8000, demo user seeded.
Run: .venv/Scripts/python.exe scripts/ui_snapshot.py

Outputs: screenshots/<name>.png (overwrites each run).
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "screenshots"
OUT_DIR.mkdir(exist_ok=True)

BASE = "http://127.0.0.1:8000"
EMAIL = "demo@visiquost.app"
PASSWORD = "demo1234"

# (name, click-selector-or-nav-key, wait-selector)
SCREENS = [
    ("contacts", "contacts", ".table"),
    ("companies", "companies", ".table"),
    ("opportunities", "opportunities", ".table"),
    ("leads", "leads", "body"),
    ("tasks", "tasks", "body"),
    ("meetings", "meetings", "body"),
    ("kanban", "kanban", "body"),
]


def snap():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  device_scale_factor=1)
        # Disable all HTTP caching so we always see the freshest code.
        ctx.route("**/*", lambda route: route.continue_(headers={**route.request.headers, "cache-control": "no-cache"}))
        page = ctx.new_page()
        page.on("console", lambda m: print(f"[console.{m.type}]", m.text) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: print(f"[pageerror] {e}"))
        # 1) Auth screen
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(OUT_DIR / "01_auth.png"), full_page=False)
        print(f"saved 01_auth.png")

        # 2) Log in
        page.fill('input[type="email"]', EMAIL)
        page.fill('input[type="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_selector('.app-view', timeout=10000)
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(OUT_DIR / "02_dashboard.png"), full_page=False)
        print("saved 02_dashboard.png")

        # 3) Cycle through nav items via data-page attribute
        for i, (name, nav_key, wait_sel) in enumerate(SCREENS, start=3):
            selector = f'[data-page="{nav_key}"]'
            btn = page.query_selector(selector)
            if not btn:
                print(f"skip {name}: no nav button")
                continue
            btn.click()
            try:
                page.wait_for_selector(wait_sel, timeout=4000)
            except Exception:
                pass
            page.wait_for_timeout(500)
            fname = f"{i:02d}_{name}.png"
            page.screenshot(path=str(OUT_DIR / fname), full_page=False)
            print(f"saved {fname}")

        browser.close()
    print(f"\nDone. Screenshots in: {OUT_DIR}")


if __name__ == "__main__":
    try:
        snap()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
