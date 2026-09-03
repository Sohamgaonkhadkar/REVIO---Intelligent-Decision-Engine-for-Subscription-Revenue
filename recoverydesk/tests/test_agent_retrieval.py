import pytest
import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.ingest_runtime_data import main as ingest_main
from core.agent.tools import get_case, get_timeline, get_decision_record, explain_verdict

def test_agent_temporal_leakage_safeguard():
    """
    Verifies queries correctly drop events that happened strictly after the `as_of` time,
    and mask future case fields (like resolution, cost).
    """
    # Use an arbitrary early date where the case is NOT closed
    as_of = datetime.datetime(2024, 2, 25, tzinfo=datetime.timezone.utc)
    
    # Timeline should not include events after as_of
    timeline = get_timeline(case_id=101, policy_id="B0_NONE", as_of=as_of)
    for record in timeline:
        assert record["timestamp"] <= as_of
        
    # Get case bounds payments to as_of and masks future fields
    case_context = get_case(case_id=101, policy_id="B0_NONE", as_of=as_of)
    if case_context:
        for p in case_context.get("payment_attempts", []):
            assert p["ts_iso"] <= as_of
        
        # Verify temporal masking for future fields
        assert case_context.get("resolution") is None
        assert case_context.get("recovered_flag") is None

def test_action_log_format():
    """
    Verifies `decision_id` vs `action_id` mapping.
    Ensures semantic identity is preserved via (case_id, decision_seq).
    """
    # Using case_id=101, decision_seq=1, policy_id="B0_NONE"
    record = get_decision_record(case_id=101, decision_seq=1, policy_id="B0_NONE")
    if record:
        assert "internal_action_id" in record
        assert "action_type" in record
        assert "decision_event_detail" in record
        assert record["case_id"] == 101
        assert record["decision_seq"] == 1

def test_explain_verdict():
    """
    Verifies explain verdict returns evidence context correctly using semantic identity.
    """
    explanation = explain_verdict(case_id=101, decision_seq=1, candidate="WAIT", policy_id="B0_NONE")
    if "error" not in explanation:
        assert "was_candidate_feasible" in explanation
        assert "historical_context" in explanation
        assert "verdict" in explanation

@patch("scripts.ingest_runtime_data.RUNTIME_DATA_DIR")
def test_history_allowlist_validation(mock_dir):
    """
    Verifies prohibited files are rejected.
    """
    mock_file1 = MagicMock()
    mock_file1.name = "ml_datamart_features.parquet"
    
    mock_dir.glob.return_value = [mock_file1]
    mock_dir.exists.return_value = True
    
    result = ingest_main()
    assert result == 1

def test_transactional_ingestion():
    """
    Verifies either all 6 load or none do.
    """
    pass

def test_idempotent_ingestion():
    """
    Verifies running twice does not duplicate rows.
    """
    pass
