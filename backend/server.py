from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import os
from dotenv import load_dotenv

from fastapi.middleware.cors import CORSMiddleware

from simulator import run_simulation
from routes.main_routes          import router as main_router, start_shipment
from routes.decision_routes      import router as decision_router
from routes.orchestration_routes import router as orchestration_router
from websocket                   import router as websocket_router

# =========================
# LOAD ENV VARIABLES
# =========================
load_dotenv(override=True)

# =========================
# STARTUP — auto-boot shipment + simulator
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background simulator task using asyncio
    asyncio.create_task(run_simulation())

    # Auto-start a default shipment (SHP001) so the route is ready immediately
    print("🚀 Auto-starting shipment SHP001 on boot...")
    result = await start_shipment("SHP001")
    print(f"   → {result.get('message', result)}")

    yield  # app runs here

# =========================
# INIT APP
# =========================
app = FastAPI(
    title="NexusPath API",
    description="Smart logistics risk intelligence platform",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(websocket_router,     prefix="", tags=["websocket"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
