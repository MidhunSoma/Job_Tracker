import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI

from .api.auth import router as auth_router
from .api.jobs import router as jobs_router
from .api.run import router as run_router
from .scheduler.jobs import start_scheduler, stop_scheduler
from .utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle context manager executing actions during startup and shutdown."""
    logger.info(
        "Starting up AI Job Application Email Tracker Agent API...",
        extra={"action": "STARTUP"}
    )
    
    # Start the periodic background sync scheduler
    start_scheduler()
    
    yield
    
    # Gracefully shut down background sync scheduler
    stop_scheduler()
    logger.info(
        "Shutting down AI Job Application Email Tracker Agent API...",
        extra={"action": "SHUTDOWN"}
    )


app = FastAPI(
    title="AI Job Application Email Tracker API",
    description="Automated system that tracks job applications from Gmail and syncs them with SQLite and Excel.",
    version="0.1.0",
    lifespan=lifespan
)

# Register API Routers
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(run_router)


@app.get("/")
def read_root():
    """Root endpoint for status checks."""
    return {"status": "ok", "message": "AI Job Application Email Tracker is running."}


if __name__ == "__main__":
    uvicorn.run("job_tracker.main:app", host="127.0.0.1", port=8000, reload=True)
