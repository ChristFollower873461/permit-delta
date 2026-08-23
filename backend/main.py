import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api import api_router

# Configure logging to standard output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("permit_delta.main")

app = FastAPI(
    title="Permit Delta - Decision Support Tool",
    description="Operational review tool for Leo Carrillo State Park film permit revisions",
    version="1.0.0"
)

# Constrain CORS origins specifically (wildcard with credentials is invalid)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router first
app.include_router(api_router)

# Resolve the frontend dist path robustly across local dev and container directories
base_dir = Path(__file__).resolve().parent
possible_paths = [
    base_dir.parent / "frontend" / "dist",  # local source tree structure
    base_dir / "frontend" / "dist",         # docker container relative structure
    Path("/app/frontend/dist")               # absolute docker path
]

frontend_dist_path = None
for path in possible_paths:
    if path.exists() and path.is_dir():
        frontend_dist_path = path
        break

if frontend_dist_path:
    logger.info(f"Serving static production frontend from resolved path: {frontend_dist_path}")
    app.mount("/", StaticFiles(directory=str(frontend_dist_path), html=True), name="frontend")
else:
    logger.warning(
        "Frontend distribution directory not resolved. "
        "Server is running in backend-only API mode."
    )
    
    @app.get("/")
    def read_root():
        return {
            "name": "Permit Delta API",
            "status": "online",
            "frontend_served": False,
            "docs_url": "/docs"
        }
