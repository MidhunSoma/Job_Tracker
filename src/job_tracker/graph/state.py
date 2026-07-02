from typing import List, Optional, TypedDict
from ..schemas.extraction import AIJobEmailExtraction


class GraphState(TypedDict):
    """The state representation passed between nodes in the LangGraph workflow."""
    
    # Ingestion Batch context (serializable list of message IDs)
    raw_email_ids: List[str]
    current_idx: int
    
    # Extraction output of the current email under process
    current_extraction: Optional[AIJobEmailExtraction]
    
    # Normalization outputs
    current_normalized_status: Optional[str]
    current_status_confidence: Optional[float]
    
    # Duplicate checking outputs
    is_duplicate: Optional[bool]
    matched_app_id: Optional[int]
    
    # Process telemetry counters
    emails_scanned: int
    emails_processed: int
    new_applications: int
    updated_applications: int
    
    # AI Cost Metrics Tracking
    input_tokens: int
    output_tokens: int
    cost_usd: float
    
    # Pipeline execution logging
    errors: List[str]
