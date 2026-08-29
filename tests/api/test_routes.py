"""
HTTP-level tests for the Core API routes.

Uses FastAPI's synchronous ``TestClient`` (backed by ``httpx``, already a
project dependency).  Each failure-scenario test overrides the
``get_orchestrator`` and ``get_repository`` dependencies via
``app.dependency_overrides`` so that stubs can be configured per-test without
touching ``app.state``.

The ``client`` fixture uses ``with TestClient(app)`` to trigger the ``lifespan``
context (required for ``app.state`` to be populated).  Tests that override the
dependency skip ``app.state`` entirely, so lifespan is not needed there.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_orchestrator, get_repository
from app.main import app
from app.models.failures import FailureCode
from app.run_manager.orchestrator import RunOrchestrator
from app.run_manager.repository import RunRepository
from app.run_manager.stubs import (
    StubEvidenceRetriever,
    StubObjectiveResolver,
    StubPostPlanAnalyzer,
    StubStrategicPlanner,
    StubStrategyValidator,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Minimal valid request body matching RunRequest + nested contract shapes.
_VALID_BODY: dict = {
    "project": {
        "project_id": "test-proj-001",
        "species": "Canis lupus",
        "scope": "de-extinction",
        "objective": "Make the coat white.",
    },
    "run": {
        "max_edits": 3,
        "strategy": "minimal",
    },
}


def _make_orchestrator(
    *,
    resolver: object | None = None,
    retriever: object | None = None,
    planner: object | None = None,
    validator: object | None = None,
    analyzer: object | None = None,
) -> tuple[RunOrchestrator, RunRepository]:
    """Build an orchestrator with selectable stubs; return (orch, repo) pair."""
    repo = RunRepository()
    orch = RunOrchestrator(
        resolver=resolver or StubObjectiveResolver(),  # type: ignore[arg-type]
        retriever=retriever or StubEvidenceRetriever(),  # type: ignore[arg-type]
        planner=planner or StubStrategicPlanner(),  # type: ignore[arg-type]
        validator=validator or StubStrategyValidator(),  # type: ignore[arg-type]
        analyzer=analyzer or StubPostPlanAnalyzer(),  # type: ignore[arg-type]
        repository=repo,
    )
    return orch, repo


def _override(orch: RunOrchestrator, repo: RunRepository) -> None:
    """Install DI overrides for both orchestrator and repository."""
    app.dependency_overrides[get_orchestrator] = lambda: orch
    app.dependency_overrides[get_repository] = lambda: repo


def _clear() -> None:
    app.dependency_overrides.clear()


def _client_with(orch: RunOrchestrator, repo: RunRepository) -> TestClient:
    """Return a ``TestClient`` pre-wired to the given orchestrator and repository."""
    _override(orch, repo)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """
    ``TestClient`` that triggers the app ``lifespan`` context.

    Using ``with TestClient(app)`` ensures ``app.state.orchestrator`` and
    ``app.state.repository`` are populated before any request is made.
    """
    with TestClient(app) as tc:
        yield tc


# ===========================================================================
# GET /v1/health
# ===========================================================================


class TestHealthRoute:
    def test_status_code_is_200(self, client: TestClient) -> None:
        resp = client.get("/v1/health")
        assert resp.status_code == 200

    def test_body_status_is_ok(self, client: TestClient) -> None:
        resp = client.get("/v1/health")
        assert resp.json()["status"] == "ok"

    def test_content_type_is_json(self, client: TestClient) -> None:
        resp = client.get("/v1/health")
        assert "application/json" in resp.headers["content-type"]


# ===========================================================================
# GET /v1/system
# ===========================================================================


class TestSystemRoute:
    def test_status_code_is_200(self, client: TestClient) -> None:
        resp = client.get("/v1/system")
        assert resp.status_code == 200

    def test_version_present(self, client: TestClient) -> None:
        resp = client.get("/v1/system")
        assert "version" in resp.json()
        assert isinstance(resp.json()["version"], str)

    def test_debug_field_present(self, client: TestClient) -> None:
        resp = client.get("/v1/system")
        assert "debug" in resp.json()

    def test_max_concurrent_runs_present(self, client: TestClient) -> None:
        body = client.get("/v1/system").json()
        assert "max_concurrent_runs" in body
        assert isinstance(body["max_concurrent_runs"], int)

    def test_run_timeout_seconds_present(self, client: TestClient) -> None:
        body = client.get("/v1/system").json()
        assert "run_timeout_seconds" in body
        assert isinstance(body["run_timeout_seconds"], int)


# ===========================================================================
# POST /v1/runs — successful run
# ===========================================================================


class TestRunsPostSuccess:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator()
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_status_code_is_200(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 200

    def test_run_status_is_complete(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["status"] == "complete"

    def test_run_id_present(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        body = resp.json()
        assert "run_id" in body
        assert isinstance(body["run_id"], str)
        assert len(body["run_id"]) > 0

    def test_structured_objective_present(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["structured_objective"] is not None

    def test_strategies_non_empty(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert len(resp.json()["strategies"]) > 0

    def test_selected_strategy_present(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["selected_strategy"] is not None

    def test_validation_passed(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["validation"]["valid"] is True

    def test_no_failure_on_success(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["failure"] is None


# ===========================================================================
# POST /v1/runs — CLARIFICATION_REQUIRED
# ===========================================================================


class TestRunsPostClarificationRequired:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(resolver=StubObjectiveResolver(clarification_required=True))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_http_status_is_200(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 200

    def test_run_status_is_failed(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["status"] == "failed"

    def test_failure_code(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["failure"]["code"] == FailureCode.CLARIFICATION_REQUIRED

    def test_structured_objective_returned(self) -> None:
        """Resolver produced a StructuredObjective before returning CLARIFICATION_REQUIRED."""
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        obj = resp.json()["structured_objective"]
        assert obj is not None
        assert obj["ambiguity_status"] == "CLARIFICATION_REQUIRED"


# ===========================================================================
# POST /v1/runs — INSUFFICIENT_EVIDENCE
# ===========================================================================


class TestRunsPostInsufficientEvidence:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(retriever=StubEvidenceRetriever(return_empty=True))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_run_status_is_failed(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["status"] == "failed"

    def test_failure_code(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["failure"]["code"] == FailureCode.INSUFFICIENT_EVIDENCE


# ===========================================================================
# POST /v1/runs — NO_FEASIBLE_PLAN
# ===========================================================================


class TestRunsPostNoFeasiblePlan:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(planner=StubStrategicPlanner(return_empty=True))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_run_status_is_failed(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["status"] == "failed"

    def test_failure_code(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["failure"]["code"] == FailureCode.NO_FEASIBLE_PLAN


# ===========================================================================
# POST /v1/runs — VALIDATION_FAILED
# ===========================================================================


class TestRunsPostValidationFailed:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(validator=StubStrategyValidator(return_valid=False))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_run_status_is_failed(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["status"] == "failed"

    def test_failure_code(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["failure"]["code"] == FailureCode.VALIDATION_FAILED


# ===========================================================================
# POST /v1/runs — PARTIAL_ANALYSIS (run stays COMPLETE)
# ===========================================================================


class TestRunsPostPartialAnalysis:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(analyzer=StubPostPlanAnalyzer(return_status="partial"))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_run_status_is_complete(self) -> None:
        """Architecture §3.10: run.status is independent of post_plan_analysis_status."""
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["status"] == "complete"

    def test_post_plan_status_is_partial(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["post_plan"]["status"] == "partial"

    def test_failure_code_is_partial_analysis(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.json()["failure"]["code"] == FailureCode.PARTIAL_ANALYSIS


# ===========================================================================
# POST /v1/runs — request validation (422)
# ===========================================================================


class TestRunsPostBadRequest:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator()
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_missing_project_field_returns_422(self) -> None:
        body = {"run": _VALID_BODY["run"]}
        resp = TestClient(app).post("/v1/runs", json=body)
        assert resp.status_code == 422

    def test_missing_run_field_returns_422(self) -> None:
        body = {"project": _VALID_BODY["project"]}
        resp = TestClient(app).post("/v1/runs", json=body)
        assert resp.status_code == 422

    def test_extra_top_level_field_returns_422(self) -> None:
        """RunRequest has extra='forbid'."""
        body = {**_VALID_BODY, "unexpected_field": "value"}
        resp = TestClient(app).post("/v1/runs", json=body)
        assert resp.status_code == 422


# ===========================================================================
# GET /v1/runs/{run_id}
# ===========================================================================


class TestRunsGetState:
    def test_known_run_id_returns_200(self) -> None:
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            post_resp = tc.post("/v1/runs", json=_VALID_BODY)
            run_id = post_resp.json()["run_id"]
            get_resp = tc.get(f"/v1/runs/{run_id}")
            assert get_resp.status_code == 200
        finally:
            _clear()

    def test_known_run_id_has_correct_run_id_field(self) -> None:
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            post_resp = tc.post("/v1/runs", json=_VALID_BODY)
            run_id = post_resp.json()["run_id"]
            get_resp = tc.get(f"/v1/runs/{run_id}")
            assert get_resp.json()["run_id"] == run_id
        finally:
            _clear()

    def test_known_run_id_has_status_field(self) -> None:
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            post_resp = tc.post("/v1/runs", json=_VALID_BODY)
            run_id = post_resp.json()["run_id"]
            get_resp = tc.get(f"/v1/runs/{run_id}")
            assert "status" in get_resp.json()
        finally:
            _clear()

    def test_unknown_run_id_returns_404(self) -> None:
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            resp = tc.get("/v1/runs/nonexistent-run-id")
            assert resp.status_code == 404
        finally:
            _clear()

    def test_unknown_run_id_detail_message(self) -> None:
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            resp = tc.get("/v1/runs/nonexistent-run-id")
            assert resp.json()["detail"] == "run not found"
        finally:
            _clear()


# ===========================================================================
# Phase 2E: Concurrency Guard API
# ===========================================================================


class TestConcurrencyAPI:
    def teardown_method(self) -> None:
        _clear()

    def test_submit_run_at_capacity_returns_429(self) -> None:
        orch, repo = _make_orchestrator()
        orch._max_concurrent_runs = 0  # Zero capacity
        tc = _client_with(orch, repo)

        resp = tc.post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 429
        assert "Server is at capacity" in resp.json()["detail"]


# ===========================================================================
# Phase 2E: Timeout Guard API
# ===========================================================================


class TestTimeoutAPI:
    def teardown_method(self) -> None:
        _clear()

    def test_timeout_run_exposed_via_get(self) -> None:
        orch, repo = _make_orchestrator()
        orch._run_timeout_seconds = 0  # Instant timeout

        import time

        original_monotonic = time.monotonic

        try:
            time.monotonic = lambda: original_monotonic() + 1
            tc = _client_with(orch, repo)
            post_resp = tc.post("/v1/runs", json=_VALID_BODY)
        finally:
            time.monotonic = original_monotonic

        assert post_resp.status_code == 200
        run_id = post_resp.json()["run_id"]
        assert post_resp.json()["status"] == "failed"
        assert post_resp.json()["failure"]["code"] == FailureCode.RUN_TIMEOUT

        # Verify exposed correctly through GET
        get_resp = tc.get(f"/v1/runs/{run_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "failed"
        assert "wall-clock budget" in get_resp.json()["errors"][0].lower()
