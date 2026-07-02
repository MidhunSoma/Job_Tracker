from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.application import Application
from ..models.status_history import StatusHistory
from ..models.raw_email import RawEmail
from ..repositories.application import ApplicationRepository
from ..repositories.status_history import StatusHistoryRepository
from ..repositories.raw_email import RawEmailRepository
from ..schemas.application import ApplicationResponse
from ..services.llm_service import LLMService
from ..utils.matching import is_duplicate_application
from ..utils.normalization import can_transition
from ..utils.logging import logger


class ApplicationService:
    """Service encapsulating all job application business logic and validation rules."""

    def __init__(self, db: Session) -> None:
        """Initializes the ApplicationService.

        Args:
            db: SQLAlchemy Session dependency.
        """
        self.db = db
        self.app_repo = ApplicationRepository(db)
        self.history_repo = StatusHistoryRepository(db)
        self.raw_repo = RawEmailRepository(db)
        self.llm_service = LLMService()

    def get_application(self, app_id: int) -> Optional[ApplicationResponse]:
        """Fetches an application by ID."""
        app = self.app_repo.get(app_id)
        if app:
            return ApplicationResponse.model_validate(app)
        return None

    def get_all_applications(self) -> List[ApplicationResponse]:
        """Fetches all applications."""
        apps = self.app_repo.get_all()
        return [ApplicationResponse.model_validate(app) for app in apps]

    def process_raw_email(self, raw_email: RawEmail) -> Optional[Application]:
        """Runs the complete AI extraction and database synchronization pipeline for one raw email.

        Uses the processing queue states (NEW -> PROCESSING -> COMPLETED/FAILED/IGNORED).

        Args:
            raw_email: The raw email record to process.

        Returns:
            The created or updated Application if job-related and succeeded, else None.
        """
        logger.info(
            f"Starting AI pipeline for raw email ID {raw_email.message_id}.",
            extra={"action": "START_PIPELINE", "message_id": raw_email.message_id}
        )
        
        # 1. Update state to PROCESSING to lock the email
        raw_email.processing_state = "PROCESSING"
        self.db.add(raw_email)
        self.db.commit()
        
        try:
            # 2. Call LLM for extraction (single call for classification + details)
            extraction, telemetry = self.llm_service.extract_job_details(
                subject=raw_email.subject or "",
                sender=raw_email.sender,
                date_str=raw_email.received_at.isoformat(),
                body=raw_email.body or ""
            )
            
            # Save LLM telemetry on RawEmail
            raw_email.raw_llm_json = telemetry.get("raw_llm_json")
            raw_email.prompt_version = telemetry.get("prompt_version")
            raw_email.model = telemetry.get("model")
            raw_email.temperature = telemetry.get("temperature")
            raw_email.token_usage = telemetry.get("token_usage")
            
            if not extraction:
                raise ValueError("LLM returned null extraction or failed to parse schema.")
                
            # 3. Check if email is classified as job-related
            if not extraction.is_job_email:
                raw_email.processing_state = "IGNORED"
                raw_email.classification = "ignored"
                self.db.add(raw_email)
                self.db.commit()
                logger.info(
                    f"Email {raw_email.message_id} classified as NOT job-related. Skipped.",
                    extra={"action": "CLASSIFY_IGNORED", "message_id": raw_email.message_id}
                )
                return None
                
            # 4. Normalize the hiring status
            normalized_status, status_conf = self.llm_service.normalize_status(
                extraction.extracted_status or "Applied"
            )
            
            # 5. Evaluate confidence score trigger for human review
            needs_review = extraction.overall_confidence < 0.70
            if needs_review:
                logger.warning(
                    f"Email {raw_email.message_id} has overall confidence {extraction.overall_confidence} < 0.70. Flagged for review.",
                    extra={"action": "LOW_CONFIDENCE_FLAG", "confidence": extraction.overall_confidence}
                )
            
            # 6. Perform fuzzy duplicate checking (Company + Role)
            all_apps = self.app_repo.get_all()
            matched_app = None
            for app in all_apps:
                if is_duplicate_application(app.company, app.role, extraction.company, extraction.role):
                    matched_app = app
                    break
            
            if matched_app:
                # Update existing application
                logger.info(
                    f"Duplicate detected: matching existing application (id={matched_app.id}, company='{matched_app.company}')",
                    extra={"action": "DUPLICATE_FOUND", "app_id": matched_app.id}
                )
                
                old_status = matched_app.status
                transition_allowed = can_transition(old_status, normalized_status)
                
                # Update latest details
                if extraction.recruiter_name:
                    matched_app.recruiter_name = extraction.recruiter_name
                if extraction.recruiter_email:
                    matched_app.recruiter_email = extraction.recruiter_email
                    
                matched_app.gmail_message_id = raw_email.message_id
                matched_app.gmail_thread_id = raw_email.thread_id
                matched_app.gmail_link = raw_email.gmail_link
                matched_app.last_email_date = raw_email.received_at
                
                # Append summaries to notes
                if extraction.notes:
                    date_stamp = raw_email.received_at.strftime("%Y-%m-%d")
                    note_entry = f"[{date_stamp}] Status update: {extraction.notes}"
                    if matched_app.notes:
                        matched_app.notes = matched_app.notes + "\n" + note_entry
                    else:
                        matched_app.notes = note_entry

                # Respect anti-regression status updates
                if transition_allowed:
                    matched_app.status = normalized_status
                    matched_app.company_confidence = extraction.company_confidence
                    matched_app.role_confidence = extraction.role_confidence
                    matched_app.status_confidence = status_conf
                    matched_app.overall_confidence = extraction.overall_confidence
                    matched_app.updated_at = datetime.utcnow()
                    
                    if needs_review:
                        matched_app.needs_review = True
                        
                    logger.info(
                        f"Updated application ID {matched_app.id} status: '{old_status}' -> '{normalized_status}'",
                        extra={"action": "APPLICATION_STATUS_UPDATED", "app_id": matched_app.id}
                    )
                else:
                    logger.warning(
                        f"Blocked status regression for application ID {matched_app.id} from '{old_status}' to '{normalized_status}'",
                        extra={"action": "STATUS_REGRESSION_BLOCKED", "app_id": matched_app.id}
                    )
                
                self.app_repo.update(matched_app)
                
                # Record in StatusHistory timeline
                history_note = extraction.notes
                if not transition_allowed:
                    history_note = f"[REGRESSION BLOCKED] {history_note or ''}"
                    
                history = StatusHistory(
                    application_id=matched_app.id,
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
                self.history_repo.create(history)
                target_app = matched_app
                
            else:
                # Create new application
                logger.info(
                    f"Creating new job application record: company='{extraction.company}', role='{extraction.role}'",
                    extra={"action": "CREATE_APPLICATION", "company": extraction.company, "role": extraction.role}
                )
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
                created_app = self.app_repo.create(new_app)
                
                # Record initial timeline state in StatusHistory
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
                self.history_repo.create(history)
                target_app = created_app

            # 7. Update raw email state to COMPLETED
            raw_email.processing_state = "COMPLETED"
            raw_email.classification = "job_related"
            raw_email.error_message = None
            self.db.add(raw_email)
            self.db.commit()
            
            logger.info(
                f"Successfully processed raw email ID {raw_email.message_id}.",
                extra={"action": "PIPELINE_SUCCESS", "message_id": raw_email.message_id}
            )
            return target_app
            
        except Exception as e:
            self.db.rollback()
            # 8. Dead letter queue retry evaluation
            raw_email.retry_count = (raw_email.retry_count or 0) + 1
            if raw_email.retry_count >= 3:
                raw_email.processing_state = "DEAD_LETTER"
                logger.error(
                    f"Email {raw_email.message_id} failed 3 times. Quarantined as DEAD_LETTER.",
                    extra={"action": "PIPELINE_DEAD_LETTER", "message_id": raw_email.message_id, "error": str(e)}
                )
            else:
                raw_email.processing_state = "FAILED"
                
            raw_email.error_message = str(e)
            self.db.add(raw_email)
            self.db.commit()
            
            logger.exception(
                f"Pipeline failed for raw email ID {raw_email.message_id}. Retries: {raw_email.retry_count}.",
                extra={"action": "PIPELINE_FAILURE", "message_id": raw_email.message_id}
            )
            return None
