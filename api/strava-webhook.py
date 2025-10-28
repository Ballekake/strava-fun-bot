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
STRAVA_ACCESS_TOKEN = os.environ.get("STRAVA_ACCESS_TOKEN")

# ---------------------------------------------------------------------
# PARADISE HOTEL – STYLE TITLES 🎤
# ---------------------------------------------------------------------
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
    "Det var ekte kjærlighet helt til frokosten tok slutt",
    "Jeg sa jeg ikke bryr meg, men jeg skrev det på Instagram etterpå",
    "Hvis lojalitet var en drink, hadde alle vært fulle",
    "Han lovte evig kjærlighet, men holdt bare til checkout",
    "Jeg har mer følelser enn solkremrester på sofaen",
    "Ingen plan overlever første shot",
    "Jeg elsker drama, men bare når jeg starter det selv",
    "Jeg vet ikke hva jeg føler, men jeg føler det sterkt",
    "Kjærlighet uten strategi er som badestamp uten bobler",
    "Jeg tenker ikke, jeg opplever",
    "Han sa han ville snakke, men han mente diskutere med tårer",
    "Vi hadde kjemi – men også dårlig timing og høy promille",
    "Jeg angrer ikke, men jeg skammer meg kunstnerisk",
    "Han sa jeg var drama, men jeg er bare sesong 3-materiale",
    "Jeg kom hit som deltaker, men forlater som advarsel",
    "Jeg tror på kjærlighet, men jeg stoler mer på produksjonen",
    "Jeg er ikke falsk, jeg er bare dårlig på ærlighet i sollys",
    "Det var ikke løgn, det var strategi med sminke",
    "Han sa jeg var intens, jeg kaller det karakterutvikling",
    "Jeg er her for kjærlighet, men jeg tar også spons",
    "Jeg gikk ikke bak ryggen hans, jeg tok bare en omvei",
    "Jeg sa jeg er rolig, men jeg mente mellom episodene",
    "Han sa han likte meg som venn – jeg liker hevn bedre",
    "Jeg er ikke her for å spille, men jeg vinner gjerne spillet",
    "Jeg tror jeg lærte noe, men jeg glemte det i baren",
    "Ærlighet varer lengst, men løgn gir bedre TV",
    "Jeg kom hit som enkeltperson, men forlot som kaoskollektiv",
    "Jeg er ikke sint, jeg bare kommuniserer med capslock",
    "Han ghosta meg i villaen – det krever talent",
    "Jeg føler meg dyp, men det er bare spraytanen"
]

# ---------------------------------------------------------------------
# PARADISE HOTEL – STYLE ARGUMENT DESCRIPTIONS 🥂
# ---------------------------------------------------------------------
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
    "Jeg kom hit for kjærligheten, men jeg ble for dramatikken – og AirConditionen.",
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
    "Jeg tror på kjærlighet, men jeg stoler ikke på noen med sixpack og smil."
]

def random_title_desc():
    return {
        "title": random.choice(TITLE_BANK),
        "description": random.choice(DESC_BANK)
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
# STRAVA WEBHOOK HANDLERS
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

    logging.info(f"📬 Received Strava webhook: {json.dumps(payload)}")
    if payload.get("object_type") != "activity":
        return PlainTextResponse("ignored", status_code=200)

    activity_id = payload.get("object_id")
    aspect = payload.get("aspect_type")

    if already_processed(activity_id):
        logging.info(f"⏳ Duplicate activity {activity_id}, skipping.")
        return PlainTextResponse("duplicate", status_code=200)

    if aspect not in ("create", "update"):
        return PlainTextResponse("ignored", status_code=200)

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
        )

        if r.status_code != 200:
            logging.warning(f"❌ Unable to fetch activity: {r.text}")
            return PlainTextResponse("not found", status_code=404)

        title_desc = random_title_desc()
        update_data = {
            "name": title_desc["title"],
            "description": title_desc["description"],
            "private": True  # re-set to "Only You" after update
        }

        put_resp = await client.put(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers={"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"},
            data=update_data
        )
        logging.info(f"✅ Updated activity {activity_id}: {put_resp.status_code}")

    return PlainTextResponse("OK", status_code=200)
