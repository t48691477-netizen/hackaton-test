import sys
import os
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
print("Step 1: Importing app...", flush=True)
from app.main import app
print("Step 2: App imported successfully!", flush=True)

import uvicorn
print("Step 3: Creating config...", flush=True)
config = uvicorn.Config(app, host="127.0.0.1", port=8000, lifespan="off", log_level="info")
print("Step 4: Creating server...", flush=True)
server = uvicorn.Server(config)

async def test_startup():
    print("Step 5: Calling server.startup()...", flush=True)
    await server.startup()
    print("Step 6: Server started successfully!", flush=True)
    print("Started flag:", server.started, flush=True)
    print("Listeners:", server.servers, flush=True)
    print("Step 7: Shutting down...", flush=True)
    await server.shutdown()
    print("Step 8: Shutdown complete!", flush=True)

asyncio.run(test_startup())
