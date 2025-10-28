from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import os
import json
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

VERIFY_TOKEN = "mystravaisgarbage"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")

# ---------------------------------------------------------------------
# PROMPT GENERATOR
# ---------------------------------------------------------------------
def generate_prompt(activity_name, distance_km, moving_time_min):
    return f"""
You are a Norwegian cultural mash-up machine.

For each Strava activity, create:
- "title": a short rugged outdoors quote (max 12 words) that sounds like it came from **Lars Monsen** —
  something about wilderness, endurance, storms, solitude, or adventure.
- "description": a short paragraph (2–4 sentences) written in the tone and style of **Henrik Ibsen** —
  introspective, dramatic, exploring the struggle of man versus nature and self.

Context:
- Original title: {activity_name}
- Distance: {distance_km} km
- Moving time: {moving_time_min} minutes

Return ONLY valid JSON:
{{
  "title": "...",
  "description": "..."
}}
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
            logging.info(f"OpenAI response: {content}")

            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logging.warning("⚠ OpenAI returned non-JSON text, wrapping manually.")
                return {"title": content.strip().split("\n")[0][:60],
                        "description": content.strip()}

        except httpx.HTTPStatusError as e:
            logging.error(f"OpenAI API error: {e.response.status_code} {e.response.text}")
        except Exception as e:
            logging.error(f"Unexpected OpenAI error: {e}")

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

    logging.info(f"📬 Received Strava webhook: {json.dumps(payload)}")

    if payload.get("object_type") == "activity" and payload.get("aspect_type") in ("create", "update"):
        activity_id = payload.get("object_id")

        if not STRAVA_ACCESS_TOKEN:
            logging.error("🚫 STRAVA_ACCESS_TOKEN missing")
            return PlainTextResponse("Missing Strava token", status_code=500)

        async with httpx.AsyncClient() as client:
            try:
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
                logging.info(f"🎨 Generated: {title_desc}")

                update_resp = await client.put(
                    f"https://www.strava.com/api/v3/activities/{activity_id}",
                    headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"},
                    data={
                        "name": title_desc.get("title", name),
                        "description": title_desc.get("description", "")
                    }
                )
                logging.info(f"✅ Updated activity {activity_id}: {update_resp.status_code}")

            except httpx.HTTPStatusError as e:
                logging.error(f"❌ Strava API error: {e.response.status_code} {e.response.text}")
            except Exception as e:
                logging.error(f"💥 Unexpected Strava error: {e}")

    return PlainTextResponse("OK", status_code=200)
