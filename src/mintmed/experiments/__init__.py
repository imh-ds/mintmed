"""Frozen validation experiments and evidence reporting.

Exports are resolved lazily so ``python -m
mintmed.experiments.mediation_validation`` does not import the target module
before ``runpy`` executes it.
"""

__all__ = [
    "COMBINATION_COLUMNS",
    "EVIDENCE_ARTIFACTS",
    "RAW_COLUMNS",
    "ValidationConfig",
    "cell_definition",
    "cell_truth",
    "expected_combinations",
    "expected_row_count",
    "extract_metrics",
    "generate_cell",
    "load_config",
    "metric_record",
    "run",
    "seed_pair",
    "selected_combinations",
]


def __getattr__(name: str):
    if name in __all__:
        from . import mediation_validation

        return getattr(mediation_validation, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
