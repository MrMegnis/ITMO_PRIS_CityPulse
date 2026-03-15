from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from citypulse.api.routes import router


app = FastAPI(
    title="CityPulse",
    description="Smart city operations platform prototype",
    version="0.1.0",
)

app.mount(
    "/ui-static",
    StaticFiles(directory=Path(__file__).resolve().parent / "ui"),
    name="ui-static",
)
app.include_router(router)
