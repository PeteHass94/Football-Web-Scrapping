import streamlit as st
import pandas as pd
from supabase import create_client
from utils.extractors.data_fetcher import fetch_shotmap
from utils.page_components import add_common_page_elements

# Supabase client
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# Shared UI elements
add_common_page_elements()
st.title("🎯 Add Shots from SofaScore Shotmap")

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

def get_existing_shots():
    """Get set of (fixture_id, shot_id) tuples that already exist."""
    res = supabase.table("shots").select("fixture_id, shot_id").execute()
    if not res.data:
        return set()
    return {(r["fixture_id"], r["shot_id"]) for r in res.data if r.get("shot_id") is not None and r.get("fixture_id") is not None}

def insert_shots(rows):
    """Insert shots rows."""
    if not rows:
        return None
    return supabase.table("shots").insert(rows).execute()

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

def extract_shots_rows(shotmap_json: dict, fixture_id: int, home_team_id: int | None, away_team_id: int | None) -> list[dict]:
    """Extract shots rows from SofaScore shotmap JSON."""
    rows: list[dict] = []
    
    # Handle both {"shotmap": [...]} and plain list formats
    items = []
    if isinstance(shotmap_json, dict):
        items = shotmap_json.get("shotmap") or []
    elif isinstance(shotmap_json, list):
        items = shotmap_json
    else:
        return rows
    
    def _team_from_flag(is_home):
        if is_home is True:
            return home_team_id
        if is_home is False:
            return away_team_id
        return None
    
    for shot in items:
        player = shot.get("player") or {}
        player_id = _safe_int(player.get("id"))
        is_home = shot.get("isHome")
        team_id = _team_from_flag(is_home)
        
        shot_id = _safe_int(shot.get("id"))
        if not shot_id:
            continue  # Skip shots without an ID
        
        rows.append({
            "fixture_id": fixture_id,
            "player_id": player_id,
            "team_id": team_id,
            "shot_type": shot.get("shotType"),
            "goal_type": shot.get("goalType"),
            "situation": shot.get("situation"),
            "player_coordinates": shot.get("playerCoordinates"),
            "body_part": shot.get("bodyPart"),
            "goal_mouth_location": shot.get("goalMouthLocation"),
            "goal_mouth_coordinates": shot.get("goalMouthCoordinates"),
            "xg": _safe_float(shot.get("xg")),
            "xgot": _safe_float(shot.get("xgot")),
            "shot_id": shot_id,
            "minute": _safe_int(shot.get("time")),
            "added_time": _safe_int(shot.get("addedTime")),
            "time_seconds": _safe_int(shot.get("timeSeconds")),
            "incident_type": shot.get("incidentType"),
        })
    
    return rows

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
    
    if st.button("📥 Fetch Shots from All Fixtures"):
        existing_shot_ids = get_existing_shots()
        
        all_shots = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Track issues
        no_shotmap_count = 0
        error_count = 0
        
        for idx, fixture in enumerate(fixtures):
            fixture_id = fixture["fixture_id"]
            home_team_id = fixture["home_team_id"]
            away_team_id = fixture["away_team_id"]
            
            status_text.text(f"Processing fixture {idx + 1}/{len(fixtures)} (ID: {fixture_id})...")
            progress_bar.progress((idx + 1) / len(fixtures))
            
            try:
                shotmap_json = fetch_shotmap(fixture_id)
                if shotmap_json:
                    shots = extract_shots_rows(shotmap_json, fixture_id, home_team_id, away_team_id)
                    all_shots.extend(shots)
                else:
                    no_shotmap_count += 1
                    
            except Exception as e:
                error_count += 1
                if idx < 3:  # Only show first 3 errors
                    st.warning(f"Error processing fixture {fixture_id}: {e}")
                continue
        
        progress_bar.empty()
        status_text.empty()
        
        if all_shots:
            # Filter out existing shots (check by fixture_id + shot_id)
            new_shots = [
                s for s in all_shots
                if (s.get("fixture_id"), s.get("shot_id")) not in existing_shot_ids
            ]
            
            st.success(
                f"Extracted {len(all_shots)} shots from fixtures"
            )
            
            if no_shotmap_count > 0 or error_count > 0:
                st.info(f"⚠️ {no_shotmap_count} fixtures with no shotmap data, {error_count} errors")
            
            # Show summary
            st.subheader("📊 Shots Summary")
            st.metric("Shots", f"{len(new_shots)} new / {len(all_shots)} total")
            if len(all_shots) - len(new_shots) > 0:
                st.caption(f"({len(all_shots) - len(new_shots)} already exist)")
            
            # Store in session state
            st.session_state["new_shots"] = new_shots
            
            # Show preview
            if new_shots:
                st.subheader("🆕 New Shots to Add")
                preview_df = pd.DataFrame(new_shots[:100])  # Show first 100
                st.dataframe(preview_df, use_container_width=True)
                if len(new_shots) > 100:
                    st.caption(f"Showing first 100 of {len(new_shots)} shots")
        else:
            st.warning("No shots found in any fixtures.")
else:
    st.info("No fixtures found for the selected season. Please add fixtures first.")

# Insert shots
if "new_shots" in st.session_state:
    new_shots = st.session_state.get("new_shots", [])
    
    if new_shots:
        st.divider()
        st.subheader("💾 Insert Shots into Supabase")
        
        if st.button("➕ Insert Shots", type="primary"):
            with st.spinner(f"Inserting {len(new_shots)} shots..."):
                try:
                    # Insert in batches
                    batch_size = 500
                    total_inserted = 0
                    for i in range(0, len(new_shots), batch_size):
                        batch = new_shots[i : i + batch_size]
                        result = insert_shots(batch)
                        if result and hasattr(result, "data") and result.data:
                            total_inserted += len(result.data)
                    
                    st.success(f"🎉 Successfully inserted {total_inserted} shots!")
                    st.session_state.pop("new_shots", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error inserting shots: {e}")
    else:
        st.info("✅ All shots already exist in the database.")

