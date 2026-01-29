import json
import streamlit as st
import pandas as pd
from supabase import create_client
from utils.page_components import add_common_page_elements
from utils.extractors.data_fetcher import fetch_incidents

# ------------------ Supabase ------------------
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# ------------------ Cached lookups ------------------
@st.cache_data(show_spinner=False)
def get_tournaments():
    res = supabase.table("tournaments").select("id, name, tournament_id, unique_tournament_id").execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_seasons(tournament_id):
    res = supabase.table("seasons").select("id, season_id, name, year").eq("tournament_id", tournament_id).execute()
    return res.data or []

@st.cache_data(show_spinner=False)
def get_fixtures(season_id):
    res = (
        supabase.table("fixtures")
        .select("fixture_id, home_team_id, away_team_id, season_id, round, kickoff_date_time")
        .eq("season_id", season_id)
        .execute()
    )
    return res.data or []

@st.cache_data(show_spinner=False)
def get_existing_players_ids() -> set:
    res = supabase.table("players").select("player_id").execute()
    return {r["player_id"] for r in (res.data or []) if r.get("player_id") is not None}

# ------------------ Utilities ------------------
def _safe_int(x):
    try:
        return int(x) if x is not None else None
    except Exception:
        return None

def _safe_float(x):
    try:
        return float(x) if x is not None else None
    except Exception:
        return None

def _added_time_norm(x):
    """Normalize addedTime - SofaScore uses 999 as sentinel for period markers"""
    x = _safe_int(x)
    return None if (x is None or x >= 900) else x

def _match_minute(minute, added):
    if minute is None:
        return None
    return minute + (added or 0)

def _half_from_minute(minute):
    """Determine half from minute"""
    if minute is None:
        return None
    if minute <= 45:
        return "1"
    if minute <= 90:
        return "2"
    if minute <= 105:
        return "ET1"
    if minute <= 120:
        return "ET2"
    return None

def _team_from_flag(is_home, home_team_id, away_team_id):
    if is_home is True:
        return home_team_id
    if is_home is False:
        return away_team_id
    return None

# ------------------ Existing rows (per fixture) ------------------
def get_existing_cards_for_fixture(fixture_id: int) -> set:
    res = supabase.table("cards").select(
        "player_id,team_id,card_minute,added_time,yellow,red,yellow_2"
    ).eq("fixture_id", fixture_id).execute()
    rows = res.data or []
    return {
        (
            r.get("player_id"),
            r.get("team_id"),
            r.get("card_minute"),
            r.get("added_time"),
            bool(r.get("yellow")),
            bool(r.get("yellow_2")),
            bool(r.get("red")),
        )
        for r in rows
    }

def get_existing_goals_for_fixture(fixture_id: int) -> set:
    res = supabase.table("goals").select(
        "player_id,team_id,goal_minute,added_time,type,is_own_goal"
    ).eq("fixture_id", fixture_id).execute()
    rows = res.data or []
    return {
        (
            r.get("player_id"),
            r.get("team_id"),
            r.get("goal_minute"),
            r.get("added_time"),
            r.get("type"),
            bool(r.get("is_own_goal")),
        )
        for r in rows
    }

def get_existing_substitutions_for_fixture(fixture_id: int) -> set:
    """Get existing substitutions as (player_in_id, player_out_id, minute, added_time)"""
    res = supabase.table("substitutions").select(
        "player_in_id,player_out_id,minute,added_time"
    ).eq("fixture_id", fixture_id).execute()
    rows = res.data or []
    return {
        (
            r.get("player_in_id"),
            r.get("player_out_id"),
            r.get("minute"),
            r.get("added_time"),
        )
        for r in rows
    }

def get_existing_incidents_for_fixture(fixture_id: int) -> set:
    """Get existing incidents as (incident_type, incident_id, minute, added_time)"""
    res = supabase.table("incidents").select(
        "incident_type,incident_id,minute,added_time"
    ).eq("fixture_id", fixture_id).execute()
    rows = res.data or []
    return {
        (
            r.get("incident_type"),
            r.get("incident_id"),
            r.get("minute"),
            r.get("added_time"),
        )
        for r in rows
    }

# ------------------ Parsers ------------------
def parse_incidents(incidents_json, home_team_id: int | None, away_team_id: int | None):
    """
    Parse all incident types from incidents JSON.
    Returns:
      cards_rows: list of dicts for public.cards
      goals_rows: list of dicts for public.goals
      substitutions_rows: list of dicts for public.substitutions
      incidents_rows: list of dicts for public.incidents (period, injuryTime, varDecision, inGamePenalty)
    """
    cards_rows = []
    goals_rows = []
    substitutions_rows = []
    incidents_rows = []
    
    # Handle both {"incidents": [...]} and plain list formats
    items = []
    if isinstance(incidents_json, dict):
        items = incidents_json.get("incidents") or []
    elif isinstance(incidents_json, list):
        items = incidents_json
    else:
        return cards_rows, goals_rows, substitutions_rows, incidents_rows
    
    for inc in items:
        itype = inc.get("incidentType") or inc.get("type") or "unknown"
        iclass = inc.get("incidentClass")  # e.g., "yellow", "red", "regular"
        is_home = inc.get("isHome")
        team_id = _team_from_flag(is_home, home_team_id, away_team_id)
        
        minute = _safe_int(inc.get("time"))
        added = _added_time_norm(inc.get("addedTime"))
        match_minute = _match_minute(minute, added)
        half = _half_from_minute(minute)
        incident_id = _safe_int(inc.get("id"))
        
        # --- Substitutions ---
        if itype == "substitution":
            player_in = inc.get("playerIn") or {}
            player_out = inc.get("playerOut") or {}
            player_in_id = _safe_int(player_in.get("id"))
            player_out_id = _safe_int(player_out.get("id"))
            
            if player_in_id or player_out_id:
                substitutions_rows.append({
                    "fixture_id": None,  # Will be filled later
                    "team_id": team_id,
                    "player_in_id": player_in_id,
                    "player_out_id": player_out_id,
                    "minute": minute,
                    "added_time": added,
                    "match_minute": match_minute,
                    "half": half,
                    "injury": bool(inc.get("injury", False)),
                    "incident_id": incident_id,
                })
            continue
        
        # --- Cards ---
        if itype == "card":
            player = inc.get("player") or {}
            player_id = _safe_int(player.get("id"))
            
            # Determine card type from incidentClass
            is_yellow = iclass in {"yellow", "secondYellow", "yellowRed"}
            is_red = iclass in {"red", "yellowRed", "secondYellow"}
            is_yellow_2 = iclass in {"secondYellow", "yellowRed"}
            
            cards_rows.append({
                "fixture_id": None,  # Will be filled later
                "team_id": team_id,
                "player_id": player_id,
                "card_minute": minute,
                "added_time": added,
                "match_minute": match_minute,
                "yellow": is_yellow,
                "yellow_2": is_yellow_2,
                "red": is_red,
                "reason": inc.get("reason"),
                "rescinded": bool(inc.get("rescinded", False)),
                "incident_id": incident_id,
            })
            continue
        
        # --- Goals ---
        if itype == "goal":
            player = inc.get("player") or {}
            player_id = _safe_int(player.get("id"))
            
            goal_type = iclass or "regular"  # regular, ownGoal, penalty, etc.
            is_own_goal = iclass == "ownGoal"
            
            goals_rows.append({
                "fixture_id": None,  # Will be filled later
                "team_id": team_id,
                "player_id": player_id,
                "goal_minute": minute,
                "added_time": added,
                "match_minute": match_minute,
                "half": half,
                "type": goal_type,
                "is_own_goal": is_own_goal,
                "assist_player_id": _safe_int((inc.get("assist1") or {}).get("id")),
                "incident_id": incident_id,
            })
            continue
        
        # --- Period (HT, FT, etc.) ---
        if itype == "period":
            incidents_rows.append({
                "fixture_id": None,  # Will be filled later
                "incident_type": "period",
                "incident_id": incident_id,
                "minute": minute,
                "added_time": added,
                "match_minute": match_minute,
                "half": half,
                "text": inc.get("text"),  # "HT", "FT", etc.
                "home_score": _safe_int(inc.get("homeScore")),
                "away_score": _safe_int(inc.get("awayScore")),
                "is_live": bool(inc.get("isLive", False)),
                "time_seconds": _safe_int(inc.get("timeSeconds")),
                "period_time_seconds": _safe_int(inc.get("periodTimeSeconds")),
                "incident_data": json.dumps(inc),  # Store full JSON for reference
            })
            continue
        
        # --- Injury Time ---
        if itype == "injuryTime":
            incidents_rows.append({
                "fixture_id": None,  # Will be filled later
                "incident_type": "injuryTime",
                "incident_id": incident_id,
                "minute": minute,
                "added_time": added,
                "match_minute": match_minute,
                "half": half,
                "length": _safe_int(inc.get("length")),
                "incident_data": json.dumps(inc),
            })
            continue
        
        # --- VAR Decision ---
        if itype == "varDecision":
            player = inc.get("player") or {}
            player_id = _safe_int(player.get("id"))
            
            incidents_rows.append({
                "fixture_id": None,  # Will be filled later
                "incident_type": "varDecision",
                "incident_id": incident_id,
                "team_id": team_id,
                "player_id": player_id,
                "minute": minute,
                "added_time": added,
                "match_minute": match_minute,
                "half": half,
                "confirmed": bool(inc.get("confirmed", False)),
                "incident_class": iclass,
                "incident_data": json.dumps(inc),
            })
            continue
        
        # --- In-Game Penalty ---
        if itype == "inGamePenalty":
            player = inc.get("player") or {}
            player_id = _safe_int(player.get("id"))
            
            incidents_rows.append({
                "fixture_id": None,  # Will be filled later
                "incident_type": "inGamePenalty",
                "incident_id": incident_id,
                "team_id": team_id,
                "player_id": player_id,
                "minute": minute,
                "added_time": added,
                "match_minute": match_minute,
                "half": half,
                "reason": inc.get("reason"),
                "description": inc.get("description"),
                "incident_class": iclass,
                "incident_data": json.dumps(inc),
            })
            continue
    
    return cards_rows, goals_rows, substitutions_rows, incidents_rows

# ------------------ UI Shell ------------------
add_common_page_elements()
st.title("🎯 Add Incidents (All Fixtures in Season)")

st.caption(
    "This page scans all fixtures in a selected season and adds incident data "
    "(cards, goals, substitutions, periods, injuryTime, varDecisions, inGamePenalties) to Supabase."
)

tournaments = get_tournaments()
valid_tournaments = [
    {"name": t["name"], "id": t["tournament_id"], "unique_tournament": t["unique_tournament_id"]}
    for t in tournaments
    if t.get("name") and t.get("tournament_id") is not None and t.get("unique_tournament_id") is not None
]

if not valid_tournaments:
    st.warning("No tournaments found. Add tournaments first.")
    st.stop()

selected_tournament_name = st.selectbox("Select Tournament", [t["name"] for t in valid_tournaments])
tournament = {t["name"]: t for t in valid_tournaments}[selected_tournament_name]

seasons = get_seasons(tournament["id"])
valid_seasons = [{"name": s["name"], "year": s.get("year"), "id": s["season_id"]} for s in seasons if s.get("name")]
if not valid_seasons:
    st.warning("No seasons found for this tournament.")
    st.stop()

selected_season_name = st.selectbox("Select Season", [s["name"] for s in valid_seasons])
season_id = {s["name"]: s for s in valid_seasons}[selected_season_name]["id"]

fixtures = get_fixtures(season_id)
st.info(f"Found {len(fixtures)} fixtures in this season.")

if st.button("🔎 Fetch Incidents from All Fixtures"):
    all_cards = []
    all_goals = []
    all_substitutions = []
    all_incidents = []
    
    errors = 0
    no_incidents = 0
    
    progress = st.progress(0)
    status = st.empty()
    
    for i, fixture in enumerate(fixtures):
        fixture_id = int(fixture["fixture_id"])
        home_team_id = _safe_int(fixture.get("home_team_id"))
        away_team_id = _safe_int(fixture.get("away_team_id"))
        
        status.text(f"Processing fixture {i+1}/{len(fixtures)} — {fixture_id}")
        progress.progress((i + 1) / len(fixtures))
        
        try:
            incidents_json = fetch_incidents(fixture_id)
            if not incidents_json:
                no_incidents += 1
                continue
            
            cards_rows, goals_rows, subs_rows, incidents_rows = parse_incidents(
                incidents_json, home_team_id, away_team_id
            )
            
            # Fill fixture_id
            for r in cards_rows:
                r["fixture_id"] = fixture_id
            for r in goals_rows:
                r["fixture_id"] = fixture_id
            for r in subs_rows:
                r["fixture_id"] = fixture_id
            for r in incidents_rows:
                r["fixture_id"] = fixture_id
            
            all_cards.extend(cards_rows)
            all_goals.extend(goals_rows)
            all_substitutions.extend(subs_rows)
            all_incidents.extend(incidents_rows)
            
        except Exception as e:
            errors += 1
            st.warning(f"Error processing fixture {fixture_id}: {str(e)}")
    
    progress.empty()
    status.empty()
    
    st.success(
        f"Fetch complete. Found: {len(all_cards)} cards, {len(all_goals)} goals, "
        f"{len(all_substitutions)} substitutions, {len(all_incidents)} other incidents "
        f"(errors={errors}, no_incidents={no_incidents})"
    )
    
    # Check for existing records
    st.subheader("🔍 Checking for existing records...")
    
    # Get existing records for all fixtures
    existing_cards = set()
    existing_goals = set()
    existing_subs = set()
    existing_incidents = set()
    
    fixture_ids = {int(f["fixture_id"]) for f in fixtures}
    for fid in fixture_ids:
        existing_cards.update(get_existing_cards_for_fixture(fid))
        existing_goals.update(get_existing_goals_for_fixture(fid))
        existing_subs.update(get_existing_substitutions_for_fixture(fid))
        existing_incidents.update(get_existing_incidents_for_fixture(fid))
    
    # Filter new records
    new_cards = []
    for r in all_cards:
        key = (
            r.get("player_id"),
            r.get("team_id"),
            r.get("card_minute"),
            r.get("added_time"),
            bool(r.get("yellow")),
            bool(r.get("yellow_2")),
            bool(r.get("red")),
        )
        if key not in existing_cards:
            new_cards.append(r)
    
    new_goals = []
    for r in all_goals:
        key = (
            r.get("player_id"),
            r.get("team_id"),
            r.get("goal_minute"),
            r.get("added_time"),
            r.get("type"),
            bool(r.get("is_own_goal")),
        )
        if key not in existing_goals:
            new_goals.append(r)
    
    new_subs = []
    for r in all_substitutions:
        key = (
            r.get("player_in_id"),
            r.get("player_out_id"),
            r.get("minute"),
            r.get("added_time"),
        )
        if key not in existing_subs:
            new_subs.append(r)
    
    new_incidents = []
    for r in all_incidents:
        key = (
            r.get("incident_type"),
            r.get("incident_id"),
            r.get("minute"),
            r.get("added_time"),
        )
        if key not in existing_incidents:
            new_incidents.append(r)
    
    # Display results
    st.subheader("✅ New Records to Insert")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Cards (new)", len(new_cards))
    with col2:
        st.metric("Goals (new)", len(new_goals))
    with col3:
        st.metric("Substitutions (new)", len(new_subs))
    with col4:
        st.metric("Other Incidents (new)", len(new_incidents))
    
    # Insert buttons
    if new_cards and st.button("➕ Insert Cards"):
        # Remove fields that might not exist in table
        cards_to_insert = []
        for r in new_cards:
            row = {k: v for k, v in r.items() if k in [
                "fixture_id", "team_id", "player_id", "card_minute", "added_time",
                "match_minute", "yellow", "yellow_2", "red", "reason"
            ]}
            cards_to_insert.append(row)
        
        try:
            res = supabase.table("cards").insert(cards_to_insert).execute()
            st.success(f"Inserted {len(res.data or [])} cards")
            st.rerun()
        except Exception as e:
            st.error(f"Error inserting cards: {e}")
    
    if new_goals and st.button("➕ Insert Goals"):
        goals_to_insert = []
        for r in new_goals:
            row = {k: v for k, v in r.items() if k in [
                "fixture_id", "team_id", "player_id", "goal_minute", "added_time",
                "match_minute", "half", "type", "is_own_goal"
            ]}
            goals_to_insert.append(row)
        
        try:
            res = supabase.table("goals").insert(goals_to_insert).execute()
            st.success(f"Inserted {len(res.data or [])} goals")
            st.rerun()
        except Exception as e:
            st.error(f"Error inserting goals: {e}")
    
    if new_subs and st.button("➕ Insert Substitutions"):
        try:
            res = supabase.table("substitutions").insert(new_subs).execute()
            st.success(f"Inserted {len(res.data or [])} substitutions")
            st.rerun()
        except Exception as e:
            st.error(f"Error inserting substitutions: {e}")
    
    if new_incidents and st.button("➕ Insert Other Incidents"):
        try:
            res = supabase.table("incidents").insert(new_incidents).execute()
            st.success(f"Inserted {len(res.data or [])} incidents")
            st.rerun()
        except Exception as e:
            st.error(f"Error inserting incidents: {e}")
    
    # Preview tables
    if new_cards:
        with st.expander(f"📋 Preview New Cards ({len(new_cards)})"):
            st.dataframe(pd.DataFrame(new_cards).head(20))
    
    if new_goals:
        with st.expander(f"📋 Preview New Goals ({len(new_goals)})"):
            st.dataframe(pd.DataFrame(new_goals).head(20))
    
    if new_subs:
        with st.expander(f"📋 Preview New Substitutions ({len(new_subs)})"):
            st.dataframe(pd.DataFrame(new_subs).head(20))
    
    if new_incidents:
        with st.expander(f"📋 Preview New Other Incidents ({len(new_incidents)})"):
            st.dataframe(pd.DataFrame(new_incidents).head(20))
