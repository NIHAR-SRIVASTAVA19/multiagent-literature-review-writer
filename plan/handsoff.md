# Multi-Agent Research System — Project Handoff Context

## 1. Project

Project title:

**A Multi-Agent Pipeline for Automated Literature Review with Vision-Grounded Paper Analysis and Citation Verification**

This is a final-year project focused on **Agentic AI / Multi-Agent Systems**.

The system should:

1. Interview the user about their literature-review requirements.
2. Convert those requirements into a structured research specification.
3. Generate search queries.
4. Search real academic databases and the web.
5. Retrieve candidate research papers.
6. Deduplicate, rank, and select relevant papers.
7. Download selected PDFs.
8. Render complete PDF pages.
9. Analyze those pages using a Vision-Language Model.
10. Extract structured evidence.
11. Perform cross-paper synthesis and research-gap analysis.
12. Generate a literature review.
13. Validate both the content and citations.
14. Produce the final verified report.

The project uses Python 3.11+, Google ADK, LiteLLM, NVIDIA NIM, Pydantic v2, httpx, PyMuPDF, and eventually Streamlit.

---

# 2. IMPORTANT: FROZEN ARCHITECTURE

Do NOT redesign this architecture unless explicitly asked.

The final pipeline is:

User
  ↓
Root Agent (`literature_review_writer`)
  - user interview
  - research planning
  - query expansion
  - SearchQuery generation
  ↓
Search Coordinator
  - SEARCH EXECUTION ONLY
  - academic search
  - web search
  - candidate-paper retrieval
  ↓
Analysis Agent
  - deduplication
  - re-ranking
  - paper selection
  - PDF download
  - complete-page rendering
  - Vision-Language Model analysis
  - structured evidence generation
  ↓
Synthesizer
  - cross-paper evidence analysis
  - thematic synthesis
  - methodological comparison
  - contradiction/trend analysis
  - research-gap identification
  ↓
Writer
  - literature-review draft generation
  ↓
Validator
  ├── Content Reviewer
  └── Citation Reviewer
  ↓
Final Report

Agent hierarchy:

literature_review_writer / root_agent
├── search_coordinator
├── analysis_agent
├── synthesizer
├── writer
└── validator
    ├── content_reviewer
    └── citation_reviewer

There is NO separate Research Planner Agent.

---

# 3. CRITICAL RESPONSIBILITY BOUNDARIES

These boundaries are frozen.

## Root Agent

Responsible for:

- interviewing the user
- understanding review requirements
- creating ResearchSpecification
- research planning
- query expansion
- generating SearchQuery[]

The Root Agent owns query generation.

## Search Coordinator

Responsible ONLY for executing queries supplied by the Root Agent.

It performs:

SearchQuery[]
    ↓
retrieval execution
    ↓
academic APIs / web search
    ↓
candidate papers + web context

It MUST NOT:

- generate search queries
- expand queries
- modify the research strategy
- deduplicate papers
- rank papers
- select papers
- analyze PDFs
- synthesize evidence

## Analysis Agent

The Analysis Agent owns:

- candidate-paper deduplication
- re-ranking
- paper selection
- PDF downloading
- PDF preparation
- full-page rendering
- vision-grounded analysis
- evidence extraction

IMPORTANT:

Deduplication and ranking DO NOT belong to Search Coordinator.

## Synthesizer

Responsible for cross-paper reasoning:

- thematic synthesis
- methodology comparison
- contradiction detection
- trend analysis
- research-gap identification

## Writer

Responsible for producing the literature-review draft from the synthesis/evidence.

## Validator

Contains:

Validator
├── Content Reviewer
└── Citation Reviewer

Validation is sequential:

Writer Draft
    ↓
Content Reviewer
    ├── REVISE → Writer → Content Reviewer
    └── PASS
         ↓
Citation Reviewer
    ├── REVISE → Writer → Content Reviewer → Citation Reviewer
    └── PASS
         ↓
Final Report

Maximum revision rounds per gate will eventually be enforced deterministically.

Target maximum: 3 revision rounds per validation gate.

---

# 4. PDF / VISION ARCHITECTURE

Do NOT design a separate OCR-first paper-analysis pipeline.

The intended architecture is:

PDF
 ↓
PyMuPDF
 ↓
render COMPLETE PDF pages as images
 ↓
Vision-Language Model
 ↓
structured PageAnalysis / Evidence / PaperAnalysis

The VLM should receive complete rendered pages so that it can reason over:

- normal text
- figures
- tables
- equations
- page layout
- captions
- relationships between visual and textual elements

OCR/text/table/image extraction is NOT the primary analysis path.

## 4.1 How the vision call actually happens (clarified during implementation)

OpenAI-compatible chat APIs (NVIDIA NIM / LiteLLM, which this project
uses throughout) only allow image content inside `user`-role message
content, never inside a tool/function *result*. This means a tool
cannot hand rendered page image bytes back into an ADK agent's own
conversational turn for the agent to "look at" mid-reasoning - that
channel is text/JSON only.

Practical consequence: the vision inference itself happens *inside*
the tool function (`analyze_pages_with_vlm()` in `tools.py`), via a
direct `litellm.acompletion()` call using the same model already
assigned to the Analysis Agent (`ANALYSIS_MODEL_NAME`, currently
`moonshotai/kimi-k3` - confirmed natively multimodal). The tool reads
already-rendered page PNGs, base64-encodes them, sends them as
separate full-resolution `image_url` content parts in one model call,
and returns structured `PageAnalysis` objects as its tool result.

The Analysis Agent still owns and directs the process end to end - it
decides which paper and which rendered pages to send, and interprets
the structured results the tool returns - it just does not literally
receive raw image bytes inside its own turn. This is an implementation
detail forced by the chat-completions protocol, not a change to the
Analysis Agent's ownership of vision-grounded analysis.

Pages are batched `VLM_PAGES_PER_CALL` at a time (default 4, in
`config.py`) as separate images in one call - not composited into a
single image - to reduce the number of VLM requests without shrinking
any individual page's resolution (a composited grid was considered and
rejected: most VLMs tile images and charge per tile, so a composite
costs about the same tokens as separate images while hurting
legibility of small text/tables/equations).

---

# 5. CURRENT PROJECT STRUCTURE

multiagent-research-system/
│
├── data/
│
├── literature_review_writer/
│   ├── __init__.py
│   ├── agent.py
│   │
│   └── subagents/
│       │
│       ├── analysis_agent/
│       │   ├── __init__.py
│       │   └── agent.py
│       │
│       ├── search_coordinator/
│       │   ├── __init__.py
│       │   └── agent.py
│       │
│       ├── synthesizer/
│       │   ├── __init__.py
│       │   └── agent.py
│       │
│       ├── writer/
│       │   ├── __init__.py
│       │   └── agent.py
│       │
│       └── validator/
│           ├── __init__.py
│           ├── agent.py
│           │
│           └── subagents/
│               │
│               ├── citation_reviewer/
│               │   ├── __init__.py
│               │   └── agent.py
│               │
│               └── content_reviewer/
│                   ├── __init__.py
│                   └── agent.py
│
├── .env
├── .gitignore
├── config.py
├── main.py
├── prompts.py
├── schemas.py
├── tools.py
├── utils.py
├── test_tools.py
├── test_search_coordinator.py
└── requirements.txt

The project intentionally uses centralized root-level:

- config.py
- schemas.py
- prompts.py
- tools.py
- utils.py

Do not split these into per-agent files unless explicitly requested.

---

# 6. DEVELOPMENT PHASES

The project is being implemented incrementally.

## Phase 0 — Architecture Freeze

STATUS: COMPLETE

Completed:

- agent architecture
- agent responsibilities
- tool vs agent classification
- folder structure
- schemas/state contracts
- validation flow

## Phase 1 — ADK Skeleton

STATUS: COMPLETE

Completed:

- Google ADK environment
- Root Agent
- all agent skeletons
- sub-agent hierarchy
- Runner
- persistent session service
- NVIDIA NIM through LiteLLM
- successful basic invocation

## Phase 2 — Retrieval

STATUS: MOSTLY COMPLETE / CURRENT PHASE

Completed:

- arXiv retrieval
- Semantic Scholar retrieval implementation
- OpenAlex retrieval
- Crossref retrieval
- Tavily retrieval
- metadata normalization
- deterministic source routing
- multi-source aggregation
- Search Coordinator tool integration
- standalone Search Coordinator ADK test

The standalone Search Coordinator test is currently running successfully.

NEXT work should continue from the end of Phase 2 rather than rebuilding retrieval.

---

# 7. MODEL PROVIDER

We are NOT using Gemini as the primary model provider.

We use NVIDIA NIM hosted models through LiteLLM.

Base URL:

https://integrate.api.nvidia.com/v1

Google ADK integration uses:

from google.adk.models.lite_llm import LiteLlm

Model allocation currently planned:

Root Agent
→ nvidia/nemotron-3.5-lightning-30b-a3b

Search Coordinator
→ nvidia/nemotron-3.5-lightning-30b-a3b

Analysis Agent
→ moonshotai/kimi-k3

Synthesizer
→ nvidia/nemotron-3-ultra-550b-a55b

Writer
→ deepseek-ai/deepseek-v4-pro-0813

Validator
→ nvidia/nemotron-3.5-lightning-30b-a3b

Content Reviewer
→ nvidia/nemotron-3-ultra-550b-a55b

Citation Reviewer
→ nvidia/nemotron-3.5-lightning-30b-a3b

Model configuration is centralized in config.py.

Do not call load_dotenv() separately inside every agent.

---

# 8. SESSION PERSISTENCE

Google ADK uses DatabaseSessionService.

Current local development database:

sqlite+aiosqlite:///./data/adk_sessions.db

Pattern:

from google.adk.sessions import DatabaseSessionService

session_service = DatabaseSessionService(
    db_url=DATABASE_URL
)

Future production could use PostgreSQL.

Persistent ADK sessions have already been tested successfully.

---

# 9. SCHEMAS

schemas.py uses Pydantic v2.

Important enums:

AcademicSource:
- arxiv
- semantic_scholar
- openalex
- crossref
- tavily

RetrievalStatus:
- pending
- downloaded
- failed

ReviewStatus:
- PASS
- REVISE

Severity:
- low
- medium
- high
- critical

ConfidenceLevel:
- low
- medium
- high

EvidenceType:
- methodology
- result
- finding
- limitation
- dataset
- comparison
- figure
- table
- equation
- other

Important models include:

ResearchSpecification
SearchQuery
WebSource
PaperMetadata
RetrievedPaper
PageAnalysis
Evidence
PaperAnalysis
RankedPaper
ResearchGap
Claim
Synthesis
Citation
ReviewSection
LiteratureReviewDraft
ReviewIssue
ContentReviewResult
CitationVerification
CitationReviewResult
FinalReport
ResearchState

Ownership:

Root
→ ResearchSpecification
→ SearchQuery[]

Search Coordinator
→ WebSource[]
→ candidate PaperMetadata / RetrievedPaper[]

Analysis
→ RankedPaper[]
→ selected_paper_ids
→ PaperAnalysis[]
→ Evidence[]

Synthesizer
→ Synthesis

Writer
→ LiteratureReviewDraft

Content Reviewer
→ ContentReviewResult

Citation Reviewer
→ CitationReviewResult

Final pipeline
→ FinalReport

ResearchState contains roughly:

research_id
specification
search_queries
web_sources
retrieved_papers
ranked_papers
selected_paper_ids
paper_analyses
synthesis
draft
content_review
citation_review
final_report
content_revision_round
citation_revision_round
current_stage

SearchQuery is GENERATED by Root and EXECUTED by Search Coordinator.

---

# 10. RETRIEVAL IMPLEMENTATION

tools.py contains the external retrieval capabilities.

## arXiv

Function:

search_arxiv(query, max_results)

Endpoint:

https://export.arxiv.org/api/query

Uses:

- httpx
- XML parsing
- arXiv Atom API

Extracts/normalizes:

- title
- abstract
- authors
- publication date/year
- DOI
- journal reference
- categories
- arXiv ID
- landing URL
- PDF URL

Tested successfully.

---

## Semantic Scholar

Function:

search_semantic_scholar(...)

Endpoint:

Semantic Scholar Academic Graph API.

Implementation exists and includes graceful HTTP 429 handling.

CURRENT ISSUE:

Unauthenticated Semantic Scholar requests are being rate-limited.

Observed:

Success: False
Count: 0
Error: Semantic Scholar rate limit exceeded.

Do NOT remove Semantic Scholar.

The architecture intentionally tolerates one provider failing while the remaining providers continue.

An API key may be added later.

Do not add aggressive retry behavior without discussion.

---

## OpenAlex

Function:

search_openalex(query, max_results)

Endpoint:

https://api.openalex.org/works

Optional:

OPENALEX_MAILTO

Implementation includes reconstruction of OpenAlex's inverted-index abstracts.

Helper:

reconstruct_openalex_abstract(...)

Extracts:

- OpenAlex ID
- title
- authors
- DOI
- arXiv ID where available
- publication information
- venue
- landing URL
- OA PDF when available
- concepts/keywords
- abstract
- citation count

Tested successfully.

PDF URL being None is valid and expected for many records.

---

## Crossref

Function:

search_crossref(...)

Endpoint:

https://api.crossref.org/works

Optional:

CROSSREF_MAILTO

Helper exists for parsing Crossref dates:

parse_crossref_date(...)

Normalizes:

- DOI
- title
- authors
- publication date/year
- venue
- abstract
- subjects
- URL
- possible PDF link
- citation count

Tested successfully.

Crossref is primarily bibliographic/DOI metadata, so missing PDF URLs are expected.

---

## Tavily

Function:

search_tavily(...)

Endpoint:

https://api.tavily.com/search

Requires:

TAVILY_API_KEY

Uses basic search currently.

IMPORTANT distinction:

Academic APIs
→ PaperMetadata
→ candidate papers

Tavily
→ WebSource
→ supporting web context

Do NOT convert arbitrary Tavily web pages into academic PaperMetadata.

Tested successfully.

---

# 11. STANDARD RETRIEVAL RESULT FORMAT

Academic retrieval tools return approximately:

{
    "success": true,
    "source": "...",
    "query": "...",
    "count": N,
    "papers": [...],
    "error": null
}

Tavily returns approximately:

{
    "success": true,
    "source": "tavily",
    "query": "...",
    "count": N,
    "web_sources": [...],
    "error": null
}

Failures should be returned as structured data rather than fabricated replacement results.

---

# 12. DETERMINISTIC RETRIEVAL ROUTING

utils.py contains:

execute_search_query(...)
execute_search_queries(...)

Architecture:

SearchQuery
    ↓
execute_search_query()
    ↓
inspect AcademicSource
    ↓
appropriate retrieval function

Mappings:

ARXIV
→ search_arxiv()

SEMANTIC_SCHOLAR
→ search_semantic_scholar()

OPENALEX
→ search_openalex()

CROSSREF
→ search_crossref()

TAVILY
→ search_tavily()

execute_search_queries() executes multiple SearchQuery objects and aggregates:

candidate_papers
web_sources
errors
executions
paper_count
web_source_count

Current implementation is sequential.

Do not prematurely optimize to asyncio.gather unless necessary.

IMPORTANT:

execute_search_queries() intentionally DOES NOT deduplicate results.

If the same paper appears in:

- arXiv
- OpenAlex
- Crossref

all records currently remain in the candidate corpus.

Deduplication happens later in Analysis Agent.

---

# 13. SEARCH COORDINATOR IMPLEMENTATION

The Search Coordinator now exposes a wrapper tool around deterministic retrieval.

Conceptually:

Search Coordinator LLM
        ↓
execute_research_searches()
        ↓
SearchQuery.model_validate()
        ↓
execute_search_queries()
        ↓
deterministic source routing
        ↓
retrieval APIs
        ↓
candidate_papers + web_sources + errors

The wrapper accepts JSON-compatible:

list[dict]

because LLM/ADK function calling naturally works with JSON.

It converts these into:

list[SearchQuery]

using:

SearchQuery.model_validate(...)

before invoking utils.py.

This boundary should be preserved.

Do NOT expose source selection to arbitrary LLM reasoning when it is already encoded in SearchQuery.source.

Example:

Root creates:

{
    "query_id": "q1",
    "query": "multi agent systems",
    "source": "arxiv",
    ...
}

Then deterministic routing must result in:

source="arxiv"
    ↓
search_arxiv()

The Search Coordinator should not decide to substitute Crossref/OpenAlex for that query.

---

# 14. SEARCH COORDINATOR PROMPT

A detailed SEARCH_COORDINATOR_PROMPT already exists in prompts.py.

KEEP IT.

Its central rule is:

"You are a SEARCH EXECUTION specialist."

It explicitly prohibits:

- research planning
- query generation
- query expansion
- deduplication
- re-ranking
- paper selection
- PDF analysis
- synthesis
- writing
- validation

It also requires:

- real search results only
- preserved source provenance
- graceful provider failure reporting
- Tavily web results remaining separate from academic papers

Do not replace this detailed prompt with a simplified prompt without a reason.

---

# 15. SEARCH COORDINATOR TEST

A standalone ADK test exists:

test_search_coordinator.py

It tests the Search Coordinator independently before integrating the entire pipeline.

Example queries include:

arXiv:
"multi agent systems"

OpenAlex:
"multi agent systems"

Crossref:
"multi agent systems"

Tavily:
"multi agent systems recent research trends"

with approximately 2 results per query.

The test currently runs successfully.

Expected approximate result:

Academic candidate papers:
6

Web sources:
2

Semantic Scholar is intentionally omitted from this test because it currently receives HTTP 429 without an API key.

This proves:

ADK
  ↓
Search Coordinator
  ↓
execute_research_searches()
  ↓
utils routing
  ↓
live retrieval APIs

is working.

---

# 16. PREVIOUS DIRECT RETRIEVAL TEST

Before ADK integration, deterministic routing was tested directly.

Observed:

Overall success: True
Candidate papers: 6
Web sources: 2

Executions:

q1 → arxiv → success → 2
q2 → openalex → success → 2
q3 → crossref → success → 2
q4 → tavily → success → 2

No errors.

This confirmed utils.py routing independently of the agent.

---

# 17. IMPORTANT ENGINEERING PRINCIPLES

Please preserve these during further development.

### Agents reason; tools execute.

Use agents for:

- planning
- interpretation
- analysis
- synthesis
- writing
- review

Use deterministic Python for:

- API calls
- routing
- validation
- PDF downloading
- page rendering
- IDs/hashes
- retry limits
- counters
- state transitions where appropriate

### Never fabricate retrieval data.

If an API fails:

return/report the failure.

Do NOT ask the LLM to invent replacement papers.

### Preserve provenance.

We need to know which database produced every result.

### Keep academic and web results separate.

candidate_papers != web_sources

### Do not deduplicate during retrieval.

Deduplication belongs to Analysis Agent.

### Do not let Search Coordinator generate queries.

Query generation belongs to Root Agent.

---

# 18. CURRENT DEVELOPMENT CHECKPOINT

We have reached:

Phase 2
    ↓
Retrieval providers implemented
    ↓
Normalization implemented
    ↓
Deterministic routing implemented
    ↓
Aggregation implemented
    ↓
Search Coordinator connected
    ↓
Standalone Search Coordinator ADK test PASSED
    ↓
CURRENT CHECKPOINT

Do NOT rebuild these components unless an actual bug is found.

---

# 19. WHAT TO DO NEXT

Continue incrementally from this checkpoint.

Before writing new code:

1. Inspect the existing repository.
2. Read schemas.py.
3. Read config.py.
4. Read tools.py.
5. Read utils.py.
6. Read prompts.py.
7. Read the existing agent files.
8. Read the existing tests.

Do not assume this handoff is more authoritative than the actual code for implementation details.

If the repository differs from this document, point out the difference before making architectural changes.

The next development work should finish the remaining Phase 2 integration/state flow and then move into Phase 3 / Analysis Agent work according to the architecture blueprint.

Do not jump directly into synthesis/writing/validation.

Work incrementally and test each layer before moving to the next.

---

# 20. DEVELOPMENT STYLE

The developer is still building familiarity with Python and Google ADK.

When implementing changes:

- explain what is being changed and why
- make small changes
- provide exact file paths
- avoid unnecessary abstractions
- test each component before continuing
- do not rewrite working code without a concrete reason
- do not silently change the frozen architecture
- point out architectural implications before making them


# 21. ATOMIC DEVELOPMENT METHODOLOGY — VERY IMPORTANT

This project MUST be implemented incrementally by breaking every phase, feature,
agent, tool, and workflow into the smallest practical testable units.

This is how the project has been developed so far and this methodology must continue.

Do NOT attempt to implement an entire phase or multiple agents in one large change.

The development philosophy is:

Architecture
    ↓
Phase
    ↓
Component
    ↓
Atomic Task
    ↓
Implement
    ↓
Test
    ↓
Verify
    ↓
Commit / Accept
    ↓
Next Atomic Task

Every significant component should be independently verified before it is connected
to the next component.

For example, Phase 2 Retrieval was NOT implemented as one large feature.

It was broken down approximately like this:

Phase 2 — Retrieval

    1. Implement arXiv search
       ↓
       Test arXiv independently
       ↓
       Confirm working

    2. Implement Semantic Scholar search
       ↓
       Test independently
       ↓
       Discover/handle HTTP 429 correctly

    3. Implement OpenAlex search
       ↓
       Test independently
       ↓
       Confirm metadata normalization

    4. Implement Crossref search
       ↓
       Test independently
       ↓
       Confirm working

    5. Implement Tavily search
       ↓
       Test independently
       ↓
       Confirm WebSource separation

    6. Implement deterministic single-query routing
       ↓
       Test routing

    7. Implement multi-query aggregation
       ↓
       Test aggregation

    8. Connect routing to Search Coordinator
       ↓
       Test Search Coordinator independently through ADK

Only after all of those atomic pieces worked did we consider the retrieval subsystem
integrated.

Continue using exactly this philosophy.

============================================================
RULE: ONE LOGICAL CHANGE AT A TIME
============================================================

When implementing something new:

1. Identify the smallest useful component.
2. Explain what that component does.
3. Explain why it belongs at that architectural location.
4. Implement only that component.
5. Create or update a focused test.
6. Run the test.
7. Inspect the actual output.
8. Fix problems before continuing.
9. Confirm the component works.
10. Only then move to the next component.

Do not make several unrelated architectural changes simultaneously.

============================================================
DO NOT BUILD AHEAD
============================================================

Do NOT implement future components simply because their implementation appears
obvious.

For example, when working on Analysis Agent:

Do NOT immediately implement:

deduplication
+ ranking
+ selection
+ PDF downloading
+ PDF rendering
+ VLM analysis
+ evidence extraction

in one step.

Instead, break it down.

A possible progression might be:

Candidate Corpus
    ↓
Deduplication
    ↓
TEST
    ↓
Re-ranking
    ↓
TEST
    ↓
Paper Selection
    ↓
TEST
    ↓
PDF Retrieval
    ↓
TEST
    ↓
PDF Validation
    ↓
TEST
    ↓
Page Rendering
    ↓
TEST
    ↓
VLM Input Preparation
    ↓
TEST
    ↓
Single-Page Vision Analysis
    ↓
TEST
    ↓
Multi-Page Paper Analysis
    ↓
TEST
    ↓
Evidence Structuring
    ↓
TEST
    ↓
Full Analysis Agent Integration
    ↓
TEST

The exact atomic breakdown should be determined when we reach that phase.

Do NOT assume this example is permission to implement all of those components now.

============================================================
TEST BOTTOM-UP
============================================================

Prefer testing in this order:

Level 1 — Pure helper function
Level 2 — Individual external tool/API
Level 3 — deterministic utility/orchestration function
Level 4 — individual Agent
Level 5 — Agent + tools
Level 6 — Agent-to-Agent integration
Level 7 — complete phase
Level 8 — end-to-end system

Example already followed:

search_arxiv()
    ↓
tested

search_openalex()
    ↓
tested

search_crossref()
    ↓
tested

search_tavily()
    ↓
tested

execute_search_query()
    ↓
tested

execute_search_queries()
    ↓
tested

Search Coordinator + execute_research_searches()
    ↓
tested through ADK

This bottom-up testing strategy should continue.

============================================================
FAILURE ISOLATION
============================================================

When a test fails, do NOT compensate by rewriting several surrounding components.

First determine which atomic layer failed.

For example:

Agent test fails
    ↓
Is the API tool working independently?
    ↓
Is deterministic routing working independently?
    ↓
Is schema validation working?
    ↓
Is ADK function calling the problem?
    ↓
Is the agent prompt the problem?

Fix the failing layer rather than redesigning the entire pipeline.

============================================================
NO PREMATURE ABSTRACTION
============================================================

Do not introduce complex abstractions, frameworks, base classes, factories,
registries, or generalized orchestration systems unless the existing implementation
actually requires them.

Prefer simple, readable Python.

The project should remain understandable to a developer who is still learning
Python and Google ADK.

A little duplication is acceptable when it makes the architecture easier to
understand.

Refactor only after a repeated pattern genuinely justifies it.

============================================================
NO PREMATURE OPTIMIZATION
============================================================

Correctness and architectural clarity come before performance optimization.

For example, execute_search_queries() currently performs retrieval sequentially.

Do not automatically convert it to asyncio.gather(), concurrency pools, queues,
or another concurrency architecture just because it could be faster.

First make the complete behavior correct and testable.

Optimization can happen later when there is evidence that it is needed.

============================================================
PRESERVE WORKING COMPONENTS
============================================================

A component that has already passed its isolated tests should generally be treated
as stable.

Do not rewrite working code merely to make it stylistically different.

If an existing component must be changed because of a new requirement:

1. explain why,
2. identify what existing behavior could be affected,
3. make the smallest possible modification,
4. rerun the existing tests.

============================================================
BEFORE EVERY IMPLEMENTATION STEP
============================================================

Before writing code, tell me:

CURRENT PHASE:
<phase>

CURRENT COMPONENT:
<component>

ATOMIC TASK:
<single task being implemented>

WHY:
<why this task is needed>

FILES THAT WILL CHANGE:
<files>

FILES THAT WILL NOT CHANGE:
<important neighboring files>

TEST:
<how this exact change will be verified>

EXPECTED RESULT:
<what proves that the task succeeded>

Then wait for approval if the change is architecturally significant.

For straightforward implementation within an already-approved atomic task,
proceed incrementally without expanding the scope.

============================================================
AFTER EVERY IMPLEMENTATION STEP
============================================================

Report:

IMPLEMENTED:
<what changed>

TESTED:
<what test was run>

RESULT:
<actual result>

ARCHITECTURE IMPACT:
<none, or explicitly describe it>

NEXT ATOMIC STEP:
<exactly one next step>

Do not silently continue implementing several future steps.

============================================================
CORE PRINCIPLE
============================================================

The goal is not to reach the final system as quickly as possible.

The goal is to build a system where every layer is understood, tested,
and trustworthy before another layer depends on it.

Think:

Small change → test → verify → next small change.

NOT:

Large feature → many files → debug everything afterward.

Most importantly:

**Continue from the existing implementation. Do not regenerate the project from scratch.**