import streamlit as st
import pandas as pd
from supabase import create_client
from utils.extractors.data_fetcher import fetch_lineups, fetch_statistics
from utils.page_components import add_common_page_elements

# Supabase client
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# Shared UI elements
add_common_page_elements()
st.title("📊 Add Statistics (Match + Player)")

# Fetch tournaments
@st.cache_data
def get_tournaments():
    res = supabase.table("tournaments").select("id, name, tournament_id, unique_tournament_id").execute()
    return res.data or []

@st.cache_data
def get_seasons(tournament_id):
    res = supabase.table("seasons").select("id, season_id, name, year").eq("tournament_id", tournament_id).execute()
    return res.data or []

@st.cache_data
def get_fixtures(season_id):
    res = supabase.table("fixtures").select("id, fixture_id, home_team_id, away_team_id, round, kickoff_date_time").eq("season_id", season_id).execute()
    return res.data or []

def get_existing_match_statistics():
    """Get set of (fixture_id, period, key) tuples that already exist."""
    res = supabase.table("match_statistics").select("fixture_id, period, key").execute()
    if not res.data:
        return set()
    return {(r["fixture_id"], r["period"], r["key"]) for r in res.data}

def get_existing_player_statistics():
    """Get set of (fixture_id, player_id) tuples that already exist."""
    res = supabase.table("player_statistics").select("fixture_id, player_id").execute()
    if not res.data:
        return set()
    return {(r["fixture_id"], r["player_id"]) for r in res.data}

def insert_match_statistics(rows):
    """Insert match statistics rows (skip duplicates via upsert on unique constraint)."""
    if not rows:
        return None
    # match_statistics_uniq: (fixture_id, period, key)
    return (
        supabase.table("match_statistics")
        .upsert(rows, on_conflict="fixture_id,period,key", ignore_duplicates=True)
        .execute()
    )

def insert_player_statistics(rows):
    """Insert player statistics rows (skip duplicates via upsert on unique constraint)."""
    if not rows:
        return None
    # player_statistics_uniq: (fixture_id, player_id)
    return (
        supabase.table("player_statistics")
        .upsert(rows, on_conflict="fixture_id,player_id", ignore_duplicates=True)
        .execute()
    )

def _safe_float(x):
    try:
        return float(x) if x is not None else None
    except Exception:
        return None

def _safe_int(x):
    try:
        return int(x) if x is not None else None
    except Exception:
        return None

def extract_match_statistics_rows(stats_json: dict, fixture_id: int) -> list[dict]:
    """Extract match statistics rows from SofaScore statistics JSON."""
    rows: list[dict] = []
    stats = (stats_json or {}).get("statistics") or []
    for block in stats:
        period = block.get("period")
        if not period:
            continue
        for g in (block.get("groups") or []):
            group_name = g.get("groupName")
            for it in (g.get("statisticsItems") or []):
                rows.append(
                    {
                        "fixture_id": fixture_id,
                        "period": period,
                        "group_name": group_name,
                        "key": it.get("key"),
                        "name": it.get("name"),
                        "value_type": it.get("valueType"),
                        "home_value": _safe_float(it.get("homeValue")),
                        "away_value": _safe_float(it.get("awayValue")),
                        "home_raw": it.get("home"),
                        "away_raw": it.get("away"),
                    }
                )
    return rows

def extract_player_statistics_rows(lineups_json: dict, fixture_id: int, home_team_id: int | None, away_team_id: int | None) -> list[dict]:
    """Extract player statistics rows from lineups JSON."""
    out: list[dict] = []
    for side_key, team_id in (("home", home_team_id), ("away", away_team_id)):
        side = (lineups_json or {}).get(side_key) or {}
        for entry in (side.get("players") or []):
            p = (entry or {}).get("player") or {}
            pid = p.get("id")
            if not pid:
                continue
            stats = (entry or {}).get("statistics") or {}
            out.append(
                {
                    "fixture_id": fixture_id,
                    "player_id": _safe_int(pid),
                    "team_id": _safe_int(team_id),
                    "side": side_key,
                    "started": not bool(entry.get("substitute")),
                    "substitute": bool(entry.get("substitute")),
                    "position": (entry or {}).get("position"),
                    "jersey_number": (entry or {}).get("jerseyNumber"),
                    "stats_json": stats,
                }
            )
    return out

# --- UI Flow ---

# Tournament selection
tournaments = get_tournaments()
valid_tournaments = [
    {
        "name": t["name"],
        "id": t["tournament_id"],
        "unique_tournament": t["unique_tournament_id"],
    }
    for t in tournaments
    if t.get("name") and t.get("tournament_id") is not None and t.get("unique_tournament_id") is not None
]

if not valid_tournaments:
    st.warning("No tournaments found. Please add tournaments first.")
    st.stop()

tournament_names = [t["name"] for t in valid_tournaments]
tournament_map = {t["name"]: t for t in valid_tournaments}

selected_tournament_name = st.selectbox("Select Tournament", tournament_names)
tournament = tournament_map[selected_tournament_name]

# Get seasons from Supabase for the selected tournament
seasons = get_seasons(tournament["id"])
valid_seasons = [
    {
        "name": s["name"],
        "year": s["year"],
        "id": s["season_id"]
    }
    for s in seasons
    if s.get("name") and s.get("season_id") is not None
]

if not valid_seasons:
    st.warning("No seasons found for the selected tournament.")
    st.stop()

season_names = [s["name"] for s in valid_seasons]
season_map = {s["name"]: s for s in valid_seasons}

selected_season_name = st.selectbox("Select Season", season_names)
season_id = season_map[selected_season_name]["id"]

# Display fixtures count
fixtures = get_fixtures(season_id)
if fixtures:
    st.info(f"Found {len(fixtures)} fixtures for {selected_season_name}")
    
    if st.button("📥 Fetch Statistics from All Fixtures"):
        existing_match_keys = get_existing_match_statistics()
        existing_player_keys = get_existing_player_statistics()
        
        all_match_rows = []
        all_player_rows = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Track issues
        no_stats_count = 0
        no_lineups_count = 0
        error_count = 0
        
        for idx, fixture in enumerate(fixtures):
            fixture_id = fixture["fixture_id"]
            home_team_id = fixture["home_team_id"]
            away_team_id = fixture["away_team_id"]
            
            status_text.text(f"Processing fixture {idx + 1}/{len(fixtures)} (ID: {fixture_id})...")
            progress_bar.progress((idx + 1) / len(fixtures))
            
            try:
                # Fetch match statistics
                stats_json = fetch_statistics(fixture_id)
                if stats_json:
                    match_rows = extract_match_statistics_rows(stats_json, fixture_id)
                    all_match_rows.extend(match_rows)
                else:
                    no_stats_count += 1
                
                # Fetch player statistics from lineups
                lineups_json = fetch_lineups(fixture_id)
                if lineups_json and isinstance(lineups_json, dict) and ("home" in lineups_json or "away" in lineups_json):
                    player_rows = extract_player_statistics_rows(lineups_json, fixture_id, home_team_id, away_team_id)
                    all_player_rows.extend(player_rows)
                else:
                    no_lineups_count += 1
                    
            except Exception as e:
                error_count += 1
                if idx < 3:  # Only show first 3 errors
                    st.warning(f"Error processing fixture {fixture_id}: {e}")
                continue
        
        progress_bar.empty()
        status_text.empty()
        
        if all_match_rows or all_player_rows:
            # Filter out existing rows
            new_match_rows = [
                r for r in all_match_rows
                if (r["fixture_id"], r["period"], r["key"]) not in existing_match_keys
            ]
            new_player_rows = [
                r for r in all_player_rows
                if (r["fixture_id"], r["player_id"]) not in existing_player_keys
            ]
            
            st.success(
                f"Extracted {len(all_match_rows)} match statistics rows and {len(all_player_rows)} player statistics rows"
            )
            
            if no_stats_count > 0 or no_lineups_count > 0 or error_count > 0:
                st.info(f"⚠️ {no_stats_count} fixtures with no match stats, {no_lineups_count} with no lineups, {error_count} errors")
            
            # Show summary
            st.subheader("📊 Statistics Summary")
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Match Statistics", f"{len(new_match_rows)} new / {len(all_match_rows)} total")
                if len(all_match_rows) - len(new_match_rows) > 0:
                    st.caption(f"({len(all_match_rows) - len(new_match_rows)} already exist)")
            
            with col2:
                st.metric("Player Statistics", f"{len(new_player_rows)} new / {len(all_player_rows)} total")
                if len(all_player_rows) - len(new_player_rows) > 0:
                    st.caption(f"({len(all_player_rows) - len(new_player_rows)} already exist)")
            
            # Store in session state
            st.session_state["new_match_rows"] = new_match_rows
            st.session_state["new_player_rows"] = new_player_rows
        else:
            st.warning("No statistics found in any fixtures.")
else:
    st.info("No fixtures found for the selected season. Please add fixtures first.")

# Insert statistics
if "new_match_rows" in st.session_state or "new_player_rows" in st.session_state:
    new_match_rows = st.session_state.get("new_match_rows", [])
    new_player_rows = st.session_state.get("new_player_rows", [])
    
    if new_match_rows or new_player_rows:
        st.divider()
        st.subheader("💾 Insert Statistics into Supabase")
        
        if new_match_rows and new_player_rows:
            if st.button("➕ Insert Both Match & Player Statistics", type="primary"):
                with st.spinner(f"Inserting {len(new_match_rows)} match statistics and {len(new_player_rows)} player statistics..."):
                    try:
                        # Insert in batches
                        match_inserted = 0
                        if new_match_rows:
                            batch_size = 500
                            for i in range(0, len(new_match_rows), batch_size):
                                batch = new_match_rows[i : i + batch_size]
                                result = insert_match_statistics(batch)
                                if result and hasattr(result, "data") and result.data:
                                    match_inserted += len(result.data)
                        
                        player_inserted = 0
                        if new_player_rows:
                            batch_size = 500
                            for i in range(0, len(new_player_rows), batch_size):
                                batch = new_player_rows[i : i + batch_size]
                                result = insert_player_statistics(batch)
                                if result and hasattr(result, "data") and result.data:
                                    player_inserted += len(result.data)
                        
                        st.success(
                            f"🎉 Successfully inserted {match_inserted} match statistics rows "
                            f"and {player_inserted} player statistics rows!"
                        )
                        st.session_state.pop("new_match_rows", None)
                        st.session_state.pop("new_player_rows", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error inserting statistics: {e}")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                if new_match_rows:
                    if st.button("➕ Insert Match Statistics", type="primary", use_container_width=True):
                        with st.spinner(f"Inserting {len(new_match_rows)} match statistics rows..."):
                            try:
                                batch_size = 500
                                total_inserted = 0
                                for i in range(0, len(new_match_rows), batch_size):
                                    batch = new_match_rows[i : i + batch_size]
                                    result = insert_match_statistics(batch)
                                    if result and hasattr(result, "data") and result.data:
                                        total_inserted += len(result.data)
                                st.success(f"🎉 Successfully inserted {total_inserted} match statistics rows!")
                                st.session_state.pop("new_match_rows", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error inserting match statistics: {e}")
                else:
                    st.info("No new match statistics to insert.")
            
            with col2:
                if new_player_rows:
                    if st.button("➕ Insert Player Statistics", type="primary", use_container_width=True):
                        with st.spinner(f"Inserting {len(new_player_rows)} player statistics rows..."):
                            try:
                                batch_size = 500
                                total_inserted = 0
                                for i in range(0, len(new_player_rows), batch_size):
                                    batch = new_player_rows[i : i + batch_size]
                                    result = insert_player_statistics(batch)
                                    if result and hasattr(result, "data") and result.data:
                                        total_inserted += len(result.data)
                                st.success(f"🎉 Successfully inserted {total_inserted} player statistics rows!")
                                st.session_state.pop("new_player_rows", None)
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error inserting player statistics: {e}")
                else:
                    st.info("No new player statistics to insert.")
    else:
        st.info("✅ All statistics already exist in the database.")
