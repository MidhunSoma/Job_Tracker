from typing import Optional
from ..models.application import ApplicationStatus

# Precedence ranking for statuses to prevent invalid regression overrides
STATUS_PRECEDENCE = {
    ApplicationStatus.APPLIED: 1,
    ApplicationStatus.APPLICATION_RECEIVED: 1,
    ApplicationStatus.UNDER_REVIEW: 2,
    ApplicationStatus.SHORTLISTED: 3,
    ApplicationStatus.ASSESSMENT_ROUND: 4,
    ApplicationStatus.ASSIGNMENT_ROUND: 4,
    ApplicationStatus.ONLINE_TEST: 4,
    ApplicationStatus.CODING_CHALLENGE: 4,
    ApplicationStatus.INTERVIEW_SCHEDULED: 5,
    ApplicationStatus.TECHNICAL_INTERVIEW: 6,
    ApplicationStatus.HR_INTERVIEW: 6,
    ApplicationStatus.FINAL_INTERVIEW: 7,
    ApplicationStatus.INTERVIEW_COMPLETED: 8,
    ApplicationStatus.OFFER_RECEIVED: 9,
    ApplicationStatus.OFFER_ACCEPTED: 10,
    ApplicationStatus.OFFER_DECLINED: 10,
    ApplicationStatus.REJECTED: 10,
    ApplicationStatus.POSITION_CLOSED: 10,
    ApplicationStatus.WITHDRAWN: 10,
    ApplicationStatus.JOINED: 11,
}


def can_transition(current_status_str: Optional[str], new_status_str: str) -> bool:
    """Checks whether a status transition is valid by comparing precedence weights.

    Prevents regressions (e.g. overriding Interview with Applied) unless it is a new application.

    Args:
        current_status_str: The current status of the application, if any.
        new_status_str: The new status proposed.

    Returns:
        True if transition is allowed (weight is equal or greater), False otherwise.
    """
    if not current_status_str:
        return True

    # Try mapping strings to ApplicationStatus enums
    try:
        current_status = ApplicationStatus(current_status_str)
    except ValueError:
        # If current status is non-standard, allow overwrite
        return True

    try:
        new_status = ApplicationStatus(new_status_str)
    except ValueError:
        # If new status is invalid, do not allow transition
        return False

    current_weight = STATUS_PRECEDENCE.get(current_status, 0)
    new_weight = STATUS_PRECEDENCE.get(new_status, 0)

    # Transition allowed if new weight is equal or higher
    return new_weight >= current_weight
