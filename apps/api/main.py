from contextlib import asynccontextmanager
from pathlib import Path
import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.routers import (
    agents_router,
    approvals_router,
    chat_router,
    devices_router,
    mcp_router,
    memory_router,
    quantum_router,
    tasks_router,
    tools_router,
    voice_router,
    ws_router,
)


def _load_root_env() -> None:
    """Load .env from project root with override=True."""
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        env_file = parent / ".env"
        if env_file.is_file():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k:
                                os.environ[k] = v
            except Exception:
                pass
            break


_load_root_env()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rio.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle hooks."""
    logger.info("⚡ Initializing R.I.O. (Reasoning Intelligence Orchestration) Operating System Core...")
    yield
    logger.info("🛑 Shutting down R.I.O. Core...")


app = FastAPI(
    title="R.I.O. Personal AI Operating System",
    description="Reasoning Intelligence Orchestration - Backend API Gateway & Agent Runtime",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST API v1
api_v1_prefix = "/api/v1"
app.include_router(chat_router, prefix=api_v1_prefix)
app.include_router(tasks_router, prefix=api_v1_prefix)
app.include_router(approvals_router, prefix=api_v1_prefix)
app.include_router(devices_router, prefix=api_v1_prefix)
app.include_router(agents_router, prefix=api_v1_prefix)
app.include_router(tools_router, prefix=api_v1_prefix)
app.include_router(mcp_router, prefix=api_v1_prefix)
app.include_router(memory_router, prefix=api_v1_prefix)
app.include_router(voice_router, prefix=api_v1_prefix)
app.include_router(quantum_router, prefix=api_v1_prefix)

# Mount Real-time WebSockets
app.include_router(ws_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "rio-api", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
