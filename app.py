import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from db_ops.app import AppDB
from core.db_core import DBCore
from core.logger_config import logger
from inference.internal_event_handler import app_event_handler
from inference.speech2text import audio_transcriber
from core.app_config import ImageConfig
from core.unique_id_manager import id_manager
from core.embedding_worker import embedding_worker
from core.vector_db import vector_db
from core.user_config_definitions import USER_CONFIG_OPTIONS
from core.memory_worker import memory_worker
from agent_tools.mcp_client import close_global_mcp_client
from pathlib import Path
import asyncio
from socket_handlers import (
    ChatSocketHandler,
    AudioSocketHandler,
    BridgeSocketHandler
)

# --- frontend config ---
FRONTEND_DIR = './frontend/dist'
# Jinja2 is used here just to serve the index.html file
templates = Jinja2Templates(directory=FRONTEND_DIR)
# Configure Jinja2 to preserve dict order in JSON
templates.env.policies['json.dumps_kwargs'] = {'sort_keys': False}

# --- websocket handlers ---
audio_socket_handler = AudioSocketHandler()
chat_socket_handler = ChatSocketHandler()
bridge_socket_handler = BridgeSocketHandler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 1. Startup Logic (Equivalent to your main() initialization) ---
    clear_db = True

    # Set up database
    await DBCore.setup(clear_db=clear_db)
    logger.info("Core database ready...")

    await vector_db.setup(clear_db=clear_db)
    logger.info("Vector database ready")

    # Create image cache directory
    path = Path(ImageConfig.IMAGE_CACHE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    logger.info('Set up image cache directory!')

    # Set up our unique id manager
    session_id = await AppDB.get_session()
    id_manager.set_session(session_id)
    logger.info('ID manager ready!')

    # Set up memory worker background "process" (loops w/ long sleeps)
    asyncio.create_task(memory_worker.start_loop())
    logger.info("Started memory worker loop")

    # Set up internal event watcher loop
    await app_event_handler.start_event_loop()

    # Set up embedding worker background 'process' (loops with inference event triggers)
    asyncio.create_task(embedding_worker.start_loop())

    # Connect to speech-to-text provider websocket
    await audio_transcriber.connect(on_partial=audio_socket_handler.receive_partial_transcript,
                                    on_committed=audio_socket_handler.receive_committed_transcript)
    logger.info('ElevenLabs connection ready!')

    # The application is now ready to receive requests
    yield

    # --- 2. Shutdown Logic ---
    logger.info("Application Shutdown: Cleaning up...")
    await audio_transcriber.close()

    logger.info('Saving vector DB')
    await vector_db.close()

    # Close MCP client
    await close_global_mcp_client()

app = FastAPI(lifespan=lifespan)

# Mount the static files (JS, CSS, images) from the React build
app.mount("/assets", StaticFiles(directory=f"{FRONTEND_DIR}/assets"), name="assets")

# --- REACT FRONTEND ROUTES (HTTP) ---
# The main route serves the index.html
@app.get("/")
def serve_index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"config_options": USER_CONFIG_OPTIONS})

# --- USER INPUT (CHAT + AUDIO) WEBSOCKET ENDPOINTS ---
@app.websocket("/ws/chat")
async def chat_endpoint(websocket: WebSocket):
    await chat_socket_handler.handle_socket(websocket)

@app.websocket("/ws/audio")
async def audio_endpoint(websocket: WebSocket):
    await audio_socket_handler.handle_socket(websocket)

# --- FRONTEND BACKEND COMMUNICATION WEBSOCKET ENDPOINTS ---
@app.websocket("/ws/app_bridge")
async def bridge_endpoint(websocket: WebSocket):
    await bridge_socket_handler.handle_socket(websocket)

@app.get("/api/image/{image_id}")
async def serve_image_endpoint(image_id: str):
    """API endpoint to serve a generated image by its ID"""
    return await serve_generated_image(image_id)

async def serve_generated_image(image_id: str):
    """Serve a generated image by its ID from the cache"""
    try:
        cache = await AppDB.get_image_cache()
        if not cache:
            return {"error": "Failed to fetch image cache"}

        for img in cache:
            if img['image_id'] == image_id:
                local_path = img['path']
                if Path(local_path).exists():
                    return FileResponse(local_path)
                else:
                    return {"error": f"Image file not found at {local_path}"}
        
        return {"error": f"Image with ID {image_id} not found in cache"}
    except Exception as e:
        return {"error": f"Failed to serve image: {str(e)}"}

# Catch-all route for React Router (must be the LAST route)
@app.get("/{full_path:path}")
async def serve_react_router(request: Request, full_path: str):
    return templates.TemplateResponse(request, "index.html", {"config_options": USER_CONFIG_OPTIONS})

# To run this file: uvicorn app:app --reload
if __name__ == '__main__':
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)