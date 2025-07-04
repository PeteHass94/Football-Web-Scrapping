# utils/data_fetcher.py
import json
import asyncio
from playwright.async_api import async_playwright

import streamlit as st

# Async Playwright JSON fetcher
async def fetch_json_data(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)
        pre_tag = await page.query_selector("pre")
        json_text = await pre_tag.text_content() if pre_tag else "{}"
        await browser.close()
        return json.loads(json_text)

# Sync wrapper
def fetch_json(url):
    return asyncio.run(fetch_json_data(url))

def fetch_season_json(tournament):
    seasons_url = f"https://api.sofascore.com/api/v1/unique-tournament/{tournament['unique_tournament']}/seasons"
    # https://api.sofascore.com/api/v1/unique-tournament/17/seasons
    return fetch_json(seasons_url)

def fetch_standing_json(tournament, season):
    standings_url = (
            f"https://www.sofascore.com/api/v1/unique-tournament/"
            f"{tournament['unique_tournament']}/season/{season['id']}/standings/total"
        )
    
    return fetch_json(standings_url)

def fetch_rounds_json(tournament, season):
    rounds_url = (
        f"https://www.sofascore.com/api/v1/unique-tournament/"
        f"{tournament['unique_tournament']}/season/{season['id']}/rounds"
    )
    # https://www.sofascore.com/api/v1/unique-tournament/17/season/61627/rounds"
    return fetch_json(rounds_url)

def fetch_round_events(tournament, season, round_number):
    round_events_url = (
        f"https://www.sofascore.com/api/v1/unique-tournament/"
        f"{tournament['unique_tournament']}/season/{season['id']}/events/round/{round_number}"
    )
    # https://www.sofascore.com/api/v1/unique-tournament/17/season/62483/events/round/1
    round_response = fetch_json(round_events_url)
    round_events = round_response.get("events", [])
    return round_events