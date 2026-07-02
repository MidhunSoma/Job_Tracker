import time
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..graph.workflow import app_graph
from ..models.processing_run import ProcessingRun
from ..repositories.processing_run import ProcessingRunRepository
from ..utils.logging import logger

router = APIRouter(prefix="/api/run", tags=["Agent Operations"])


@router.post("", response_model=Dict[str, Any])
def trigger_agent_run(db: Session = Depends(get_db)):
    """Manually triggers the LangGraph Email Tracking Agent pipeline to sync emails and extract jobs."""
    logger.info("API: Manual execution of agent pipeline requested.", extra={"action": "API_TRIGGER_RUN"})
    
    # 1. Log start time and initialize run entry
    start_time = datetime.utcnow()
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
        # 2. Invoke LangGraph workflow, passing SQLite DB session in config
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
        
        final_state = app_graph.invoke(
            initial_state,
            {"configurable": {"db": db, "thread_id": f"manual_run_{run_log.id}"}}
        )
        
        end_perf = time.perf_counter()
        duration_ms = int((end_perf - start_perf) * 1000)
        
        # 3. Save telemetry results to ProcessingRun
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
            f"API: Agent run complete. Scanned: {run_log.emails_scanned}, Processed: {run_log.emails_processed}, Cost: ${run_log.cost_usd:.4f}, Duration: {duration_ms}ms.",
            extra={
                "action": "API_RUN_SUCCESS",
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
        
        return {
            "status": "success",
            "run_id": run_log.id,
            "emails_scanned": run_log.emails_scanned,
            "emails_processed": run_log.emails_processed,
            "new_applications": run_log.new_applications,
            "updated_applications": run_log.updated_applications,
            "duration_ms": duration_ms,
            "errors": errors
        }
        
    except Exception as e:
        end_perf = time.perf_counter()
        duration_ms = int((end_perf - start_perf) * 1000)
        
        run_log.end_time = datetime.utcnow()
        run_log.errors = f"Run Exception: {str(e)}"
        run_log.duration_ms = duration_ms
        run_repo.update(run_log)
        
        logger.exception("API: Agent run crashed due to an unhandled exception.")
        raise HTTPException(
            status_code=500,
            detail=f"Agent run failed: {str(e)}"
        )
