import json
from datetime import datetime
from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

from .state import GraphState
from ..config.settings import settings
from ..models.application import Application
from ..models.status_history import StatusHistory
from ..repositories.application import ApplicationRepository
from ..repositories.status_history import StatusHistoryRepository
from ..repositories.raw_email import RawEmailRepository
from ..services.gmail_service import GmailService
from ..services.llm_service import LLMService
from ..services.excel_service import ExcelService
from ..utils.matching import is_duplicate_application
from ..utils.normalization import can_transition
from ..utils.logging import logger

gmail_service = GmailService()
llm_service = LLMService()
excel_service = ExcelService()


def estimate_llm_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimates the financial cost of an LLM invocation based on standard model pricing."""
    prov = provider.lower()
    mod = model.lower()
    
    in_rate = 0.15 / 1_000_000
    out_rate = 0.60 / 1_000_000
    
    if prov == "openai":
        if "gpt-4o" in mod and "mini" not in mod:
            in_rate = 2.50 / 1_000_000
            out_rate = 10.00 / 1_000_000
        elif "gpt-4o-mini" in mod:
            in_rate = 0.15 / 1_000_000
            out_rate = 0.60 / 1_000_000
            
    elif prov == "gemini":
        if "1.5-pro" in mod:
            in_rate = 1.25 / 1_000_000
            out_rate = 5.00 / 1_000_000
        else:
            in_rate = 0.075 / 1_000_000
            out_rate = 0.30 / 1_000_000
            
    elif prov == "anthropic":
        if "sonnet" in mod:
            in_rate = 3.00 / 1_000_000
            out_rate = 15.00 / 1_000_000
        elif "haiku" in mod:
            in_rate = 0.25 / 1_000_000
            out_rate = 1.25 / 1_000_000
            
    return (prompt_tokens * in_rate) + (completion_tokens * out_rate)


def fetch_emails_node(state: GraphState, config: RunnableConfig) -> GraphState:
    """Ingests recent emails from Gmail into SQLite and lists unprocessed batch items."""
    db: Session = config.get("configurable", {}).get("db")
    if not db:
        raise ValueError("Database session missing from LangGraph execution config.")

    logger.info("LangGraph: executing fetch_emails_node.", extra={"action": "NODE_FETCH_EMAILS"})
    
    # Sync new emails from Gmail to database RawEmail table
    gmail_service.sync_emails(db)
    
    # Query up to 20 unprocessed emails to process in this run
    raw_repo = RawEmailRepository(db)
    unprocessed = raw_repo.get_unprocessed_emails()
    batch = unprocessed[:20]
    
    return {
        "raw_email_ids": [e.message_id for e in batch],
        "current_idx": 0,
        "current_extraction": None,
        "current_normalized_status": None,
        "current_status_confidence": None,
        "is_duplicate": None,
        "matched_app_id": None,
        "emails_scanned": len(batch),
        "emails_processed": 0,
        "new_applications": 0,
        "updated_applications": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "errors": []
    }


def classify_and_extract_node(state: GraphState, config: RunnableConfig) -> GraphState:
    """Uses LLM to classify if email is job-related and extract structured application information."""
    db: Session = config.get("configurable", {}).get("db")
    idx = state["current_idx"]
    msg_id = state["raw_email_ids"][idx]

    logger.info(
        f"LangGraph: executing classify_and_extract_node for index {idx} (message_id={msg_id}).",
        extra={"action": "NODE_EXTRACT", "message_id": msg_id}
    )

    raw_repo = RawEmailRepository(db)
    raw_email = raw_repo.get_by_message_id(msg_id)
    if not raw_email:
        raise ValueError(f"RawEmail record with message_id {msg_id} not found in database.")

    try:
        # Mark as processing
        raw_email.processing_state = "PROCESSING"
        db.add(raw_email)
        db.commit()

        # Invoke LLM single classification + details extraction
        extraction, telemetry = llm_service.extract_job_details(
            subject=raw_email.subject or "",
            sender=raw_email.sender,
            date_str=raw_email.received_at.isoformat(),
            body=raw_email.body or ""
        )

        # Update telemetry coordinates
        raw_email.raw_llm_json = telemetry.get("raw_llm_json")
        raw_email.prompt_version = telemetry.get("prompt_version")
        raw_email.model = telemetry.get("model")
        raw_email.temperature = telemetry.get("temperature")
        raw_email.token_usage = telemetry.get("token_usage")
        db.add(raw_email)
        db.commit()

        if not extraction:
            raise ValueError("LLM returned empty or malformed structured extraction.")

        # Parse token usage metrics from telemetry
        token_data = {}
        try:
            token_data = json.loads(telemetry.get("token_usage", "{}"))
        except Exception:
            pass
            
        p_tokens = token_data.get("prompt_tokens", 0) or token_data.get("input_tokens", 0) or 0
        c_tokens = token_data.get("completion_tokens", 0) or token_data.get("output_tokens", 0) or 0
        
        # Estimate cost
        cost = estimate_llm_cost(
            provider=settings.llm.provider,
            model=telemetry.get("model", settings.llm.model),
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens
        )

        return {
            **state,
            "current_extraction": extraction,
            "emails_processed": state["emails_processed"] + 1,
            "input_tokens": state["input_tokens"] + p_tokens,
            "output_tokens": state["output_tokens"] + c_tokens,
            "cost_usd": state["cost_usd"] + cost
        }

    except Exception as e:
        db.rollback()
        
        # Dead letter queue retry evaluation
        raw_email.retry_count = (raw_email.retry_count or 0) + 1
        if raw_email.retry_count >= 3:
            raw_email.processing_state = "DEAD_LETTER"
        else:
            raw_email.processing_state = "FAILED"
            
        raw_email.error_message = str(e)
        db.add(raw_email)
        db.commit()
        
        logger.error(
            f"Failed extraction for email {raw_email.message_id}: {e}",
            extra={"action": "NODE_EXTRACT_ERROR", "message_id": raw_email.message_id}
        )
        
        errors = list(state["errors"])
        errors.append(f"Email {raw_email.message_id}: {str(e)}")
        return {
            **state,
            "errors": errors
        }


def normalize_and_dedup_node(state: GraphState, config: RunnableConfig) -> GraphState:
    """Normalizes the extracted stage status and checks if a duplicate application exists in SQLite."""
    db: Session = config.get("configurable", {}).get("db")
    extraction = state["current_extraction"]
    
    if not extraction:
        return state

    logger.info("LangGraph: executing normalize_and_dedup_node.", extra={"action": "NODE_NORM_DEDUP"})

    # 1. Normalize raw status into one of our exact standard statuses
    normalized_status, status_conf = llm_service.normalize_status(
        extraction.extracted_status or "Applied"
    )

    # 2. Check for duplicate company + role in SQLite
    app_repo = ApplicationRepository(db)
    all_apps = app_repo.get_all()
    
    matched_app = None
    for app in all_apps:
        if is_duplicate_application(app.company, app.role, extraction.company, extraction.role):
            matched_app = app
            break

    return {
        **state,
        "current_normalized_status": normalized_status,
        "current_status_confidence": status_conf,
        "is_duplicate": matched_app is not None,
        "matched_app_id": matched_app.id if matched_app else None
    }


def db_update_node(state: GraphState, config: RunnableConfig) -> GraphState:
    """Inserts or updates the Application and logs transitions in StatusHistory."""
    db: Session = config.get("configurable", {}).get("db")
    idx = state["current_idx"]
    msg_id = state["raw_email_ids"][idx]
    extraction = state["current_extraction"]
    normalized_status = state["current_normalized_status"]
    status_conf = state["current_status_confidence"]
    
    if not extraction or not normalized_status:
        return state

    raw_repo = RawEmailRepository(db)
    raw_email = raw_repo.get_by_message_id(msg_id)
    if not raw_email:
        raise ValueError(f"RawEmail record with message_id {msg_id} not found in database during DB update.")

    app_repo = ApplicationRepository(db)
    history_repo = StatusHistoryRepository(db)

    logger.info("LangGraph: executing db_update_node.", extra={"action": "NODE_DB_UPDATE"})

    new_apps = state["new_applications"]
    updated_apps = state["updated_applications"]
    
    needs_review = extraction.overall_confidence < 0.70

    try:
        if state["is_duplicate"]:
            # Update existing Application record
            app_id = state["matched_app_id"]
            app = app_repo.get(app_id)
            
            old_status = app.status
            transition_allowed = can_transition(old_status, normalized_status)
            
            if extraction.recruiter_name:
                app.recruiter_name = extraction.recruiter_name
            if extraction.recruiter_email:
                app.recruiter_email = extraction.recruiter_email
                
            app.gmail_message_id = raw_email.message_id
            app.gmail_thread_id = raw_email.thread_id
            app.gmail_link = raw_email.gmail_link
            app.last_email_date = raw_email.received_at
            
            if extraction.notes:
                date_stamp = raw_email.received_at.strftime("%Y-%m-%d")
                note_entry = f"[{date_stamp}] Status update: {extraction.notes}"
                app.notes = (app.notes + "\n" + note_entry) if app.notes else note_entry

            if transition_allowed:
                app.status = normalized_status
                app.company_confidence = extraction.company_confidence
                app.role_confidence = extraction.role_confidence
                app.status_confidence = status_conf
                app.overall_confidence = extraction.overall_confidence
                app.updated_at = datetime.utcnow()
                
                if needs_review:
                    app.needs_review = True
                    
                updated_apps += 1
                
            app_repo.update(app)

            # Record StatusHistory log
            history_note = extraction.notes
            if not transition_allowed:
                history_note = f"[REGRESSION BLOCKED] {history_note or ''}"

            history = StatusHistory(
                application_id=app.id,
                old_status=old_status,
                new_status=normalized_status,
                email_subject=raw_email.subject,
                email_date=raw_email.received_at,
                gmail_message_id=raw_email.message_id,
                llm_reason=extraction.llm_reason,
                status_confidence=status_conf,
                overall_confidence=extraction.overall_confidence,
                needs_review=needs_review,
                notes=history_note
            )
            history_repo.create(history)

        else:
            # Create a brand new Job Application record
            new_app = Application(
                company=extraction.company or "Unknown",
                role=extraction.role or "Position Unknown",
                status=normalized_status,
                applied_date=extraction.applied_date or raw_email.received_at,
                recruiter_name=extraction.recruiter_name,
                recruiter_email=extraction.recruiter_email,
                gmail_message_id=raw_email.message_id,
                gmail_thread_id=raw_email.thread_id,
                gmail_link=raw_email.gmail_link,
                last_email_date=raw_email.received_at,
                is_active=True,
                company_confidence=extraction.company_confidence,
                role_confidence=extraction.role_confidence,
                status_confidence=status_conf,
                overall_confidence=extraction.overall_confidence,
                needs_review=needs_review,
                notes=extraction.notes
            )
            created_app = app_repo.create(new_app)
            new_apps += 1

            # Log initial StatusHistory timeline record
            history = StatusHistory(
                application_id=created_app.id,
                old_status=None,
                new_status=normalized_status,
                email_subject=raw_email.subject,
                email_date=raw_email.received_at,
                gmail_message_id=raw_email.message_id,
                llm_reason=extraction.llm_reason,
                status_confidence=status_conf,
                overall_confidence=extraction.overall_confidence,
                needs_review=needs_review,
                notes=extraction.notes
            )
            history_repo.create(history)

        # Ingestion succeeded: Mark raw email as COMPLETED
        raw_email.processing_state = "COMPLETED"
        raw_email.classification = "job_related"
        raw_email.error_message = None
        db.add(raw_email)
        db.commit()

    except Exception as e:
        db.rollback()
        
        # Dead letter queue retry evaluation
        raw_email.retry_count = (raw_email.retry_count or 0) + 1
        if raw_email.retry_count >= 3:
            raw_email.processing_state = "DEAD_LETTER"
        else:
            raw_email.processing_state = "FAILED"
            
        raw_email.error_message = str(e)
        db.add(raw_email)
        db.commit()
        
        logger.error(
            f"Failed database commit for email {raw_email.message_id}: {e}",
            extra={"action": "NODE_DB_UPDATE_ERROR", "message_id": raw_email.message_id}
        )
        
        errors = list(state["errors"])
        errors.append(f"DB Update {raw_email.message_id}: {str(e)}")
        return {
            **state,
            "errors": errors
        }

    return {
        **state,
        "new_applications": new_apps,
        "updated_applications": updated_apps
    }


def skip_email_node(state: GraphState, config: RunnableConfig) -> GraphState:
    """Updates non-job emails' pipeline state in database to IGNORED."""
    db: Session = config.get("configurable", {}).get("db")
    idx = state["current_idx"]
    msg_id = state["raw_email_ids"][idx]

    logger.info(
        f"LangGraph: executing skip_email_node for message_id={msg_id}.",
        extra={"action": "NODE_SKIP_EMAIL", "message_id": msg_id}
    )

    raw_repo = RawEmailRepository(db)
    raw_email = raw_repo.get_by_message_id(msg_id)
    if not raw_email:
        raise ValueError(f"RawEmail record with message_id {msg_id} not found in database during skip email.")

    try:
        raw_email.processing_state = "IGNORED"
        raw_email.classification = "ignored"
        db.add(raw_email)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to skip email {raw_email.message_id}: {e}")

    return state


def increment_index_node(state: GraphState) -> GraphState:
    """Increments index counter and clears temporal variables for the next loop iteration."""
    return {
        **state,
        "current_idx": state["current_idx"] + 1,
        "current_extraction": None,
        "current_normalized_status": None,
        "current_status_confidence": None,
        "is_duplicate": None,
        "matched_app_id": None
    }


def excel_export_node(state: GraphState, config: RunnableConfig) -> GraphState:
    """Overwrites and updates the Excel report tracker once at the end of the batch processing runs."""
    db: Session = config.get("configurable", {}).get("db")
    
    if state["new_applications"] > 0 or state["updated_applications"] > 0:
        logger.info("LangGraph: executing excel_export_node.", extra={"action": "NODE_EXCEL_EXPORT"})
        try:
            excel_service.sync_db_to_excel(db)
        except Exception as e:
            logger.error(f"Excel generation node failed: {e}")
            errors = list(state["errors"])
            errors.append(f"Excel Export: {str(e)}")
            return {
                **state,
                "errors": errors
            }
            
    return state
