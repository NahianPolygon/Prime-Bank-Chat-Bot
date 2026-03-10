"""Tasks module for bank chatbot agents."""

from .retrieval import retrieve_products_task
from .eligibility import analyze_eligibility_task
from .comparison import compare_features_task
from .formatting import format_response_task
from .alternatives import recommend_alternatives_task
from .cardholder_task import cardholder_service_task

__all__ = [
    "retrieve_products_task",
    "analyze_eligibility_task",
    "compare_features_task",
    "format_response_task",
    "recommend_alternatives_task",
    "cardholder_service_task",
]
