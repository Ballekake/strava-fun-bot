from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import httpx, os, json, random, logging, time
from datetime import datetime, timedelta

app = FastAPI()
logging.basicConfig(level=logging.INFO)

# -----------------------------
# Config / Env
# -----------------------------
VERIFY_TOKEN = "mystravaisgarbage"

STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN")
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")  # initial, will be refreshed

# -----------------------------
# Auto-refreshing Strava token
# -----------------------------
def get_valid_token():
    """
    Returns a valid Strava access token. If unknown/expired (or near expiry),
    it refreshes using the long-lived STRAVA_REFRESH_TOKEN.
    Caches expiry timestamp on the function object.
    """
    global STRAVA_ACCESS_TOKEN
    now = time.time()

    # If we don't know expiry, force a refresh on first call
    expires_at = getattr(get_valid_token, "expires_at", 0)

    # Refresh if <5 min left or token missing
    if not STRAVA_ACCESS_TOKEN or now > (expires_at - 300):
        if not all([STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN]):
            logging.error("❌ Missing STRAVA_CLIENT_ID/SECRET/REFRESH_TOKEN in env; cannot refresh token.")
            return STRAVA_ACCESS_TOKEN  # may be None -> calls will fail; logs make it obvious

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
# Paradise Hotel content banks
# -----------------------------
TITLE_BANK = [
    "Jeg kom hit for å vinne, ikke for å tenke",
    "Strategi? Jeg bare føler meg fram, ass",
    "Han backstabba meg hardere enn kneika på Svolværgeita",
    "Jeg sa jeg var ekte – men jeg løy, bro",
    "Kroppen er på ferie, men hjernen har aldri møtt opp",
    "100 % chill, 0 % konsekvenser",
    "Jeg har aldri vært så forvirra, men jeg elsker drama",
    "Jeg kom som en tiger, men gikk ut som en taco",
    "Det er ikke løgn hvis du sier det med selvtillit",
    "Vi har kjemi, men null oksygen",
    "Alt handler om vibes, ikke verdier",
    "Jeg trenger ikke hjelm – jeg har personlighet",
    "Jeg føler jeg vokste som person, men bare på høyrefoten",
    "Hvis kjærlighet er et spill, så jukser jeg",
    "Jeg skjønner ingenting, men jeg ser bra ut",
    "Vi hadde en connection, men også en kolleksjon av løgner",
    "Jeg angrer ikke, jeg bare reflekterer bakover",
    "Han sa han løp intervaller – men han løp fra følelsene sine",
    "Jeg tror jeg er smart, men kameraet vet bedre",
    "Jeg kom for kjærligheten, men ble for gratis alkohol",
    "Det var ekte til frokosten var over",
    "Ingen plan overlever første shot",
    "Ærlighet varer lengst, men løgn gir bedre TV",
    "Jeg er ikke sint, jeg kommuniserer i capslock",
    "Jeg gikk ikke bak ryggen hans, jeg tok en snarvei",
    "Lagspiller? Bare når jeg leder",
    "Kjærlighet uten strategi er bare svette med musikk",
    "Jeg tenker ikke – jeg opplever",
    "Vi hadde kjemi, timing og tequila (dårlig miks)",
    "Jeg kom som deltaker, drar som advarsel",
    "Jeg er rolig mellom episodene",
    "Han ghosta meg i samme villa – imponerende",
    "Jeg er ikke falsk, bare dårlig på ærlighet i sollys",
    "Det var ikke løgn, det var strategi med sminke",
    "Intens? Kall det karakterutvikling",
    "Jeg er her for kjærlighet, men tar sponsor først",
    "Jeg lærte noe, men glemte det i baren",
    "Hvis lojalitet var en drink, hadde alle vært fulle",
    "Jeg har mer følelser enn sofaen har solkrem",
    "Jeg kom for dramaet, ble for airconditionen",
]

DESC_BANK = [
    "Jeg ble ikke sur fordi han kysset henne, jeg ble sur fordi han sa han ikke skulle kysse noen andre rett etter han kysset henne.",
    "Alle sier jeg spiller spillet, men jeg bare lever livet mitt med kamera og gratis frokostbuffet.",
    "Jeg føler meg ikke falsk, jeg føler meg bare taktisk med følelser.",
    "Hvis han virkelig likte meg, hadde han ikke stemt meg ut mens han holdt meg i hånda.",
    "Det er ikke drama, det er bare ærlighet med volum på 200.",
    "Jeg sa ikke at jeg elsker deg, jeg sa at jeg kunne se for meg å kanskje elske deg om to episoder.",
    "Jeg er ikke her for å vinne, jeg er her for å bevise at jeg kan tape med stil.",
    "Han sier jeg er toksisk, men jeg er bare ærlig på en litt eksplosiv måte.",
    "Jeg tror på kjærlighet, men jeg tror også på taktikk og happy hour.",
    "Det føles ekte når vi gråter i samme basseng.",
    "Hun backstabba meg, men jeg forstår det – jeg hadde backstabba meg selv i den situasjonen.",
    "Jeg angrer ikke, jeg reflekterer bare med solbriller på.",
    "Folk sier jeg overreagerer, men de har aldri vært i en trio med dårlig kommunikasjon.",
    "Kjærlighet er komplisert, spesielt når det er kamera i trynet og tequila i blodet.",
    "Han sa det ikke betydde noe, men det var slow motion og musikk i bakgrunnen, så det betydde noe.",
    "Jeg er ikke falsk, jeg er bare tilpasningsdyktig i et lukket økosystem av løgn og solkrem.",
    "Det var ikke løgn, det var bare dårlig timing og bedre belysning.",
    "Jeg sa ikke at jeg er drama – jeg sa at jeg skaper det.",
    "Alle sier jeg flørter for mye, men jeg kaller det relasjonsbygging med undertoner.",
    "Han sa jeg var komplisert, men jeg er egentlig bare en følelsesmessig sudoku.",
    "Hvis du ikke tåler varmen, ikke sitt i boblebadet.",
    "Det handler ikke om å finne kjærlighet – det handler om å ikke bli stemt ut av den.",
    "Jeg ble ikke sjalu, jeg ble bare emosjonelt investert med knyttnevene.",
    "Vi er ikke gift, men vi har hatt en felles frokost, og det betyr noe for meg.",
    "Han ghosta meg selv om vi bor i samme villa – det krever talent.",
    "Jeg sier ikke at jeg angrer, jeg sier bare at jeg har lært at tequila ikke er en følelse.",
    "Det var ikke en løgn, det var et strategisk narrativ.",
    "Alle spiller spillet, men jeg gjør det med vipper og verdighet.",
    "Hvis ærlighet er en strategi, da er jeg i finaleuken allerede.",
    "Jeg kom hit for kjærligheten, men jeg ble for dramatikken – og airconditionen.",
    "Han sa jeg var intens, men han var bare dårlig trent på emosjonell utholdenhet.",
    "Kjærlighet er som tequila: det føles bra i starten og svir etterpå.",
    "Jeg sa aldri at jeg er stabil, jeg sa jeg har balanse i uroen.",
    "Det var ikke falskt, det var bare en følelse med manus.",
    "Jeg er ærlig, men også litt kreativ med sannheten.",
    "Han er søt, men han er også en menneskelig varseltrekant.",
    "Jeg prøvde å være ekte, men produksjonen klippet det bort.",
    "Det var ekte følelser, men midlertidig kontrakt.",
    "Hun sier hun ikke er drama, men hun puster dramatisk.",
    "Jeg vet ikke hva jeg føler, men jeg føler det sterkt.",
    "Han sa vi hadde en connection, men jeg tror det var wifi-en.",
    "Jeg sier det rett ut fordi jeg ikke vet hvordan man sier det pent.",
    "Han sa vi var et lag, men han spilte solo med alle.",
    "Jeg skjønner ikke hvorfor folk tror jeg manipulerer – jeg bare påvirker med tårer.",
    "Jeg liker ham, men jeg liker også oppmerksomhet – vanskelig valg.",
    "Jeg sier jeg er ferdig med ham, men jeg sier det veldig høyt så han hører det.",
    "Vi hadde en prat, men ingen av oss hørte etter.",
    "Jeg sa jeg var ferdig med drama, men drama var ikke ferdig med meg.",
    "Det var ikke en krangel, det var emosjonell crossfit.",
    "Han sa han ville være ærlig, men jeg foretrekker komfortable løgner.",
    "Jeg tror på kjærlighet, men jeg stoler ikke på noen med sixpack og smil.",
]

def pick_paradise():
    t = random.choice(TITLE_BANK)
    d = random.choice(DESC_BANK)
    logging.info(f"🧪 Selected title: {t}")
    logging.info(f"🧪 Selected desc: {d[:100]}…")
    return {"title": t, "description": d}

# -----------------------------
# Duplicate guard (5 minutes)
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
# Strava: verify webhook
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
# Strava: handle events
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

    # GET activity (requires readable visibility and valid token)
    async with httpx.AsyncClient(timeout=15) as client:
        headers = {"Authorization": f"Bearer {get_valid_token()}"}
        r = await client.get(f"https://www.strava.com/api/v3/activities/{activity_id}", headers=headers)
        logging.info(f"➡️ GET-status: {r.status_code}")
        if r.status_code != 200:
            logging.error(f"❌ Unable to fetch activity: {r.text}")
            return PlainTextResponse("GET failed", status_code=r.status_code)

        # build Paradise title/description
        td = pick_paradise()
        update_data = {
            "name": td["title"],
            "description": td["description"],
            # If you want the activity to end up private after update, keep this:
            # "private": True
        }
        logging.info(f"📝 PUT payload: {json.dumps(update_data, ensure_ascii=False)[:240]}")

        put = await client.put(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers=headers,
            data=update_data,
        )
        logging.info(f"✅ Updated activity {activity_id}: {put.status_code} — {put.text[:200]}")

    return PlainTextResponse("OK", status_code=200)
