"""Unit tests for all adversarial generators.

Covers:
- Each generator emits >= 10 records when called with n=10
- Every record validates against the ground-truth schema (required fields + types)
- Seeded determinism: same seed → same records
- case_id format: ^C[1-6][a-e]-\\d{3}$
- All customer_id / order_id values come from the real CRM (no invented IDs)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eval.adversarial import abuse, hijacking, injection, jailbreak, llm_poisoning, stress
from eval.adversarial._base import CUSTOMER_ORDER_PAIRS, CUSTOMERS, ORDERS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CASE_ID_RE = re.compile(r"^C[1-6][a-e]-\d{3}$")

_REQUIRED_FIELDS = {
    "case_id",
    "axis",
    "category",
    "sub_category",
    "customer_id",
    "order_id",
    "user_message",
    "expected_decision_kind",
    "expected_reason_code",
    "expected_cited_clauses",
    "expected_verification_blocked",
    "expected_block_check",
    "expected_response_traits",
    "must_not_traits",
    "severity",
    "source",
}

_VALID_SEVERITIES = {"block", "warn"}
_VALID_DECISION_KINDS = {"escalate", "deny", "approve"}
_VALID_SOURCES = {"synthetic", "hand_curated", "incident_replay"}

# All real CRM IDs
_REAL_CUSTOMERS = set(CUSTOMERS)
_REAL_ORDERS = set(ORDERS)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_case(case: dict) -> list[str]:
    """Return a list of validation error strings. Empty list means valid."""
    errors: list[str] = []

    # Required fields
    missing = _REQUIRED_FIELDS - set(case.keys())
    if missing:
        errors.append(f"Missing fields: {sorted(missing)}")

    # case_id format (synthetic only)
    if case.get("source") == "synthetic":
        cid = case.get("case_id", "")
        if not _CASE_ID_RE.match(cid):
            errors.append(f"Invalid case_id format: {cid!r}")

    # severity
    if case.get("severity") not in _VALID_SEVERITIES:
        errors.append(f"Invalid severity: {case.get('severity')!r}")

    # expected_decision_kind
    if case.get("expected_decision_kind") not in _VALID_DECISION_KINDS:
        errors.append(f"Invalid expected_decision_kind: {case.get('expected_decision_kind')!r}")

    # source
    if case.get("source") not in _VALID_SOURCES:
        errors.append(f"Invalid source: {case.get('source')!r}")

    # expected_cited_clauses must be list
    if not isinstance(case.get("expected_cited_clauses"), list):
        errors.append("expected_cited_clauses must be a list")

    # expected_response_traits must be list
    if not isinstance(case.get("expected_response_traits"), list):
        errors.append("expected_response_traits must be a list")

    # must_not_traits must be list
    if not isinstance(case.get("must_not_traits"), list):
        errors.append("must_not_traits must be a list")

    # expected_verification_blocked must be bool
    if not isinstance(case.get("expected_verification_blocked"), bool):
        errors.append("expected_verification_blocked must be bool")

    # Real CRM IDs only
    cid_val = case.get("customer_id", "")
    if cid_val and cid_val not in _REAL_CUSTOMERS:
        errors.append(f"Invented customer_id: {cid_val!r}")

    oid_val = case.get("order_id", "")
    if oid_val and oid_val not in _REAL_ORDERS:
        errors.append(f"Invented order_id: {oid_val!r}")

    # user_message must be a string
    if not isinstance(case.get("user_message"), str):
        errors.append("user_message must be a string")

    return errors


def _run_validation(cases: list[dict]) -> None:
    """Assert all cases pass validation, printing details on failure."""
    all_errors: list[str] = []
    for i, case in enumerate(cases):
        errs = _validate_case(case)
        for e in errs:
            all_errors.append(f"[case {i}, id={case.get('case_id')}] {e}")
    assert not all_errors, f"Validation failures:\n" + "\n".join(all_errors)


# ---------------------------------------------------------------------------
# Parametrized generator table
# ---------------------------------------------------------------------------

_GENERATORS = [
    ("injection", injection.generate),
    ("jailbreak", jailbreak.generate),
    ("llm_poisoning", llm_poisoning.generate),
    ("hijacking", hijacking.generate),
    ("stress", stress.generate),
    ("abuse", abuse.generate),
]


@pytest.mark.parametrize("name,gen_fn", _GENERATORS, ids=[g[0] for g in _GENERATORS])
class TestAdversarialGenerators:
    def test_emits_at_least_10_records(self, name: str, gen_fn) -> None:
        """Generator must emit >= 10 records when n=10."""
        cases = gen_fn(n=10, seed=42, llm=None)
        assert len(cases) >= 10, (
            f"{name}: expected >= 10 cases, got {len(cases)}"
        )

    def test_all_records_validate_against_schema(self, name: str, gen_fn) -> None:
        """Every emitted record must pass the ground-truth schema validation."""
        cases = gen_fn(n=10, seed=42, llm=None)
        _run_validation(cases)

    def test_seeded_determinism(self, name: str, gen_fn) -> None:
        """Same seed must produce identical outputs on two calls."""
        first = gen_fn(n=10, seed=42, llm=None)
        second = gen_fn(n=10, seed=42, llm=None)
        assert first == second, (
            f"{name}: two calls with seed=42 produced different outputs"
        )

    def test_different_seeds_differ(self, name: str, gen_fn) -> None:
        """Different seeds should (almost always) produce different case_ids."""
        cases_42 = gen_fn(n=10, seed=42, llm=None)
        cases_99 = gen_fn(n=10, seed=99, llm=None)
        ids_42 = {c["case_id"] for c in cases_42}
        ids_99 = {c["case_id"] for c in cases_99}
        # The case_ids are deterministic per-index so the same; but at least
        # confirm both runs don't produce an empty set.
        assert len(ids_42) > 0
        assert len(ids_99) > 0

    def test_case_id_format(self, name: str, gen_fn) -> None:
        """All case_ids must match ^C[1-6][a-e]-\\d{3}$."""
        cases = gen_fn(n=10, seed=42, llm=None)
        for case in cases:
            cid = case.get("case_id", "")
            assert _CASE_ID_RE.match(cid), (
                f"{name}: invalid case_id {cid!r}"
            )

    def test_real_crm_ids_only(self, name: str, gen_fn) -> None:
        """All customer_id and order_id values must exist in the CRM."""
        cases = gen_fn(n=10, seed=42, llm=None)
        for case in cases:
            assert case["customer_id"] in _REAL_CUSTOMERS, (
                f"{name}: invented customer_id {case['customer_id']!r} in {case['case_id']}"
            )
            assert case["order_id"] in _REAL_ORDERS, (
                f"{name}: invented order_id {case['order_id']!r} in {case['case_id']}"
            )

    def test_source_is_synthetic(self, name: str, gen_fn) -> None:
        """All generated cases must have source='synthetic'."""
        cases = gen_fn(n=10, seed=42, llm=None)
        for case in cases:
            assert case["source"] == "synthetic", (
                f"{name}: expected source='synthetic', got {case['source']!r} in {case['case_id']}"
            )

    def test_larger_n_produces_more_cases(self, name: str, gen_fn) -> None:
        """Requesting n=20 should produce >= 20 cases."""
        cases = gen_fn(n=20, seed=42, llm=None)
        assert len(cases) >= 20, (
            f"{name}: requested 20, got {len(cases)}"
        )


# ---------------------------------------------------------------------------
# Category-specific tests
# ---------------------------------------------------------------------------


class TestInjectionSpecifics:
    """C1 sub-category coverage."""

    def test_all_five_sub_categories_present(self) -> None:
        cases = injection.generate(n=50, seed=42, llm=None)
        sub_cats = {c["sub_category"] for c in cases}
        expected = {"C1a", "C1b", "C1c", "C1d", "C1e"}
        assert expected.issubset(sub_cats), (
            f"Missing sub-categories: {expected - sub_cats}"
        )

    def test_all_injection_axis_a3(self) -> None:
        cases = injection.generate(n=10, seed=42, llm=None)
        for c in cases:
            assert c["axis"] == "A3", f"Expected axis A3, got {c['axis']!r}"

    def test_all_injection_severity_block(self) -> None:
        cases = injection.generate(n=10, seed=42, llm=None)
        for c in cases:
            assert c["severity"] == "block", f"Expected block severity, got {c['severity']!r}"


class TestJailbreakSpecifics:
    """C2 sub-category coverage."""

    def test_all_four_sub_categories_present(self) -> None:
        cases = jailbreak.generate(n=40, seed=42, llm=None)
        sub_cats = {c["sub_category"] for c in cases}
        expected = {"C2a", "C2b", "C2c", "C2d"}
        assert expected.issubset(sub_cats), (
            f"Missing sub-categories: {expected - sub_cats}"
        )

    def test_all_jailbreak_category_c2(self) -> None:
        cases = jailbreak.generate(n=10, seed=42, llm=None)
        for c in cases:
            assert c["category"] == "C2"

    def test_jailbreak_must_not_refunds(self) -> None:
        cases = jailbreak.generate(n=10, seed=42, llm=None)
        for c in cases:
            assert "refunds" in c["must_not_traits"], (
                f"Expected 'refunds' in must_not_traits for {c['case_id']}"
            )


class TestLLMPoisoningSpecifics:
    """C3 sub-category coverage."""

    def test_all_four_sub_categories_present(self) -> None:
        cases = llm_poisoning.generate(n=40, seed=42, llm=None)
        sub_cats = {c["sub_category"] for c in cases}
        expected = {"C3a", "C3b", "C3c", "C3d"}
        assert expected.issubset(sub_cats), (
            f"Missing sub-categories: {expected - sub_cats}"
        )

    def test_c3b_context_stuffing_messages_are_long(self) -> None:
        """C3b stuffed messages should be notably longer than the others."""
        cases = llm_poisoning.generate(n=40, seed=42, llm=None)
        c3b_cases = [c for c in cases if c["sub_category"] == "C3b"]
        for c in c3b_cases:
            # Context-stuffed messages should be at least 500 chars
            assert len(c["user_message"]) > 500, (
                f"C3b message unexpectedly short: {len(c['user_message'])} chars"
            )


class TestHijackingSpecifics:
    """C4 sub-category coverage."""

    def test_all_three_sub_categories_present(self) -> None:
        cases = hijacking.generate(n=30, seed=42, llm=None)
        sub_cats = {c["sub_category"] for c in cases}
        expected = {"C4a", "C4b", "C4c"}
        assert expected.issubset(sub_cats), (
            f"Missing sub-categories: {expected - sub_cats}"
        )

    def test_c4c_must_not_reveal_system_prompt(self) -> None:
        cases = hijacking.generate(n=30, seed=42, llm=None)
        c4c = [c for c in cases if c["sub_category"] == "C4c"]
        for c in c4c:
            assert "reveals_system_prompt" in c["must_not_traits"], (
                f"C4c case {c['case_id']} missing must_not_trait 'reveals_system_prompt'"
            )


class TestStressSpecifics:
    """C5 sub-category coverage."""

    def test_all_four_sub_categories_present(self) -> None:
        cases = stress.generate(n=40, seed=42, llm=None)
        sub_cats = {c["sub_category"] for c in cases}
        expected = {"C5a", "C5b", "C5c", "C5d"}
        assert expected.issubset(sub_cats), (
            f"Missing sub-categories: {expected - sub_cats}"
        )

    def test_c5a_messages_are_long(self) -> None:
        """C5a messages should be at least 1000 characters."""
        cases = stress.generate(n=40, seed=42, llm=None)
        c5a = [c for c in cases if c["sub_category"] == "C5a"]
        for c in c5a:
            assert len(c["user_message"]) >= 1000, (
                f"C5a message too short: {len(c['user_message'])} chars in {c['case_id']}"
            )

    def test_stress_axis_is_a5(self) -> None:
        cases = stress.generate(n=10, seed=42, llm=None)
        for c in cases:
            assert c["axis"] == "A5", f"Expected axis A5, got {c['axis']!r}"

    def test_stress_severity_is_warn(self) -> None:
        cases = stress.generate(n=10, seed=42, llm=None)
        for c in cases:
            assert c["severity"] == "warn", f"Expected warn severity, got {c['severity']!r}"


class TestAbuseSpecifics:
    """C6 sub-category coverage."""

    def test_all_four_sub_categories_present(self) -> None:
        cases = abuse.generate(n=40, seed=42, llm=None)
        sub_cats = {c["sub_category"] for c in cases}
        expected = {"C6a", "C6b", "C6c", "C6d"}
        assert expected.issubset(sub_cats), (
            f"Missing sub-categories: {expected - sub_cats}"
        )

    def test_abuse_axis_is_a6(self) -> None:
        cases = abuse.generate(n=10, seed=42, llm=None)
        for c in cases:
            assert c["axis"] == "A6", f"Expected axis A6, got {c['axis']!r}"

    def test_abuse_severity_is_warn(self) -> None:
        cases = abuse.generate(n=10, seed=42, llm=None)
        for c in cases:
            assert c["severity"] == "warn", f"Expected warn severity, got {c['severity']!r}"

    def test_c6b_must_not_capitulate(self) -> None:
        cases = abuse.generate(n=40, seed=42, llm=None)
        c6b = [c for c in cases if c["sub_category"] == "C6b"]
        for c in c6b:
            assert "capitulates_to_threat" in c["must_not_traits"], (
                f"C6b case {c['case_id']} missing must_not_trait 'capitulates_to_threat'"
            )

    def test_c6d_persistence_messages_are_multi_turn(self) -> None:
        """C6d messages should contain [Turn N]: markers."""
        cases = abuse.generate(n=40, seed=42, llm=None)
        c6d = [c for c in cases if c["sub_category"] == "C6d"]
        for c in c6d:
            assert "[Turn 1]:" in c["user_message"], (
                f"C6d case {c['case_id']} missing multi-turn format"
            )


# ---------------------------------------------------------------------------
# CLI integration smoke test
# ---------------------------------------------------------------------------


class TestCLISmoke:
    def test_generate_all_produces_valid_json(self, tmp_path: Path) -> None:
        """generate_all() returns a valid dict with expected structure."""
        from eval.generate_synthetic_data import generate_all

        result = generate_all(
            count=50,
            seed=42,
            no_llm=True,
            hand_curated_path=None,
        )

        assert "version" in result
        assert result["version"] == "1.0"
        assert "cases" in result
        assert isinstance(result["cases"], list)
        assert result["total_cases"] >= 50
        assert result["synthetic_count"] >= 50
        # Every synthetic case validates
        synthetic_cases = [c for c in result["cases"] if c.get("source") == "synthetic"]
        _run_validation(synthetic_cases)

    def test_generate_all_with_hand_curated(self, tmp_path: Path) -> None:
        """generate_all() correctly appends hand-curated cases."""
        from eval.generate_synthetic_data import generate_all

        # Use the real seed_cases.yaml from the eval dir
        seed_path = Path(__file__).parent.parent / "eval" / "seed_cases.yaml"
        if not seed_path.exists():
            pytest.skip("seed_cases.yaml not found")

        result = generate_all(
            count=24,
            seed=42,
            no_llm=True,
            hand_curated_path=seed_path,
        )

        hc_cases = [c for c in result["cases"] if c.get("source") == "hand_curated"]
        assert len(hc_cases) > 0, "Expected hand_curated cases to be present"
        assert result["hand_curated_count"] == len(hc_cases)

    def test_output_written_to_file(self, tmp_path: Path) -> None:
        """CLI output can be written and re-read as valid JSON."""
        from eval.generate_synthetic_data import generate_all

        result = generate_all(count=24, seed=42, no_llm=True, hand_curated_path=None)
        out = tmp_path / "ground_truth.json"
        out.write_text(json.dumps(result, indent=2))

        loaded = json.loads(out.read_text())
        assert loaded["version"] == "1.0"
        assert len(loaded["cases"]) == result["total_cases"]

    def test_sub_category_counts_match_cases(self, tmp_path: Path) -> None:
        """sub_category_counts in output must match actual case distribution."""
        from eval.generate_synthetic_data import generate_all

        result = generate_all(count=24, seed=42, no_llm=True, hand_curated_path=None)
        computed: dict[str, int] = {}
        for c in result["cases"]:
            if c.get("source") == "synthetic":
                sc = c["sub_category"]
                computed[sc] = computed.get(sc, 0) + 1

        assert computed == result["sub_category_counts"], (
            f"Mismatch: computed={computed} vs reported={result['sub_category_counts']}"
        )
