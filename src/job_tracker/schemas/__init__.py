from .email import EmailMetadata, EmailExtractionResult
from .extraction import AIJobEmailExtraction
from .application import ApplicationBase, ApplicationCreate, ApplicationUpdate, ApplicationResponse
from .status import StatusHistoryBase, StatusHistoryCreate, StatusHistoryResponse

__all__ = [
    "EmailMetadata",
    "EmailExtractionResult",
    "AIJobEmailExtraction",
    "ApplicationBase",
    "ApplicationCreate",
    "ApplicationUpdate",
    "ApplicationResponse",
    "StatusHistoryBase",
    "StatusHistoryCreate",
    "StatusHistoryResponse",
]
