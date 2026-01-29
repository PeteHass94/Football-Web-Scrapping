import json
from collections import Counter, defaultdict
from typing import Any

import pandas as pd
import streamlit as st
from supabase import create_client

from utils.extractors.data_fetcher import fetch_incidents
from utils.page_components import add_common_page_elements

supabase = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])

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
        .select("fixture_id, home_team_id, away_team_id, round, kickoff_date_time")
        .eq("season_id", season_id)
        .execute()
    )
    return res.data or []

def discover_incident_types(incidents_json: dict) -> dict[str, Any]:
    """
    Discover all incident types and their field structures.
    Returns a dict with:
    - type_counts: Counter of incident types
    - type_fields: dict mapping incident type to set of fields found
    - type_examples: dict mapping incident type to example incident
    """
    type_counts = Counter()
    type_fields: dict[str, set] = defaultdict(set)
    type_examples: dict[str, dict] = {}
    
    # Handle both {"incidents": [...]} and plain list formats
    items = []
    if isinstance(incidents_json, dict):
        items = incidents_json.get("incidents") or []
    elif isinstance(incidents_json, list):
        items = incidents_json
    else:
        return {"type_counts": type_counts, "type_fields": type_fields, "type_examples": type_examples}
    
    for inc in items:
        itype = inc.get("incidentType") or inc.get("type") or "unknown"
        type_counts[itype] += 1
        
        # Collect all fields for this incident type
        for key in inc.keys():
            type_fields[itype].add(key)
        
        # Store first example of each type
        if itype not in type_examples:
            type_examples[itype] = inc
    
    return {
        "type_counts": type_counts,
        "type_fields": type_fields,
        "type_examples": type_examples,
    }

add_common_page_elements()
st.title("🔍 Discover Incident Types")

st.caption(
    "This page scans fixtures and discovers all unique incident types that appear in "
    "`/event/{id}/incidents`. It shows what fields each incident type has."
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

col1, col2 = st.columns([1, 2])
with col1:
    max_fixtures = st.number_input("Max fixtures to scan", min_value=1, max_value=500, value=min(50, max(1, len(fixtures))))
with col2:
    show_examples = st.checkbox("Show example JSON for each incident type", value=True)

if st.button("🔎 Scan fixtures and discover incident types"):
    scan = fixtures[: int(max_fixtures)]
    
    all_type_counts = Counter()
    all_type_fields: dict[str, set] = defaultdict(set)
    all_type_examples: dict[str, dict] = {}
    
    no_incidents = 0
    errors = 0
    
    progress = st.progress(0)
    status = st.empty()
    
    for i, fx in enumerate(scan):
        fixture_id = fx["fixture_id"]
        
        status.text(f"Scanning fixture {i+1}/{len(scan)} — {fixture_id}")
        progress.progress((i + 1) / len(scan))
        
        try:
            incidents_json = fetch_incidents(fixture_id)
            if incidents_json:
                discovery = discover_incident_types(incidents_json)
                all_type_counts.update(discovery["type_counts"])
                
                # Merge fields
                for itype, fields in discovery["type_fields"].items():
                    all_type_fields[itype].update(fields)
                
                # Store examples (keep first one found)
                for itype, example in discovery["type_examples"].items():
                    if itype not in all_type_examples:
                        all_type_examples[itype] = example
            else:
                no_incidents += 1
        except Exception:
            errors += 1
    
    progress.empty()
    status.empty()
    
    st.success(
        f"Scan complete. Found {len(all_type_counts)} unique incident types "
        f"(no_incidents={no_incidents}, errors={errors})"
    )
    
    if all_type_counts:
        st.subheader("📊 Incident Types Discovered")
        df_types = pd.DataFrame(
            [
                {
                    "incident_type": k,
                    "count": int(v),
                    "fields_count": len(all_type_fields.get(k, set())),
                }
                for k, v in all_type_counts.most_common()
            ]
        )
        st.dataframe(df_types, use_container_width=True)
        
        st.subheader("📋 Fields by Incident Type")
        for itype in sorted(all_type_counts.keys()):
            with st.expander(f"{itype} ({all_type_counts[itype]} occurrences)"):
                fields = sorted(all_type_fields.get(itype, set()))
                st.write(f"**Fields ({len(fields)}):** {', '.join(fields)}")
                
                if show_examples and itype in all_type_examples:
                    st.write("**Example JSON:**")
                    st.json(all_type_examples[itype], expanded=False)
        
        # Download helpers
        st.divider()
        st.subheader("📥 Download discovered incident types")
        col_a, col_b = st.columns(2)
        with col_a:
            summary = {
                "type_counts": dict(all_type_counts.most_common()),
                "type_fields": {k: sorted(list(v)) for k, v in all_type_fields.items()},
            }
            st.download_button(
                "Download incident_types_summary.json",
                data=json.dumps(summary, indent=2),
                file_name="incident_types_summary.json",
                mime="application/json",
            )
        with col_b:
            examples_data = {
                "examples": all_type_examples,
            }
            st.download_button(
                "Download incident_examples.json",
                data=json.dumps(examples_data, indent=2, default=str),
                file_name="incident_examples.json",
                mime="application/json",
            )
    else:
        st.warning("No incident types discovered (maybe incidents endpoint returned empty).")

