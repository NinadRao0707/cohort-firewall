"""QuestionSpec: the structured form of a proposed AI question.

Kept dependency-free (dataclasses + manual validation) so the engine runs anywhere.
The FastAPI layer can mirror this with Pydantic for request validation.

Default-deny: if a spec fails validation, the engine returns INSUFFICIENT_EVIDENCE
rather than guessing what the user meant.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any

TASK_TYPES = {"binary_classification", "survival", "regression", "descriptive"}
INTENDED_USES = {
    "research",                      # allowed
    "model_development",             # allowed
    "clinical_decision_support",     # out of scope for this event -> BLOCKED
    "direct_patient_care",           # out of scope for this event -> BLOCKED
}
FILTER_OPS = {"==", "!=", ">", ">=", "<", "<=", "in", "not_in"}


@dataclass
class PopulationFilter:
    column: str
    op: str
    value: Any


@dataclass
class QuestionSpec:
    question_text: str
    task_type: str
    intended_use: str
    cancer_type: str | None = None
    population_filters: list[PopulationFilter] = field(default_factory=list)
    outcome_column: str | None = None
    outcome_positive_value: Any = 1
    time_column: str | None = None          # follow-up / time-to-event column
    time_horizon_months: float | None = None
    feature_columns: list[str] = field(default_factory=list)  # ["*"] = all eligible columns
    subgroup_columns: list[str] = field(default_factory=list)
    parse_confidence: float = 1.0           # set by the LLM parser; 1.0 for hand-written specs
    parser_notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), default=str)


class SpecError(ValueError):
    pass


def spec_from_dict(d: dict) -> QuestionSpec:
    """Validate and build a QuestionSpec. Raises SpecError listing every problem found."""
    errors: list[str] = []
    if not isinstance(d, dict):
        raise SpecError("spec must be a JSON object")

    def req_str(key):
        v = d.get(key)
        if not isinstance(v, str) or not v.strip():
            errors.append(f"'{key}' is required and must be a non-empty string")
        return v

    question_text = req_str("question_text")
    task_type = req_str("task_type")
    intended_use = req_str("intended_use")
    if isinstance(task_type, str) and task_type not in TASK_TYPES:
        errors.append(f"task_type must be one of {sorted(TASK_TYPES)}")
    if isinstance(intended_use, str) and intended_use not in INTENDED_USES:
        errors.append(f"intended_use must be one of {sorted(INTENDED_USES)}")

    filters = []
    for i, f in enumerate(d.get("population_filters") or []):
        if not isinstance(f, dict) or not {"column", "op", "value"} <= set(f):
            errors.append(f"population_filters[{i}] needs column, op, value")
            continue
        if f["op"] not in FILTER_OPS:
            errors.append(f"population_filters[{i}].op must be one of {sorted(FILTER_OPS)}")
            continue
        filters.append(PopulationFilter(str(f["column"]), f["op"], f["value"]))

    for key in ("feature_columns", "subgroup_columns"):
        v = d.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errors.append(f"'{key}' must be a list of strings")

    if task_type in {"binary_classification", "survival", "regression"} and not d.get("outcome_column"):
        errors.append(f"task_type '{task_type}' requires outcome_column")
    if task_type == "survival" and not d.get("time_column"):
        errors.append("survival task requires time_column")

    conf = d.get("parse_confidence", 1.0)
    try:
        conf = float(conf)
        if not 0.0 <= conf <= 1.0:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("parse_confidence must be a number in [0, 1]")
        conf = 0.0

    horizon = d.get("time_horizon_months")
    if horizon is not None:
        try:
            horizon = float(horizon)
        except (TypeError, ValueError):
            errors.append("time_horizon_months must be a number")

    if errors:
        raise SpecError("; ".join(errors))

    return QuestionSpec(
        question_text=question_text.strip(),
        task_type=task_type,
        intended_use=intended_use,
        cancer_type=d.get("cancer_type"),
        population_filters=filters,
        outcome_column=d.get("outcome_column"),
        outcome_positive_value=d.get("outcome_positive_value", 1),
        time_column=d.get("time_column"),
        time_horizon_months=horizon,
        feature_columns=list(d.get("feature_columns", [])),
        subgroup_columns=list(d.get("subgroup_columns", [])),
        parse_confidence=conf,
        parser_notes=str(d.get("parser_notes", "")),
    )
