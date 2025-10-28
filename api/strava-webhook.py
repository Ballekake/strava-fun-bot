from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import os
import json
import logging
import random
from datetime import datetime, timedelta

app = FastAPI()
logging.basicConfig(level=logging.INFO)

VERIFY_TOKEN = "mystravaisgarbage"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")

# ---------------------------------------------------------------------
# SIMPLE MEMORY CACHE to prevent duplicate processing
# ---------------------------------------------------------------------
recent_updates = {}  # {activity_id: timestamp}

def already_processed(activity_id):
    now = datetime.utcnow()
    last = recent_updates.get(activity_id)
    if last and (now - last) < timedelta(minutes=5):
        return True
    recent_updates[activity_id] = now
    return False

# ---------------------------------------------------------------------
# MONSEN QUOTES
# ---------------------------------------------------------------------
MONSEN_QUOTES = [
    "Det finnes ikke dårlig vær, bare dårlige klær.",
    "Når du er langt ute, finner du deg selv.",
    "Stillheten er aldri tom – den er full av svar.",
    "Fjellet bryr seg ikke om unnskyldninger.",
    "Man lærer lite på asfalt.",
    "Den som fryser, har gjort noe feil.",
    "Et spor i snøen er bedre enn tusen planer."
]

def pick_monsen_quote():
    if random.random() < 0.7:
        return random.choice(MONSEN_QUOTES)
    return None  # fall back to AI generation

# ---------------------------------------------------------------------
# PROMPT GENERATOR (distance-based Ibsen in Norwegian)
# ---------------------------------------------------------------------
def generate_prompt(activity_name, distance_km, moving_time_min):
    if distance_km < 5:
        tone = "kort, ironisk refleksjon over hverdagens slit og små ambisjoner"
    elif distance_km < 15:
        tone = "dramatisk monolog om selvransakelse, frihet og naturens ubarmhjertighet"
    else:
        tone = "eksistensiell og storslått refleksjon om menneskets kamp mot skjebnen og fjellets evighet"

    real_quote = pick_monsen_quote()
    if real_quote:
        return f"""
Du skal KUN skrive Ibsen-delen. Tittelen er allerede bestemt:
"{real_quote}"

Lag en kort tekst (2–5 setninger) i stilen til Henrik Ibsen på norsk.
Tonen skal være {tone}.
Returner gyldig JSON:
{{
  "title": "{real_quote}",
  "description": "..."
}}
"""
    # fallback: let AI invent both
    return f"""
Lag følgende på norsk:
- "title": Et kort, barskt sitat i Lars Monsens ånd (maks 10 ord)
- "description": En tekst (2–5 setninger) i Henrik Ibsens stil, {tone}.
Kontekst:
- Original tittel: {activity_name}
- Distanse: {distance_km} km
- Bevegelsestid: {moving_time_min} min
Returner gyldig JSON:
{{ "title": "...", "description": "..." }}
"""

# ---------------------------------------------------------------------
# OPENAI CALL
# ---------------------------------------------------------------------
async def call_openai(prompt: str):
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.95,
            "max_tokens": 300,
        }
        try:
            r = await client.post("https://api.openai.com/v1/chat/completions",
                                  headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            logging.info(f"🧠 OpenAI response: {content}")

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logging.warning("⚠ OpenAI returnerte ikke gyldig JSON, pakker manuelt.")
                return {
                    "title": content.strip().split("\n")[0][:60],
                    "description": content.strip()
                }

        except Exception as e:
            logging.error(f"OpenAI-feil: {e}")
            return {"title": "Monsen på villspor", "description": "Ingen Ibsen i sikte."}

# ---------------------------------------------------------------------
# STRAVA WEBHOOK VERIFICATION
# ---------------------------------------------------------------------
@app.get("/api/strava-webhook")
async def verify_webhook(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        return JSONResponse(content={"hub.challenge": hub_challenge}, status_code=200)
    return JSONResponse(content={"error": "invalid verify token"}, status_code=400)

# ---------------------------------------------------------------------
# STRAVA WEBHOOK HANDLER
# ---------------------------------------------------------------------
@app.post("/api/strava-webhook")
async def handle_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON"}, status_code=400)

    logging.info(f"📬 Mottok Strava-webhook: {json.dumps(payload)}")

    if payload.get("object_type") != "activity":
        return PlainTextResponse("Ignored", status_code=200)

    aspect = payload.get("aspect_type")
    activity_id = payload.get("object_id")
    updates = payload.get("updates", {})

    # Prevent spamming same activity repeatedly
    if already_processed(activity_id):
        logging.info(f"⏳ Hopper over duplikat for aktivitet {activity_id}")
        return PlainTextResponse("Duplicate ignored", status_code=200)

    if aspect not in ("create", "update"):
        logging.info(f"⚪ Uventet aspekt {aspect}, ignorerer.")
        return PlainTextResponse("Ignored", status_code=200)

    # Even empty updates trigger generation now
    logging.info(f"🔄 Behandler aktivitet {activity_id} ({aspect}) ...")

    if not STRAVA_ACCESS_TOKEN:
        logging.error("🚫 STRAVA_ACCESS_TOKEN mangler")
        return PlainTextResponse("Missing Strava token", status_code=500)

    async with httpx.AsyncClient() as client:
        try:
            # Hent aktivitet
            r = await client.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
            )
            r.raise_for_status()
            activity = r.json()
            name = activity.get("name", "Uten tittel")
            distance_km = round(activity.get("distance", 0) / 1000, 2)
            moving_time_min = round(activity.get("moving_time", 0) / 60, 1)

            prompt = generate_prompt(name, distance_km, moving_time_min)
            title_desc = await call_openai(prompt)
            logging.info(f"🎨 Generert: {title_desc}")

            update_resp = await client.put(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"},
                data={
                    "name": title_desc.get("title", name),
                    "description": title_desc.get("description", "")
                }
            )
            logging.info(f"✅ Oppdatert aktivitet {activity_id}: {update_resp.status_code}")

        except httpx.HTTPStatusError as e:
            logging.error(f"❌ Strava API-feil: {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.error(f"💥 Uventet Strava-feil: {e}")

    return PlainTextResponse("OK", status_code=200)
