"""Evaluation package for dry-run verification accuracy, anomaly detection rates, and Anomaly Lab telemetry."""

from backend.evaluation.evaluator import (
    ANOMALY_SCENARIO_META,
    EvaluationRunner,
    get_latest_evaluation_report,
    reset_latest_evaluation_report,
)

__all__ = [
    "ANOMALY_SCENARIO_META",
    "EvaluationRunner",
    "get_latest_evaluation_report",
    "reset_latest_evaluation_report",
]

