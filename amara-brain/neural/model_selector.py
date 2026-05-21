"""
Model selection layer — consults accuracy_tracker for data-driven choice,
falls back to TASK_MODEL_MAP defaults when data is insufficient.
"""

from neural import accuracy_tracker


def get_best_model(task_type: str) -> str:
    """Returns the best model for task_type based on empirical accuracy."""
    return accuracy_tracker.get_best_model(task_type)
