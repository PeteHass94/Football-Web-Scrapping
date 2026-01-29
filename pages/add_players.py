import streamlit as st
import pandas as pd
from supabase import create_client
from utils.extractors.data_fetcher import fetch_lineups
from utils.page_components import add_common_page_elements

# Supabase client
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# Shared UI elements
add_common_page_elements()
st.title("⚽ Add Players from SofaScore Lineups")

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

def get_existing_players():
    res = supabase.table("players").select("player_id").execute()
    return {p["player_id"] for p in res.data} if res.data else set()

def insert_players(players):
    return supabase.table("players").insert(players).execute()

def parse_players_from_lineups(lineups_json, home_team_id: int | None, away_team_id: int | None):
    """
    Extract unique players from lineup JSON.
    Returns a list of player dictionaries ready for insertion.
    """
    def _safe_int(x):
        try:
            return int(x) if x is not None else None
        except Exception:
            return None

    players_rows: list[dict] = []

    if not isinstance(lineups_json, dict):
        return players_rows

    for side_key, side_team_id in (("home", home_team_id), ("away", away_team_id)):
        side = lineups_json.get(side_key) or {}
        for entry in side.get("players", []) or []:
            p = (entry or {}).get("player") or {}
            pid = p.get("id")
            if not pid:
                continue

            # Extract sofascoreId if available, otherwise use player_id as string
            sofascore_id = p.get("sofascoreId")
            if not sofascore_id and pid:
                sofascore_id = str(pid)

            players_rows.append(
                {
                    "player_id": _safe_int(pid),
                    "name": p.get("name"),
                    "short_name": p.get("shortName"),
                    "dateOfBirthTimestamp": _safe_int(p.get("dateOfBirthTimestamp")),
                    "team_id": _safe_int(side_team_id),
                    "sofascoreId": sofascore_id,
                }
            )

    return players_rows

def extract_unique_players(all_players):
    """
    Deduplicate players by player_id, keeping the most recent/complete record.
    """
    unique_players = {}
    for player in all_players:
        pid = player.get("player_id")
        if not pid:
            continue
        
        # If we haven't seen this player, or if current record has more info, keep it
        if pid not in unique_players:
            unique_players[pid] = player
        else:
            # Prefer record with more complete data (non-null values)
            existing = unique_players[pid]
            existing_null_count = sum(1 for v in existing.values() if v is None)
            current_null_count = sum(1 for v in player.values() if v is None)
            if current_null_count < existing_null_count:
                unique_players[pid] = player
    
    return list(unique_players.values())

# --- UI Flow ---

# Tournament selection
tournaments = get_tournaments()
# Build full tournament dicts
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

# Match format: {"name": ..., "year": ..., "id": season_id}
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
    
    # Test with first fixture
    if st.button("🧪 Test with First Fixture"):
        if fixtures:
            test_fixture = fixtures[0]
            fixture_id = test_fixture["fixture_id"]
            home_team_id = test_fixture["home_team_id"]
            away_team_id = test_fixture["away_team_id"]
            
            st.write(f"Testing fixture ID: {fixture_id}")
            st.write(f"Home team ID: {home_team_id}, Away team ID: {away_team_id}")
            
            try:
                lineups = fetch_lineups(fixture_id)
                st.write("**Raw lineup response:**")
                st.json(lineups)
                
                if lineups and isinstance(lineups, dict):
                    if "home" in lineups or "away" in lineups:
                        players = parse_players_from_lineups(lineups, home_team_id, away_team_id)
                        st.write(f"**Extracted {len(players)} players:**")
                        if players:
                            st.dataframe(pd.DataFrame(players))
                        else:
                            st.warning("No players extracted!")
                            # Debug: check structure
                            if "home" in lineups:
                                home_players = lineups["home"].get("players", [])
                                st.write(f"Home players count: {len(home_players)}")
                            if "away" in lineups:
                                away_players = lineups["away"].get("players", [])
                                st.write(f"Away players count: {len(away_players)}")
                    else:
                        st.error(f"No 'home' or 'away' keys. Keys found: {list(lineups.keys())}")
                else:
                    st.error(f"Lineups is not a dict. Type: {type(lineups)}, Value: {lineups}")
            except Exception as e:
                st.error(f"Error: {e}")
                import traceback
                st.code(traceback.format_exc())
    
    if st.button("📥 Fetch Players from All Fixtures"):
        existing_player_ids = get_existing_players()
        all_players = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Track issues for summary
        no_data_count = 0
        no_players_count = 0
        error_count = 0
        success_count = 0
        
        for idx, fixture in enumerate(fixtures):
            fixture_id = fixture["fixture_id"]
            home_team_id = fixture["home_team_id"]
            away_team_id = fixture["away_team_id"]
            
            status_text.text(f"Processing fixture {idx + 1}/{len(fixtures)} (ID: {fixture_id})...")
            progress_bar.progress((idx + 1) / len(fixtures))
            
            try:
                lineups = fetch_lineups(fixture_id)
                
                # Debug: Check what we got
                if not lineups:
                    no_data_count += 1
                    if idx < 3:  # Only show first 3 warnings
                        st.warning(f"No lineup data returned for fixture {fixture_id}")
                    continue
                
                if not isinstance(lineups, dict):
                    error_count += 1
                    if idx < 3:
                        st.warning(f"Lineup data is not a dict for fixture {fixture_id}, got type: {type(lineups)}")
                    continue
                
                # Check if it has the expected structure with "home" and/or "away" keys
                if "home" not in lineups and "away" not in lineups:
                    error_count += 1
                    if idx < 3:
                        keys = list(lineups.keys())[:5]  # Show first 5 keys
                        st.warning(f"Fixture {fixture_id}: No 'home' or 'away' keys. Found keys: {keys}")
                    continue
                
                # Parse players from the lineup
                players = parse_players_from_lineups(lineups, home_team_id, away_team_id)
                
                if not players:
                    no_players_count += 1
                    if idx < 3:
                        st.warning(f"No players extracted from fixture {fixture_id}")
                else:
                    success_count += 1
                    all_players.extend(players)
                    
            except Exception as e:
                error_count += 1
                if idx < 3:
                    st.warning(f"Error fetching lineup for fixture {fixture_id}: {str(e)}")
                continue
        
        # Show summary
        st.info(f"**Summary:** {success_count} fixtures with players, {no_players_count} with no players, {no_data_count} with no data, {error_count} errors")
        
        progress_bar.empty()
        status_text.empty()
        
        if all_players:
            # Deduplicate players
            unique_players = extract_unique_players(all_players)
            st.success(f"Extracted {len(unique_players)} unique players from {len(all_players)} total player entries")
            
            # Filter out players that already exist
            new_players = [p for p in unique_players if p["player_id"] not in existing_player_ids]
            existing_count = len(unique_players) - len(new_players)
            
            if existing_count > 0:
                st.info(f"⚠️ {existing_count} players already exist in database")
            
            if new_players:
                st.subheader(f"🆕 {len(new_players)} New Players to Add")
                df = pd.DataFrame(new_players)
                st.dataframe(df)
                
                st.session_state["players_to_insert"] = new_players
            else:
                st.info("✅ All players already exist in the database.")
        else:
            st.warning("No players found in any fixtures.")
else:
    st.info("No fixtures found for the selected season. Please add fixtures first.")

# Insert players
if "players_to_insert" in st.session_state and st.session_state["players_to_insert"]:
    if st.button("➕ Insert Players into Supabase"):
        players_to_insert = st.session_state["players_to_insert"]
        try:
            result = insert_players(players_to_insert)
            if hasattr(result, "data") and result.data:
                st.success(f"🎉 Successfully inserted {len(result.data)} players!")
                st.session_state.pop("players_to_insert", None)
            else:
                st.error("❌ Insert failed. Check the error message above.")
        except Exception as e:
            st.error(f"❌ Error inserting players: {e}")
    