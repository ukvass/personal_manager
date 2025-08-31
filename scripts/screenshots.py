#!/usr/bin/env python3
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
OUT_DIR = Path(os.getenv("OUT_DIR", "app/static/screenshots"))


def ensure_out_dir() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def snap(name: str, page) -> None:
    page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=True)


def run():
    ensure_out_dir()
    unique = int(time.time())
    email = f"snap_{unique}@example.com"
    password = "secret"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()

        # 1) Login page snapshot
        page.goto(f"{BASE_URL}/login", wait_until="networkidle")
        snap("login", page)

        # 2) Register a fresh user (safe even if demo already exists)
        page.goto(f"{BASE_URL}/register", wait_until="networkidle")
        page.fill('input[name="email"]', email)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_url(f"{BASE_URL}/")

        # 3) Create a couple of tasks
        for title, prio in [("Buy milk", "2"), ("Finish report", "3")]:
            page.fill('input[name="title"]', title)
            page.fill('input[name="priority"]', prio)
            page.click('button:has-text("Add")')
            page.wait_for_timeout(200)  # allow server to process

        # 4) Tasks page snapshot
        snap("tasks", page)

        # 5) Inline edit: focus first title input and modify slightly
        try:
            page.click('input[id^="title-input-"]')
            page.type('input[id^="title-input-"]', "!")
        except Exception:
            pass
        snap("inline-edit", page)

        browser.close()


if __name__ == "__main__":
    run()

