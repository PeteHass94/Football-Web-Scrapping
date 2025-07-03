from utils.extractors.data_fetcher import fetch_json

def extract_goal_incidents(base_row):
    home_team_id = base_row["homeTeam.id"]
    away_team_id = base_row["awayTeam.id"]
    
    max_injuryTime1 = base_row["time.injuryTime1"] 
    max_injuryTime2 = base_row["time.injuryTime2"]
    
    eventsId = base_row["id"]
    
    incidents_url = f"https://www.sofascore.com/api/v1/event/{eventsId}/incidents"
    incidents = fetch_json(incidents_url)
    
    home_goals = []
    away_goals = []                       

    for incident in incidents.get("incidents", []):
        if incident.get("incidentType") == "goal":
            goal_event = {                                    
                "minute": incident.get("time"),
                "timestamp": incident.get("timeSeconds"),
                "half": "1st" if incident.get("time") <= 45 else "2nd",
                "addedTime": incident.get("addedTime", None), 
                "playerId": incident.get("player", {}).get("id"),
                "player": incident.get("player", {}).get("name"),
                "playerShortName": incident.get("player", {}).get("shortName"),                                    
                "isOwnGoal": incident.get("icidentClass") == "ownGoal",
                "type": incident.get("incidentClass", "regular"),
            }
            
            if (goal_event["half"] == "1st" and goal_event["addedTime"] is not None):
                if goal_event["addedTime"] > max_injuryTime1:
                    max_injuryTime1 = goal_event["addedTime"]
            
            if (goal_event["half"] == "2nd" and goal_event["addedTime"] is not None):
                if goal_event["addedTime"] > max_injuryTime2:
                    max_injuryTime2 = goal_event["addedTime"]                                
            
            if incident.get("isHome", False):
                goal_event["teamId"] = home_team_id
                home_goals.append(goal_event)
            else:
                goal_event["teamId"] = away_team_id
                away_goals.append(goal_event)

    return max_injuryTime1, max_injuryTime2, home_goals, away_goals