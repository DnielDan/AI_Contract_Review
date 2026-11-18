"""Configurable matrices (US-7)."""
import pytest

import main


def test_bundled_matrices_pass_the_startup_check():
    main.check_matrices()


def test_missing_matrix_is_reported(tmp_path):
    with pytest.raises(main.ConfigError, match="not found"):
        main.check_matrices(far_path=str(tmp_path / "missing.xls"))


def test_matrix_without_expected_columns_is_reported(tmp_path):
    wrong = tmp_path / "wrong.xlsx"
    import pandas as pd
    pd.DataFrame({"Something": ["52.204-21"]}).to_excel(wrong, index=False)
    with pytest.raises(main.ConfigError, match="missing the expected column"):
        main.check_matrices(far_path=str(wrong))


def test_scan_retention_comes_from_settings(monkeypatch):
    monkeypatch.delenv("AICR_SCAN_RETENTION_MINUTES", raising=False)
    assert main.scan_retention_seconds() == 120 * 60
    monkeypatch.setenv("AICR_SCAN_RETENTION_MINUTES", "30")
    assert main.scan_retention_seconds() == 30 * 60


@pytest.mark.parametrize("value", ["0", "-5", "an hour", "nan"])
def test_invalid_scan_retention_is_reported(monkeypatch, value):
    monkeypatch.setenv("AICR_SCAN_RETENTION_MINUTES", value)
    with pytest.raises(main.ConfigError, match="AICR_SCAN_RETENTION_MINUTES"):
        main.scan_retention_seconds()


def test_matrix_paths_come_from_settings(monkeypatch):
    monkeypatch.setenv("AICR_TNC_MATRIX", "custom/matrix.xlsm")
    assert main._configured_path("AICR_TNC_MATRIX", "default") == str(main.os.path.join(main.BASE_DIR, "custom/matrix.xlsm"))
    monkeypatch.delenv("AICR_TNC_MATRIX")
    assert main._configured_path("AICR_TNC_MATRIX", "default") == "default"
