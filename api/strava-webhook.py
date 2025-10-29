# api/strava-webhook.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import os
import httpx
import random
import json
import datetime
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# === KONFIGURASJON === #
VERIFY_TOKEN = "mystravaisgarbage"
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")

# === DUPLIKAT-GUARD (enkel minne-cache) === #
processed_activities = set()

# === TITTEL OG BESKRIVELSER (forkortet for eksempel, du har hele lista) === #
titles_and_descriptions = [
    {"title": "Jeg trodde pushups var noe man kjøper på Rema.",
     "description": "Forventningsavvik mellom produkt og aktivitet dokumentert. Ingen videre oppfølging nødvendig."},
    {"title": "Det er ikke kroppen min som sliter, det er sjela.",
     "description": "Subjektiv opplevelse av utmattelse registrert. Fysisk kapasitet vurderes som tilfredsstillende."},
    {"title": "Det ser flatt ut på kartet, men kartet lyver!",
     "description": "Avvik mellom kartgrunnlag og faktisk høydeprofil bekreftet."},
    {"title": "Jeg meldte meg på for utsikten, ikke for å dø.",
     "description": "Forventningsavvik mellom motivasjon og terreng dokumentert. Saken anses lukket."},
    {"title": "Dette er ikke tur – dette er terapi med bakker.",
     "description": "Tiltaket klassifiseres som egeninitiert rehabilitering med fysisk komponent."},
]

# === RANDOM FUNKSJON === #
def get_random_pair():
    return random.choice(titles_and_descriptions)

# === TOKEN REFRESH === #
async def refresh_strava_token():
    if not all([STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN]):
        logging.error("❌ Mangler STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN i miljøvariabler.")
        return None
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": STRAVA_REFRESH_TOKEN
            }
        )
        if r.status_code == 200:
            data = r.json()
            os.environ["STRAVA_ACCESS_TOKEN"] = data["access_token"]
            logging.info(f"✅ Nytt Strava-token gyldig til {datetime.datetime.utcfromtimestamp(data['expires_at'])}")
            return data["access_token"]
        logging.error(f"⚠️ Feil ved token-refresh: {r.text}")
        return None

# === STRAVA WEBHOOK VERIFY === #
@app.get("/api/strava-webhook")
async def verify(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        return JSONResponse({"hub.challenge": hub_challenge})
    return JSONResponse({"error": "invalid verify token"}, status_code=400)

# === HOVED WEBHOOK === #
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

    # === DUPLIKAT-GUARD === #
    key = f"{activity_id}-{aspect_type}"
    if key in processed_activities:
        logging.info(f"⏳ Duplicate activity {activity_id}, skipping.")
        return PlainTextResponse("duplicate", status_code=200)
    processed_activities.add(key)

    # === HENT TOKEN === #
    token = os.environ.get("STRAVA_ACCESS_TOKEN") or await refresh_strava_token()
    if not token:
        return PlainTextResponse("token missing", status_code=401)

    # === HENT AKTIVITET === #
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://www.strava.com/api/v3/activities/{activity_id}",
                             headers={"Authorization": f"Bearer {token}"})
        logging.info(f"➡️ GET-status: {r.status_code}")
        if r.status_code != 200:
            logging.error(f"❌ Kunne ikke hente aktivitet: {r.text}")
            return PlainTextResponse("fetch failed", status_code=r.status_code)

        # === VELG TILFELDIG TITTEL OG BESKRIVELSE === #
        pair = get_random_pair()
        update_payload = {"name": pair["title"], "description": pair["description"]}
        logging.info(f"📝 Oppdaterer aktivitet {activity_id} med: {update_payload}")

        # === OPPDATER STRAVA === #
        put = await client.put(f"https://www.strava.com/api/v3/activities/{activity_id}",
                               headers={"Authorization": f"Bearer {token}"},
                               data=update_payload)
        logging.info(f"✅ Oppdateringsstatus {put.status_code}: {put.text[:200]}")

    return PlainTextResponse("OK", status_code=200)
