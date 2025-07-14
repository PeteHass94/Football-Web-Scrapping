import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta

from utils.api.incidents import compute_game_states

def prepare_gantt_data(segments, team_name, team_type, injury_time_1):
    halftime_boundary = 45 + injury_time_1
    colors = {
        "winning": "green",
        "drawing": "blue",
        "losing": "red"
    }

    data = []
    for seg in segments:
        start = seg["start"]
        end = seg["end"]
        state = seg[team_type]

        data.append({
            "Team": team_name,
            "Start": start,
            "End": end,
            "Duration": end - start,
            "State": state,
            "Color": colors[state],
            "Half": "1st Half" if start < halftime_boundary else "2nd Half"
        })

    return data


def plot_game_state_gantt(segments, goal_events, home_team_name, away_team_name):
    home_data = prepare_gantt_data(segments, home_team_name, "home")
    away_data = prepare_gantt_data(segments, away_team_name, "away")
    df = pd.DataFrame(home_data + away_data)
    
    st.dataframe(df)
    
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="End",
        y="Team",
        color="State",
        color_discrete_map={
            "winning": "green",
            "drawing": "blue",
            "losing": "red"
        },
        category_orders={"Team": [away_team_name, home_team_name]},  # away on top
    )

    fig.update_layout(
        title="Game State Timeline",
        xaxis_title="Minute",
        yaxis_title="Team",
        showlegend=True,
        height=400,
    )

    # Add goal annotations
    for g in goal_events:
        team = g["team"]
        minute = g["minute"] + (g.get("addedTime") or 0)
        player = g.get("playerShortName", g.get("player", "Unknown"))
        is_own_goal = g.get("isOwnGoal", False)
        text = f"{player} {'(OG)' if is_own_goal else ''}"

        fig.add_vline(
            x=minute,
            line=dict(color="black", dash="dash"),
            annotation=dict(text=text, showarrow=True, yanchor="bottom", font_size=10),
        )

    return fig

def render_game_state_gantt(home_team_name, away_team_name, total_time, injury_time_1, injury_time_2, home_goals, away_goals, segments):
    """
    Renders a Gantt chart showing the game state over time.
    
    Args:
        home_team_name (str): Name of the home team.
        away_team_name (str): Name of the away team.
        total_time (int): Total game time in minutes.
        injury_time_1 (int): Injury time for the first half.
        injury_time_2 (int): Injury time for the second half.
        home_goals (list): List of home goals with their details.
        away_goals (list): List of away goals with their details.
        
    Returns:
        plotly.graph_objects.Figure: Gantt chart figure.
    """
    
    for g in home_goals:
        g["team"] = "home"
    for g in away_goals:
        g["team"] = "away"
    
    st.write(f"goals processed")
    
    all_goals = home_goals + away_goals    
    
    return plot_game_state_gantt(segments, all_goals, home_team_name, away_team_name)