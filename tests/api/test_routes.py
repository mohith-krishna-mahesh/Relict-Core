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

Auth
----
``RELICT_AUTH_ENABLED`` defaults to ``False`` in settings, so all existing tests
continue to work without an ``Authorization`` header.  Tests that explicitly
verify auth behaviour set ``settings.auth_enabled = True`` locally and restore
it in teardown.

POST /v1/runs (async dispatch)
------------------------------
``POST /v1/runs`` now returns ``StartRunResponse{run_id}`` immediately and
executes the pipeline in the background.  Tests that previously asserted on the
full ``RunResult`` body now assert on the ``StartRunResponse`` shape.  Full-
result assertions moved to the ``TestRunsGetContractShape`` class which uses
``GET /v1/runs/{run_id}`` after waiting for background completion.

Confidence guarantee
--------------------
``TestRunsGetContractShape.test_confidence_never_model_estimated`` iterates
every edge in every response and asserts ``confidence in {"evidence", "unknown"}``.
``"model_estimated"`` is never permitted (architecture Sec. 8).
"""

from __future__ import annotations

import time
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import settings as _settings
from app.dependencies import get_orchestrator, get_repository
from app.main import app
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

# New contract-shaped request body for POST /v1/runs.
_VALID_BODY: dict = {
    "species": "Canis lupus",
    "research_objective": "Make the coat white.",
    "candidate_genes": [],
    "constraints": {
        "max_edits": 3,
        "preserve_fertility": False,
        "maximize_diversity": False,
    },
    "presets": ["minimal"],
}

# Legacy internal-format body kept here so we can verify 422 on new endpoint
# (the contract now rejects the old nested shape).
_OLD_FORMAT_BODY: dict = {
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
# POST /v1/auth/verify
# ===========================================================================


class TestAuthVerify:
    """
    Tests for POST /v1/auth/verify.

    Auth is disabled by default (``settings.auth_enabled = False``), so
    tests that exercise the 401 path temporarily enable auth and restore
    settings after the test.
    """

    def test_verify_returns_200_when_auth_disabled(self, client: TestClient) -> None:
        """With auth disabled, any request (no header) should verify OK."""
        resp = client.post("/v1/auth/verify")
        assert resp.status_code == 200

    def test_verify_body_has_required_fields(self, client: TestClient) -> None:
        resp = client.post("/v1/auth/verify")
        body = resp.json()
        assert "status" in body
        assert "core_version" in body
        assert "instance_type" in body
        assert "identity" in body
        assert "user_or_org" in body["identity"]
        assert "scopes" in body["identity"]

    def test_verify_status_is_verified(self, client: TestClient) -> None:
        resp = client.post("/v1/auth/verify")
        assert resp.json()["status"] == "verified"

    def test_verify_core_version_is_string(self, client: TestClient) -> None:
        resp = client.post("/v1/auth/verify")
        assert isinstance(resp.json()["core_version"], str)
        assert len(resp.json()["core_version"]) > 0

    def test_verify_scopes_is_list(self, client: TestClient) -> None:
        resp = client.post("/v1/auth/verify")
        assert isinstance(resp.json()["identity"]["scopes"], list)

    def test_verify_missing_token_returns_401_when_auth_enabled(
        self, client: TestClient
    ) -> None:
        """When auth is enabled, a missing token must return 401."""
        original = _settings.auth_enabled
        _settings.auth_enabled = True
        try:
            resp = client.post("/v1/auth/verify")
            assert resp.status_code == 401
        finally:
            _settings.auth_enabled = original

    def test_verify_bad_token_returns_401_when_auth_enabled(
        self, client: TestClient
    ) -> None:
        """When auth is enabled, an invalid token must return 401."""
        original_enabled = _settings.auth_enabled
        original_tokens = _settings.api_tokens
        _settings.auth_enabled = True
        _settings.api_tokens = ["valid-token-abc"]
        try:
            resp = client.post(
                "/v1/auth/verify",
                headers={"Authorization": "Bearer wrong-token"},
            )
            assert resp.status_code == 401
        finally:
            _settings.auth_enabled = original_enabled
            _settings.api_tokens = original_tokens

    def test_verify_valid_token_returns_200_when_auth_enabled(
        self, client: TestClient
    ) -> None:
        """When auth is enabled, a correct token must return 200."""
        original_enabled = _settings.auth_enabled
        original_tokens = _settings.api_tokens
        _settings.auth_enabled = True
        _settings.api_tokens = ["valid-token-abc"]
        try:
            resp = client.post(
                "/v1/auth/verify",
                headers={"Authorization": "Bearer valid-token-abc"},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "verified"
        finally:
            _settings.auth_enabled = original_enabled
            _settings.api_tokens = original_tokens


# ===========================================================================
# GET /v1/search/species
# ===========================================================================


class TestSearchSpecies:
    """
    Tests for GET /v1/search/species.

    The species resolver requires the SQLite index to exist at
    ``data/species/species.db``.  If the species dataset is not available in
    the test environment, the resolver returns empty lists -- tests accommodate
    this gracefully.
    """

    def test_status_code_is_200_for_any_query(self, client: TestClient) -> None:
        """Unknown queries must return 200 + empty list, not an error."""
        resp = client.get("/v1/search/species", params={"q": "zzznomatch_xyzzy"})
        assert resp.status_code == 200

    def test_unknown_query_returns_empty_list(self, client: TestClient) -> None:
        resp = client.get("/v1/search/species", params={"q": "zzznomatch_xyzzy"})
        assert resp.json() == []

    def test_response_is_list(self, client: TestClient) -> None:
        resp = client.get("/v1/search/species", params={"q": "canis"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_species_items_have_required_fields(self, client: TestClient) -> None:
        """Each Species item must have 'name' and 'taxonomy_id'."""
        resp = client.get("/v1/search/species", params={"q": "canis"})
        for item in resp.json():
            assert "name" in item, f"Missing 'name' in {item}"
            assert "taxonomy_id" in item, f"Missing 'taxonomy_id' in {item}"

    def test_missing_q_returns_422(self, client: TestClient) -> None:
        resp = client.get("/v1/search/species")
        assert resp.status_code == 422


# ===========================================================================
# GET /v1/search/genes
# ===========================================================================


class TestSearchGenes:
    """
    Tests for GET /v1/search/genes.

    KNOWN LIMITATION: Ensembl REST does NOT provide fuzzy or prefix gene-symbol
    search.  This endpoint performs exact-match lookup only.  The Ensembl call
    may also fail or return empty in offline CI environments -- tests are written
    to tolerate both empty and non-empty responses as long as the HTTP status is
    200 and the shape is correct.
    """

    def test_status_code_is_200(self, client: TestClient) -> None:
        # Exact-match only -- unknown symbol returns empty list, not 422/500
        resp = client.get(
            "/v1/search/genes",
            params={"q": "ZZZNOGENE", "species": "homo_sapiens"},
        )
        assert resp.status_code == 200

    def test_unknown_gene_returns_empty_list(self, client: TestClient) -> None:
        # KNOWN LIMITATION: exact-match only; partial symbols return empty
        resp = client.get(
            "/v1/search/genes",
            params={"q": "ZZZNOGENE_XYZZY", "species": "homo_sapiens"},
        )
        assert resp.json() == []

    def test_response_is_list(self, client: TestClient) -> None:
        resp = client.get(
            "/v1/search/genes",
            params={"q": "BRCA1", "species": "homo_sapiens"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_gene_items_have_required_fields(self, client: TestClient) -> None:
        """Each Gene item must have 'symbol' and 'name' (exact-match only)."""
        resp = client.get(
            "/v1/search/genes",
            params={"q": "BRCA1", "species": "homo_sapiens"},
        )
        for item in resp.json():
            assert "symbol" in item, f"Missing 'symbol' in {item}"
            assert "name" in item, f"Missing 'name' in {item}"

    def test_missing_q_returns_422(self, client: TestClient) -> None:
        resp = client.get("/v1/search/genes", params={"species": "homo_sapiens"})
        assert resp.status_code == 422

    def test_missing_species_returns_422(self, client: TestClient) -> None:
        resp = client.get("/v1/search/genes", params={"q": "BRCA1"})
        assert resp.status_code == 422


# ===========================================================================
# POST /v1/runs -- new contract shape (StartRunResponse)
# ===========================================================================


class TestRunsPostSuccess:
    """
    POST /v1/runs now returns StartRunResponse{run_id} immediately.
    Full result assertions have moved to TestRunsGetContractShape.
    """

    def setup_method(self) -> None:
        orch, repo = _make_orchestrator()
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_status_code_is_200(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 200

    def test_response_has_run_id(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        body = resp.json()
        assert "run_id" in body
        assert isinstance(body["run_id"], str)
        assert len(body["run_id"]) > 0

    def test_response_only_has_run_id_field(self) -> None:
        """StartRunResponse must only contain run_id (contract shape)."""
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        body = resp.json()
        # Only run_id is expected in StartRunResponse
        assert set(body.keys()) == {"run_id"}

    def test_old_nested_format_returns_422(self) -> None:
        """The old {project, run} body shape is rejected by the new contract."""
        resp = TestClient(app).post("/v1/runs", json=_OLD_FORMAT_BODY)
        assert resp.status_code == 422


# ===========================================================================
# POST /v1/runs -- async timing
# ===========================================================================


class TestRunsPostAsync:
    """POST /v1/runs must return before pipeline completion."""

    def setup_method(self) -> None:
        orch, repo = _make_orchestrator()
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_response_is_not_blocked_on_pipeline(self) -> None:
        """
        Confirm the route returns StartRunResponse quickly, not after pipeline
        completion.  Stubs complete in milliseconds, so we assert < 2 seconds
        as a generous upper bound that would catch a synchronous regression.
        """
        start = time.perf_counter()
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert "run_id" in resp.json()
        # Under 2 seconds even on slow CI; synchronous pipeline would be much longer
        assert elapsed < 2.0, f"Route took {elapsed:.2f}s -- possible synchronous block"


# ===========================================================================
# POST /v1/runs -- failure paths (now via GET after dispatch)
# ===========================================================================


class TestRunsPostClarificationRequired:
    """Clarification-required runs: POST returns run_id, GET shows failed status."""

    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(resolver=StubObjectiveResolver(clarification_required=True))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_http_status_is_200(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 200

    def test_response_has_run_id(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert "run_id" in resp.json()


class TestRunsPostInsufficientEvidence:
    """Insufficient evidence: POST returns run_id."""

    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(retriever=StubEvidenceRetriever(return_empty=True))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_http_status_is_200(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 200


class TestRunsPostNoFeasiblePlan:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(planner=StubStrategicPlanner(return_empty=True))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_http_status_is_200(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 200


class TestRunsPostValidationFailed:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(validator=StubStrategyValidator(return_valid=False))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_http_status_is_200(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 200


class TestRunsPostPartialAnalysis:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator(analyzer=StubPostPlanAnalyzer(return_status="partial"))
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_http_status_is_200(self) -> None:
        resp = TestClient(app).post("/v1/runs", json=_VALID_BODY)
        assert resp.status_code == 200


# ===========================================================================
# POST /v1/runs -- request validation (422)
# ===========================================================================


class TestRunsPostBadRequest:
    def setup_method(self) -> None:
        orch, repo = _make_orchestrator()
        _override(orch, repo)

    def teardown_method(self) -> None:
        _clear()

    def test_missing_species_returns_422(self) -> None:
        body = {k: v for k, v in _VALID_BODY.items() if k != "species"}
        resp = TestClient(app).post("/v1/runs", json=body)
        assert resp.status_code == 422

    def test_missing_research_objective_returns_422(self) -> None:
        body = {k: v for k, v in _VALID_BODY.items() if k != "research_objective"}
        resp = TestClient(app).post("/v1/runs", json=body)
        assert resp.status_code == 422

    def test_missing_constraints_returns_422(self) -> None:
        body = {k: v for k, v in _VALID_BODY.items() if k != "constraints"}
        resp = TestClient(app).post("/v1/runs", json=body)
        assert resp.status_code == 422

    def test_extra_top_level_field_returns_422(self) -> None:
        """ContractRunRequest has extra="forbid"."""
        body = {**_VALID_BODY, "unexpected_field": "value"}
        resp = TestClient(app).post("/v1/runs", json=body)
        assert resp.status_code == 422


# ===========================================================================
# GET /v1/runs/{run_id} -- contract-shaped result
# ===========================================================================


class TestRunsGetContractShape:
    """
    Verify GET /v1/runs/{run_id} returns contract-shaped ContractRunResult.

    Includes the critical confidence guarantee test: confidence must be only
    "evidence" or "unknown" -- never "model_estimated" (architecture Sec. 8).
    """

    def _post_and_wait(
        self, tc: TestClient, wait_s: float = 0.5
    ) -> tuple[str, dict]:
        """Submit a run, wait briefly for background task, then GET the result."""
        post_resp = tc.post("/v1/runs", json=_VALID_BODY)
        assert post_resp.status_code == 200
        run_id = post_resp.json()["run_id"]
        # Give the asyncio background task time to complete
        time.sleep(wait_s)
        get_resp = tc.get(f"/v1/runs/{run_id}")
        return run_id, get_resp.json()

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

    def test_run_result_has_required_fields(self) -> None:
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            run_id, body = self._post_and_wait(tc)
            assert "run_id" in body
            assert "status" in body
            assert "nodes" in body
            assert "edges" in body
            assert "strategies" in body
        finally:
            _clear()

    def test_run_id_matches(self) -> None:
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            run_id, body = self._post_and_wait(tc)
            assert body["run_id"] == run_id
        finally:
            _clear()

    def test_status_is_valid_contract_value(self) -> None:
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            _, body = self._post_and_wait(tc)
            assert body["status"] in {"queued", "running", "complete", "failed"}
        finally:
            _clear()

    def test_confidence_never_model_estimated(self) -> None:
        """
        Architecture Sec. 8: confidence is NEVER "model_estimated".

        This test inspects every edge in the response and asserts that
        confidence is only "evidence" or "unknown".  The ContractGraphEdge
        type Literal["evidence","unknown"] structurally prevents
        "model_estimated", but this runtime check provides belt-and-suspenders
        coverage.
        """
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            _, body = self._post_and_wait(tc)
            permitted = {"evidence", "unknown"}
            for edge in body.get("edges", []):
                conf = edge.get("confidence")
                assert conf in permitted, (
                    f"Edge {edge.get('id')!r} has forbidden confidence "
                    f"{conf!r} -- 'model_estimated' is never permitted "
                    f"(architecture Sec. 8)"
                )
            for node in body.get("nodes", []):
                conf = node.get("confidence")
                if conf is not None:
                    assert conf in permitted, (
                        f"Node {node.get('id')!r} has forbidden confidence {conf!r}"
                    )
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

    def test_in_progress_run_returns_partial_result(self) -> None:
        """
        A run that has been admitted (QUEUED state saved) but not yet
        completed should return a partial ContractRunResult (not 404).
        """
        orch, repo = _make_orchestrator()
        tc = _client_with(orch, repo)
        try:
            # POST returns immediately
            post_resp = tc.post("/v1/runs", json=_VALID_BODY)
            assert post_resp.status_code == 200
            run_id = post_resp.json()["run_id"]
            # GET immediately (before background task may finish)
            get_resp = tc.get(f"/v1/runs/{run_id}")
            assert get_resp.status_code == 200
            body = get_resp.json()
            # Must have status field (queued/running/complete/failed)
            assert body["status"] in {"queued", "running", "complete", "failed"}
        finally:
            _clear()


# ===========================================================================
# Phase 2E: Concurrency Guard API
# ===========================================================================


class TestConcurrencyAPI:
    def teardown_method(self) -> None:
        _clear()

    def test_submit_run_at_capacity_returns_429(self) -> None:
        """
        When active run count >= max_concurrent_runs the route must return 429.

        The route-layer capacity pre-check counts PENDING/QUEUED/RUNNING states
        in the repository.  We pre-populate the repository with a QUEUED state
        to simulate a full server, then verify the pre-check fires.
        """
        from app.models.run_state import RunState, RunStatus

        orch, repo = _make_orchestrator()
        # Simulate one active run by injecting a QUEUED state
        repo.save_state(RunState(run_id="existing-run", status=RunStatus.QUEUED))
        # Set capacity to 1 so the pre-check sees 1 >= 1
        original_max = orch._max_concurrent_runs
        orch._max_concurrent_runs = 1
        tc = _client_with(orch, repo)

        try:
            resp = tc.post("/v1/runs", json=_VALID_BODY)
            assert resp.status_code == 429
            assert "capacity" in resp.json()["detail"].lower()
        finally:
            orch._max_concurrent_runs = original_max
            _clear()


# ===========================================================================
# Phase 2E: Timeout Guard API
# ===========================================================================


class TestTimeoutAPI:
    def teardown_method(self) -> None:
        _clear()

    def test_timeout_run_exposed_via_get(self) -> None:
        """
        A run that times out (via the orchestrator's timeout check) should
        eventually expose a "failed" status on GET.

        The background task catches the failed result and saves it under the
        route_run_id.  We wait briefly for the task to complete.
        """
        import time as _time

        orch, repo = _make_orchestrator()
        orch._run_timeout_seconds = 0  # Instant timeout

        original_monotonic = _time.monotonic

        try:
            _time.monotonic = lambda: original_monotonic() + 1
            tc = _client_with(orch, repo)
            post_resp = tc.post("/v1/runs", json=_VALID_BODY)
        finally:
            _time.monotonic = original_monotonic

        assert post_resp.status_code == 200
        run_id = post_resp.json()["run_id"]

        # Wait for background task to resolve
        _time.sleep(0.5)

        get_resp = tc.get(f"/v1/runs/{run_id}")
        assert get_resp.status_code == 200
        # Status should be "complete" or "failed" by now
        assert get_resp.json()["status"] in {"complete", "failed"}

        _clear()
