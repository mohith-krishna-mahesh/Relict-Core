import asyncio
import time
from pathlib import Path
from app.models.requests import ProjectContext, RunConfiguration, Scope, StrategyMode
from app.run_manager.orchestrator import RunOrchestrator
from app.core_model.resolver import CoreModelObjectiveResolver
from app.knowledge_retrieval.retrieval import RetrievalOrchestrator
from app.planner.adapter import ProductionStrategicPlanner
from app.validator.plan_validator import PlanValidator
from app.post_plan.analyzer import DefaultPostPlanAnalyzer
from app.cache.sqlite_client import open_connection, ensure_schema
from app.cache.sqlite_repository import SQLiteRunRepository
from app.run_manager.events import InMemoryRunEventBus

TEST_SUITE = [
    {
        "scope": Scope.CONSERVATION,
        "species": "Gorilla gorilla",
        "objective": "Increase fertility in gorillas by upregulating luteinizing hormone (LH) secretion",
        "candidate_genes": [],  # Test autonomous gene discovery from prompt!
        "constraints": ["preserve_fertility", "maximize_diversity"],
    },
    {
        "scope": Scope.DE_EXTINCTION,
        "species": "Mammuthus primigenius",
        "objective": "Reconstitute cold adaptation traits in mammoth lineage by modulating non-shivering thermogenesis",
        "candidate_genes": ["UCP1", "TRPV3"],
        "constraints": ["maximize_diversity"],
    },
    {
        "scope": Scope.AGRICULTURE,
        "species": "Oryza sativa",
        "objective": "Enhance drought tolerance in rice by modulating deep rooting architecture",
        "candidate_genes": ["DRO1", "OsNAC10"],
        "constraints": ["preserve_vigor"],
    },
    {
        "scope": Scope.SYNTHETIC_BIOLOGY,
        "species": "Escherichia coli",
        "objective": "Optimize isoprenoid biosynthetic pathway flux by balancing precursor supply",
        "candidate_genes": ["dxs", "idi", "ispA"],
        "constraints": ["minimize_toxicity"],
    },
    {
        "scope": Scope.POPULATION_CONTROL,
        "species": "Anopheles gambiae",
        "objective": "Suppress malaria vector populations by targeting female fertility genes with gene drive",
        "candidate_genes": ["dsx", "zpg"],
        "constraints": ["limit_off_target"],
    },
    {
        "scope": Scope.PRECISION_MEDICINE,
        "species": "Homo sapiens",
        "objective": "Lower circulating LDL cholesterol by downregulating PCSK9 expression",
        "candidate_genes": ["PCSK9", "LDLR"],
        "constraints": ["minimize_off_target"],
    },
]


async def benchmark():
    conn = open_connection(Path("data/relict.db"))
    ensure_schema(conn)
    repo = SQLiteRunRepository(conn)
    bus = InMemoryRunEventBus()

    orch = RunOrchestrator(
        resolver=CoreModelObjectiveResolver(),
        retriever=RetrievalOrchestrator(),
        planner=ProductionStrategicPlanner(),
        validator=PlanValidator(),
        analyzer=DefaultPostPlanAnalyzer(),
        repository=repo,
        event_bus=bus,
    )

    print("=====================================================================")
    print("RELICT CORE — FULL PIPELINE 6-SCOPE COMPREHENSIVE BENCHMARK")
    print("=====================================================================")

    results_summary = []

    for i, test in enumerate(TEST_SUITE, 1):
        scope = test["scope"]
        species = test["species"]
        objective = test["objective"]
        genes = test["candidate_genes"]
        constraints = test["constraints"]

        print(f"\n[{i}/6] Testing Scope: {scope.value.upper()} | Species: {species}")
        print(f'    Objective: "{objective}"')
        print(f"    Candidates: {genes or '(Autonomous Discovery)'}")
        print(f"    Constraints: {constraints}")

        project = ProjectContext(
            project_id=f"bench_{scope.value}",
            species=species,
            scope=scope,
            objective=objective,
        )
        config = RunConfiguration(
            candidate_genes=genes,
            max_edits=3,
            constraints=constraints,
            strategy=StrategyMode.MINIMAL,
        )

        t0 = time.time()
        try:
            result = await orch.execute(project, config)
            duration = time.time() - t0
            status_str = (
                result.status.value if hasattr(result.status, "value") else str(result.status)
            )
            strat_count = len(result.strategies) if result.strategies else 0
            best_strat = result.strategies[0] if result.strategies else None
            best_score = f"{best_strat.score:.2f}" if best_strat else "N/A"
            best_cands = ", ".join(best_strat.selected_candidates) if best_strat else "None"
            post_plan_status = (
                result.post_plan.status.value
                if result.post_plan and hasattr(result.post_plan.status, "value")
                else "N/A"
            )

            print(f"    ✓ Run Status: {status_str.upper()} in {duration:.2f}s")
            print(f"    ✓ Strategies: {strat_count} candidate plans (Best Score: {best_score})")
            print(f"    ✓ Top Candidates: [{best_cands}]")
            print(f"    ✓ Post-Plan Analysis: {post_plan_status}")

            results_summary.append(
                {
                    "scope": scope.value,
                    "species": species,
                    "duration": f"{duration:.2f}s",
                    "status": status_str,
                    "strategies": strat_count,
                    "top_candidates": best_cands,
                    "score": best_score,
                    "post_plan": post_plan_status,
                }
            )
        except Exception as e:
            duration = time.time() - t0
            print(f"    ✗ FAILED with error: {e} ({duration:.2f}s)")
            results_summary.append(
                {
                    "scope": scope.value,
                    "species": species,
                    "duration": f"{duration:.2f}s",
                    "status": f"ERROR: {e}",
                    "strategies": 0,
                    "top_candidates": "None",
                    "score": "N/A",
                    "post_plan": "N/A",
                }
            )

    print("\n" + "=" * 80)
    print("FINAL 6-SCOPE BENCHMARK SUMMARY TABLE")
    print("=" * 80)
    header = f"{'Scope':<20} | {'Species':<22} | {'Duration':<10} | {'Status':<10} | {'Candidates':<20} | {'Score':<6}"
    print(header)
    print("-" * len(header))
    for r in results_summary:
        print(
            f"{r['scope']:<20} | {r['species']:<22} | {r['duration']:<10} | {r['status']:<10} | {r['top_candidates']:<20} | {r['score']:<6}"
        )
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(benchmark())
