## 1. Architecture Overview

Relict Core is the self-hostable, continuously running computational engine behind Relict Shell. It converts a researcher's natural-language biological objective into an evidence-grounded, constrained strategy and performs downstream guide/risk analysis, population analysis, and explanation.

The canonical execution pipeline is:

```text
Core Model
    ↓
Knowledge Retrieval
    ↓
Planner
    ↓
Plan Validator
    ↓
Post-Plan Analysis
    ├── Guide & Risk Analysis
    ├── Population Propagation
    └── Explanation Generation
    ↓
Final Result
    ↓
Core API
```

The **Run Manager** surrounds and orchestrates this pipeline. It starts the run, invokes each stage in order, tracks state and failures, and collects the resulting artifacts.

The central separation is:

```text
Core Model          → interprets the objective
Knowledge Retrieval → obtains evidence
Planner             → computes a strategy
Validator           → verifies the strategy
Post-Plan Analysis  → analyzes and explains the strategy
Run Manager         → orchestrates execution
Core API            → exposes the result
```

Unsupported biological relationships are not inserted into the planning graph by default. Model output is not treated as biological evidence.

---

# 2. Core Components

## 2.1 Core Model

The Core Model is the primary open-weight language model used by Relict Core and the only learned component in the main Core pipeline.

### Model

```text
Base model:       Qwen3-4B-Instruct
Adaptation:       QLoRA
Quantization:     4-bit
LoRA rank:        16
LoRA alpha:       32
Initial dataset:  ~500–2,000 examples
Training format:  Alpaca instruction/input/output
```

Qwen3-4B-Instruct is preferred over a raw base checkpoint because it is already instruction-tuned and suited to narrow structured extraction with a relatively small task-specific dataset.

The same deployed model performs two Relict-specific tasks.

### Task 1 — Objective Resolution

Objective Resolution operates on the run's natural-language objective. It does not resolve project or run configuration.

Project-level context is already established by Shell:

```text
ProjectContext
├── species
└── scope
```

Run-level configuration is already established by Shell:

```text
RunConfiguration
├── objective
├── candidate_genes
├── max_edits
├── constraints
└── strategy = minimal | redundant
```

The Core Model receives these authoritative values as context, but it does not infer or overwrite them.

Its learned task is:

```text
Natural-language objective
        ↓
StructuredObjective
```

The model resolves the biological meaning of the objective, including:

```text
target phenotype or trait
desired change
biological processes
relevant concepts
retrieval targets
ambiguities
```

For example:

```text
ProjectContext:
    species = Canis lupus
    scope   = de-extinction

RunConfiguration:
    objective = "Make the coat white"
    max_edits = 3
    strategy  = minimal

        ↓

StructuredObjective:
    target_phenotype = coat pigmentation
    desired_change   = white pigmentation
    biological_processes = pigmentation
    retrieval_targets = relevant genes/pathways/phenotypes
```

The model does not decide the species, project scope, Minimal/Redundant strategy, edit budget, candidate-gene list, or run constraints.

If the objective cannot be resolved without guessing:

```text
CLARIFICATION_REQUIRED
```

Core returns the missing or ambiguous objective fields for Shell rather than becoming a conversational chatbot.

Structured values supplied by Shell are authoritative and cannot be silently overwritten by model inference.

Model-generated genes, pathways, concepts, or relationships are retrieval targets only. They are never directly inserted into the evidence graph.

Scope-specific project validation, such as de-extinction species-selection rules, is enforced by the project/run configuration layer before planning.

### Task 2 — Whole-Strategy Synthesis

```text
Validated Strategy
+
retrieved evidence
+
Planner rationale
        ↓
Plain-English strategy synthesis
```

The model explains the computed strategy using evidence supplied by Core. It is not used as a biological knowledge database and must not introduce unsupported biological claims from its weights.

Graph node and edge explanations remain primarily deterministic templates.

### Fine-Tuning

The same Qwen3-4B-Instruct model is fine-tuned for both tasks using QLoRA.

```text
Qwen3-4B-Instruct
        ↓
Relict SFT dataset
        ↓
QLoRA adapter
        ↓
Relict Core Model
```

Objective-resolution training data focuses on interpreting natural-language biological objectives: normal objectives, paraphrases, generic and specific objectives, biological processes, desired changes, retrieval targets, ambiguous cases, and deliberate `CLARIFICATION_REQUIRED` negative examples.

Project metadata and run configuration are contextual inputs, not fields the model is responsible for deciding.

The synthesis dataset is smaller and consists of validated strategies, retrieved evidence, and Planner rationale paired with expected explanations.

Paraphrase augmentation is used for training diversity. The held-out evaluation set is authored separately and never used for training.

### Evaluation

```text
Separate held-out eval set
        ↓
Prompted Qwen3-4B-Instruct baseline
        +
QLoRA Relict model
        ↓
Task-specific comparison
```

The fine-tuned model is accepted only if it demonstrates meaningful task-specific improvement over the prompted baseline.

### Serving

Core uses a provider-agnostic `ModelClient`.

```text
Relict Core
     ↓
ModelClient
     ↓
vLLM / Ollama / llama.cpp
     ↓
Relict model
```

vLLM is suitable for GPU servers and throughput. Ollama provides simple local serving. llama.cpp provides broad local, CPU, and Apple-Silicon compatibility.

These are serving runtimes, not different Core models.

Gemini Flash may be an optional external fallback for open-ended synthesis, but normal Core operation does not require an external LLM API.

## 2.2 Knowledge Retrieval

Knowledge Retrieval obtains the biological evidence required by the Planner.

### Input

```text
StructuredObjective
+
retrieval targets
```

### Output

```text
EvidenceRecords
```

The layer resolves species, genes, pathways, sequences, interactions, and other relevant biological entities and normalizes source-specific responses into a common evidence format. Structured project fields supplied by Shell are authoritative; the model may not override them with inferred values.

Retrieval is target-driven; a run does not need every source.

### Primary sources

| Scope                   | Source                 | Purpose                                                       |
| ----------------------- | ---------------------- | ------------------------------------------------------------- |
| **Common — All scopes** | Ensembl                | Genome, gene and sequence resolution                          |
|                         | Ensembl Compara        | Ortholog/paralog relationships                                |
|                         | NCBI                   | Species and genomic coverage                                  |
|                         | STRING                 | Functional interaction graph                                  |
|                         | KEGG                   | Biological pathways                                           |
|                         | Reactome               | Pathways and reactions                                        |
|                         | WikiPathways           | Complementary pathways                                        |
|                         | UniProt                | Protein function and domains                                  |
|                         | RCSB PDB               | Protein structures and structural relationships               |
|                         | BLAST                  | Sequence-homology fallback                                    |
|                         | GBIF                   | Species and ecological context                                |
|                         | TimeTree               | Evolutionary divergence                                       |
| **Conservation**        | DNA Zoo                | Non-model genome assemblies                                   |
|                         | VGP                    | High-quality vertebrate genome assemblies                     |
|                         | Genome 10K             | Vertebrate genome resources                                   |
| **De-Extinction**       | DNA Zoo                | Non-model genome assemblies                                   |
|                         | VGP                    | High-quality vertebrate genome assemblies                     |
|                         | Genome 10K             | Comparative vertebrate genome resources                       |
| **Agriculture**         | Gramene                | Plant/crop comparative genomics and annotations               |
|                         | Plant Reactome         | Plant pathways and gene–pathway relationships                 |
|                         | Animal QTLdb           | Livestock QTL and trait associations                          |
|                         | FAANG                  | Functional annotation and regulatory genomics in farm animals |
|                         | FarmGTEx               | Farm-animal expression and regulatory variation               |
|                         | EpiDB                  | Livestock expression and epigenetic data                      |
| **Synthetic Biology**   | BRENDA                 | Enzyme function, reactions and kinetics                       |
|                         | SABIO-RK               | Biochemical reactions and kinetic parameters                  |
|                         | SynBioHub              | Synthetic-biology parts and biological designs                |
| **Population Control**  | VectorBase / VEuPathDB | Vector genomes, genes, variants and functional data           |
| **Precision Medicine**  | AlphaMissense          | Missense-variant pathogenicity predictions                    |
|                         | Open Targets           | Target–disease–drug associations                              |
|                         | ChEMBL                 | Drug, compound, target and bioactivity data                   |
|                         | Human Protein Atlas    | Protein expression and tissue localization                    |
|                         | GTEx                   | Human tissue expression and regulatory variation              |
|                         | gnomAD                 | Human population variation and constraint                     |

### Retrieval flow

```text
StructuredObjective
        ↓
Identify retrieval targets
        ↓
Resolve entities
        ↓
Query relevant sources
        ↓
Normalize responses
        ↓
Filter relevant evidence
        ↓
EvidenceRecords
```

External data should use cache-aside retrieval:

```text
Request
   ↓
Cache
 ┌─┴─┐
hit miss
 │   │
 │   └→ Source → Normalize → Cache
 └───────────────→ Return
```

SQLite is suitable for the initial local cache; persistent Core deployments retain this cache across runs.

---

## 2.3 Planner

The Planner is the actual computational planning engine of Relict Core.

### Input

```text
StructuredObjective
EvidenceRecords
constraints
max_edits
strategy
```

### Output

```text
Ranked CandidateStrategies
```

The Planner constructs the relevant **evidence-only graph** internally and searches that graph for candidate strategies.

NetworkX provides the graph representation and computation.

### Graph structure

Nodes represent biological entities:

```text
Gene
Protein
Pathway
Phenotype
Species
etc.
```

Edges represent source-backed relationships:

```json
{
  "source": "GENE_A",
  "target": "GENE_B",
  "relationship": "functional_association",
  "source_db": "STRING",
  "source_score": 0.91
}
```

The Planner does not invent an unsupported relationship. Missing evidence does not create an edge.

### Planner duties

The Planner:

- constructs the relevant graph;
- preserves evidence provenance;
- extracts relevant subgraphs;
- identifies candidate genes/pathways;
- generates candidate combinations;
- enforces constraints and edit budgets;
- evaluates target coverage;
- evaluates evidence and conflicts;
- optimizes according to strategy;
- ranks candidate strategies.

NetworkX performs graph operations; it does not understand biology or determine the objective.

### Strategy modes

Strategy is a Planner parameter, not a post-processing step.

#### Minimal

```text
maximize target coverage
maximize evidence strength
minimize conflicts
minimize edits
```

#### Redundant

```text
maximize target coverage
maximize independent routes
maximize evidence strength
minimize conflicts
respect edit budget
```

Redundancy must represent meaningful independent biological routes, such as distinct graph paths, functional relationships, or independently supported mechanisms. Simply selecting more genes is not sufficient.

### Initial search

A deterministic greedy/beam search is sufficient for the first implementation:

```text
Candidate genes
      ↓
Generate combinations
      ↓
Score partial strategies
      ↓
Reject invalid/conflicting states
      ↓
Expand strongest candidates
      ↓
Check target coverage
      ↓
Rank strategies
```

The Planner is deterministic and is not a trained model.

---

## 2.4 Plan Validator

The Plan Validator deterministically checks the Planner's output.

### Checks

```text
Edit budget
Target coverage
Project constraints
Species consistency
Graph integrity
Evidence provenance
Strategy requirements
```

For Minimal, minimality is evaluated relative to the search space and optimization procedure actually executed. Global optimality must not be claimed unless the method formally establishes it.

For Redundant, the Validator checks that additional candidates provide meaningful independent coverage according to the Planner's redundancy criteria.

When no evidence-backed relationship exists between candidates, the Planner represents the relationship as **unknown**, not as a positive or negative biological relationship. Unknown relationships may be retained for analysis but must not be treated as evidence of compatibility or conflict without supporting data.

The Validator verifies computational and evidence consistency. It does not prove experimental efficacy.

---

## 2.5 Post-Plan Analysis

Post-Plan Analysis operates only after a strategy has passed validation.

```text
Post-Plan Analysis
├── Guide & Risk Analysis
├── Population Propagation
└── Explanation Generation
```

### Guide & Risk Analysis

Analyzes selected candidate loci.

Potential tools:

```text
CRISPOR
CHOPCHOP
Evo 2
```

CRISPOR/CHOPCHOP can provide guide candidates, guide scoring, and off-target analysis. Evo 2 can provide relevant sequence/regulatory risk analysis.

The boundary is:

```text
Planner:
"What targets should be considered?"

Guide/Risk:
"What are the downstream editing considerations for those targets?"
```

### Population Propagation

Used where population-level behavior is relevant.

Possible inputs:

```text
initial frequency
population size
inheritance model
fitness effect
generation time
migration
selection pressure
geographic structure
```

Possible outputs:

```text
allele frequency over generations
population penetration
persistence
time to threshold
sensitivity to fitness costs
```

The simulation must expose its assumptions and must not be presented as a complete ecological forecast.

### Explanation Generation

Explanations are attached directly to graph nodes, graph edges, candidates, and the final strategy.

They are not a chat transcript.

Most explanations are deterministic templates:

```text
Gene A

Role:
Pigmentation-associated gene.

Why it matters:
Selected because it provides evidence-supported
coverage of the target pigmentation pathway.

Evidence:
STRING · Reactome
```

For an edge:

```text
Gene A — Gene B

Functional association.
Source: STRING.
Evidence score: 0.91.
```

Only open-ended whole-strategy synthesis requires the Core Model; routine node/edge explanations remain template-driven.

The preferred synthesis model is the self-hosted Core Model. Gemini Flash may be an optional fallback. Ollama is a model-serving/runtime option, not a model.

---

## 2.6 Run Manager

The Run Manager is the persistent orchestration layer around the pipeline.

It is not a biological reasoning stage. A Core installation is intended to remain running continuously and accept multiple runs over its lifetime.

### Duties

```text
Start run
    ↓
Queue / schedule run
    ↓
Invoke stages in order
    ↓
Track state
    ↓
Handle failures / recovery
    ↓
Emit progress
    ↓
Persist artifacts
    ↓
Wait for next run
```

Typical state:

```text
PENDING
   ↓
QUEUED
   ↓
RUNNING
   ↓
COMPLETE
```

Run status and post-plan analysis status are independent:

```text
run.status:
    pending | queued | running | complete | failed

post_plan_analysis_status:
    pending | running | complete | partial | failed
```

A valid Planner + Validator result may therefore have `run.status = complete` while post-plan analysis is `partial` or `failed`.

The Runtime should keep the API, workers, model connection, retrieval/cache layer, and persistent run state available continuously. The Run Manager coordinates the sequential pipeline rather than branching independently into multiple components.

---

## 2.7 Core API

The Core API is the interface between Core and Relict Shell.

Shell should not directly access Core's biological sources, caches, or internal graph structures.

Example:

```text
POST /v1/runs
GET  /v1/runs/{run_id}
GET  /v1/runs/{run_id}/stream
GET  /v1/health
GET  /v1/system
```

### Example request

The API may accept project and run configuration in one request, but Core separates them before execution. These are authoritative configuration fields; they are not fields resolved by the Core Model.

```json
{
  "project": {
    "species": "Canis lupus",
    "scope": "de-extinction"
  },
  "run": {
    "objective": "Make this wolf's coat white while preserving fertility.",
    "candidate_genes": [],
    "constraints": ["preserve fertility"],
    "max_edits": 3,
    "strategy": "minimal"
  }
}
```

Internally:

```text
POST /v1/runs
        │
        ├── ProjectContext
        │     ├── species
        │     └── scope
        │
        └── RunConfiguration
              ├── objective
              ├── candidate_genes
              ├── constraints
              ├── max_edits
              └── strategy
                        │
                        ▼
                   Core Model
                        │
                        ▼
               StructuredObjective
```

The Core Model interprets only the natural-language `objective` within the supplied project/run context. It does not choose or modify species, scope, candidate genes, constraints, edit budget, or strategy.

### Result

The API exposes:

```text
run status
structured objective
selected candidates
strategy
relevant evidence
validation result
post-plan analysis
relevant graph
provenance
explanations
```

The complete internal evidence cache and retrieval graph remain private to Core.

Core is designed to be self-hosted indefinitely. The model is accessed through a provider-agnostic model client, allowing local serving through vLLM, Ollama, or llama.cpp without making any one serving framework part of the biological pipeline. A deployed Core instance exposes the API continuously for connected Shell clients.

Recommended stack:

```text
FastAPI
Pydantic
OpenAPI
Server-Sent Events
```

---

# 3. Data & Evidence Model

## 3.1 ProjectContext

```text
project_id
species
scope
objective
```

`ProjectContext` contains the authoritative project-level inputs supplied by Shell.

`species` identifies the biological system being analyzed.

`scope` identifies the selected Relict scope and determines which scope-specific retrieval sources are available.

`objective` contains the researcher's natural-language biological objective. It is the input to Core Model Task 1.

These fields are not inferred or overwritten by the Core Model.

## 3.2 RunConfiguration

```text
candidate_genes
max_edits
constraints
strategy
```

`RunConfiguration` contains the authoritative run-level configuration supplied by Shell.

`candidate_genes` may constrain the Planner's candidate space.

`max_edits` defines the permitted edit budget.

`constraints` defines run-specific requirements that the Planner and Validator must respect.

`strategy` selects the planning objective:

```text
minimal
redundant
```

These fields are not model-generated.

## 3.3 StructuredObjective

```text
target_phenotypes
biological_processes
desired_change
relevant_concepts
retrieval_targets
ambiguity_status
```

`StructuredObjective` is produced by Core Model Task 1 from `ProjectContext.objective`, using the authoritative project and run context.

The model resolves the biological meaning of the objective but does not decide `species`, `scope`, `candidate_genes`, `max_edits`, `constraints`, or `strategy`.

If the objective cannot be resolved without guessing:

```text
ambiguity_status = CLARIFICATION_REQUIRED
```

## 3.4 RetrievalContext

```text
project_context
run_configuration
structured_objective
```

`RetrievalContext` is the input contract to Knowledge Retrieval.

Knowledge Retrieval uses:

```text
ProjectContext.species
ProjectContext.scope
ProjectContext.objective
RunConfiguration
StructuredObjective
```

to determine the biological system, permitted source set, and evidence required for the objective.

Knowledge Retrieval does not modify these inputs.

The resulting source-backed evidence is returned as `EvidenceRecord[]`.

## 3.5 EvidenceRecord

```text
source
source_id
entity_a
entity_b
relationship
source_score
provenance
metadata
```

`EvidenceRecord` is the normalized representation of evidence returned by Knowledge Retrieval.

`source_score` is the score supplied by the originating source where available. It is not automatically a calibrated probability.

If Core derives a normalized planning weight, it is kept separate:

```text
source_score
planner_weight
```

`planner_weight` is an internal Planner value and is not biological evidence.

## 3.6 Evidence Graph

```text
GraphNode[]
GraphEdge[]
```

Nodes represent biological entities.

Edges represent source-backed relationships.

Edge metadata:

```text
relationship
source
source_score
provenance
```

The Evidence Graph is constructed internally by `planner/graph_builder.py` from `EvidenceRecord[]`.

Knowledge Retrieval returns evidence records; it does not construct the Planner graph.

The graph is an internal Planner structure. Only the relevant subgraph is exposed to Shell.

## 3.7 Strategy

A `Strategy` represents one candidate strategy produced by the Planner.

```text
strategy_type
selected_candidates
covered_targets
edit_count
score
supporting_edges
conflicting_edges
rationale
```

A run may contain multiple candidate strategies:

```text
Strategy[]
```

The Planner ranks feasible strategies. A selected strategy may be identified separately in the final result.

## 3.8 ValidationResult

```text
valid
checks
violations
warnings
```

`ValidationResult` records the deterministic checks performed by the Plan Validator and their outcomes.

A strategy that fails validation does not proceed to Post-Plan Analysis.

## 3.9 PostPlanResult

```text
status
guide_risk
population_analysis
node_explanations
edge_explanations
strategy_explanation
```

`status` is independent of the primary run status:

```text
complete
partial
failed
```

Post-Plan Analysis runs only after a strategy has passed validation.

`node_explanations`, `edge_explanations`, and `strategy_explanation` are produced by Explanation Generation. Whole-strategy synthesis uses Core Model Task 2 and is grounded in the validated strategy, retrieved evidence, and Planner rationale.

If an optional downstream tool is unavailable or fails, the available Post-Plan results are retained and:

```text
status = partial
```

with `PARTIAL_ANALYSIS` recorded as the failure code.

## 3.10 RunState

```text
run_id
status
current_stage
progress
post_plan_analysis_status
timestamps
errors
```

`status` reflects the primary Core run:

```text
pending
queued
running
complete
failed
```

`post_plan_analysis_status` independently reports the downstream analysis state:

```text
pending
running
complete
partial
failed
```

A valid Planner + Validator run can therefore have:

```text
status = complete
post_plan_analysis_status = partial
```

## 3.11 RunResult

`RunResult` is the final aggregate returned by Core API to Shell.

```text
run_id
status
project_context
run_configuration
structured_objective
strategies
selected_strategy
validation
post_plan
failure
warnings
```

`strategies` contains the ranked candidate strategies produced by the Planner.

`selected_strategy` identifies the strategy selected for downstream analysis, where applicable.

`validation` and `post_plan` are present only when their respective stages have executed.

For short-circuited failure paths, unavailable downstream artifacts are omitted rather than fabricated.

`RunResult` therefore supports both successful and failed runs.

## 3.12 FailureCode

```text
CLARIFICATION_REQUIRED
INSUFFICIENT_EVIDENCE
NO_FEASIBLE_PLAN
VALIDATION_FAILED
PARTIAL_ANALYSIS
```

`FailureCode` is a shared enum used to represent defined pipeline failure conditions.

`PARTIAL_ANALYSIS` does not invalidate an otherwise successful Planner + Validator result. It indicates that one or more optional Post-Plan outputs were unavailable.

# 4. End-to-End Pipeline

The complete execution flow is:

```text
ProjectContext.objective
        │
        ▼
Core Model — Task 1
Objective Resolution
        │
        ├── ambiguous objective
        │       └── CLARIFICATION_REQUIRED ──────→ RunResult
        │
        ▼
StructuredObjective
        │
        ├──────────────────────┐
        │                      │
ProjectContext          RunConfiguration
        │                      │
        └───────────┬──────────┘
                    ▼
           RetrievalContext
                    │
                    ▼
        Knowledge Retrieval
                    │
                    ├── insufficient evidence
                    │       └── INSUFFICIENT_EVIDENCE ─→ RunResult
                    │
                    ▼
             EvidenceRecord[]
                    │
                    ▼
                 Planner
                    │
                    ├── no feasible strategy
                    │       └── NO_FEASIBLE_PLAN ─────→ RunResult
                    │
                    ▼
             Evidence Graph
             ├── GraphNode[]
             └── GraphEdge[]
                    │
                    ▼
                Strategy[]
                    │
                    ▼
            Plan Validator
                    │
                    ├── strategy violates requirements
                    │       └── VALIDATION_FAILED ─────→ RunResult
                    │
                    ▼
           ValidationResult
                (passed)
                    │
                    ▼
          Post-Plan Analysis
                    │
          ┌─────────┼──────────┐
          │         │          │
          ▼         ▼          ▼
      Guide &    Population  Explanation
       Risk      Propagation  Generation
                              │
                              ▼
                       Core Model — Task 2
                       Whole-Strategy Synthesis
          │         │          │
          └─────────┴──────────┘
                    │
                    ▼
             PostPlanResult
          ├── complete
          ├── partial
          └── failed
                    │
                    ├── optional tool unavailable
                    │       └── PARTIAL_ANALYSIS
                    │
                    ▼
                RunResult
                    │
                    ▼
                 Core API
                    │
                    ▼
                Relict Shell
```

The Run Manager orchestrates the complete pipeline:

```text
Run Manager
    ├── starts run
    ├── invokes each stage
    ├── tracks state
    ├── handles failures
    ├── persists artifacts
    └── collects final RunResult
```

The stage contracts are:

```text
Core Model — Task 1
    ProjectContext + RunConfiguration
        ↓
    StructuredObjective

Knowledge Retrieval
    RetrievalContext
        ↓
    EvidenceRecord[]

Planner
    ProjectContext
    + RunConfiguration
    + StructuredObjective
    + EvidenceRecord[]
        ↓
    Evidence Graph
    + Strategy[]

Plan Validator
    Strategy
    + Evidence Graph
    + RunConfiguration
        ↓
    ValidationResult

Post-Plan Analysis
    Validated Strategy
    + relevant evidence
        ↓
    PostPlanResult

Core API
    RunResult
        ↓
    Shell
```

Failures short-circuit the pipeline at the stage where they occur. Post-Plan Analysis never runs for an unvalidated or validation-failed strategy.

# 5. Technology Stack

| Layer             | Technology                              |
| ----------------- | --------------------------------------- |
| Core              | Python                                  |
| Open-weight model | Qwen3-4B-Instruct                       |
| Fine-tuning       | PyTorch, Transformers, PEFT/LoRA, QLoRA |
| Model serving     | vLLM, Ollama, or llama.cpp              |
| API               | FastAPI                                 |
| Validation        | Pydantic                                |
| HTTP              | httpx                                   |
| Async execution   | asyncio                                 |
| Runtime / workers | Persistent worker processes / job queue |
| Graph             | NetworkX                                |
| Cache             | SQLite                                  |
| Interactions      | STRING                                  |
| Pathways          | KEGG, Reactome, WikiPathways            |
| Gene/protein      | Ensembl, UniProt, NCBI                  |
| Evolution         | Ensembl Compara, BLAST, TimeTree        |
| Guide analysis    | CRISPOR, CHOPCHOP                       |
| Sequence/risk     | Evo 2                                   |
| Streaming         | Server-Sent Events                      |
| API contract      | OpenAPI                                 |

---

# 6. Model Training

The Core Model is adapted through supervised fine-tuning with LoRA.

## Task 1 — Objective interpretation

```text
Natural-language objective
        ↓
StructuredObjective
```

Dataset coverage should include:

```text
normal objectives
multiple phrasings
species-specific objectives
multiple constraints
different scopes
ambiguous objectives
clarification-required cases
```

## Task 2 — Evidence-grounded strategy synthesis

```text
Validated strategy
+
retrieved evidence
+
planner rationale
        ↓
Plain-English strategy explanation
```

The model generates language from supplied evidence; it is not trained to supply gene function, protein products, or other biological facts from its own memory. Graph-node and graph-edge explanations remain primarily deterministic templates. This dataset can be smaller than the objective-interpretation dataset.

## Training flow

```text
Open-weight base
      ↓
Relict SFT dataset
      ↓
LoRA adapter
      ↓
Relict Core Model
```

The model should be trained only after the StructuredObjective and Planner contracts are stable.

---

# 7. Failure States

Failures must never be silently converted into model-generated biological claims.

| Stage               | Condition                      | Result                   |
| ------------------- | ------------------------------ | ------------------------ |
| Core Model          | Ambiguous objective            | `CLARIFICATION_REQUIRED` |
| Knowledge Retrieval | Insufficient evidence          | `INSUFFICIENT_EVIDENCE`  |
| Planner             | No feasible strategy           | `NO_FEASIBLE_PLAN`       |
| Validator           | Strategy violates requirements | `VALIDATION_FAILED`      |
| Post-Plan Analysis  | Optional tool unavailable      | `PARTIAL_ANALYSIS`       |

`run.status` is independent of post-plan analysis. A valid Planner + Validator result can remain `complete` while `post_plan_analysis_status` is `partial` or `failed`. Partial results must identify which outputs are unavailable and why.

---

# 8. Implementation Principles

### Evidence is authoritative for the graph

Model-generated retrieval targets are not evidence. Only normalized source-backed records enter the planning graph. Unknown relationships remain unknown.

### Structured inputs are authoritative

Shell-supplied structured fields, such as species/taxonomy and configured constraints, take precedence over conflicting inference from free text.

### Planning is deterministic

The Planner is not trained. It searches the evidence graph according to explicit objectives, constraints, edit budgets, and strategy modes.

### Provenance is mandatory

Every important relationship retains its source and source-native score where available.

### Strategy modes belong inside the Planner

Minimal and Redundant are optimization objectives, not post-processing filters.

### Validation is separate

The Planner computes a strategy; the Validator independently checks it.

### Post-Plan Analysis cannot rewrite the primary strategy

Guide/Risk, Population Propagation, and Explanation Generation operate on the validated strategy.

### Machine learning is limited

Relict Core uses one open-weight model for two narrow tasks: objective interpretation and evidence-grounded whole-strategy synthesis. The graph, Planner, Validator, and simulations remain deterministic or computational wherever possible. The model is self-hosted and is not required to call an external LLM API.

### No unsupported certainty

Relict Core can establish that a strategy is computationally feasible and evidence-supported. It cannot establish that an intervention will definitely produce the desired real-world biological outcome.

Unknown evidence is not treated as proof of safety, compatibility, conflict, or efficacy.

---

# 9. Canonical Architecture

```text
                         RELICT CORE

                    ┌─────────────────┐
                    │   Run Manager   │
                    │ Persistent      │
                    │ Orchestrator    │
                    └───────┬─────────┘
                            │
                  continuously orchestrates
                            │
                            ▼
                    ┌────────────┐
                    │ Core Model │
                    └─────┬──────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │ Knowledge        │
                 │ Retrieval        │
                 └────────┬─────────┘
                          │
                          ▼
                    ┌───────────┐
                    │  Planner  │
                    └─────┬─────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Plan Validator  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Post-Plan       │
                 │ Analysis        │
                 │                 │
                 │ Guide/Risk      │
                 │ Population      │
                 │ Explanation     │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   Final Result  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │    Core API     │
                 └────────┬────────┘
                          │
                          ▼
                    Relict Shell
```

> **The Core Model interprets. Knowledge Retrieval supplies evidence. The Planner computes. The Validator verifies. Post-Plan Analysis evaluates and explains. The Run Manager orchestrates execution. The Core API exposes the system.**

---

# 10. Folder Structure

```
 relict-core/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── models/
│   │   ├── requests.py
│   │   ├── responses.py
│   │   ├── evidence.py
│   │   ├── graph.py
│   │   ├── validation.py
│   │   ├── post_plan.py
│   │   ├── run_state.py
│   │   └── failures.py
│   │
│   ├── routes/
│   │   ├── auth.py
│   │   ├── search.py
│   │   ├── runs.py
│   │   ├── stream.py
│   │   ├── health.py
│   │   └── system.py
│   │
│   ├── run_manager/
│   │   ├── orchestrator.py
│   │   ├── state.py
│   │   ├── progress.py
│   │   └── repository.py
│   │
│   ├── core_model/
│   │   ├── weights/
│   │   │   └── relict-qwen3-4b/
│   │   ├── inference/
│   │   │   ├── base.py
│   │   │   ├── vllm.py
│   │   │   ├── ollama.py
│   │   │   └── llama_cpp.py
│   │   ├── prompts/
│   │   │   ├── objective_resolution.txt
│   │   │   └── strategy_synthesis.txt
│   │   ├── training/
│   │   │   ├── datasets/
│   │   │   │   ├── generate_task1.py
│   │   │   │   ├── generate_task2.py
│   │   │   │   ├── augment_paraphrase.py
│   │   │   │   ├── generate_negatives.py
│   │   │   │   └── eval_set.jsonl
│   │   │   ├── train_qlora.py
│   │   │   ├── merge_adapter.py
│   │   │   └── evaluate.py
│   │   ├── model_client.py
│   │   ├── objective_parser.py
│   │   ├── explanation_generator.py
│   │   └── fallback.py
│   │
│   ├── knowledge_retrieval/
│   │   ├── retrieval.py
│   │   ├── normalize.py
│   │   ├── registry.py
│   │   │
│   │   ├── common/
│   │   │   ├── ensembl.py
│   │   │   ├── ncbi/
│   │   │   │   ├── eutils.py
│   │   │   │   ├── datasets_v2.py
│   │   │   │   ├── blast.py
│   │   │   │   └── pmc.py
│   │   │   ├── string_db.py
│   │   │   ├── kegg.py
│   │   │   ├── uniprot.py
│   │   │   ├── reactome.py
│   │   │   ├── wikipathways.py
│   │   │   ├── rcsb_pdb.py
│   │   │   ├── gbif.py
│   │   │   └── timetree.py
│   │   │
│   │   ├── conservation/
│   │   │   ├── dna_zoo.py
│   │   │   ├── vgp.py
│   │   │   └── genome10k.py
│   │   │
│   │   ├── de_extinction/
│   │   │   ├── dna_zoo.py
│   │   │   ├── vgp.py
│   │   │   └── genome10k.py
│   │   │
│   │   ├── agriculture/
│   │   │   ├── gramene.py
│   │   │   ├── plant_reactome.py
│   │   │   ├── animal_qtldb.py
│   │   │   ├── faang.py
│   │   │   ├── farmgtex.py
│   │   │   └── epidb.py
│   │   │
│   │   ├── synthetic_biology/
│   │   │   ├── brenda.py
│   │   │   ├── sabio_rk.py
│   │   │   └── synbiohub.py
│   │   │
│   │   ├── population_control/
│   │   │   └── vectorbase.py
│   │   │
│   │   └── precision_medicine/
│   │       ├── alphamissense.py
│   │       ├── opentargets.py
│   │       ├── chembl.py
│   │       ├── hpa.py
│   │       ├── gtex.py
│   │       └── gnomad.py
│   │
│   ├── planner/
│   │   ├── graph_builder.py
│   │   ├── search.py
│   │   └── constraints.py
│   │
│   ├── validator/
│   │   └── plan_validator.py
│   │
│   ├── post_plan/
│   │   ├── guide_risk/
│   │   │   ├── crispor.py
│   │   │   ├── chopchop.py
│   │   │   └── evo2.py
│   │   ├── population/
│   │   │   └── propagation.py
│   │   └── explanations/
│   │       ├── node.py
│   │       ├── edge.py
│   │       └── strategy.py
│   │
│   └── cache/
│       ├── sqlite_client.py
│       ├── duckdb_client.py
│       └── bootstrap.py
│
├── tools/
│   ├── crispor/
│   └── chopchop/
│
├── scripts/
│   ├── setup_model.py
│   ├── download_model.py
│   └── prefetch_demo_species.py
│
├── data/
├── tests/
├── docs/
│   ├── architecture.md
│   ├── oracle-api-reference.md
│   └── self-hosting.md
├── docker/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── test.yml
│       └── publish-model.yml
│
├── model_manifest.json
├── .gitignore
├── .gitattributes
├── pyproject.toml
├── API.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── LICENSE
└── README.md
```
