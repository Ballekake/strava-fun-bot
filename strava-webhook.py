from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx
import os
import json

app = FastAPI()

# Environment variables
VERIFY_TOKEN = "mystravaisgarbage"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")

# Generate sarcastic prompt
def generate_sarcastic_title_desc(activity_name, distance_km, moving_time_min):
    prompt = f"""You are a sarcastic, over-the-top running influencer (like subreddit RunningCircleJerk and YaboyScottJurek).
Create a fun title and description for this run:

- Original activity name: {activity_name}
- Distance (km): {distance_km}
- Moving time (minutes): {moving_time_min}

Respond in JSON format: {{ "title": "...", "description": "..." }}"""
    return prompt

# Call OpenAI GPT-4-mini
async def call_openai(prompt):
    async with httpx.AsyncClient() as client:
        headers = {'Authorization': f'Bearer {OPENAI_API_KEY}'}
        json_data = {
            'model': 'gpt-4-mini',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.9,
            'max_tokens': 120
        }
        try:
            r = await client.post('https://api.openai.com/v1/chat/completions', headers=headers, json=json_data)
            r.raise_for_status()
            data = r.json()
            content = data['choices'][0]['message']['content'].replace("'", '"')
            return json.loads(content)
        except Exception as e:
            print("OpenAI error:", e)
            return {'title': 'Epic Run', 'description': 'No description generated'}

# Strava webhook verification
@app.get('/api/strava-webhook')
async def strava_verify(request: Request):
    hub_mode = request.query_params.get('hub.mode')
    hub_token = request.query_params.get('hub.verify_token')
    hub_challenge = request.query_params.get('hub.challenge')

    if hub_mode == 'subscribe' and hub_token == VERIFY_TOKEN:
        return JSONResponse(content={'hub.challenge': hub_challenge}, status_code=200)
    return JSONResponse(content={'error': 'invalid verify token'}, status_code=400)

# Strava webhook event handler
@app.post('/api/strava-webhook')
async def strava_event(request: Request):
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(content={'error': 'Invalid JSON'}, status_code=400)

    print('Received Strava webhook event:', json.dumps(payload, indent=2))

    # Only handle new activities
    if payload.get('object_type') == 'activity' and payload.get('aspect_type') == 'create':
        activity_id = payload.get('object_id')

        if STRAVA_ACCESS_TOKEN:
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(
                        f'https://www.strava.com/api/v3/activities/{activity_id}',
                        headers={'Authorization': f'Bearer {STRAVA_ACCESS_TOKEN}'}
                    )
                    r.raise_for_status()
                    activity = r.json()
                    name = activity.get('name', 'Unnamed Run')
                    distance_km = round(activity.get('distance', 0)/1000, 2)
                    moving_time_min = round(activity.get('moving_time', 0)/60, 1)

                    # Generate sarcastic title/description
                    prompt = generate_sarcastic_title_desc(name, distance_km, moving_time_min)
                    title_desc = await call_openai(prompt)

                    # Update activity on Strava
                    update_data = {
                        'name': title_desc.get('title', name),
                        'description': title_desc.get('description', '')
                    }
                    update_resp = await client.put(
                        f'https://www.strava.com/api/v3/activities/{activity_id}',
                        headers={'Authorization': f'Bearer {STRAVA_ACCESS_TOKEN}'},
                        json=update_data
                    )
                    print('Updated activity:', update_resp.status_code, update_resp.text)
            except Exception as e:
                print("Error fetching/updating Strava activity:", e)

    return PlainTextResponse('OK', status_code=200)
