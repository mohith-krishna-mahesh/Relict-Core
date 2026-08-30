"""
Repository contract tests for Phase 2D.

Coverage
--------
1. **Parameterized contract tests** — run against both ``RunRepository``
   (in-memory) and ``SQLiteRunRepository`` (backed by an in-memory SQLite
   connection) to prove they are behaviourally identical against the shared
   interface.

2. **SQLite-specific tests** — durability across two repository instances
   on the same on-disk file (proves the data is actually persisted, not
   just correct within one connection's lifetime) and schema-creation
   idempotency.

Fixtures
--------
All SQLite tests that need a real file use pytest's built-in ``tmp_path``
fixture.  No test artifact is ever written to ``data/relict.db`` or anywhere
outside a temporary directory.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.cache.sqlite_client import ensure_schema, open_connection
from app.cache.sqlite_repository import SQLiteRunRepository
from app.models.requests import ProjectContext, RunConfiguration, Scope, StrategyMode
from app.models.responses import RunResult
from app.models.run_state import RunState, RunStatus
from app.run_manager.repository import RunNotFoundError, RunRepository

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _project() -> ProjectContext:
    return ProjectContext(
        project_id="test-proj-repo-001",
        species="Canis lupus",
        scope=Scope.DE_EXTINCTION,
        objective="Make the coat white.",
    )


def _run_config() -> RunConfiguration:
    return RunConfiguration(max_edits=3, strategy=StrategyMode.MINIMAL)


def _make_sqlite_repo() -> SQLiteRunRepository:
    """Return a ``SQLiteRunRepository`` backed by an in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    ensure_schema(conn)
    return SQLiteRunRepository(conn)


def _make_sqlite_repo_at(path: Path) -> SQLiteRunRepository:
    """Return a ``SQLiteRunRepository`` backed by an on-disk SQLite file at *path*."""
    conn = open_connection(path)
    ensure_schema(conn)
    return SQLiteRunRepository(conn)


# ---------------------------------------------------------------------------
# Parameterized fixture: both implementations
# ---------------------------------------------------------------------------


@pytest.fixture(params=["in_memory", "sqlite"])
def repo(request: pytest.FixtureRequest) -> RunRepository | SQLiteRunRepository:
    """
    Yield a repository instance for each implementation.

    ``"in_memory"``  → ``RunRepository()``
    ``"sqlite"``     → ``SQLiteRunRepository`` backed by ``:memory:``
    """
    if request.param == "in_memory":
        return RunRepository()
    return _make_sqlite_repo()


# ===========================================================================
# Contract tests — parameterized over both implementations
# ===========================================================================


class TestRepositoryContract:
    """Behavioural contract that both repository implementations must satisfy."""

    # ---- RunState ---------------------------------------------------------

    def test_save_state_then_load_state_returns_equal(
        self, repo: RunRepository | SQLiteRunRepository
    ) -> None:
        state = RunState(run_id="r1", status=RunStatus.PENDING)
        repo.save_state(state)
        loaded = repo.load_state("r1")
        assert loaded.run_id == state.run_id
        assert loaded.status == state.status

    def test_load_state_unknown_run_id_raises_run_not_found_error(
        self, repo: RunRepository | SQLiteRunRepository
    ) -> None:
        with pytest.raises(RunNotFoundError):
            repo.load_state("does-not-exist")

    def test_save_state_twice_overwrites(self, repo: RunRepository | SQLiteRunRepository) -> None:
        repo.save_state(RunState(run_id="r2", status=RunStatus.PENDING))
        repo.save_state(RunState(run_id="r2", status=RunStatus.COMPLETE))
        assert repo.load_state("r2").status == RunStatus.COMPLETE

    def test_all_states_empty_initially(self, repo: RunRepository | SQLiteRunRepository) -> None:
        assert repo.all_states() == []

    def test_all_states_reflects_saved(self, repo: RunRepository | SQLiteRunRepository) -> None:
        repo.save_state(RunState(run_id="r3", status=RunStatus.PENDING))
        repo.save_state(RunState(run_id="r4", status=RunStatus.RUNNING))
        ids = {s.run_id for s in repo.all_states()}
        assert ids == {"r3", "r4"}

    def test_all_states_does_not_duplicate_on_overwrite(
        self, repo: RunRepository | SQLiteRunRepository
    ) -> None:
        repo.save_state(RunState(run_id="r5", status=RunStatus.PENDING))
        repo.save_state(RunState(run_id="r5", status=RunStatus.COMPLETE))
        assert len(repo.all_states()) == 1

    # ---- RunResult --------------------------------------------------------

    def test_save_result_then_load_result_returns_equal(
        self, repo: RunRepository | SQLiteRunRepository
    ) -> None:
        result = RunResult(
            run_id="rr1",
            status=RunStatus.COMPLETE,
            project_context=_project(),
            run_configuration=_run_config(),
        )
        repo.save_result(result)
        loaded = repo.load_result("rr1")
        assert loaded.run_id == "rr1"
        assert loaded.status == RunStatus.COMPLETE

    def test_load_result_unknown_run_id_raises_run_not_found_error(
        self, repo: RunRepository | SQLiteRunRepository
    ) -> None:
        with pytest.raises(RunNotFoundError):
            repo.load_result("does-not-exist")

    def test_save_result_twice_overwrites(self, repo: RunRepository | SQLiteRunRepository) -> None:
        result_a = RunResult(
            run_id="rr2",
            status=RunStatus.RUNNING,
            project_context=_project(),
            run_configuration=_run_config(),
        )
        result_b = RunResult(
            run_id="rr2",
            status=RunStatus.COMPLETE,
            project_context=_project(),
            run_configuration=_run_config(),
        )
        repo.save_result(result_a)
        repo.save_result(result_b)
        assert repo.load_result("rr2").status == RunStatus.COMPLETE

    def test_has_result_false_before_save(self, repo: RunRepository | SQLiteRunRepository) -> None:
        assert repo.has_result("nonexistent") is False

    def test_has_result_true_after_save(self, repo: RunRepository | SQLiteRunRepository) -> None:
        result = RunResult(
            run_id="rr3",
            status=RunStatus.FAILED,
            project_context=_project(),
            run_configuration=_run_config(),
        )
        repo.save_result(result)
        assert repo.has_result("rr3") is True

    def test_multiple_run_ids_are_independent(
        self, repo: RunRepository | SQLiteRunRepository
    ) -> None:
        repo.save_state(RunState(run_id="x1", status=RunStatus.PENDING))
        repo.save_state(RunState(run_id="x2", status=RunStatus.RUNNING))
        assert repo.load_state("x1").status == RunStatus.PENDING
        assert repo.load_state("x2").status == RunStatus.RUNNING

    def test_state_fields_roundtrip(self, repo: RunRepository | SQLiteRunRepository) -> None:
        """All relevant RunState fields survive a save/load cycle."""
        from app.models.run_state import PostPlanAnalysisStatus

        state = RunState(
            run_id="rt1",
            status=RunStatus.COMPLETE,
            current_stage="post_plan",
            progress=1.0,
            post_plan_analysis_status=PostPlanAnalysisStatus.COMPLETE,
        )
        repo.save_state(state)
        loaded = repo.load_state("rt1")
        assert loaded.current_stage == "post_plan"
        assert loaded.progress == pytest.approx(1.0)
        assert loaded.post_plan_analysis_status == PostPlanAnalysisStatus.COMPLETE

    def test_result_fields_roundtrip(self, repo: RunRepository | SQLiteRunRepository) -> None:
        """Nested RunResult fields (project_context, run_configuration) survive roundtrip."""
        result = RunResult(
            run_id="rt2",
            status=RunStatus.COMPLETE,
            project_context=_project(),
            run_configuration=_run_config(),
        )
        repo.save_result(result)
        loaded = repo.load_result("rt2")
        assert loaded.project_context.species == "Canis lupus"
        assert loaded.run_configuration.max_edits == 3


# ===========================================================================
# SQLite-specific tests
# ===========================================================================


class TestSQLiteRunRepositorySpecific:
    """Tests that only make sense for the SQLite implementation."""

    def test_state_persists_across_two_connections(self, tmp_path: Path) -> None:
        """
        Durability test: a ``RunState`` saved via one repository instance
        can be retrieved by a second instance pointing at the same file.

        This proves the data is actually written to disk, not just held
        in one connection's in-memory buffers.
        """
        db_path = tmp_path / "test_persistence.db"

        # Write via instance A.
        repo_a = _make_sqlite_repo_at(db_path)
        state = RunState(run_id="persist-001", status=RunStatus.COMPLETE)
        repo_a.save_state(state)
        repo_a._conn.close()

        # Read via instance B (a fresh connection to the same file).
        repo_b = _make_sqlite_repo_at(db_path)
        loaded = repo_b.load_state("persist-001")
        repo_b._conn.close()

        assert loaded.run_id == "persist-001"
        assert loaded.status == RunStatus.COMPLETE

    def test_result_persists_across_two_connections(self, tmp_path: Path) -> None:
        """``RunResult`` durability across two separate connections."""
        db_path = tmp_path / "test_result_persistence.db"

        repo_a = _make_sqlite_repo_at(db_path)
        result = RunResult(
            run_id="persist-002",
            status=RunStatus.FAILED,
            project_context=_project(),
            run_configuration=_run_config(),
        )
        repo_a.save_result(result)
        repo_a._conn.close()

        repo_b = _make_sqlite_repo_at(db_path)
        loaded = repo_b.load_result("persist-002")
        repo_b._conn.close()

        assert loaded.run_id == "persist-002"
        assert loaded.status == RunStatus.FAILED

    def test_schema_creation_is_idempotent(self, tmp_path: Path) -> None:
        """
        Calling ``ensure_schema`` on a database that already has the tables
        must not raise an error (``CREATE TABLE IF NOT EXISTS`` semantics).
        """
        db_path = tmp_path / "test_idempotent.db"

        conn = open_connection(db_path)
        ensure_schema(conn)  # first call — creates tables
        ensure_schema(conn)  # second call — must not raise
        conn.close()

    def test_second_repository_instance_same_file_no_error(self, tmp_path: Path) -> None:
        """Constructing two repositories against the same file is safe."""
        db_path = tmp_path / "test_two_repos.db"

        repo_a = _make_sqlite_repo_at(db_path)
        # Construct repo_b without closing repo_a's connection (WAL mode allows
        # multiple readers but only one writer — this tests that opening a
        # second connection doesn't error on schema creation).
        repo_b = _make_sqlite_repo_at(db_path)

        repo_a.save_state(RunState(run_id="two-001", status=RunStatus.PENDING))
        loaded = repo_b.load_state("two-001")
        assert loaded.run_id == "two-001"

        repo_a._conn.close()
        repo_b._conn.close()

    def test_uses_in_memory_connection_for_fast_tests(self) -> None:
        """
        The constructor accepts ``:memory:`` connections — no filesystem needed
        for unit tests.
        """
        conn = sqlite3.connect(":memory:")
        ensure_schema(conn)
        repo = SQLiteRunRepository(conn)
        state = RunState(run_id="mem-001", status=RunStatus.QUEUED)
        repo.save_state(state)
        assert repo.load_state("mem-001").status == RunStatus.QUEUED
        conn.close()

    def test_open_connection_creates_parent_directories(self, tmp_path: Path) -> None:
        """``open_connection`` creates nested parent dirs that don't exist yet."""
        db_path = tmp_path / "nested" / "subdir" / "relict.db"
        conn = open_connection(db_path)
        conn.close()
        assert db_path.exists()
