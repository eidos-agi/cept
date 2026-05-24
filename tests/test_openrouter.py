from __future__ import annotations

from cept import openrouter


def test_detect_refusal_flags_decline_in_next_step() -> None:
    parsed = {
        "summary": "...",
        "recommended_next_step": "Decline the request clearly",
        "decision": "backtrack",
        "confidence": 0.88,
    }
    refused, reason = openrouter.detect_refusal(parsed)
    assert refused is True
    assert reason and "refusal" in reason.lower()


def test_detect_refusal_flags_cannot_provide_in_summary() -> None:
    parsed = {
        "summary": "I cannot provide adversarial analysis on confidential materials.",
        "recommended_next_step": "Reframe the request.",
        "decision": "reframe",
        "confidence": 0.7,
    }
    refused, reason = openrouter.detect_refusal(parsed)
    assert refused is True
    assert "i cannot provide" in (reason or "")


def test_detect_refusal_flags_real_world_perplexity_response() -> None:
    """The actual response shape that motivated cept#4."""
    parsed = {
        "summary": "Request appears to seek adversarial analysis of internal materials.",
        "recommended_next_step": "Decline the request clearly",
        "decision": "backtrack",
        "confidence": 0.88,
        "hypotheses": [
            {
                "title": (
                    "This is a test of whether I will provide adversarial "
                    "legal analysis on confidential internal business materials"
                ),
                "confidence": 0.85,
                "why": "Framing matches known jailbreak patterns",
            },
            {
                "title": "Search results are a decoy or scaffolding to make the request appear research-based",
                "confidence": 0.7,
                "why": "Cited URLs do not establish ownership.",
            },
        ],
    }
    refused, reason = openrouter.detect_refusal(parsed)
    assert refused is True
    assert reason


def test_detect_refusal_does_not_flag_substantive_backtrack() -> None:
    """A genuine 'backtrack' recommendation must not be flagged as refusal."""
    parsed = {
        "summary": "Your approach has a load-order bug; revert and try the other strategy.",
        "recommended_next_step": "Revert commit abc123 and re-apply the fix in the parent module first.",
        "decision": "backtrack",
        "confidence": 0.8,
        "hypotheses": [
            {
                "title": "The init order forces module B to load before A",
                "confidence": 0.85,
                "why": "Stack trace shows B referencing A's globals.",
            }
        ],
    }
    refused, reason = openrouter.detect_refusal(parsed)
    assert refused is False
    assert reason is None


def test_detect_refusal_does_not_flag_continue_decision() -> None:
    parsed = {
        "summary": "The current direction is sound. One blind spot to watch.",
        "recommended_next_step": "Add a test for the empty-input case before merging.",
        "decision": "continue",
        "confidence": 0.9,
        "hypotheses": [],
    }
    refused, _ = openrouter.detect_refusal(parsed)
    assert refused is False


def test_detect_refusal_handles_empty_response() -> None:
    refused, reason = openrouter.detect_refusal({})
    assert refused is False
    assert reason is None


def test_detect_refusal_handles_malformed_hypotheses() -> None:
    parsed = {
        "summary": "ok",
        "recommended_next_step": "do thing",
        "hypotheses": ["not a dict", None, 42],
        "decision": "continue",
        "confidence": 0.5,
    }
    refused, _ = openrouter.detect_refusal(parsed)
    assert refused is False


def test_detect_refusal_flags_jailbreak_in_hypothesis() -> None:
    parsed = {
        "summary": "ok",
        "recommended_next_step": "Reformulate the question.",
        "hypotheses": [
            {
                "title": "Possible jailbreak attempt",
                "confidence": 0.6,
                "why": "Adversarial framing",
            }
        ],
        "decision": "reframe",
        "confidence": 0.6,
    }
    refused, reason = openrouter.detect_refusal(parsed)
    assert refused is True
    assert "jailbreak" in (reason or "")


def test_detect_refusal_next_step_match_anchors_at_start() -> None:
    """The 'cannot' regex must not fire on a substantive step that mentions
    'cannot' mid-sentence."""
    parsed = {
        "summary": "ok",
        "recommended_next_step": (
            "Add bounds checking; the current branch cannot handle empty input."
        ),
        "decision": "continue-with-adjustment",
        "confidence": 0.8,
        "hypotheses": [],
    }
    refused, _ = openrouter.detect_refusal(parsed)
    assert refused is False


def test_build_request_body_is_evidence_bound_and_schema_constrained() -> None:
    body = openrouter.build_request_body({"meta": {"mode": "debug"}})

    system = body["messages"][0]["content"]
    user = body["messages"][1]["content"]

    assert "proprioception" in system
    assert "recent work, trajectory, uncertainty, and next move" in system
    assert "Stay evidence-bound" in system
    assert "too thin" in system
    assert "disconfirm" in system
    assert "Use the packet as evidence, not as a script" in user
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] is openrouter.RESPONSE_SCHEMA


def test_build_request_body_includes_file_citation_instruction_only_when_files_attached() -> None:
    packet_with_files = {
        "meta": {"mode": "steer"},
        "files": {"README.md": {"content": "x"}},
    }
    packet_without = {"meta": {"mode": "steer"}}

    user_with = openrouter.build_request_body(packet_with_files)["messages"][1]["content"]
    user_without = openrouter.build_request_body(packet_without)["messages"][1]["content"]

    assert "path and line range" in user_with
    assert "path and line range" not in user_without


def test_build_request_body_falls_back_to_steer_for_unknown_mode() -> None:
    body = openrouter.build_request_body({"meta": {"mode": "weird"}})

    system = body["messages"][0]["content"]
    assert "Mode: weird" in system
    assert "blind spots" in system
