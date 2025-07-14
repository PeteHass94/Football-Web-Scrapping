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
            "Half": seg["half"],
        })

    return data


def plot_game_state_gantt_split(segments, goal_events, home_team_name, away_team_name, injury_time_1, injury_time_2):
    home_data = prepare_gantt_data(segments, home_team_name, "home", injury_time_1)
    away_data = prepare_gantt_data(segments, away_team_name, "away", injury_time_1)
    df = pd.DataFrame(home_data + away_data)

    half_ranges = {
        "1st Half": (0, 45 + injury_time_1+1),
        "2nd Half": (45, 90 + injury_time_2+1)
    }

    plots = {}

    for team, team_name in [("home", home_team_name), ("away", away_team_name)]:
        for half in ["1st", "2nd"]:
            label = f"{team_name} - {half} Half"
            data = df[(df["Team"] == team_name) & (df["Half"] == half)]

            if data.empty:
                continue
            
            fig = go.Figure()
            color_map = {
                "winning": "green",
                "drawing": "blue",
                "losing": "red"
            }
            for _, row in data.iterrows():
                fig.add_trace(go.Bar(
                    x=[row["Duration"]],
                    y=[row["Team"]],
                    base=row["Start"],
                    orientation="h",
                    marker=dict(color=color_map[row["State"]]),
                    name=row["State"],
                    hovertemplate=(
                        f"<b>{row['Team']}</b><br>"
                        f"{row['State'].capitalize()}<br>"
                        f"{row['Start']} → {row['End']} min<br>"
                        "<extra></extra>"
                    ),
                    showlegend=False  # Optional: avoid repeated legend
                ))

            x_min, x_max = half_ranges[f"{half} Half"]

            fig.update_layout(
                title=label,
                xaxis_title="Minute",
                xaxis=dict(type="linear", range=[x_min, x_max], tick0=0, dtick=5),
                yaxis_title=None,
                height=200,
                barmode="stack",
            )

            # Add goals for this team and half
            for g in goal_events:
                if g["team"] != team:
                    continue
                goal_minute = g["minute"] + (g.get("addedTime") or 0)
                goal_half = "1st" if goal_minute < 45 + injury_time_1 else "2nd"
                if goal_half != half:
                    continue
                player = g.get("playerShortName", g.get("player", "Unknown"))
                is_own_goal = g.get("isOwnGoal", False)
                text_matchMinute = f"{g['matchMinute']}'"
                if g['addedTime'] > 0:
                    text_matchMinute += f"+{g['addedTime']}"
                text = f"{player} {'(OG)' if is_own_goal else ''} - {text_matchMinute}"

                fig.add_vline(
                    x=goal_minute,
                    line=dict(color="goldenrod", dash="dot"),
                    annotation=dict(text=text, showarrow=True, yanchor="bottom", font_size=10, arrowcolor="goldenrod"),
                )

            plots[label] = fig

    return plots

def render_game_state_gantt(home_team_name, away_team_name, mathch_label, total_time, injury_time_1, injury_time_2, home_goals, away_goals, segments):
    for g in home_goals:
        g["team"] = "home"
    for g in away_goals:
        g["team"] = "away"

    all_goals = home_goals + away_goals    

    plots = plot_game_state_gantt_split(
        segments,
        all_goals,
        home_team_name,
        away_team_name,
        injury_time_1,
        injury_time_2
    )

    st.subheader("Game State Timeline by Team & Half")
    st.markdown(f"**Match:** {mathch_label} - **Total Time:** {total_time} min")
    for label, fig in plots.items():
        # st.markdown(f"#### {label}")
        st.plotly_chart(fig, use_container_width=True)
