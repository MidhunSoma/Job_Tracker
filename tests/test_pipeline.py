import os
import tempfile
import openpyxl
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from sqlalchemy.orm import Session

from job_tracker.config.settings import settings
from job_tracker.graph.workflow import app_graph
from job_tracker.models.application import ApplicationStatus
from job_tracker.models.raw_email import RawEmail
from job_tracker.repositories.application import ApplicationRepository
from job_tracker.repositories.status_history import StatusHistoryRepository
from job_tracker.repositories.raw_email import RawEmailRepository
from job_tracker.schemas.extraction import AIJobEmailExtraction


def get_mock_extraction(subject: str) -> tuple:
    if "Application Received: Software Engineer at Microsoft" in subject:
        parsed = AIJobEmailExtraction(
            is_job_email=True,
            company="Microsoft",
            role="Software Engineer",
            extracted_status="Application Received",
            recruiter_name="Recruiter Team",
            recruiter_email="careers@microsoft.com",
            notes="Thank you for applying. We received your application.",
            company_confidence=0.98,
            role_confidence=0.95,
            status_confidence=0.95,
            overall_confidence=0.96,
            llm_reason="Application receipt confirmation."
        )
        telemetry = {
            "raw_llm_json": '{"company": "Microsoft", "role": "Software Engineer"}',
            "prompt_version": "extract_prompt_v1",
            "model": "mock-model",
            "temperature": 0.0,
            "token_usage": '{"prompt_tokens": 120, "completion_tokens": 60}'
        }
        return parsed, telemetry

    elif "Interview Invitation: Software Engineer at Microsoft" in subject:
        parsed = AIJobEmailExtraction(
            is_job_email=True,
            company="Microsoft",
            role="Software Engineer",
            extracted_status="Technical Interview",
            recruiter_name="Jane Doe",
            recruiter_email="jane@microsoft.com",
            notes="Inviting you to a 45-minute coding session.",
            company_confidence=0.95,
            role_confidence=0.90,
            status_confidence=0.90,
            overall_confidence=0.92,
            llm_reason="Email requests technical coding interview scheduling."
        )
        telemetry = {
            "raw_llm_json": '{"status": "Technical Interview"}',
            "prompt_version": "extract_prompt_v1",
            "model": "mock-model",
            "temperature": 0.0,
            "token_usage": '{"prompt_tokens": 150, "completion_tokens": 80}'
        }
        return parsed, telemetry

    elif "Application Received: Different Job at Microsoft" in subject:
        parsed = AIJobEmailExtraction(
            is_job_email=True,
            company="Microsoft",
            role="Data Scientist",
            extracted_status="Applied",
            recruiter_name="Careers",
            recruiter_email="careers@microsoft.com",
            notes="Applied for Data Scientist role.",
            company_confidence=0.95,
            role_confidence=0.95,
            status_confidence=0.90,
            overall_confidence=0.94,
            llm_reason="Applied for Data Scientist."
        )
        telemetry = {
            "raw_llm_json": '{"company": "Microsoft", "role": "Data Scientist"}',
            "prompt_version": "extract_prompt_v1",
            "model": "mock-model",
            "temperature": 0.0,
            "token_usage": '{"prompt_tokens": 100, "completion_tokens": 50}'
        }
        return parsed, telemetry

    elif "Newsletter: Software engineering tips" in subject:
        parsed = AIJobEmailExtraction(
            is_job_email=False,
            company=None,
            role=None,
            extracted_status=None,
            recruiter_name=None,
            recruiter_email=None,
            notes=None,
            llm_reason="This is a general marketing/career advice newsletter."
        )
        telemetry = {
            "raw_llm_json": '{"is_job_email": false}',
            "prompt_version": "extract_prompt_v1",
            "model": "mock-model",
            "temperature": 0.0,
            "token_usage": '{"prompt_tokens": 80, "completion_tokens": 15}'
        }
        return parsed, telemetry

    elif "Ambiguous recruiter update" in subject:
        parsed = AIJobEmailExtraction(
            is_job_email=True,
            company="Unknown Startup",
            role="Engineer",
            extracted_status="Under Review",
            recruiter_name="Anonymous",
            recruiter_email="recruiting@startup.co",
            notes="Ambiguous status update.",
            company_confidence=0.50,
            role_confidence=0.40,
            status_confidence=0.50,
            overall_confidence=0.48,
            llm_reason="Ambiguous email body, low overall confidence."
        )
        telemetry = {
            "raw_llm_json": '{"company": "Unknown Startup"}',
            "prompt_version": "extract_prompt_v1",
            "model": "mock-model",
            "temperature": 0.0,
            "token_usage": '{"prompt_tokens": 110, "completion_tokens": 55}'
        }
        return parsed, telemetry
        
    return None, {}


def mock_normalize_status(self, raw_status: str) -> tuple:
    if "Technical Interview" in raw_status:
        return "Technical Interview", 0.95
    elif "Application Received" in raw_status:
        return "Application Received", 0.95
    elif "Under Review" in raw_status:
        return "Under Review", 0.90
    return "Applied", 0.90


@patch("job_tracker.services.llm_service.LLMService.extract_job_details")
@patch("job_tracker.services.llm_service.LLMService.normalize_status")
@patch("job_tracker.services.gmail_service.GmailService.sync_emails")
def test_pipeline_e2e(
    mock_sync,
    mock_norm,
    mock_extract,
    db_session: Session
):
    """E2E Integration test verifying email ingestion, classification, duplicate check,

    anti-regression status updates, DLQ handling, and Excel output sync.
    """
    mock_sync.return_value = 0
    
    email1 = RawEmail(
        message_id="msg001",
        thread_id="thread001",
        subject="Application Received: Software Engineer at Microsoft",
        sender="careers@microsoft.com",
        received_at=datetime(2026, 7, 1, 10, 0, 0),
        snippet="Thanks for applying",
        body="Body of application confirmation",
        processing_state="NEW"
    )
    email2 = RawEmail(
        message_id="msg002",
        thread_id="thread001",
        subject="Interview Invitation: Software Engineer at Microsoft",
        sender="jane@microsoft.com",
        received_at=datetime(2026, 7, 2, 11, 0, 0),
        snippet="Please schedule your interview",
        body="Body of interview invitation",
        processing_state="NEW"
    )
    email3 = RawEmail(
        message_id="msg003",
        thread_id="thread001",
        subject="Application Received: Software Engineer at Microsoft",
        sender="careers@microsoft.com",
        received_at=datetime(2026, 7, 3, 9, 0, 0),
        snippet="We received your application",
        body="Repeated application confirmation",
        processing_state="NEW"
    )
    email4 = RawEmail(
        message_id="msg004",
        thread_id="thread002",
        subject="Newsletter: Software engineering tips",
        sender="newsletter@medium.com",
        received_at=datetime(2026, 7, 3, 10, 0, 0),
        snippet="Tips for python",
        body="Newsletter tips details",
        processing_state="NEW"
    )
    email5 = RawEmail(
        message_id="msg005",
        thread_id="thread003",
        subject="Ambiguous recruiter update",
        sender="recruiting@startup.co",
        received_at=datetime(2026, 7, 3, 12, 0, 0),
        snippet="ambiguous",
        body="Low confidence content",
        processing_state="NEW"
    )
    db_session.add_all([email1, email2, email3, email4, email5])
    db_session.commit()

    mock_extract.side_effect = lambda subject, sender, date_str, body: get_mock_extraction(subject)
    mock_norm.side_effect = lambda raw_status: mock_normalize_status(None, raw_status)

    fd, temp_path_str = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    temp_path = Path(temp_path_str)
    original_excel_path = settings.export.excel_path
    settings.export.excel_path = temp_path

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
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "errors": []
        }
        
        final_state = app_graph.invoke(
            initial_state,
            {"configurable": {"db": db_session, "thread_id": "test_e2e_run"}}
        )

        assert final_state["emails_scanned"] == 5
        assert final_state["emails_processed"] == 5
        assert final_state["new_applications"] == 2
        assert final_state["updated_applications"] == 1
        assert len(final_state["errors"]) == 0
        assert final_state["cost_usd"] > 0.0

        app_repo = ApplicationRepository(db_session)
        apps = app_repo.get_all()
        assert len(apps) == 2
        
        ms_app = next(a for a in apps if a.company == "Microsoft")
        assert ms_app.role == "Software Engineer"
        assert ms_app.status == ApplicationStatus.TECHNICAL_INTERVIEW
        assert ms_app.needs_review is False
        
        startup_app = next(a for a in apps if a.company == "Unknown Startup")
        assert startup_app.needs_review is True
        
        history_repo = StatusHistoryRepository(db_session)
        ms_history = history_repo.get_by_application_id(ms_app.id)
        assert len(ms_history) == 3
        
        regression_event = next(h for h in ms_history if h.gmail_message_id == "msg003")
        assert regression_event.old_status == "Technical Interview"
        assert regression_event.new_status == "Application Received"
        assert "[REGRESSION BLOCKED]" in regression_event.notes

        raw_repo = RawEmailRepository(db_session)
        assert raw_repo.get_by_message_id("msg001").processing_state == "COMPLETED"
        assert raw_repo.get_by_message_id("msg002").processing_state == "COMPLETED"
        assert raw_repo.get_by_message_id("msg003").processing_state == "COMPLETED"
        assert raw_repo.get_by_message_id("msg004").processing_state == "IGNORED"
        assert raw_repo.get_by_message_id("msg005").processing_state == "COMPLETED"

        assert temp_path.exists()
        wb = openpyxl.load_workbook(temp_path)
        ws = wb.active
        assert ws.max_row == 3

    finally:
        settings.export.excel_path = original_excel_path
        if temp_path.exists():
            os.remove(temp_path)
