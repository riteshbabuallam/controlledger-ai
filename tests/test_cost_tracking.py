from backend.services.cost_tracking import ExecutionTracker


def test_provider_usage_is_costed_and_offline_calls_are_free(monkeypatch):
    monkeypatch.setenv("CONTROLLEDGER_LLM_INPUT_USD_PER_M", "0.15")
    monkeypatch.setenv("CONTROLLEDGER_LLM_OUTPUT_USD_PER_M", "0.60")
    tracker = ExecutionTracker()
    tracker.start()
    tracker.record_ai_call(
        {
            "provider": "gemini",
            "operation": "grounded_explanation",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
    )
    tracker.record_ai_call(
        {
            "provider": "offline",
            "operation": "receipt_extraction",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
    )

    metadata = tracker.metadata()
    assert metadata["estimated_cost_usd"] == 0.75
    assert metadata["ai_calls"][0]["estimated_cost_usd"] == 0.75
    assert metadata["ai_calls"][1]["estimated_cost_usd"] == 0.0
