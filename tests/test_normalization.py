from job_tracker.utils.normalization import can_transition
from job_tracker.models.application import ApplicationStatus


def test_can_transition_allowed():
    """Verifies that valid status progressions are permitted."""
    assert can_transition(None, ApplicationStatus.APPLIED)
    assert can_transition(ApplicationStatus.APPLIED, ApplicationStatus.SHORTLISTED)
    assert can_transition(ApplicationStatus.SHORTLISTED, ApplicationStatus.TECHNICAL_INTERVIEW)
    assert can_transition(ApplicationStatus.TECHNICAL_INTERVIEW, ApplicationStatus.OFFER_RECEIVED)
    assert can_transition(ApplicationStatus.OFFER_RECEIVED, ApplicationStatus.JOINED)
    assert can_transition(ApplicationStatus.APPLIED, ApplicationStatus.APPLICATION_RECEIVED)
    assert can_transition(ApplicationStatus.TECHNICAL_INTERVIEW, ApplicationStatus.HR_INTERVIEW)


def test_can_transition_regressions_blocked():
    """Verifies that regressions back to earlier status stages are blocked."""
    assert not can_transition(ApplicationStatus.TECHNICAL_INTERVIEW, ApplicationStatus.APPLIED)
    assert not can_transition(ApplicationStatus.OFFER_RECEIVED, ApplicationStatus.TECHNICAL_INTERVIEW)
    assert not can_transition(ApplicationStatus.REJECTED, ApplicationStatus.SHORTLISTED)


def test_can_transition_invalid_inputs():
    """Verifies that invalid status names are handled safely."""
    assert not can_transition(ApplicationStatus.APPLIED, "InvalidStatusName")
    assert can_transition("BadState", ApplicationStatus.APPLIED)
