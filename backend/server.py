from fastapi import FastAPI
import threading
import os
from dotenv import load_dotenv

from fastapi.middleware.cors import CORSMiddleware

from simulator import run_simulation
from routes.main_routes         import router as main_router
from routes.decision_routes     import router as decision_router
from routes.orchestration_routes import router as orchestration_router

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv(override=True)

# =========================
# INIT APP
# =========================
app = FastAPI(
    title="NexusPath API",
    description="Smart logistics risk intelligence platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# INCLUDE ROUTERS
# =========================
app.include_router(main_router,          prefix="", tags=["shipment"])
app.include_router(decision_router,      prefix="", tags=["decision"])
app.include_router(orchestration_router, prefix="", tags=["orchestration"])

# =========================
# BACKGROUND SIMULATION
# =========================
def start_simulation_thread():
    thread = threading.Thread(target=run_simulation, daemon=True)
    thread.start()

start_simulation_thread()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)