import requests
from datetime import datetime, timedelta, timezone

API_TOKEN = os.environ["API_TOKEN"]
BASE_URL = "https://api.sportmonks.com/v3/football"

# --- TELEGRAM CONFIG ---
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
# -----------------------

session = requests.Session()
session.headers.update({"Accept": "application/json"})

def get_fixtures_today():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures/date/{today}"
    params = {
        "include": "participants",
        "api_token": API_TOKEN
    }
    r = session.get(url, params=params, timeout=30)
    if not r.ok:
        print(f"API error: {r.status_code} - {r.text}")
        return []
    return r.json().get("data", [])

def get_team_last_fixture_ids(team_id, count=3):
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=180)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures/between/{start}/{end}/{team_id}"
    params = {
        "api_token": API_TOKEN
    }
    r = session.get(url, params=params, timeout=30)
    if not r.ok:
        print(f"API error: {r.status_code} - {r.text}")
        return []
    fixtures = r.json().get("data", [])
    finished = [f for f in fixtures if f.get("state_id") == 5]
    finished.sort(key=lambda x: x.get("starting_at", ""), reverse=True)
    return [f["id"] for f in finished[:count]]

def get_fixture_scores(fixture_id):
    url = f"{BASE_URL}/fixtures/{fixture_id}"
    params = {
        "include": "scores;participants",
        "api_token": API_TOKEN
    }
    r = session.get(url, params=params, timeout=30)
    if not r.ok:
        print(f"API error: {r.status_code} - {r.text}")
        return None
    return r.json().get("data", {})

def get_final_score(fixture):
    home_goals = away_goals = None
    for s in fixture.get("scores", []):
        if s.get("description") == "CURRENT":
            participant = s["score"].get("participant")
            goals = s["score"].get("goals")
            if participant == "home":
                home_goals = goals
            elif participant == "away":
                away_goals = goals
    return home_goals, away_goals

def btts_no(home_goals, away_goals):
    if home_goals is None or away_goals is None:
        return False
    return home_goals == 0 or away_goals == 0

def get_team_names(fixture):
    home = away = None
    for p in fixture.get("participants", []):
        loc = p.get("meta", {}).get("location")
        if loc == "home":
            home = (p["id"], p["name"])
        elif loc == "away":
            away = (p["id"], p["name"])
    return home, away

# --- TELEGRAM FUNCTION ---
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        r = requests.post(url, json=payload, timeout=20)
        if not r.ok:
            print(f"Telegram error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Telegram exception: {e}")
# -------------------------

def main():
    print("Fetching today's fixtures and analyzing BTTS streaks...\n")
    fixtures = get_fixtures_today()
    if not fixtures:
        print("No fixtures found or API error.")
        send_telegram_message("⚠️ No fixtures found today or API error.")
        return

    teams_checked = set()
    teams_btts_no = []

    for fixture in fixtures:
        home, away = get_team_names(fixture)
        for team in [home, away]:
            if not team or team[0] in teams_checked:
                continue
            teams_checked.add(team[0])
            last3_ids = get_team_last_fixture_ids(team[0], 3)
            if len(last3_ids) < 3:
                continue
            all_no = True
            print(f"\nChecking {team[1]}'s last 3 matches:")
            for fid in last3_ids:
                fdata = get_fixture_scores(fid)
                if not fdata:
                    print(f"  Could not fetch fixture {fid}")
                    all_no = False
                    break
                home_goals, away_goals = get_final_score(fdata)
                opp = None
                for p in fdata.get("participants", []):
                    if p["id"] != team[0]:
                        opp = p["name"]
                print(f"  vs {opp}: {home_goals}-{away_goals} ", end="")
                if btts_no(home_goals, away_goals):
                    print("(BTTS=No)")
                else:
                    print("(BTTS=Yes)")
                    all_no = False
            if all_no:
                teams_btts_no.append(team[1])

    if teams_btts_no:
        message = "📊 *Teams with 3 consecutive matches WITHOUT BTTS:*\n\n"
        print("\nTeams with 3 consecutive matches WITHOUT BTTS (BTTS=No):\n")
        for name in teams_btts_no:
            print(f" - {name}")
            message += f"• {name}\n"
        send_telegram_message(message)
    else:
        print("\nNo teams found with 3 consecutive matches without BTTS.")
        send_telegram_message("ℹ️ No teams found today with 3 consecutive matches without BTTS.")

if __name__ == "__main__":
    main()
