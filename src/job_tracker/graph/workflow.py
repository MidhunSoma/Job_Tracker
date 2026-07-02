from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import GraphState
from .nodes import (
    fetch_emails_node,
    classify_and_extract_node,
    normalize_and_dedup_node,
    db_update_node,
    skip_email_node,
    increment_index_node,
    excel_export_node,
)


def should_continue_loop(state: GraphState) -> str:
    """Checks if there are still unprocessed raw emails left in the batch list.

    Args:
        state: The current workflow state.

    Returns:
        "classify_and_extract" if current index < total emails, else "excel_export".
    """
    if state["current_idx"] < len(state["raw_email_ids"]):
        return "classify_and_extract"
    return "excel_export"


def is_job_email_router(state: GraphState) -> str:
    """Routes based on whether the email was classified as job-related or if extraction failed.

    Args:
        state: The current workflow state.

    Returns:
        The name of the next node to execute.
    """
    extraction = state.get("current_extraction")
    if not extraction:
        # If extraction failed, skip directly to increment index (error is logged in state)
        return "increment_index"
        
    if extraction.is_job_email:
        return "normalize_and_dedup"
        
    return "skip_email"


# Instantiate the workflow graph
workflow = StateGraph(GraphState)

# Add execution nodes
workflow.add_node("fetch_emails", fetch_emails_node)
workflow.add_node("classify_and_extract", classify_and_extract_node)
workflow.add_node("normalize_and_dedup", normalize_and_dedup_node)
workflow.add_node("db_update", db_update_node)
workflow.add_node("skip_email", skip_email_node)
workflow.add_node("increment_index", increment_index_node)
workflow.add_node("excel_export", excel_export_node)

# Declare transition edges
workflow.set_entry_point("fetch_emails")

# Route from entry point: check if we have any emails fetched
workflow.add_conditional_edges(
    "fetch_emails",
    should_continue_loop,
    {
        "classify_and_extract": "classify_and_extract",
        "excel_export": "excel_export"
    }
)

# Route from classification/extraction: check if it's a job-related email
workflow.add_conditional_edges(
    "classify_and_extract",
    is_job_email_router,
    {
        "normalize_and_dedup": "normalize_and_dedup",
        "skip_email": "skip_email",
        "increment_index": "increment_index"
    }
)

# Linear transitions
workflow.add_edge("normalize_and_dedup", "db_update")
workflow.add_edge("db_update", "increment_index")
workflow.add_edge("skip_email", "increment_index")

# Route back to top of loop or end
workflow.add_conditional_edges(
    "increment_index",
    should_continue_loop,
    {
        "classify_and_extract": "classify_and_extract",
        "excel_export": "excel_export"
    }
)

# Final exit edge
workflow.add_edge("excel_export", END)

# Compile the compiled runnable graph with MemorySaver checkpointer
app_graph = workflow.compile(checkpointer=MemorySaver())
