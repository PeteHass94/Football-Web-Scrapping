import json
import asyncio
from playwright.async_api import async_playwright

TOURNAMENTS = [
    {"name": "Premier League", "id": 1, "unique_tournament": 17},
    {"name": "La Liga", "id": 36, "unique_tournament": 8},
    {"name": "Bundesliga", "id": 42, "unique_tournament": 35},
    {"name": "Serie A", "id": 33, "unique_tournament": 23},
    {"name": "Ligue 1", "id": 34, "unique_tournament": 34},
]