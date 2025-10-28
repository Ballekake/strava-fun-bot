from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx, os, json, random, logging
from datetime import datetime, timedelta

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
VERIFY_TOKEN = "mystravaisgarbage"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# ---------------------------------------------------------------------
# FALLBACK TITLES & DESCRIPTIONS
# ---------------------------------------------------------------------
FALLBACK_TITLES = [
    "Det finnes ikke snarveier i motbakke",
    "Jeg fant ikke stien, så jeg lagde en",
    "Stillheten er aldri feil",
    "Kaffen smaker best på toppen",
    "I dag løp jeg meg selv igjen",
    "Hadde jeg visst hvor langt det var, hadde jeg løpt lenger",
    "Ikke alle som går seg bort, er tapt",
    "En fot foran den andre – alltid",
    "Når svetten svir, vet du at du lever",
    "Ingen dekning, ingen bekymring"
]

FALLBACK_DESCRIPTIONS = [
    "Jeg gikk, som Peer Gynt, og fant meg selv i villmarkens favn.",
    "Fjellet talte, og jeg måtte tie. I stillheten fant jeg alt jeg søkte.",
    "Det som ikke lar seg skrive, må løpes.",
    "Som Brand sa: Alt eller intet – og i dag ble det alt.",
    "Man må miste stien for å finne seg selv igjen, sa jeg – og gjorde det.",
    "Skodden lettet, og med den mitt sinn. Naturen tok meg tilbake.",
    "Det var ikke målet, men reisen, som skrev historien.",
    "Et løp som et Ibsensk drama – fullt av smerte, ærlighet og svette.",
    "Jeg løp ut av byen og inn i et dikt.",
    "Som Nora forlot dukkehjemmet, forlot jeg asfalten."
]

def fallback_monsen_ibsen():
    """Return a random fallback title + description."""
    return {
        "title": random.choice(FALLBACK_TITLES),
        "description": random.choice(FALLBACK_DESCRIPTIONS)
    }

# ---------------------------------------------------------------------
# RECENT UPDATE CACHE
# ---------------------------------------------------------------------
recent_updates = {}
def already_processed(activity_id):
    now = datetime.utcnow()
    if activity_id in recent_updates and (now - recent_updates[activity_id]) < timedelta(minutes=5):
        return True
    recent_updates[activity_id] = now
    return False

# ---------------------------------------------------------------------
# OPENAI GENERATION
# ---------------------------------------------------------------------
async def call_openai(prompt: str):
    if not OPENAI_API_KEY:
        logging.warning("OPENAI_API_KEY missing, using fallback.")
        return fallback_monsen_ibsen()

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.95,
        "max_tokens": 300
    }

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(OPENAI_URL, headers=headers, json=payload)
            logging.info(f"OpenAI response: {r.status_code}")
            if r.status_code != 200:
                logging.warning(f"OpenAI error {r.status_code}: {r.text[:150]}")
                return fallback_monsen_ibsen()

            data = r.json()
            content = data["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(content)
                return parsed
            except json.JSONDecodeError:
                return {
                    "title": content.strip().split("\n")[0][:60],
                    "description": content.strip()
                }

        except Exception as e:
            logging.error(f"OpenAI call failed: {e}")
            return fallback_monsen_ibsen()

# ---------------------------------------------------------------------
# PROMPT GENERATOR
# ---------------------------------------------------------------------
def generate_prompt(name, distance_km, moving_time_min):
    tone = "kort og dramatisk" if distance_km < 10 else "eksistensiell og naturromantisk"
    return f"""
Du er en blanding av Lars Monsen og Henrik Ibsen.
Lag et kort JSON-objekt med en tittel (Monsen-sitat) og en beskrivelse (Ibsensk språk på norsk).
Kontekst:
- Original tittel: {name}
- Distanse: {distance_km} km
- Tid: {moving_time_min} min
Tonen skal være {tone}.
Returner gyldig JSON: {{ "title": "...", "description": "..." }}
"""

# ---------------------------------------------------------------------
# STRAVA HANDLERS
# ---------------------------------------------------------------------
@app.get("/api/strava-webhook")
async def verify_webhook(request: Request):
    if (
        request.query_params.get("hub.mode") == "subscribe"
        and request.query_params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return JSONResponse({"hub.challenge": request.query_params.get("hub.challenge")})
    return JSONResponse({"error": "invalid verify token"}, status_code=400)

@app.post("/api/strava-webhook")
async def handle_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    logging.info(f"Received Strava webhook: {json.dumps(payload)}")
    if payload.get("object_type") != "activity":
        return PlainTextResponse("ignored", status_code=200)

    activity_id = payload.get("object_id")
    aspect = payload.get("aspect_type")

    if already_processed(activity_id):
        return PlainTextResponse("duplicate", status_code=200)

    if aspect not in ("create", "update"):
        return PlainTextResponse("ignored", status_code=200)

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
        )

        if r.status_code != 200:
            logging.warning(f"Failed to fetch activity: {r.status_code}")
            title_desc = fallback_monsen_ibsen()
        else:
            activity = r.json()
            name = activity.get("name", "Uten tittel")
            distance_km = round(activity.get("distance", 0) / 1000, 2)
            moving_time_min = round(activity.get("moving_time", 0) / 60, 1)
            prompt = generate_prompt(name, distance_km, moving_time_min)
            title_desc = await call_openai(prompt)

        update_data = {
            "name": title_desc.get("title", "Uten tittel"),
            "description": title_desc.get("description", "")
        }

        put_resp = await client.put(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"},
            data=update_data
        )
        logging.info(f"Updated activity {activity_id}: {put_resp.status_code}")

    return PlainTextResponse("OK", status_code=200)
