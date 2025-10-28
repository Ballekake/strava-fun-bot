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

# ---------------------------------------------------------------------
# CONFIG & ENVIRONMENT
# ---------------------------------------------------------------------
VERIFY_TOKEN = "mystravaisgarbage"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

if not OPENAI_API_KEY:
    logging.error("❌ OPENAI_API_KEY missing in environment.")
else:
    logging.info("✅ OPENAI_API_KEY found.")

if not STRAVA_ACCESS_TOKEN:
    logging.error("❌ STRAVA_ACCESS_TOKEN missing in environment.")
else:
    logging.info(f"✅ STRAVA_ACCESS_TOKEN found: {STRAVA_ACCESS_TOKEN[:6]}... (hidden)")

# ---------------------------------------------------------------------
# CACHE TO PREVENT DUPLICATES
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
    return None  # fallback to AI

# ---------------------------------------------------------------------
# PROMPT GENERATOR
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
    # fallback: AI generates both
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
    if not OPENAI_API_KEY:
        logging.error("❌ OPENAI_API_KEY missing; skipping generation.")
        return {"title": "Monsen på villspor", "description": "Ingen Ibsen i sikte."}

    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.95,
            "max_tokens": 300,
        }
        logging.info(f"Auth header sample: {headers['Authorization'][:12]}...")

        try:
            r = await client.post(OPENAI_URL, headers=headers, json=payload)
            logging.info(f"➡️ OpenAI POST-status: {r.status_code}")
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            logging.info(f"🧠 OpenAI response: {content}")

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logging.warning("⚠ OpenAI returned non-JSON text, fallback.")
                return {
                    "title": content.strip().split("\n")[0][:60],
                    "description": content.strip()
                }

        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
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
        logging.info("✅ Strava webhook verified.")
        return JSONResponse(content={"hub.challenge": hub_challenge}, status_code=200)
    logging.error("❌ Invalid verify token from Strava.")
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

    logging.info(f"📬 Received Strava webhook: {json.dumps(payload)}")

    if payload.get("object_type") != "activity":
        logging.info("⚪ Not an activity, ignoring.")
        return PlainTextResponse("Ignored", status_code=200)

    aspect = payload.get("aspect_type")
    activity_id = payload.get("object_id")
    updates = payload.get("updates", {})

    if already_processed(activity_id):
        logging.info(f"⏳ Duplicate activity {activity_id}, skipping.")
        return PlainTextResponse("Duplicate ignored", status_code=200)

    if aspect not in ("create", "update"):
        logging.info(f"⚪ Unexpected aspect {aspect}, ignoring.")
        return PlainTextResponse("Ignored", status_code=200)

    logging.info(f"🔄 Processing activity {activity_id} ({aspect}) ...")

    if not STRAVA_ACCESS_TOKEN:
        logging.error("🚫 STRAVA_ACCESS_TOKEN missing.")
        return PlainTextResponse("Missing Strava token", status_code=500)
    else:
        logging.info(f"🔑 STRAVA_ACCESS_TOKEN found: {STRAVA_ACCESS_TOKEN[:6]}...")

    async with httpx.AsyncClient() as client:
        try:
            # GET ACTIVITY
            r = await client.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
            )
            logging.info(f"➡️ GET-status: {r.status_code}")
            if r.status_code != 200:
                logging.error(f"❌ Unable to fetch activity: {r.text}")
                return PlainTextResponse("GET failed", status_code=r.status_code)

            activity = r.json()
            name = activity.get("name", "Uten tittel")
            distance_km = round(activity.get("distance", 0) / 1000, 2)
            moving_time_min = round(activity.get("moving_time", 0) / 60, 1)

            prompt = generate_prompt(name, distance_km, moving_time_min)
            title_desc = await call_openai(prompt)
            logging.info(f"🎨 Generated: {title_desc}")

            logging.info(f"📝 Updating: {title_desc.get('title', name)} / {title_desc.get('description', '')[:60]}...")

            update_resp = await client.put(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"},
                data={
                    "name": title_desc.get("title", name),
                    "description": title_desc.get("description", "")
                }
            )
            logging.info(f"✅ Updated activity {activity_id}: {update_resp.status_code}")
            logging.info(f"➡️ PUT-response: {update_resp.text}")

        except Exception as e:
            logging.error(f"💥 Error processing Strava activity: {e}")

    return PlainTextResponse("OK", status_code=200)

# ---------------------------------------------------------------------
# OPENAI DIAGNOSTIC ENDPOINT
# ---------------------------------------------------------------------
@app.get("/api/openai-test")
async def openai_test():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                OPENAI_URL,
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Say hello in Norwegian"}]
                }
            )
            return {"status": r.status_code, "text": r.text[:300]}
        except Exception as e:
            return {"error": str(e)}
