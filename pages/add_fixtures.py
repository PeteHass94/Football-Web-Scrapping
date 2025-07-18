import streamlit as st
import pandas as pd
from supabase import create_client
from utils.extractors.data_fetcher import fetch_rounds_json, fetch_round_events
from utils.page_components import add_common_page_elements

from datetime import datetime, timezone

# Supabase client
supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

# Shared UI elements
add_common_page_elements()
st.title("🏟️ Add Fixtures from SofaScore Rounds")

# Fetch tournaments
@st.cache_data
def get_tournaments():
    res = supabase.table("tournaments").select("id, name, tournament_id, unique_tournament_id").execute()
    return res.data or []

@st.cache_data
def get_seasons(tournament_id):
    res = supabase.table("seasons").select("id, season_id, name, year").eq("tournament_id", tournament_id).execute()
    return res.data or []

def get_existing_fixtures():
    res = supabase.table("fixtures").select("fixture_id").execute()
    return {f["fixture_id"] for f in res.data} if res.data else set()

def insert_fixtures(fixtures):
    return supabase.table("fixtures").insert(fixtures).execute()

# def fetch_fixtures_from_events(standings_json):
#     rows = standings_json.get("standings", [])
#     fixtures = []
#     for row in rows:
#         for item in row.get("rows", []):
#             fixture = item.get("team", {})
#             if fixture:
#                 fixtures.append({
#                     "fixture_id": fixture["id"],
#                     "fixture_custom_id": fixture.get("customId"),
#                     "home_team_id": fixture.get("homeTeam", {}).get("id"),
#                     "away_team_id": fixture.get("awayTeam", {}).get("id"),
#                     "season_id": fixture.get("season_id"),
#                     "round": fixture.get("round_id"),
#                     "kickoff_date_time": fixture.get("startTimestamp"), #convert timestamp to datetime with timezone
#                     "injury_time_1": fixture.get("time").get("injuryTime1", 0),
#                     "injury_time_2": fixture.get("time").get("injuryTime2", 0),
#                     "total_time": 90+ fixture.get("injuryTime1", 0) + fixture.get("injuryTime2", 0),
#                     "home_score": fixture.get("homeScore", {}).get("current", 0),
#                     "away_score": fixture.get("awayScore", {}).get("current", 0),
#                     "status": fixture.get("status", {}).get("type", "unknown"),
#                     "result": "H" if fixture.get("homeScore", {}).get("current", 0) > fixture.get("awayScore", {}).get("current", 0) else "A" if fixture.get("homeScore", {}).get("current", 0) < fixture.get("awayScore", {}).get("current", 0) else "D",
#                 })
#     return fixtures

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

season_names = ["All Seasons"] + [s["name"] for s in valid_seasons]
# season_names = [s["name"] for s in valid_seasons]
season_map = {s["name"]: s for s in valid_seasons}

selected_season_name = st.selectbox("Select Season", season_names)

# Fetch Rounds
if st.button("Fetch All Rounds from SofaScore Seasons"):
    selected_seasons = valid_seasons if selected_season_name == "All Seasons" else [season_map[selected_season_name]]
    # selected_seasons = [season_map[selected_season_name]]
    
    all_api_rounds = []
    for season in selected_seasons:
        rounds_json = fetch_rounds_json(tournament, season)
        if "rounds" in rounds_json:
            for rnd in rounds_json["rounds"]:
                rnd["season_id"] = season["id"]  # Add season_id to each round
                rnd["season_name"] = season["name"]  # Optional: for display/debugging
            all_api_rounds.extend(rounds_json["rounds"])
        else:
            st.warning(f"No rounds found for season {season['name']}")
            st.stop()

    if not all_api_rounds:
        st.warning("No rounds available.")
        st.stop()

    st.subheader("📆 Available Rounds")
    rounds_df = pd.DataFrame(all_api_rounds)
    st.dataframe(rounds_df)

    st.session_state["rounds_fetched"] = rounds_df

# Fetch events for all rounds
if "rounds_fetched" in st.session_state and st.button("Fetch Fixtures for All Rounds"):
    rounds_df = st.session_state["rounds_fetched"]
    all_fixtures = []

    for _, round_row in rounds_df.iterrows():
        round_id = round_row["round"]
        season_id = round_row["season_id"]

        # Prepare season and round dicts
        season_obj = {"id": season_id}
        round_events_json = fetch_round_events(tournament, season_obj, round_id)

        events = round_events_json if isinstance(round_events_json, list) else round_events_json.get("events", [])
        if not events:
            st.info(f"No events for round ID {round_id}")
            continue

        for e in events:
            # Just capture everything for now
            if e.get("time"):
                fixture = {**e, "season_id": season_id, "round_id": round_id}            
                all_fixtures.append(fixture)

        
    if all_fixtures:
        st.subheader(f"📝 {len(all_fixtures)} Fixtures Fetched")
        st.dataframe(pd.DataFrame(all_fixtures))
        st.session_state["fixtures_fetched"] = all_fixtures
    else:
        st.warning("No fixtures found across all rounds.")
        
if "fixtures_fetched" in st.session_state and st.button("➕ Add Fixtures to Supabase"):
    raw_fixtures = st.session_state["fixtures_fetched"]
    existing_ids = get_existing_fixtures()

    insert_rows = []
    for f in raw_fixtures:
        if f["id"] in existing_ids:
            continue  # skip already inserted

        try:
            kickoff_dt = datetime.fromtimestamp(f["startTimestamp"], tz=timezone.utc)
        except Exception:
            kickoff_dt = None
        
        insert_rows.append({
            "fixture_id": f["id"],
            "fixture_custom_id": f.get("customId"),
            "home_team_id": f.get("homeTeam", {}).get("id"),
            "away_team_id": f.get("awayTeam", {}).get("id"),
            "season_id": f.get("season_id"),
            "round": f.get("round_id"),
            "kickoff_date_time": kickoff_dt.isoformat() if kickoff_dt else None,
            "injury_time_1": f.get("time", {}).get("injuryTime1", 0),
            "injury_time_2": f.get("time", {}).get("injuryTime2", 0),
            "total_time": 90 + f.get("time", {}).get("injuryTime1", 0) + f.get("time", {}).get("injuryTime2", 0),
            "home_score": f.get("homeScore", {}).get("current", 0),
            "away_score": f.get("awayScore", {}).get("current", 0),
            "result": (
                "H" if f.get("homeScore", {}).get("current", 0) > f.get("awayScore", {}).get("current", 0)
                else "A" if f.get("homeScore", {}).get("current", 0) < f.get("awayScore", {}).get("current", 0)
                else "D"
            )
        })
        
    st.dataframe(pd.DataFrame(insert_rows))
    if insert_rows:
        result = insert_fixtures(insert_rows)
        if hasattr(result, "data"):
            st.success(f"🎉 {len(result.data)} fixtures inserted into Supabase")
        else:
            st.error("❌ Fixture insert failed")
    else:
        st.info("No new fixtures to insert.")
                
    
# # Fetch teams
# if st.button("Fetch All Fixtures from SofaScore Rounds"):
#     selected_seasons = valid_seasons if selected_season_name == "All Seasons" else [season_map[selected_season_name]]

#     all_api_teams = []
#     for season in selected_seasons:
#         standings_json = fetch_standing_json(tournament, season)
#         season_teams = fetch_teams_from_standings(standings_json)
#         all_api_teams.extend(season_teams)

#     if not all_api_teams:
#         st.warning("No teams found")
#         st.stop()

#     # Deduplicate by team_id
#     unique_teams = {team["team_id"]: team for team in all_api_teams}.values()

#     # Check against existing team_ids
#     existing_ids = get_existing_teams()
#     already_added = [t for t in unique_teams if t["team_id"] in existing_ids]
#     not_added = [t for t in unique_teams if t["team_id"] not in existing_ids]

#     # Store in session
#     st.session_state["teams_already"] = already_added
#     st.session_state["teams_new"] = not_added
#     st.session_state["teams_fetched"] = True