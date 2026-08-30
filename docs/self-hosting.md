# Relict Core — Self-Hosting & Bootstrap Guide

This guide covers first-instance self-hosting bootstrap, local dataset initialization, database management, and deterministic post-plan explanation in **Relict Core**.

---

## 1. Overview & Architecture

Relict Core operates as an autonomous, self-contained biological orchestration server designed to be self-hosted either on local workstations, on-prem servers, or cloud instances.

```
Relict Shell / Client
        │  (HTTP / SSE + Bearer rc_live_...)
        ▼
   Relict Core API (FastAPI)
        │
   ┌────┴─────────────────────────────┐
   │                                  │
   ▼                                  ▼
SQLite Databases (WAL)        DuckDB (Read-Only)
- Run repository (relict.db)  - AlphaMissense / FarmGTEx / EpiDB
- Cache (cache.sqlite3)       (data/alphamissense.duckdb)
- Species Index (species.db)
```

---

## 2. First-Instance Bootstrap

To perform full local initialization on a clean machine:

```bash
relict-core bootstrap
```

### What Bootstrap Performs:
1. **Directory Tree Provisioning**: Creates `data/`, `data/species/`, `data/cache/`, `logs/`, and `app/core_model/weights/`.
2. **SQLite Initialization**: Sets up `data/relict.db` and `data/cache.sqlite3` with WAL mode, foreign keys, table schemas, and runs read-write verification tests.
3. **DuckDB Initialization**: Initializes `data/alphamissense.duckdb` and verifies read-only query capabilities.
4. **Species Database Preparation**: Verifies `data/species/species.csv` (~1.4M species) or decompresses `species.csv.gz`, and generates a high-speed SQLite indexed lookup database (`data/species/species.db`).
5. **Core Model Verification**: Verifies `model_manifest.json` assets and backend usability.
6. **API Key Generation**: Generates a secure bearer token (`rc_live_<hex>`) and writes `.env` with restrictive permissions (`0600`).

---

## 3. Idempotency & Safe Recovery

Running `relict-core bootstrap` multiple times is safe:
- **No Destruction**: Valid databases, caches, and run histories are never deleted or wiped.
- **No Key Overwriting**: Existing configured API tokens are detected and preserved.
- **Selective Repair**: Only missing or corrupted datasets/indexes are rebuilt.
- **Force Re-initialization**: Use `relict-core bootstrap --force` if you intentionally wish to regenerate credentials or re-verify all components.

---

## 4. Starting the Server

Launch the production API server:

```bash
relict-core start --host 0.0.0.0 --port 8000
```

Verify service status:

```bash
relict-core status
```

Or query the liveness endpoint:

```bash
curl http://localhost:8000/v1/health
# {"status": "ok"}
```

---

## 5. Connecting Relict Shell

Configure Relict Shell with the generated credentials:

```bash
export RELICT_CORE_URL="http://localhost:8000"
export RELICT_API_KEY="rc_live_..."
```

---

## 6. Core Model Task 1 vs. Task 2 Architecture

- **Task 1 (Objective Resolution)**:
  - Converts natural language biological research objectives into structured contracts (`StructuredObjective`).
  - Uses `ModelClient` when configured; falls back to deterministic concept extraction and ambiguity detection when offline.
  - Ambiguous objectives immediately short-circuit to `CLARIFICATION_REQUIRED`.

- **Task 2 (Post-Plan Explanation Generation)**:
  - **Core Model Task 2 is completely disabled/bypassed.**
  - Explanations are generated using a 100% deterministic evidence projection engine grounded in source-backed `EvidenceRecord` objects, `EvidenceGraph` edges, and validation results.
  - **No LLM reasoning or biological hallucination**: all claims are strictly backed by source citations, effect types, directions, and scores.
  - Preserves uncertainty if effect direction is unknown and explicitly surfaces conflicting evidence across sources.
