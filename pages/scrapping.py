"""
Entrypoint for streamlit app.
Runs top to bottom every time the user interacts with the app (other than imports and cached functions).
"""

# Library imports
import traceback
import copy

import streamlit as st
import pandas as pd

from utils.extractors.data_fetcher import fetch_json, fetch_season_json, fetch_standing_json, fetch_rounds_json, fetch_round_events
from utils.api.tournaments import TOURNAMENTS
from utils.extractors.data_flatten import get_flattened_standings, get_flattened_round_events
from utils.api.incidents import extract_goal_incidents

from utils.page_components import (
    add_common_page_elements,
)

# def show():
sidebar_container = add_common_page_elements()
page_container = st.sidebar.container()
sidebar_container = st.sidebar.container()

st.header("Web Scrapping", divider=True)
st.text("Where and how I get my data")

st.title("Football Tournament & Season Selector")

# Tournament selection
tournament_names = [t["name"] for t in TOURNAMENTS]
selected_tournament_name = st.selectbox("Select a Tournament", tournament_names, index=0)
selected_tournament = next(t for t in TOURNAMENTS if t["name"] == selected_tournament_name)
# st.text(selected_tournament)
# Fetch seasons
# seasons_url = f"https://api.sofascore.com/api/v1/tournament/{selected_tournament['id']}/seasons"
try:
    seasons_response = fetch_season_json(selected_tournament)
    seasons_data = seasons_response.get("seasons", [])
    if not seasons_data:
        st.warning("No seasons found")
        st.stop()
    
    st.subheader("Available Seasons")
    # st.dataframe(pd.json_normalize(seasons_data))

    if seasons_data:
        season_names = [f"{s.get('name')} ({s.get('year')})" for s in seasons_data]
        selected_index = st.selectbox("Select a Season", range(len(season_names)), format_func=lambda i: season_names[i], index=1)
        selected_season = seasons_data[selected_index]
        
        standings_response = fetch_standing_json(selected_tournament, selected_season)
        standing_tables = standings_response.get("standings", [])
        if not standing_tables:
            st.warning("No standings found")
            st.stop()       
        
        if standing_tables:
        
            st.subheader("League Standings (Flattened Data)")
            table_df_formatted = get_flattened_standings(standing_tables)
            st.dataframe(table_df_formatted)
            
            rounds_data = fetch_rounds_json(selected_tournament, selected_season)
            
            if "currentRound" in rounds_data and "rounds" in rounds_data:
                current_round = rounds_data["currentRound"].get("round", 0)
                available_rounds = [r["round"] for r in rounds_data["rounds"] if r["round"] <= current_round]

                selected_round = st.selectbox("Select a Round", available_rounds)

                st.subheader("Selected Round")
                st.write(f"Selected Round: {selected_round}")
                
                # round_url = f"https://www.sofascore.com/api/v1/unique-tournament/{selected_tournament['unique_tournament']}/season/{selected_season['id']}/events/round/{selected_round}"
                # round_response = fetch_json(round_url)
                # round_events = round_response.get("events", [])
                
                round_events = fetch_round_events(selected_tournament, selected_season, selected_round)
                if round_events:
                    
                    filtered_round_events = get_flattened_round_events(round_events)
                    
                    st.subheader("Flattened Round Events Data")
                    st.dataframe(filtered_round_events,
                                    column_config={
                                        "incidents.home_goals": st.column_config.JsonColumn(
                                            "Home Goal Incidents",
                                                help="JSON strings or objects",
                                                width="large",
                                        ),
                                        "incidents.away_goals": st.column_config.JsonColumn(
                                            "Away Goals Incidents",
                                                help="JSON strings or objects",
                                                width="large",
                                        )                                        
                                    }
                                )
                    
                else:
                    st.warning("No events available for this round.")
            else:
                st.warning("No rounds available for this season.")
            
        else:
            st.warning("No standings available for this season.")
    else:
        st.warning("No seasons found.")
except Exception as e:
    st.error(f"Failed to fetch data: {e}")