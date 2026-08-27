from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import build_config, load_external_env_file
from app.logging_setup import setup_logging
from app.pipeline import CallPipeline
from app.ws.ws_hub import WsHub

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("CONFIG_FILE", "./secrets/app.env")
load_external_env_file(CONFIG_PATH)
config = build_config(os.environ)

setup_logging(config.data_dir)

ws_hub = WsHub()


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline = CallPipeline(ws_hub=ws_hub)
    app.state.pipeline = pipeline

    # Imported lazily: app.sip.bridge transitively imports the pjsua2 native
    # extension, which only exists once the Docker image's builder stage has
    # compiled it (see Dockerfile). Importing it at module load time would
    # break plain `pip install -r requirements.txt` local dev/testing, where
    # pjsua2 isn't available.
    from app.sip.bridge import SipBridge

    loop = asyncio.get_running_loop()
    sip_bridge = SipBridge(
        config=config,
        loop=loop,
        on_ringing=pipeline.handle_ringing,
        on_ended=pipeline.handle_ended,
    )
    sip_bridge.start()

    try:
        yield
    finally:
        sip_bridge.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/")
async def index():
    # This is the only "server" concern the bundled reference client needs:
    # a handful of static bytes. It holds no state and does no rendering —
    # all history/UI logic lives in app/static/app.js, keeping the server's
    # actual responsibility (SIP + WS broadcast) unchanged. See README's
    # "Webブラウザ用リファレンスクライアント" section.
    return FileResponse("app/static/index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_hub.connect(websocket)
    try:
        while True:
            # This server never expects client->server messages; still need
            # to await something so we notice disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_hub.disconnect(websocket)


if __name__ == "__main__":
    # Run via `python -m app.main` (see Dockerfile) rather than the `uvicorn`
    # CLI directly, so config.http_port — resolved from secrets/app.env — is
    # honored. A CLI-only `uvicorn app.main:app --port 8080` invocation can't
    # see that value, since it's only loaded once this module executes.
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=config.http_port)
