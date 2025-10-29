from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx, os, json, random, logging, time
from datetime import datetime, timedelta

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# -----------------------------
# Config / Environment
# -----------------------------
VERIFY_TOKEN = "mystravaisgarbage"
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")

# -----------------------------
# Token auto-refresh
# -----------------------------
def get_valid_token():
    global STRAVA_ACCESS_TOKEN
    now = time.time()
    expires_at = getattr(get_valid_token, "expires_at", 0)

    if not STRAVA_ACCESS_TOKEN or now > (expires_at - 300):
        if not all([STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN]):
            logging.error("❌ Missing STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN in env; cannot refresh token.")
            return STRAVA_ACCESS_TOKEN

        logging.info("🔁 Refreshing Strava access token…")
        try:
            resp = httpx.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": STRAVA_CLIENT_ID,
                    "client_secret": STRAVA_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": STRAVA_REFRESH_TOKEN,
                },
                timeout=12,
            )
            resp.raise_for_status()
            data = resp.json()
            STRAVA_ACCESS_TOKEN = data["access_token"]
            get_valid_token.expires_at = data["expires_at"]
            logging.info(f"✅ New Strava token valid until {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(data['expires_at']))} UTC")
        except Exception as e:
            logging.error(f"💥 Failed to refresh Strava token: {e}")
    return STRAVA_ACCESS_TOKEN


# -----------------------------
# New Title & Description Banks
# -----------------------------
TITLE_BANK = [
    "Jeg trodde pushups var noe man kjøper på Rema.",
    "Det er ikke kroppen min som sliter, det er sjela.",
    "Jeg har aldri vært så sliten uten å ha hatt det gøy.",
    "Jeg har mer respekt for uniformer nå.",
    "Jeg visste ikke man kunne svette der.",
    "Jeg prøvde å gjemme meg bak en busk.",
    "Reveleir sitter i ryggraden.",
    "Jeg har aldri savnet søvn så mye.",
    "Det verste er ikke å løpe – det er å rope.",
    "Dette er karakterbygging med blåmerker.",
    "Jeg meldte meg på for utsikten, ikke for å dø.",
    "Jeg må puste med beina nå.",
    "Det ser flatt ut på kartet, men kartet lyver!",
    "Jeg skjønner hvorfor fjellfolk er stille – de sparer oksygen.",
    "Dette er ikke tur – dette er terapi med bakker.",
    "Jeg har fått gnagsår på sjelen.",
    "Jeg har ikke kondis, jeg har karisma.",
    "Jeg vurderte å gi opp, men så kom kameraet.",
    "Jeg trodde Nordkapp lå i Sverige.",
    "Det er vinden som trener oss.",
    "Tarzan uten muskler.",
    "Er dette all inclusive, eller koster vannet ekstra?",
    "Jeg kom for å slappe av, men ble solbrent, blakk og forelska.",
    "Alt går bra med sol og saus.",
    "Jeg blir brun inni.",
    "Jeg følte det på hele stemningen.",
    "Det var et slags ubehag der.",
    "Dette er et kunstprosjekt.",
    "Ingen forstår meg, og det er meninga.",
    "Det er et konsept mer enn en idé.",
    "La det marinere litt.",
    "Det er en slags kommentar til samtida.",
    "Jeg liker at det er litt ubehagelig.",
    "Dette er vondt, men riktig.",
    "Vi skal videre i prosessen.",
    "Nei, nei, nei!",
    "Næmmen, hallo i luken!",
    "Jaja, neida, så...",
    "Karl, nå må du roe neppa!",
    "Det der går ikke, Nils.",
    "Nils, du er ikke helt god!",
    "Jeg har ikke tid til dette tullet!",
    "Det er ikke lett å være Karl.",
    "Noen må gå.",
    "Jeg vil ha ro og orden!",
    "Du, jeg er så lei av dette her nå.",
    "Jeg er ikke sint, jeg er skuffa.",
    "Nils, sett ned den ølen!"
]

DESC_BANK = [
    "Livet er et lære, man må alltid lære.",
    "Jeg bærer ikke noe gnag.",
    "Every strong man is a strong woman.",
    "Det er noe skurr i mosen.",
    "Det har luktet pølse i fem dager nå.",
    "Foreløpig er jeg Bosman-spiller.",
    "Jeg ville aldri svikta deg i ryggen.",
    "Einstein fant opp graviditeten.",
    "Det er lite sjømat i sushi.",
    "Jeg skal spille litt dum – det kommer naturlig.",
    "Jeg er 99 % vann og 1 % problemer.",
    "Jeg vil ikke ha drama, men jeg er drama.",
    "Han er som en kebab – fristende, men jeg angrer i morgen.",
    "Jeg er ikke sjalu, jeg bare hater å se deg puste med noen andre.",
    "Vi har et spirituelt bånd – derfor stalker jeg ham.",
    "En ku er bare en stor gresshund.",
    "Dette blir det møte på i tinget.",
    "Jeg prøver å finne roen, men den gjemmer seg i fjøset.",
    "Melka smaker innsats.",
    "Han oppfører seg som om han har arvet gården.",
    "Det er ikke lett å være ydmyk når man melker best.",
    "Dugnaden er obligatorisk.",
    "Dette er 1800-tallet med kamerateam.",
    "Jeg er her for å overleve uten strøm.",
    "Det er mye drit i gjødsla, for å si det sånn.",
    "Vi kan snakke om det – passiv-aggressivt.",
    "Du, det er ikke en konkurranse… men jeg vinner.",
    "Vi resirkulerer følelser og glass.",
    "Hage er politikk.",
    "Vi tar det på facebook-gruppa.",
    "Det er ikke lov med trampoliner i hjertet.",
    "Jeg blir glad på en ryddig måte.",
    "Vi later som vi koser oss.",
    "Oppgaven er enkel, men umulig.",
    "Du må ikke si et ord – men forklare alt.",
    "Reglene er klare, men uklare.",
    "Dette ser jo lett ut… helt til det er din tur.",
    "Tiden starter nå.",
    "Det var kreativt – og fullstendig feil.",
    "Jeg elsker kaoset ditt.",
    "Dommeren er nådeløs.",
    "Det var pent, men ikke poenggivende.",
    "Du løste oppgaven. På en måte.",
    "Det er en skandale uten sidestykke!",
    "Vi skal til fakta, men først: litt følelser.",
    "Jeg er ikke sint, jeg bare roper.",
    "Dette er humor med bismak.",
    "Nå ble det dårlig stemning.",
    "Vi tar en kort pause fra virkeligheten.",
    "Jeg bor her, jeg!",
    "Det blir ikke noe kos i kveld.",
    "Det er min sofa!",
    "Nils! Døra!",
    "Dette er ikke et kollektiv!",
    "Jeg hater folk uten nøkkel!",
    "Hvem er det som ringer nå igjen?",
    "Ta av deg skoene!",
    "Det er forbudt å ha det gøy her!",
    "Det var ikke det jeg sa!",
    "Ikke rør mine ting!",
    "Det er min postkasse!",
    "Hvorfor skjer dette alltid meg?"
]

def pick_quote():
    t = random.choice(TITLE_BANK)
    d = random.choice(DESC_BANK)
    logging.info(f"🧪 Selected title: {t}")
    logging.info(f"🧪 Selected desc: {d[:100]}…")
    return {"title": t, "description": d}


# -----------------------------
# Duplicate guard
# -----------------------------
recent_updates = {}
def already_processed(activity_id):
    now = datetime.utcnow()
    last = recent_updates.get(activity_id)
    if last and (now - last) < timedelta(minutes=5):
        return True
    recent_updates[activity_id] = now
    return False


# -----------------------------
# Webhook verify
# -----------------------------
@app.get("/api/strava-webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logging.info("✅ Webhook verified")
        return JSONResponse({"hub.challenge": challenge})
    return JSONResponse({"error": "invalid verify token"}, status_code=400)


# -----------------------------
# Webhook handler
# -----------------------------
@app.post("/api/strava-webhook")
async def handle_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    logging.info(f"📬 Received Strava webhook: {json.dumps(payload)}")

    if payload.get("object_type") != "activity":
        return PlainTextResponse("ignored", status_code=200)

    aspect = payload.get("aspect_type")
    activity_id = payload.get("object_id")

    if already_processed(activity_id):
        logging.info(f"⏳ Duplicate activity {activity_id}, skipping.")
        return PlainTextResponse("duplicate", status_code=200)

    if aspect not in ("create", "update"):
        return PlainTextResponse("ignored", status_code=200)

    async with httpx.AsyncClient(timeout=15) as client:
        headers = {"Authorization": f"Bearer {get_valid_token()}"}
        r = await client.get(f"https://www.strava.com/api/v3/activities/{activity_id}", headers=headers)
        logging.info(f"➡️ GET-status: {r.status_code}")
        if r.status_code != 200:
            logging.error(f"❌ Unable to fetch activity: {r.text}")
            return PlainTextResponse("GET failed", status_code=r.status_code)

        td = pick_quote()
        update_data = {
            "name": td["title"],
            "description": td["description"],
        }

        logging.info(f"📝 PUT payload: {json.dumps(update_data, ensure_ascii=False)[:240]}")

        put = await client.put(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers=headers,
            data=update_data,
        )
        logging.info(f"✅ Updated activity {activity_id}: {put.status_code} — {put.text[:200]}")

    return PlainTextResponse("OK", status_code=200)
