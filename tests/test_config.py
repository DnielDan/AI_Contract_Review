"""Configurable matrices and threshold (US-7)."""
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


def test_paths_and_threshold_come_from_settings(monkeypatch):
    monkeypatch.setenv("AICR_TNC_MATRIX", "custom/matrix.xlsm")
    assert main._configured_path("AICR_TNC_MATRIX", "default") == str(main.os.path.join(main.BASE_DIR, "custom/matrix.xlsm"))
    monkeypatch.delenv("AICR_TNC_MATRIX")
    assert main._configured_path("AICR_TNC_MATRIX", "default") == "default"
    monkeypatch.setenv("AICR_SIMILARITY_THRESHOLD", "0.35")
    assert main._configured_threshold() == 0.35


@pytest.mark.parametrize("value", ["abc", "1.5", "0"])
def test_invalid_threshold_is_reported(monkeypatch, value):
    monkeypatch.setenv("AICR_SIMILARITY_THRESHOLD", value)
    with pytest.raises(main.ConfigError, match="AICR_SIMILARITY_THRESHOLD"):
        main._configured_threshold()
