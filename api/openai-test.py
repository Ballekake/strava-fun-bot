# api/openai-test.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx, os

app = FastAPI()

@app.get("/api/openai-test")
async def openai_test():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return JSONResponse({"error": "OPENAI_API_KEY missing"}, status_code=500)

    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Si hei på norsk"}]
                }
            )
            return JSONResponse({"status": r.status_code, "text": r.text[:300]})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
