# Dependency Audit Report

### `app.py`
1. **Imported by:** None
2. **Referenced by:** `README.md`
3. **Executed by production code:** Yes (Main Entry Point)
4. **Safe to move:** No
5. **Safe to delete:** No

### `train_all_models.py`, `train_anomaly_model.py`, `train_bill_model.py`, `train_disaggregation_model.py`
1. **Imported by:** `train_all_models.py` imports the other three scripts.
2. **Referenced by:** `app.py` and `README.md` (via CLI instructions).
3. **Executed by production code:** No (Manually executed to train models).
4. **Safe to move:** Yes (to `training/`).
5. **Safe to delete:** No

### `test_dates.py`, `test_db_metrics.py`, `test_disagg_r2.py`
1. **Imported by:** None
2. **Referenced by:** None
3. **Executed by production code:** No (Testing tools).
4. **Safe to move:** Yes (to `tests/`).
5. **Safe to delete:** No

### `check_metrics.py`, `check_metrics2.py`, `count_zero.py`, `get_counts.py`
1. **Imported by:** None
2. **Referenced by:** None
3. **Executed by production code:** No (Ad-hoc analysis scripts).
4. **Safe to move:** Yes (to `scripts/`).
5. **Safe to delete:** No

### `inspect_data.py`, `inspect_db_anomalies.py`
1. **Imported by:** None
2. **Referenced by:** None
3. **Executed by production code:** No (Diagnostic scripts).
4. **Safe to move:** Yes (to `database/` as requested via the mapped names).
5. **Safe to delete:** No

### `scratch_patch.py`, `scratch_patch_app.py`, `scratch_patch_jsx.py`, `scratch_remove.py`
1. **Imported by:** None
2. **Referenced by:** None
3. **Executed by production code:** No (Temporary AI agent scripts).
4. **Safe to move:** N/A
5. **Safe to delete:** Yes

### `disaggregation_model_audit.md`, `disaggregation_retraining_report.md`
1. **Imported by:** None
2. **Referenced by:** None
3. **Executed by production code:** No (Markdown reports).
4. **Safe to move:** Yes (to `reports/`).
5. **Safe to delete:** No
