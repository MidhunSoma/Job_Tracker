import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from ..config.settings import settings
from ..database.session import SessionLocal
from ..graph.workflow import app_graph
from ..models.processing_run import ProcessingRun
from ..repositories.processing_run import ProcessingRunRepository
from ..utils.logging import logger

scheduler = BackgroundScheduler()


def run_agent_job() -> None:
    """Scheduled job executing the compiled LangGraph workflow inside a managed DB session."""
    logger.info("Scheduler: Triggering scheduled agent run...", extra={"action": "SCHEDULER_JOB_TRIGGER"})
    
    db = SessionLocal()
    start_time = datetime.utcnow()
    
    # Initialize run log in database
    run_log = ProcessingRun(
        start_time=start_time,
        emails_scanned=0,
        emails_processed=0,
        new_applications=0,
        updated_applications=0
    )
    
    run_repo = ProcessingRunRepository(db)
    run_log = run_repo.create(run_log)
    
    start_perf = time.perf_counter()
    
    try:
        initial_state = {
            "raw_emails": [],
            "current_idx": 0,
            "current_extraction": None,
            "current_normalized_status": None,
            "current_status_confidence": None,
            "is_duplicate": None,
            "matched_app_id": None,
            "emails_scanned": 0,
            "emails_processed": 0,
            "new_applications": 0,
            "updated_applications": 0,
            "errors": []
        }
        
        # Execute LangGraph pipeline
        final_state = app_graph.invoke(
            initial_state,
            {"configurable": {"db": db, "thread_id": f"scheduled_run_{run_log.id}"}}
        )
        
        end_perf = time.perf_counter()
        duration_ms = int((end_perf - start_perf) * 1000)
        
        # Save run statistics
        run_log.end_time = datetime.utcnow()
        run_log.emails_scanned = final_state.get("emails_scanned", 0)
        run_log.emails_processed = final_state.get("emails_processed", 0)
        run_log.new_applications = final_state.get("new_applications", 0)
        run_log.updated_applications = final_state.get("updated_applications", 0)
        run_log.input_tokens = final_state.get("input_tokens", 0)
        run_log.output_tokens = final_state.get("output_tokens", 0)
        run_log.cost_usd = final_state.get("cost_usd", 0.0)
        run_log.duration_ms = duration_ms
        
        errors = final_state.get("errors", [])
        if errors:
            run_log.errors = "; ".join(errors)
            
        run_repo.update(run_log)
        
        logger.info(
            f"Scheduler: Scheduled run complete. Scanned: {run_log.emails_scanned}, Processed: {run_log.emails_processed}, Cost: ${run_log.cost_usd:.4f}, Duration: {duration_ms}ms.",
            extra={
                "action": "SCHEDULER_RUN_SUCCESS",
                "run_id": run_log.id,
                "scanned": run_log.emails_scanned,
                "processed": run_log.emails_processed,
                "new_apps": run_log.new_applications,
                "updated_apps": run_log.updated_applications,
                "input_tokens": run_log.input_tokens,
                "output_tokens": run_log.output_tokens,
                "cost_usd": run_log.cost_usd,
                "duration_ms": duration_ms
            }
        )
        
    except Exception as e:
        end_perf = time.perf_counter()
        duration_ms = int((end_perf - start_perf) * 1000)
        
        run_log.end_time = datetime.utcnow()
        run_log.errors = f"Scheduler Job Exception: {str(e)}"
        run_log.duration_ms = duration_ms
        run_repo.update(run_log)
        
        logger.exception("Scheduler: Scheduled agent execution crashed.")
        
    finally:
        db.close()


def start_scheduler() -> None:
    """Starts the background scheduler loop if it is not already running."""
    if not scheduler.running:
        interval = settings.scheduler.interval_minutes
        scheduler.add_job(
            run_agent_job,
            "interval",
            minutes=interval,
            id="job_tracker_agent_sync_job",
            replace_existing=True
        )
        scheduler.start()
        logger.info(
            f"Scheduler: Started successfully. Sync interval: {interval} minutes.",
            extra={"action": "SCHEDULER_START", "interval_minutes": interval}
        )


def stop_scheduler() -> None:
    """Gracefully shuts down the background scheduler threads."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler: Shut down successfully.", extra={"action": "SCHEDULER_SHUTDOWN"})
