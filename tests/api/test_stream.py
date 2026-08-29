"""
HTTP-level tests for GET /v1/runs/{run_id}/stream (Phase 2C SSE endpoint).

Test approach
-------------
``httpx.TestClient`` (via ``fastapi.testclient.TestClient``) does not support
``get(..., stream=True)`` in httpx >= 0.20.  Instead, use the ``client.stream``
context manager (``with client.stream("GET", url) as resp``), which is the
correct httpx idiom for streaming responses.  ``resp.read()`` buffers the full
SSE body after the generator closes; since ``RunOrchestrator.execute()`` runs
inline (Phase 2C), the run is always complete before the SSE client opens the
connection, so the bus replays the full history and the generator closes
immediately — no infinite blocking occurs.

Each test:
1. Submits a run via ``POST /v1/runs`` to obtain a ``run_id``.
2. Opens ``GET /v1/runs/{run_id}/stream`` via ``client.stream``.
3. Parses the raw SSE text (``event:`` / ``data:`` line pairs separated by
   ``\\r\\n\\r\\n`` blank lines).
4. Asserts on the collected events.

Fixture / helper reuse
----------------------
Uses the same request body shape and DI-override pattern as ``test_routes.py``.
"""

from __future__ import annotations

import json
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_event_bus, get_orchestrator, get_repository
from app.main import app
from app.models.failures import FailureCode
from app.run_manager.events import InMemoryRunEventBus
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
# Shared request body (matches test_routes.py)
# ---------------------------------------------------------------------------

_VALID_BODY: dict = {
    "project": {
        "project_id": "test-proj-stream-001",
        "species": "Canis lupus",
        "scope": "de-extinction",
        "objective": "Make the coat white.",
    },
    "run": {
        "max_edits": 3,
        "strategy": "minimal",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orchestrator_with_bus(
    *,
    resolver: object | None = None,
    retriever: object | None = None,
    planner: object | None = None,
    validator: object | None = None,
    analyzer: object | None = None,
) -> tuple[RunOrchestrator, RunRepository, InMemoryRunEventBus]:
    """Build orchestrator + repo + bus; return all three for DI override."""
    repo = RunRepository()
    bus = InMemoryRunEventBus()
    orch = RunOrchestrator(
        resolver=resolver or StubObjectiveResolver(),  # type: ignore[arg-type]
        retriever=retriever or StubEvidenceRetriever(),  # type: ignore[arg-type]
        planner=planner or StubStrategicPlanner(),  # type: ignore[arg-type]
        validator=validator or StubStrategyValidator(),  # type: ignore[arg-type]
        analyzer=analyzer or StubPostPlanAnalyzer(),  # type: ignore[arg-type]
        repository=repo,
        event_bus=bus,
    )
    return orch, repo, bus


def _override_all(
    orch: RunOrchestrator,
    repo: RunRepository,
    bus: InMemoryRunEventBus,
) -> None:
    """Install DI overrides for orchestrator, repository, and event bus."""
    app.dependency_overrides[get_orchestrator] = lambda: orch
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_event_bus] = lambda: bus


def _clear() -> None:
    app.dependency_overrides.clear()


def _parse_sse_body(text: str) -> list[dict]:
    """
    Parse a raw SSE response body into a list of event dicts.

    Each dict has keys ``"event"`` (str) and ``"data"`` (parsed JSON dict).

    SSE format (RFC 8895 / sse-starlette): fields separated by ``\\r\\n``,
    events separated by ``\\r\\n\\r\\n`` blank lines.  We tolerate both CRLF
    and LF line endings for robustness.
    """
    events: list[dict] = []
    # Split on blank lines (event boundaries)
    blocks = text.replace("\r\n", "\n").split("\n\n")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        current_event_type: str | None = None
        current_data: str | None = None
        for line in block.splitlines():
            if line.startswith("event:"):
                current_event_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                current_data = line[len("data:"):].strip()
        if current_data:
            events.append(
                {
                    "event": current_event_type,
                    "data": json.loads(current_data),
                }
            )
    return events


def _collect_sse_events(client: TestClient, run_id: str) -> list[dict]:
    """
    Open the SSE stream for *run_id*, read the full body, and return parsed events.

    Uses ``client.stream("GET", url)`` — the correct httpx idiom for streaming
    responses.  ``resp.read()`` reads the entire body; since the run is already
    complete (inline execution in Phase 2C), the generator closes immediately and
    the read does not block.
    """
    with client.stream("GET", f"/v1/runs/{run_id}/stream") as resp:
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        body = resp.read().decode()
    return _parse_sse_body(body)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def success_client_and_run_id() -> Generator[tuple[TestClient, str], None, None]:
    """
    Fixture that submits a successful run and yields ``(client, run_id)``.

    The client has DI overrides wired for orchestrator, repository, and
    event bus so the SSE stream is populated with real events from a real
    (stub-backed) run.
    """
    orch, repo, bus = _make_orchestrator_with_bus()
    _override_all(orch, repo, bus)
    tc = TestClient(app)
    post_resp = tc.post("/v1/runs", json=_VALID_BODY)
    assert post_resp.status_code == 200
    run_id = post_resp.json()["run_id"]
    yield tc, run_id
    _clear()


# ===========================================================================
# TestStreamUnknownRunId — HTTP 404 matching GET /v1/runs/{run_id}
# ===========================================================================


class TestStreamUnknownRunId:
    """Stream endpoint must return the same 404 body as the GET poll endpoint."""

    def setup_method(self) -> None:
        orch, repo, bus = _make_orchestrator_with_bus()
        _override_all(orch, repo, bus)

    def teardown_method(self) -> None:
        _clear()

    def test_unknown_run_id_returns_404(self) -> None:
        resp = TestClient(app).get("/v1/runs/nonexistent-run-id/stream")
        assert resp.status_code == 404

    def test_unknown_run_id_detail_matches_get_endpoint(self) -> None:
        """Detail message must be identical to GET /v1/runs/{run_id} 404."""
        resp = TestClient(app).get("/v1/runs/nonexistent-run-id/stream")
        assert resp.json()["detail"] == "run not found"


# ===========================================================================
# TestStreamSuccessfulRun — already complete before subscribing
# ===========================================================================


class TestStreamSuccessfulRun:
    """
    The run finishes inline (Phase 2C) before the SSE client connects.
    The bus replays buffered history; the client sees the full event sequence.
    """

    def test_stream_returns_200(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        with client.stream("GET", f"/v1/runs/{run_id}/stream") as resp:
            assert resp.status_code == 200

    def test_stream_has_events(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        assert len(events) > 0

    def test_last_event_is_complete(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        assert events[-1]["event"] == "complete"

    def test_terminal_event_has_complete_status(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        terminal = events[-1]["data"]
        assert terminal["status"] == "complete"

    def test_terminal_event_progress_is_1(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        terminal = events[-1]["data"]
        assert terminal["progress"] == 1.0

    def test_terminal_event_run_id_matches(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        terminal = events[-1]["data"]
        assert terminal["run_id"] == run_id

    def test_stream_terminates_without_hang(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        """
        The async generator must return after the terminal event.
        Since the run is complete before the client connects (Phase 2C inline
        execution), the bus replays history and closes immediately — no hang.
        If this test completes, the generator returned correctly.
        """
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        # If we got here without a timeout, the generator terminated correctly.
        assert events[-1]["event"] == "complete"


# ===========================================================================
# TestStreamEventPayloadShape — data field contract
# ===========================================================================


class TestStreamEventPayloadShape:
    """Validate the JSON payload shape against the SSE wire contract."""

    def test_all_events_are_json_decodable(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        # _collect_sse_events already calls json.loads; we just assert non-empty
        assert len(events) > 0

    def test_all_events_have_required_fields(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        required = {
            "run_id",
            "status",
            "current_stage",
            "progress",
            "post_plan_analysis_status",
            "warnings",
        }
        for ev in events:
            missing = required - ev["data"].keys()
            assert not missing, f"Event {ev['event']!r} missing fields: {missing}"

    def test_event_type_field_is_present_for_all(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        """Every SSE event must have an event: line (not the default 'message')."""
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        for ev in events:
            assert ev["event"] in {"stage", "complete", "failed"}, (
                f"Unexpected event type: {ev['event']!r}"
            )

    def test_progress_values_are_floats(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        for ev in events:
            assert isinstance(ev["data"]["progress"], float), (
                f"progress is not float: {ev['data']['progress']!r}"
            )

    def test_progress_is_monotonically_non_decreasing(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        progress_values = [ev["data"]["progress"] for ev in events]
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1], (
                f"Progress decreased: {progress_values[i - 1]} → {progress_values[i]} "
                f"at event index {i}"
            )

    def test_warnings_field_is_list(
        self, success_client_and_run_id: tuple[TestClient, str]
    ) -> None:
        client, run_id = success_client_and_run_id
        events = _collect_sse_events(client, run_id)
        for ev in events:
            assert isinstance(ev["data"]["warnings"], list)


# ===========================================================================
# TestStreamFailedRun — INSUFFICIENT_EVIDENCE failure path
# ===========================================================================


class TestStreamFailedRun:
    """
    Drive a failed run via ``StubEvidenceRetriever(return_empty=True)``
    (INSUFFICIENT_EVIDENCE) and assert the SSE stream ends with a "failed"
    event carrying the correct FailureCode.
    """

    def setup_method(self) -> None:
        orch, repo, bus = _make_orchestrator_with_bus(
            retriever=StubEvidenceRetriever(return_empty=True)
        )
        _override_all(orch, repo, bus)
        self._tc = TestClient(app)
        post_resp = self._tc.post("/v1/runs", json=_VALID_BODY)
        assert post_resp.status_code == 200
        self._run_id = post_resp.json()["run_id"]

    def teardown_method(self) -> None:
        _clear()

    def test_last_event_is_failed(self) -> None:
        events = _collect_sse_events(self._tc, self._run_id)
        assert events[-1]["event"] == "failed"

    def test_terminal_event_status_is_failed(self) -> None:
        events = _collect_sse_events(self._tc, self._run_id)
        assert events[-1]["data"]["status"] == "failed"

    def test_failure_payload_present(self) -> None:
        events = _collect_sse_events(self._tc, self._run_id)
        terminal_data = events[-1]["data"]
        assert terminal_data["failure"] is not None

    def test_failure_code_is_insufficient_evidence(self) -> None:
        events = _collect_sse_events(self._tc, self._run_id)
        terminal_data = events[-1]["data"]
        assert terminal_data["failure"]["code"] == FailureCode.INSUFFICIENT_EVIDENCE

    def test_failed_stream_terminates_without_hang(self) -> None:
        """Generator must return after the 'failed' terminal event."""
        events = _collect_sse_events(self._tc, self._run_id)
        assert events[-1]["event"] == "failed"

    def test_progress_non_decreasing_on_failure(self) -> None:
        events = _collect_sse_events(self._tc, self._run_id)
        progress_values = [ev["data"]["progress"] for ev in events]
        for i in range(1, len(progress_values)):
            assert progress_values[i] >= progress_values[i - 1]


# ===========================================================================
# Phase 2E: TestStreamTimeoutRun
# ===========================================================================


class TestStreamTimeoutRun:
    """
    Drive a run that times out and assert the SSE stream handles the timeout
    failure path correctly (ends with 'failed' event, RUN_TIMEOUT code).
    """

    def setup_method(self) -> None:
        orch, repo, bus = _make_orchestrator_with_bus()
        orch._run_timeout_seconds = 0  # Instant timeout
        _override_all(orch, repo, bus)
        
        self._tc = TestClient(app)
        
        import time
        original_monotonic = time.monotonic
        
        try:
            time.monotonic = lambda: original_monotonic() + 1
            post_resp = self._tc.post("/v1/runs", json=_VALID_BODY)
        finally:
            time.monotonic = original_monotonic
            
        assert post_resp.status_code == 200
        self._run_id = post_resp.json()["run_id"]

    def teardown_method(self) -> None:
        _clear()

    def test_last_event_is_failed_on_timeout(self) -> None:
        events = _collect_sse_events(self._tc, self._run_id)
        assert events[-1]["event"] == "failed"

    def test_terminal_event_status_is_failed_on_timeout(self) -> None:
        events = _collect_sse_events(self._tc, self._run_id)
        assert events[-1]["data"]["status"] == "failed"

    def test_failure_code_is_run_timeout(self) -> None:
        events = _collect_sse_events(self._tc, self._run_id)
        terminal_data = events[-1]["data"]
        assert terminal_data["failure"]["code"] == FailureCode.RUN_TIMEOUT

    def test_timeout_stream_terminates_without_hang(self) -> None:
        """Generator must return after the 'failed' terminal event on timeout."""
        events = _collect_sse_events(self._tc, self._run_id)
        assert events[-1]["event"] == "failed"
