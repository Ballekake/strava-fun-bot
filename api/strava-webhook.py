# api/strava-webhook.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import os
import httpx
import random
import json
import time
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# === CONFIG === #
VERIFY_TOKEN = "mystravaisgarbage"
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN")

# === TOKEN CACHE === #
cached_token = {
    "access_token": os.environ.get("STRAVA_ACCESS_TOKEN"),
    "expires_at": int(os.environ.get("STRAVA_EXPIRES_AT", "0"))
}

# === AUTOMATIC TOKEN REFRESH === #
async def get_strava_token():
    """Return valid Strava access token, refreshing automatically if needed."""
    global cached_token
    now = int(time.time())

    if cached_token["access_token"] and now < cached_token["expires_at"] - 60:
        return cached_token["access_token"]

    logging.info("🔁 Fornyer Strava access token...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": STRAVA_REFRESH_TOKEN
            }
        )
        data = resp.json()
        if resp.status_code != 200:
            logging.error(f"❌ Klarte ikke fornye token: {resp.text}")
            return None

        cached_token = {
            "access_token": data["access_token"],
            "expires_at": data["expires_at"]
        }
        os.environ["STRAVA_ACCESS_TOKEN"] = data["access_token"]
        os.environ["STRAVA_EXPIRES_AT"] = str(data["expires_at"])

        logging.info(f"✅ Nytt token gyldig til {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(data['expires_at']))}")
        return data["access_token"]

# === RANDOMIZED TITLE/DESCRIPTION === #
titles_and_descriptions = [
    {"title": "Jeg trodde pushups var noe man kjøper på Rema",
     "description": "Forventningsavvik mellom produkt og aktivitet dokumentert. Ingen videre oppfølging nødvendig."},
    {"title": "Det er ikke kroppen min som sliter, det er sjela",
     "description": "Subjektiv opplevelse av utmattelse registrert. Fysisk kapasitet vurderes som tilfredsstillende."},
    {"title": "Det ser flatt ut på kartet, men kartet lyver",
     "description": "Avvik mellom kartgrunnlag og faktisk høydeprofil bekreftet."},
    {"title": "Jeg meldte meg på for utsikten, ikke for å dø",
     "description": "Forventningsavvik mellom motivasjon og terreng dokumentert. Saken anses lukket."},
    {"title": "Dette er ikke tur – dette er terapi med bakker",
     "description": "Tiltaket klassifiseres som egeninitiert rehabilitering med fysisk komponent."},
]

def get_random_pair():
    """Return random bureaucratic title/description pair."""
    return random.choice(titles_and_descriptions)

# === DUPLICATE GUARD === #
processed_activities = set()

# === VERIFY ENDPOINT (for Strava subscription setup) === #
@app.get("/api/strava-webhook")
async def verify(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        return JSONResponse({"hub.challenge": hub_challenge})
    return JSONResponse({"error": "invalid verify token"}, status_code=400)

# === MAIN WEBHOOK HANDLER === #
@app.post("/api/strava-webhook")
async def webhook(request: Request):
    payload = await request.json()
    logging.info(f"📬 Received Strava webhook: {json.dumps(payload)}")

    if payload.get("object_type") != "activity":
        return PlainTextResponse("ignored", status_code=200)

    activity_id = payload.get("object_id")
    aspect_type = payload.get("aspect_type")

    if not activity_id:
        return PlainTextResponse("no activity id", status_code=400)

    key = f"{activity_id}-{aspect_type}"
    if key in processed_activities:
        logging.info(f"⏳ Duplicate activity {activity_id}, skipping.")
        return PlainTextResponse("duplicate", status_code=200)
    processed_activities.add(key)

    token = await get_strava_token()
    if not token:
        logging.error("❌ Ingen gyldig token tilgjengelig.")
        return PlainTextResponse("token missing", status_code=401)

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        logging.info(f"➡️ GET-status: {r.status_code}")
        if r.status_code != 200:
            logging.error(f"❌ Kunne ikke hente aktivitet: {r.text}")
            return PlainTextResponse("fetch failed", status_code=r.status_code)

        pair = get_random_pair()
        update_payload = {"name": pair["title"], "description": pair["description"]}
        logging.info(f"📝 Oppdaterer aktivitet {activity_id} med: {update_payload}")

        put = await client.put(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {token}"},
            data=update_payload
        )
        logging.info(f"✅ Oppdateringsstatus {put.status_code}: {put.text[:200]}")

    return PlainTextResponse("OK", status_code=200)

# === TEST ENDPOINT (for easy “ping” verification) === #
@app.get("/api/ping")
async def ping():
    """Simulate a Strava update without modifying any real activity."""
    token = await get_strava_token()
    if not token:
        return JSONResponse({"status": "error", "message": "No valid Strava token"}, status_code=401)

    pair = get_random_pair()
    mock_payload = {
        "status": "ok",
        "test_activity_update": pair,
        "token_preview": token[:8] + "..." if token else "missing",
        "note": "This was a dry-run; no real activity was updated."
    }
    logging.info(f"🧪 Ping test: would update with -> {pair}")
    return JSONResponse(mock_payload)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": STRAVA_REFRESH_TOKEN
            }
        )
        data = resp.json()
        if resp.status_code != 200:
            logging.error(f"❌ Klarte ikke fornye token: {resp.text}")
            return None

        cached_token = {
            "access_token": data["access_token"],
            "expires_at": data["expires_at"]
        }
        os.environ["STRAVA_ACCESS_TOKEN"] = data["access_token"]
        os.environ["STRAVA_EXPIRES_AT"] = str(data["expires_at"])

        logging.info(f"✅ Nytt token gyldig til {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(data['expires_at']))}")
        return data["access_token"]

# === TITLER OG BESKRIVELSER (forkortet) === #
titles_and_descriptions = [
    {"title": "Jeg trodde pushups var noe man kjøper på Rema",
     "description": "Forventningsavvik mellom produkt og aktivitet dokumentert. Ingen videre oppfølging nødvendig."},
    {"title": "Det er ikke kroppen min som sliter, det er sjela",
     "description": "Subjektiv opplevelse av utmattelse registrert. Fysisk kapasitet vurderes som tilfredsstillende."},
    {"title": "Det ser flatt ut på kartet, men kartet lyver",
     "description": "Avvik mellom kartgrunnlag og faktisk høydeprofil bekreftet."},
    {"title": "Jeg meldte meg på for utsikten, ikke for å dø",
     "description": "Forventningsavvik mellom motivasjon og terreng dokumentert. Saken anses lukket."},
    {"title": "Dette er ikke tur – dette er terapi med bakker",
     "description": "Tiltaket klassifiseres som egeninitiert rehabilitering med fysisk komponent."},
]

def get_random_pair():
    return random.choice(titles_and_descriptions)

# === DUPLIKAT-GUARD === #
processed_activities = set()

# === STRAVA VERIFY === #
@app.get("/api/strava-webhook")
async def verify(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        return JSONResponse({"hub.challenge": hub_challenge})
    return JSONResponse({"error": "invalid verify token"}, status_code=400)

# === MAIN HANDLER === #
@app.post("/api/strava-webhook")
async def webhook(request: Request):
    payload = await request.json()
    logging.info(f"📬 Received Strava webhook: {json.dumps(payload)}")

    if payload.get("object_type") != "activity":
        return PlainTextResponse("ignored", status_code=200)

    activity_id = payload.get("object_id")
    aspect_type = payload.get("aspect_type")

    if not activity_id:
        return PlainTextResponse("no activity id", status_code=400)

    # === Duplikatkontroll === #
    key = f"{activity_id}-{aspect_type}"
    if key in processed_activities:
        logging.info(f"⏳ Duplicate activity {activity_id}, skipping.")
        return PlainTextResponse("duplicate", status_code=200)
    processed_activities.add(key)

    # === Hent token automatisk === #
    token = await get_strava_token()
    if not token:
        logging.error("❌ Ingen gyldig token tilgjengelig.")
        return PlainTextResponse("token missing", status_code=401)

    # === Hent aktivitet === #
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://www.strava.com/api/v3/activities/{activity_id}",
                             headers={"Authorization": f"Bearer {token}"})
        logging.info(f"➡️ GET-status: {r.status_code}")
        if r.status_code != 200:
            logging.error(f"❌ Kunne ikke hente aktivitet: {r.text}")
            return PlainTextResponse("fetch failed", status_code=r.status_code)

        # === Oppdater med tilfeldig par === #
        pair = get_random_pair()
        update_payload = {"name": pair["title"], "description": pair["description"]}
        logging.info(f"📝 Oppdaterer aktivitet {activity_id} med: {update_payload}")

        put = await client.put(f"https://www.strava.com/api/v3/activities/{activity_id}",
                               headers={"Authorization": f"Bearer {token}"},
                               data=update_payload)
        logging.info(f"✅ Oppdateringsstatus {put.status_code}: {put.text[:200]}")

    return PlainTextResponse("OK", status_code=200)
