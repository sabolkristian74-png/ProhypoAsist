from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes.web import router as web_router
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="HypoVSPoitná suma")

# serve static from the project `static` folder
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(web_router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
