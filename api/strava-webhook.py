from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import os
import json
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# Environment variables
VERIFY_TOKEN = "mystravaisgarbage"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")

def generate_prompt(activity_name, distance_km, moving_time_min):
    return f"""You are a sarcastic, over-the-top running influencer (like subreddit RunningCircleJerk and YaboyScottJurek).
Create a fun title and description for this run:

- Original activity name: {activity_name}
- Distance (km): {distance_km}
- Moving time (minutes): {moving_time_min}

Respond in JSON format: {{'title':'...', 'description':'...'}}"""

async def call_openai(prompt: str):
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        payload = {
            "model": "gpt-4-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.9,
            "max_tokens": 120
        }
        try:
            r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return json.loads(data["choices"][0]["message"]["content"])
        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            return {"title": "Epic Run", "description": "No description generated"}

@app.get("/api/strava-webhook")
async def verify_webhook(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")
    if hub_mode == "subscribe" and hub_token == VERIFY_TOKEN:
        return JSONResponse(content={"hub.challenge": hub_challenge}, status_code=200)
    return JSONResponse(content={"error": "invalid verify token"}, status_code=400)

@app.post("/api/strava-webhook")
async def handle_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON"}, status_code=400)

    logging.info(f"Received Strava webhook: {json.dumps(payload)}")

    if payload.get("object_type") == "activity" and payload.get("aspect_type") == "create":
        activity_id = payload.get("object_id")
        if not STRAVA_ACCESS_TOKEN:
            logging.error("STRAVA_ACCESS_TOKEN not set")
            return PlainTextResponse("Missing Strava token", status_code=500)

        async with httpx.AsyncClient() as client:
            try:
                # Fetch activity details
                r = await client.get(
                    f"https://www.strava.com/api/v3/activities/{activity_id}",
                    headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
                )
                r.raise_for_status()
                activity = r.json()
                name = activity.get("name", "Unnamed Run")
                distance_km = round(activity.get("distance", 0) / 1000, 2)
                moving_time_min = round(activity.get("moving_time", 0) / 60, 1)

                # Generate sarcastic title/description
                prompt = generate_prompt(name, distance_km, moving_time_min)
                title_desc = await call_openai(prompt)

                # Update activity
                update_resp = await client.put(
                    f"https://www.strava.com/api/v3/activities/{activity_id}",
                    headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"},
                    data={
                        "name": title_desc.get("title", name),
                        "description": title_desc.get("description", "")
                    }
                )
                logging.info(f"Updated activity {activity_id}: {update_resp.status_code}")
            except httpx.HTTPStatusError as e:
                logging.error(f"Strava API error: {e.response.status_code} {e.response.text}")
            except Exception as e:
                logging.error(f"Unexpected error: {e}")

    return PlainTextResponse("OK", status_code=200)
