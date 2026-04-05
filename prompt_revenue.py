from __future__ import annotations

import json
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

try:
    import pandas as pd
except ImportError:  # pragma: no cover - pandas is optional at import time
    pd = None


SYSTEM_PROMPT = """
You are an AI Business Analyst focused on revenue analysis.

Your job is to analyze the provided dataset and answer the user's revenue
question using only the rows that appear in the dataset payload.

Mandatory rules:
1. Treat the dataset as the single source of truth.
2. Decompose the query into:
   - entity
   - metric
   - operation
   - filters
   - sort
   - limit
3. Never fabricate columns, values, groups, or totals.
4. Use exact row-level evidence from the provided dataset.
5. If the dataset is partial, mention that in notes instead of pretending you saw more rows.
6. If grouping is used, the sum of grouped values must equal the total dataset value.
7. If a required column is missing, set validation_passed to false and explain why in notes.
8. Return structured JSON only and follow the schema exactly.

Validation rules:
- total_dataset_value must represent the full revenue total from the filtered dataset.
- sum_of_group_values must equal the sum of all grouped entity totals.
- row_count_lock must equal the total number of rows used in the calculation.
- validation_passed must be true only when the totals reconcile.

Self-check before you answer:
- Did you use the actual dataset rows?
- Did you apply all filters mentioned in the query?
- Did you avoid estimating missing values?
- Does total_dataset_value equal sum_of_group_values?

If any check fails, return validation_passed=false and explain the issue in notes.
"""


CORRECTION_SYSTEM_PROMPT = """
You are repairing a previous revenue-analysis result that failed validation.

Recalculate from scratch using only the provided dataset and original query.
Do not defend the earlier answer. Produce a corrected JSON response that satisfies
the schema and reconciliation rules.
"""


class RevenueFilter(BaseModel):
    column: str = Field(description="Real dataset column used for filtering.")
    operator: str = Field(
        default="=",
        description="Filter operator such as '=', '!=', '>', '<', or 'contains'.",
    )
    value: Any = Field(description="Filter value extracted from the user query.")


class RevenueGroupResult(BaseModel):
    entity_value: str = Field(description="Grouped entity value, such as a user or campaign name.")
    metric_value: float = Field(description="Calculated revenue for this entity.")
    row_count: int = Field(description="How many rows contributed to this grouped value.")


class RevenueAnalysis(BaseModel):
    entity: str = Field(description="Column name used to group results.")
    metric: str = Field(description="Metric being calculated, usually revenue.")
    operation: str = Field(description="Math operation such as SUM, AVG, or COUNT.")
    filters: list[RevenueFilter] = Field(
        default_factory=list,
        description="Filters applied to the dataset before calculation.",
    )
    sort: str = Field(description="Sort direction, usually DESC or ASC.")
    limit: int | None = Field(
        default=None,
        description="Maximum number of grouped results requested by the user.",
    )
    group_results: list[RevenueGroupResult] = Field(
        default_factory=list,
        description="Grouped revenue results after applying filters.",
    )
    total_dataset_value: float = Field(
        description="Revenue total calculated directly from all filtered dataset rows.",
    )
    sum_of_group_values: float = Field(
        description="Sum of every metric_value inside group_results.",
    )
    row_count_lock: int = Field(
        description="Number of dataset rows actually used in the calculation.",
    )
    validation_passed: bool = Field(
        description="True only if the grouped totals reconcile with the dataset total.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Short notes about assumptions, limitations, or validation issues.",
    )


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def serialize_dataset(dataset: Any) -> str:
    """
    Convert common dataset inputs into a prompt-friendly string.
    Supports raw strings, lists of dicts, dict payloads, and pandas DataFrames.
    """
    if dataset is None:
        return ""

    if isinstance(dataset, str):
        return dataset

    if pd is not None and isinstance(dataset, pd.DataFrame):
        return json.dumps(dataset.to_dict(orient="records"), indent=2, default=str)

    if isinstance(dataset, (list, dict, tuple)):
        return json.dumps(dataset, indent=2, default=str)

    return str(dataset)


def build_revenue_parser() -> JsonOutputParser:
    return JsonOutputParser(pydantic_object=RevenueAnalysis)


def build_revenue_prompt(
    parser: JsonOutputParser | None = None,
) -> ChatPromptTemplate:
    parser = parser or build_revenue_parser()
    return ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}\n\n{format_instructions}"),
            (
                "human",
                "Analyze this dataset for revenue.\n\nDataset:\n{dataset}\n\nQuery:\n{query}",
            ),
        ]
    ).partial(
        system_prompt=SYSTEM_PROMPT,
        format_instructions=parser.get_format_instructions(),
    )


def build_revenue_correction_prompt(
    parser: JsonOutputParser | None = None,
) -> ChatPromptTemplate:
    parser = parser or build_revenue_parser()
    return ChatPromptTemplate.from_messages(
        [
            ("system", "{system_prompt}\n\n{format_instructions}"),
            (
                "human",
                "The previous result failed validation.\n\n"
                "Dataset:\n{dataset}\n\n"
                "Original Query:\n{query}\n\n"
                "Previous Result:\n{previous_result}\n\n"
                "Validation Error:\n{validation_error}\n\n"
                "Recalculate and return corrected JSON only.",
            ),
        ]
    ).partial(
        system_prompt=f"{SYSTEM_PROMPT}\n\n{CORRECTION_SYSTEM_PROMPT}",
        format_instructions=parser.get_format_instructions(),
    )


def build_revenue_chain(model: Any, parser: JsonOutputParser | None = None):
    parser = parser or build_revenue_parser()
    prompt = build_revenue_prompt(parser)
    return prompt | model | parser


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_revenue_result(
    result: dict[str, Any] | RevenueAnalysis,
    tolerance: float = 0.01,
) -> tuple[bool, str]:
    payload = _model_dump(result) if isinstance(result, BaseModel) else dict(result)

    total_dataset_value = _coerce_float(payload.get("total_dataset_value"))
    sum_of_group_values = _coerce_float(payload.get("sum_of_group_values"))
    row_count_lock = _coerce_int(payload.get("row_count_lock"))
    validation_passed = bool(payload.get("validation_passed"))
    group_results = payload.get("group_results") or []
    requested_limit = payload.get("limit")

    if not validation_passed:
        return False, "Model reported validation_passed=false."

    if abs(total_dataset_value - sum_of_group_values) > tolerance:
        return (
            False,
            "Aggregation mismatch: total_dataset_value does not equal sum_of_group_values.",
        )

    if row_count_lock < 0:
        return False, "row_count_lock must be zero or greater."

    if requested_limit is not None and len(group_results) > requested_limit:
        return False, "group_results exceeds the requested limit."

    return True, ""


def build_failure_result(query: str, error_message: str) -> dict[str, Any]:
    return {
        "entity": "unknown",
        "metric": "revenue",
        "operation": "SUM",
        "filters": [],
        "sort": "DESC",
        "limit": None,
        "group_results": [],
        "total_dataset_value": 0.0,
        "sum_of_group_values": 0.0,
        "row_count_lock": 0,
        "validation_passed": False,
        "notes": [
            "Data inconsistency detected. Unable to compute reliable result from provided dataset.",
            f"Original query: {query}",
            error_message,
        ],
    }


def run_revenue_analysis(
    model: Any,
    dataset: Any,
    query: str,
    max_attempts: int = 2,
) -> dict[str, Any]:
    """
    Execute the revenue-analysis prompt and automatically retry once when the
    result fails the reconciliation checks.

    The provided model must be LCEL-compatible, for example:
    `ChatOpenAI(...)`, `ChatAnthropic(...)`, or another LangChain chat model.
    """
    parser = build_revenue_parser()
    dataset_text = serialize_dataset(dataset)
    prompt = build_revenue_prompt(parser)
    correction_prompt = build_revenue_correction_prompt(parser)

    previous_result: dict[str, Any] | None = None
    validation_error = ""

    for attempt in range(1, max_attempts + 1):
        chain = (prompt if attempt == 1 else correction_prompt) | model | parser

        payload = {
            "dataset": dataset_text,
            "query": query,
        }

        if attempt > 1:
            payload["previous_result"] = json.dumps(previous_result or {}, indent=2)
            payload["validation_error"] = validation_error

        result = chain.invoke(payload)
        is_valid, validation_error = validate_revenue_result(result)

        if is_valid:
            return result

        previous_result = result

    return build_failure_result(query=query, error_message=validation_error)


# ---------------------------------------------------------------------------
# Legacy revenue helpers kept for compatibility with any external imports.
# ---------------------------------------------------------------------------

def total_revenue(context: dict[str, Any]) -> Any:
    return context.get("revenue")


def revenue_per_click(context: dict[str, Any]) -> float | None:
    revenue = context.get("revenue")
    clicks = context.get("clicks")

    if not clicks:
        return None

    return round(revenue / clicks, 2)


def roas(context: dict[str, Any]) -> float | None:
    revenue = context.get("revenue")
    cost = context.get("cost")

    if not cost:
        return None

    return round(revenue / cost, 2)


def revenue_per_user(context: dict[str, Any]) -> float | None:
    revenue = context.get("revenue")
    users = context.get("users")

    if not users:
        return None

    return round(revenue / users, 2)


def revenue_contribution(
    context: dict[str, Any],
    global_context: dict[str, Any],
) -> float | None:
    revenue = context.get("revenue")
    global_revenue = global_context.get("revenue")

    if not global_revenue:
        return None

    return round((revenue / global_revenue) * 100, 2)


__all__ = [
    "SYSTEM_PROMPT",
    "CORRECTION_SYSTEM_PROMPT",
    "RevenueFilter",
    "RevenueGroupResult",
    "RevenueAnalysis",
    "serialize_dataset",
    "build_revenue_parser",
    "build_revenue_prompt",
    "build_revenue_correction_prompt",
    "build_revenue_chain",
    "validate_revenue_result",
    "build_failure_result",
    "run_revenue_analysis",
    "total_revenue",
    "revenue_per_click",
    "roas",
    "revenue_per_user",
    "revenue_contribution",
]
