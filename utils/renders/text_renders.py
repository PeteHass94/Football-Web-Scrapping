import streamlit as st

def render_goal_list(goals, team_name):
    if not goals:
        st.markdown("_No goals_")
        return

    for g in sorted(goals, key=lambda x: (g := x["matchMinute"])):
        minute_str = f"{g['matchMinute']}'"
        if g.get("addedTime"):
            minute_str += f"+{g['addedTime']}"

        player = g.get("playerShortName", g.get("player", "Unknown"))
        goal_type = g.get("type", "unknown")
        is_own_goal = g.get("isOwnGoal", False)

        label = f"🕒 **{minute_str}** — **{player}** (*{goal_type}*)"
        if is_own_goal:
            label += " ⚠️ *(Own Goal)*"

        st.markdown(label)