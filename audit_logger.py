"""
Comprehensive audit logging system for revenue and leads analysis.
Tracks all calculations with full context for debugging and validation.
"""

import logging
import json
from typing import Any, Dict, List
from datetime import datetime
from dataclasses import dataclass, asdict
import sys


@dataclass
class AuditLog:
    """Structured audit log entry."""
    timestamp: str
    operation: str
    module: str
    query: str
    input_rows: int
    output_rows: int
    filters_applied: List[str]
    formula_used: str
    result_value: Any
    column_mapping: Dict[str, str]
    validation_status: bool
    error_message: str = ""
    notes: List[str] = None

    def __post_init__(self):
        if self.notes is None:
            self.notes = []


class AuditLogger:
    """Centralized audit logger for revenue and leads calculations."""

    def __init__(self, log_file: str = "audit_trail.log"):
        self.log_file = log_file
        self.logger = logging.getLogger("AuditLogger")
        self.logger.setLevel(logging.DEBUG)

        # File handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def log_operation(self, audit_log: AuditLog) -> None:
        """Log a complete operation with structured data."""
        log_dict = asdict(audit_log)
        self.logger.info(f"AUDIT: {json.dumps(log_dict, indent=2, default=str)}", extra={'encoding': 'utf-8'})

    def log_calculation(
        self,
        operation: str,
        module: str,
        query: str,
        input_rows: int,
        output_rows: int,
        filters: List[str],
        formula: str,
        result: Any,
        column_mapping: Dict[str, str],
        validation_passed: bool,
        notes: List[str] = None,
    ) -> None:
        """Convenience method to log a calculation step."""
        audit_log = AuditLog(
            timestamp=datetime.now().isoformat(),
            operation=operation,
            module=module,
            query=query,
            input_rows=input_rows,
            output_rows=output_rows,
            filters_applied=filters,
            formula_used=formula,
            result_value=result,
            column_mapping=column_mapping,
            validation_status=validation_passed,
            notes=notes or [],
        )
        self.log_operation(audit_log)

    def log_data_validation(
        self,
        dataset_name: str,
        expected_columns: List[str],
        actual_columns: List[str],
        validation_passed: bool,
        issues: List[str] = None,
    ) -> None:
        """Log data validation checks."""
        self.logger.debug(
            f"DATA VALIDATION - Dataset: {dataset_name}, "
            f"Expected: {expected_columns}, Actual: {actual_columns}, "
            f"Valid: {validation_passed}"
        )
        if issues:
            for issue in issues:
                self.logger.warning(f"  - {issue}")

    def log_row_inspection(
        self,
        operation: str,
        dataset_name: str,
        row_indices: List[int],
        row_values: List[Dict[str, Any]],
    ) -> None:
        """Log specific row-level inspections."""
        self.logger.debug(
            f"ROW INSPECTION - Op: {operation}, Dataset: {dataset_name}, "
            f"Rows: {row_indices}"
        )
        for idx, row in zip(row_indices, row_values):
            self.logger.debug(f"  Row {idx}: {json.dumps(row, default=str)}")


# Global logger instance
_audit_logger = None


def get_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
