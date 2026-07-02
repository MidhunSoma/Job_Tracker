from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..schemas.application import ApplicationResponse
from ..services.application_service import ApplicationService
from ..utils.logging import logger

router = APIRouter(prefix="/api/jobs", tags=["Job Applications"])


@router.get("", response_model=List[ApplicationResponse])
def get_all_applications(db: Session = Depends(get_db)):
    """Retrieves all tracked job applications with their status timeline history."""
    try:
        service = ApplicationService(db)
        apps = service.get_all_applications()
        logger.info(
            f"API: Fetched {len(apps)} applications.",
            extra={"action": "API_GET_ALL_JOBS", "count": len(apps)}
        )
        return apps
    except Exception as e:
        logger.exception("API: Failed to retrieve job applications.")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application(app_id: int, db: Session = Depends(get_db)):
    """Retrieves a specific job application by database ID."""
    service = ApplicationService(db)
    app = service.get_application(app_id)
    if not app:
        logger.warning(
            f"API: Job application ID {app_id} not found.",
            extra={"action": "API_GET_JOB_NOT_FOUND", "app_id": app_id}
        )
        raise HTTPException(status_code=404, detail=f"Job application ID {app_id} not found.")
    
    logger.info(
        f"API: Fetched application ID {app_id} for company '{app.company}'.",
        extra={"action": "API_GET_JOB_SUCCESS", "app_id": app_id, "company": app.company}
    )
    return app
