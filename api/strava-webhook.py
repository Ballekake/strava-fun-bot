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

# === DUPLIKAT-GUARD === #
processed_activities = set()

# === TITTEL OG BESKRIVELSER === #
titles_and_descriptions = [
    {"title": "Jeg trodde pushups var noe man kjøper på Rema",
     "description": "Forventningsavvik mellom produkt og aktivitet dokumentert. Ingen videre oppfølging nødvendig."},
    {"title": "Det er ikke kroppen min som sliter, det er sjela",
     "description": "Subjektiv opplevelse av utmattelse registrert. Fysisk kapasitet vurderes som tilfredsstillende."},
    {"title": "Jeg har aldri vært så sliten uten å ha hatt det gøy",
     "description": "Tiltaket ble gjennomført etter plan. Mangel på glede påvirker ikke måloppnåelsen."},
    {"title": "Jeg har mer respekt for uniformer nå",
     "description": "Etter praktisk erfaring ble kompleksiteten i uniformert arbeid bedre forstått."},
    {"title": "Jeg visste ikke man kunne svette der",
     "description": "Ny svettesone identifisert. Hendelsen anses som ufarlig og avsluttes uten tiltak."},
    {"title": "Jeg prøvde å gjemme meg bak en busk",
     "description": "Forsøk på kamuflasje dokumentert. Vegetasjonen ga begrenset skjul."},
    {"title": "Reveleir sitter i ryggraden",
     "description": "Langtidseffekt av tidlig læring observert. Ingen korrigerende tiltak nødvendig."},
    {"title": "Jeg har aldri savnet søvn så mye",
     "description": "Søvnmangel registrert. Tiltak for restitusjon anbefales, men er ikke påkrevd."},
    {"title": "Det verste er ikke å løpe – det er å rope",
     "description": "Verbalt energiforbruk under fysisk belastning vurderes som uhensiktsmessig."},
    {"title": "Dette er karakterbygging med blåmerker",
     "description": "Personlig utvikling påvist. Fysiske konsekvenser vurderes som moderate."},
    {"title": "Jeg meldte meg på for utsikten, ikke for å dø",
     "description": "Forventningsavvik mellom motivasjon og terreng dokumentert. Saken anses lukket."},
    {"title": "Jeg må puste med beina nå",
     "description": "Alternativ respirasjon forsøkt. Effekten vurderes som begrenset."},
    {"title": "Det ser flatt ut på kartet, men kartet lyver",
     "description": "Avvik mellom kartgrunnlag og faktisk høydeprofil bekreftet."},
    {"title": "Jeg skjønner hvorfor fjellfolk er stille – de sparer oksygen",
     "description": "Observasjonen samsvarer med kjente fysiologiske prinsipper."},
    {"title": "Dette er ikke tur – dette er terapi med bakker",
     "description": "Tiltaket klassifiseres som egeninitiert rehabilitering med fysisk komponent."},
    {"title": "Jeg har fått gnagsår på sjelen",
     "description": "Langvarig belastning dokumentert. Ingen synlige skader registrert."},
    {"title": "Jeg har ikke kondis, jeg har karisma",
     "description": "Egenskapen har ingen målbar treningseffekt. Ingen tiltak anbefales."},
    {"title": "Jeg vurderte å gi opp, men så kom kameraet",
     "description": "Ekstern observasjon bidro til midlertidig innsatsøkning."},
    {"title": "Jeg trodde Nordkapp lå i Sverige",
     "description": "Geografisk misforståelse oppklart. Ingen konsekvenser for prosjektet."},
    {"title": "Det er vinden som trener oss",
     "description": "Ekstern motstand utnyttet som ressurs. Tiltaket fungerer etter hensikten."},
    {"title": "Tarzan uten muskler",
     "description": "Rolleforståelsen er korrekt, men muskulær kapasitet mangler."},
    {"title": "Er dette all inclusive, eller koster vannet ekstra",
     "description": "Avvik mellom forventet og levert tjeneste registrert. Ingen kompensasjon gis."},
    {"title": "Jeg kom for å slappe av, men ble solbrent, blakk og forelska",
     "description": "Flere utilsiktede bieffekter dokumentert. Ingen tiltak foreslått."},
    {"title": "Alt går bra med sol og saus",
     "description": "Positive ytre faktorer påvirket opplevd resultat. Ingen avvik rapportert."},
    {"title": "Jeg blir brun inni",
     "description": "Intern varmepåvirkning registrert. Ingen helsefare identifisert."},
    {"title": "Jeg følte det på hele stemningen",
     "description": "Atmosfærisk endring observert. Ingen videre analyse nødvendig."},
    {"title": "Det var et slags ubehag der",
     "description": "Opplevelsen er notert som mindre alvorlig. Saken avsluttes."},
    {"title": "Dette er et kunstprosjekt",
     "description": "Formålet er uklart, men aktivitet er dokumentert. Ingen budsjettmidler benyttet."},
    {"title": "Ingen forstår meg, og det er meninga",
     "description": "Kommunikasjonsstrategi vurderes som bevisst uforståelig. Ingen tiltak kreves."},
    {"title": "Det er et konsept mer enn en idé",
     "description": "Klargjøring av begrepsbruk anbefales ved neste rapportering."},
    {"title": "La det marinere litt",
     "description": "Beslutning utsatt. Videre behandling planlagt ved neste vurdering."},
    {"title": "Det er en slags kommentar til samtida",
     "description": "Bidraget tolkes som refleksjon over eksisterende forhold. Ingen formelle krav."},
    {"title": "Jeg liker at det er litt ubehagelig",
     "description": "Tiltaket innebærer frivillig ubehag. Resultatet vurderes som tilfredsstillende."},
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
