# Progress Log — Session Continuity

This file is a running log of *what has actually been done*, session
by session, so a new session (or a returning developer) can pick up
exactly where things were left without re-deriving state from git
diffs alone.

`plan/handsoff.md` is the frozen architecture/methodology reference —
read that first, every time. This file is the moving checkpoint on
top of it: what's implemented, tested, and what's next.

Do not delete old entries; append new ones. If a fact here starts
contradicting the actual repository, the repository wins — say so
explicitly in the next entry rather than silently editing history.

---

## How work has been happening (development style — keep following this)

- **Atomic, bottom-up, one component at a time.** Never implement a
  whole phase or several unrelated components in one step.
- **Before implementing anything**, state: current phase, current
  component, the single atomic task, why it's needed, which files
  will change, which important neighboring files will NOT change,
  and how it will be tested — then wait for approval before touching
  files if the change is architecturally significant.
- **After implementing**, report: what changed, what test was run,
  the actual result (not a guess), architecture impact (or "none"),
  and exactly one proposed next step. Do not silently continue into
  further steps.
- **Test bottom-up**: pure helper function → individual external
  tool/API → deterministic orchestration function → individual agent
  → agent+tools → agent-to-agent → phase → full system. A function
  with no network/LLM dependency gets a Level-1 pure test (hand-built
  dicts, `assert`, run directly with `python test/test_x.py`, using
  `PYTHONPATH=.` from the project root since imports are root-level).
  A function that does real I/O (HTTP, filesystem) gets tested live,
  the same way arXiv/OpenAlex/Crossref/Tavily were — real calls,
  output inspected by hand, not mocked.
- **No premature abstraction or optimization.** Simple, readable
  Python; a little duplication is fine; sequential code stays
  sequential until there's evidence it needs to change.
- **Never fabricate data.** A failed API call / missing PDF / missing
  field is reported as a structured failure, never invented or
  silently papered over.
- **Preserve working, already-tested components.** Only touch a
  passed component again with a concrete reason, and re-run its
  existing test after doing so.
- The developer is still building Python/ADK familiarity — explain
  changes, keep them small, give exact file paths, avoid unnecessary
  abstraction.
- The user manually inspects each implemented component/test
  themselves after being told it's done — always report completion
  clearly enough for that (files touched, test run, actual output)
  before proposing the next step.

---

## Where things stood at the start of this log

Phase 2 (Retrieval) was already complete and stable:
`search_arxiv`, `search_semantic_scholar`, `search_openalex`,
`search_crossref`, `search_tavily` in `tools.py`; deterministic
routing (`execute_search_query`/`execute_search_queries`) in
`utils.py`; Search Coordinator wired to `execute_research_searches()`
and tested through ADK (`test/test_search_coordinator.py`).

Phase 3 (Analysis Agent) had two atomic tasks already done and
tested before this log started:
- `deduplicate_papers()` — DOI/arXiv-ID/normalized-title matching,
  field-merge without overwrite, duplicate-group provenance.
  Tested: `test/test_deduplicate_papers.py` — PASSED.
- `rerank_papers()` — deterministic title/abstract term-overlap
  scoring, citation-count/title tie-breaks. Tested:
  `test/test_rerank_papers.py` — PASSED.

All of the above matched `plan/handsoff.md` exactly; schemas.py's 27
classes were verified name-for-name against the handoff's Section 9
list. One stale structural note: the handoff's Section 5 tree lists
`test_tools.py`/`test_search_coordinator.py` at the project root;
they actually live under `test/` now, alongside the new test files.
Not a bug, just a doc that could be refreshed eventually.

---

## Entry 1 — `select_papers()` implemented + tested

**Component:** Analysis Agent — Paper Selection (deterministic
baseline policy, not the LLM-judgment "coverage/diversity" layer the
prompt also describes — that judgment stays the Analysis Agent LLM's
job on top of this tool's output).

**Implemented:** `select_papers(ranked_papers, max_papers=20,
min_relevance_score=0.0)` in `tools.py`, right after `rerank_papers`.
Filters by relevance floor first, then keeps at most `max_papers` by
best rank. Returns `selected_paper_ids`, `selected_papers`,
`excluded_papers` (each tagged `below_relevance_threshold` or
`max_papers_reached`), and counts.

**Tested:** `test/test_select_papers.py` (Level 1, pure function) —
5 cases: top-N cutoff, threshold-only cutoff, both combined, fewer
candidates than the cap, unsorted input (proves internal sort by
rank). Result: **ALL ASSERTIONS PASSED**. Re-ran
`test_deduplicate_papers.py` and `test_rerank_papers.py` too — no
regression.

**Wiring:** Added to `analysis_agent/agent.py`'s import and `tools=`
list (deduplicate_papers, rerank_papers, select_papers, download_pdf,
render_pdf_pages). Verified via Level-4 sanity check (agent
constructs, `tools` resolves to the expected 5 names) — no LLM call.

**Architecture impact:** None. Additive only.

---

## Entry 2 — `download_pdf()` implemented + tested

**Component:** Analysis Agent — PDF Acquisition.

**Implemented:** `download_pdf(pdf_url, paper_id)` in `tools.py`,
now `async` (real network I/O, matching the search_* functions'
pattern). Writes to `PDF_DOWNLOAD_DIR/<paper_id>.pdf`
(`PDF_DOWNLOAD_DIR` defaults to `data/pdfs`, new config value).
Reports outcomes using the same `RetrievalStatus` values
`RetrievedPaper` already uses (`downloaded`/`failed`), so the result
dict maps straight onto `RetrievedPaper` without translation.

Handles, without raising or fabricating data:
- missing `pdf_url` (common/expected — many records have none)
- non-200 HTTP status
- oversized response (`MAX_PDF_DOWNLOAD_BYTES`, default 50 MB, new
  config value) — checked via `Content-Length` when present, and
  again while streaming in case the header is absent/wrong
- downloaded content that isn't actually a PDF (missing `%PDF`
  magic bytes — e.g. an HTML paywall/error page)
- `httpx.HTTPError` transport failures

**Config added:** `PDF_DOWNLOAD_DIR`, `MAX_PDF_DOWNLOAD_BYTES` in
`config.py`. `.gitignore` updated with `data/pdfs/` so downloaded
binaries never get committed.

**Tested:** `test/test_download_pdf.py` (Level 2, live — real HTTP,
real filesystem, no mocking, matching how search_arxiv etc. were
tested). 3 cases: a real small stable arXiv PDF (download succeeds,
file exists, starts with `%PDF`, path matches
`PDF_DOWNLOAD_DIR/<paper_id>.pdf`, then the test cleans its own
artifact up), `pdf_url=None` (reported failed, no network call), a
404 URL (reported failed, confirmed no file was written). Result:
**ALL ASSERTIONS PASSED**. Re-ran the three prior Level-1 tests too —
no regression. Confirmed `analysis_agent` still constructs with all
5 tools resolving correctly.

**Architecture impact:** None on the frozen architecture. New
runtime side effect: this is the first tool that writes to disk
(`data/pdfs/`) — noted here since it's a new category of effect, not
because it changes any responsibility boundary.

---

## Entry 3 — storage layout restructured + `render_pdf_pages()` implemented + tested

**Requested change:** keep each paper's artifacts together under one
folder instead of separate `data/pdfs/` and `data/pages/` trees:

```
data/<paper_id>/<paper_id>.pdf
data/<paper_id>/pages/page_0001.png
data/<paper_id>/pages/page_0002.png
...
```

**Implemented:**
- `config.py`: renamed `PDF_DOWNLOAD_DIR` → `PAPERS_DIR` (default
  `"data"` — the root each paper gets a subfolder under, not a
  PDF-specific folder anymore). Added `PAGE_RENDER_DPI` (default
  `150`).
- `download_pdf()` updated to write to
  `PAPERS_DIR/<paper_id>/<paper_id>.pdf`. Also tightened: the
  per-paper directory is now only created right before a *successful*
  download is written to disk, so a failed download never leaves an
  empty folder behind.
- `render_pdf_pages(pdf_path)` implemented (was a stub). Uses
  PyMuPDF (`pymupdf`, added to `requirements.txt` and installed —
  it was missing from the environment/requirements entirely even
  though the frozen architecture names it) to open the PDF and
  render every page as a full-page PNG at `PAGE_RENDER_DPI`, derived
  entirely from `pdf_path`'s own parent directory (`<that dir>/pages/`)
  — no separate config coupling needed between download_pdf and
  render_pdf_pages. Pages are named `page_0001.png`, `page_0002.png`,
  etc. Missing/unopenable PDFs are reported as a structured failure,
  never raised.
- `.gitignore`: no change needed beyond the earlier `data/pdfs/`
  entry, which is now stale (removed the empty leftover directory
  from disk; the ignore rule itself can be cleaned up in a later
  pass if it ever matters).

**Tested:**
- `test/test_download_pdf.py` updated for the new path
  (`PAPERS_DIR/<paper_id>/<paper_id>.pdf`) and re-run — still
  **ALL ASSERTIONS PASSED**, including confirming a 404 leaves no
  empty per-paper directory behind.
- `test/test_render_pdf_pages.py` (new, Level 2, live): downloads a
  real PDF via the already-tested `download_pdf`, renders it, checks
  page count matches PyMuPDF's own `page_count` (independent ground
  truth), checks naming/nesting convention, checks each output file
  is a real PNG (magic-byte check), then a second case for a
  nonexistent PDF path (clean failure, no directory created). Result:
  **ALL ASSERTIONS PASSED** (10/10 pages rendered and verified for
  the arXiv 2203.08975v1 test PDF). Both tests clean up every
  artifact they create.
- Re-ran all four earlier tests (`test_deduplicate_papers`,
  `test_rerank_papers`, `test_select_papers`, `test_download_pdf`) —
  no regressions. `analysis_agent` still constructs with all 5 tools
  resolving correctly.

**Architecture impact:** None on the frozen architecture. Storage
layout is an implementation detail, not a responsibility boundary.

---

## Entry 4 — `analyze_pages_with_vlm()` implemented + tested (batched vision analysis)

**Component:** Analysis Agent — VLM Input Preparation + Vision Analysis
(batched, not single-page — see decision below).

**Model decision (resolves the open question from the previous
checkpoint):** No new/separate vision model was needed.
`moonshotai/kimi-k3`, already assigned as `ANALYSIS_MODEL`, is
natively multimodal (MoonViT-V2 vision encoder; accepts image + text
in the same message) — confirmed via NVIDIA NIM / Moonshot AI
documentation before writing any code.

**Architecture clarification (discovered during implementation,
recorded here and reflected in `handsoff.md` Section 4):** OpenAI-
compatible chat APIs (what NVIDIA NIM / LiteLLM use here) only allow
image content inside `user`-role messages, never inside a tool/
function *result*. This means a tool cannot hand rendered page image
bytes back into the Analysis Agent's own conversational turn for the
agent itself to "look at" mid-reasoning - that channel is text/JSON
only (this is also consistent with an open google/adk-python bug
around LiteLLM + image URLs). So `analyze_pages_with_vlm()` performs
the vision inference *inside* the tool, via a direct `litellm.acompletion()`
call using the same `ANALYSIS_MODEL_NAME`/NVIDIA NIM credentials
already configured for the agent, and returns structured
`PageAnalysis` results as its tool output. The Analysis Agent still
directs the process (which paper, which pages to send, what to do
with the structured results) but does not itself receive raw image
bytes in its own turn. `ANALYSIS_AGENT_PROMPT` Section 6 was reworded
to describe this accurately ("the tool performs the vision inference
... you direct which pages to send and interpret the structured
results") instead of implying the agent looks at the pages itself.

**Batching decision:** pages are sent `VLM_PAGES_PER_CALL` (default
4, new config value) at a time, as separate full-resolution images
within a single model call — not composited into one image. A 2x2
pixel-composite was considered and rejected: most VLMs tile images
into fixed-size patches and charge per tile, so a composite at the
same total pixel count costs about the same tokens as sending the
images separately, while shrinking each page to a quarter size and
hurting legibility of small text/table cells/equations. Sending
multiple full-resolution images in one call cuts the number of VLM
requests (and repeated system-prompt overhead) without that
resolution cost.

**Implemented, all in `tools.py` right after `render_pdf_pages`:**
- `parse_page_number_from_image_path(image_path)` — pure helper,
  extracts the 1-based page number from `page_NNNN.png`. The page
  number is always taken from the filename, never trusted from the
  VLM's own response, so a page can never be mislabeled even if the
  model's output ordering is imperfect.
- `parse_vlm_json_array(raw_output)` — pure helper, parses the VLM's
  text response into a JSON array, tolerating markdown code-fence
  wrapping; returns `None` (never a guess) on anything invalid.
- `analyze_pages_with_vlm(paper_id, page_image_paths)` — async, the
  actual tool. Chunks `page_image_paths` into batches of
  `VLM_PAGES_PER_CALL`; for each batch, base64-encodes every page PNG,
  sends them as separate `image_url` content parts in one
  `litellm.acompletion()` call alongside `VLM_PAGE_ANALYSIS_PROMPT`
  (new prompt in `prompts.py` instructing the model to return a JSON
  array with exactly one object per image, in order), parses the
  response, and validates each object against `PageAnalysis`
  (reusing the existing schema as-is — no schema changes needed).
  A batch-level failure (transport error, malformed JSON, wrong
  array length) is reported as a structured `failed_pages` entry for
  exactly the pages in that batch - never fabricated - and does not
  block other batches for the same paper.

**Config added:** `VLM_PAGES_PER_CALL` (default 4) in `config.py`.
Also refactored `ANALYSIS_MODEL` construction to expose the raw
model name as `ANALYSIS_MODEL_NAME` (previously only the wrapped
`LiteLlm` object existed), since the tool needs the raw string for
its own direct `litellm.acompletion()` call.

**Tested:** `test/test_analyze_pages_with_vlm.py` (Level 2, live —
real HTTP, real VLM inference, no mocking). Case 1: download +
render a real small arXiv PDF (reusing already-tested
`download_pdf`/`render_pdf_pages`), analyze its first 2 pages (one
batch), re-validate every returned object against `PageAnalysis`,
confirm `page_number`/`image_path`/`paper_id` map correctly per
page. The real model output was inspected by hand and was accurate -
it correctly identified the actual paper's content (a Comm-MARL
survey) from the images. Case 2: a nonexistent page image path -
reported as a clean `failed_pages` entry, no exception raised, no
fabricated `PageAnalysis`. Result: **ALL ASSERTIONS PASSED**. Re-ran
`test_deduplicate_papers.py`, `test_rerank_papers.py`,
`test_select_papers.py`, `test_download_pdf.py`,
`test_render_pdf_pages.py` too - no regressions. `analysis_agent`
still constructs, now resolving 6 tools (the 5 previous plus
`analyze_pages_with_vlm`).

**Architecture impact:** None on the frozen agent/responsibility
boundaries - vision analysis is still exclusively the Analysis
Agent's responsibility, and it still directs which papers/pages get
analyzed. The one clarification (recorded above and in
`handsoff.md`) is *how* the vision call physically happens (tool-
internal model call vs. inline in the agent's own turn), which is an
implementation detail forced by the underlying chat-completions
protocol, not a responsibility-boundary change.

## Entry 5 — `build_paper_analysis()` implemented + tested (PaperAnalysis assembly)

**Component:** Analysis Agent — Paper-level analysis (combining a
paper's `PageAnalysis[]` into one structured `PaperAnalysis`).

**Design decision:** the paper-level synthesis itself (working out
research objective, methodology, contributions, etc. from the
page_analyses) is genuine agent judgment, so it stays the Analysis
Agent's own reasoning - no tool does that reasoning. What *does* need
a tool, following the same pattern already used for
`analyze_pages_with_vlm`'s VLM output and `execute_research_searches`'
`SearchQuery.model_validate`, is validating the agent's synthesized
fields against the canonical `PaperAnalysis` schema at a tool
boundary rather than trusting free-form LLM output. The tool also
deterministically re-attaches the already-produced `page_analyses`
list, so the agent never has to (and cannot) re-type/garble data it
already generated.

**Implemented:** `build_paper_analysis(paper_id, page_analyses,
research_objective=None, methodology=None, datasets=None,
experimental_setup=None, metrics=None, key_findings=None,
contributions=None, limitations=None, future_work=None)` in
`tools.py`, right after `analyze_pages_with_vlm`. Pure/deterministic
- no network or LLM call in the function itself. Validates everything
via `PaperAnalysis.model_validate(...)`, with `evidence` intentionally
left `[]` (Evidence generation is a separate, later step). On
validation failure, returns a structured error (`success: False`,
`paper_analysis: None`, an `error` string) - never a fabricated or
partially-coerced result. No `schemas.py` changes were needed -
`PaperAnalysis` already fit exactly.

**Prompt updated:** `ANALYSIS_AGENT_PROMPT` Section 7 ("BUILD
PAPER-LEVEL ANALYSIS") now explicitly tells the agent to call this
tool with its synthesized fields once it has worked them out from the
page_analyses, and clarifies the tool does not synthesize or generate
evidence itself.

**Wiring:** Added to `analysis_agent/agent.py`'s import and `tools=`
list. Verified via Level-4 sanity check (agent constructs, `tools`
resolves to all 7 expected names) - no LLM call.

**Tested:** `test/test_build_paper_analysis.py` (Level 1, pure) - 4
cases: a complete valid synthesis over 2 pages (fields + embedded
page_analyses all correct, evidence defaults to `[]`), minimal input
with no synthesis fields supplied at all (every optional field falls
back to its empty default, nothing fabricated), invalid `metrics`
type (dict expected, list given - structured failure, not coerced),
and a `page_analyses` entry missing its required `summary` field
(structured failure). Result: **ALL ASSERTIONS PASSED**. Re-ran
`test_deduplicate_papers.py`, `test_rerank_papers.py`,
`test_select_papers.py` - no regressions. `analysis_agent` still
constructs, now resolving 7 tools.

**Architecture impact:** None. Additive only; no responsibility
boundaries changed.

---

## Checkpoint — where things stand right now

Phase 3 (Analysis Agent) progress:

| Component | Status |
|---|---|
| Deduplication (`deduplicate_papers`) | done, tested, wired |
| Re-ranking (`rerank_papers`) | done, tested, wired |
| Paper Selection (`select_papers`) | done, tested, wired |
| PDF Download (`download_pdf`) | done, tested, wired (nested `data/<paper_id>/` layout) |
| Page Rendering (`render_pdf_pages`) | done, tested, wired (nested `data/<paper_id>/pages/` layout) |
| VLM page analysis (`analyze_pages_with_vlm`) | done, tested, wired (batched, `VLM_PAGES_PER_CALL`=4 per call) |
| Paper-level `PaperAnalysis` assembly (`build_paper_analysis`) | done, tested, wired (validation only; synthesis is agent reasoning) |
| `Evidence` generation | not started — next |
| Citation Reviewer tools (`verify_doi`, `verify_paper_metadata`, `verify_source_identity`) | stubs only, wired but unimplemented — later phase |

Nothing has been committed to git yet — all of this is still sitting
as uncommitted working-tree changes (`config.py`, `tools.py`,
`schemas.py`, `prompts.py`, `requirements.txt`, `.gitignore`,
`search_coordinator/agent.py`, `analysis_agent/agent.py`, new
`utils.py`, new `test/`, new `plan/`). Commit only when explicitly
asked.

## Next atomic step (proposed, not yet started)

Evidence generation: produce `Evidence` objects (per `schemas.py` -
`evidence_id`, `paper_id`, `page_numbers`, `description`,
`evidence_type`, `relevance_to_research_question`,
`supporting_observation`, `confidence`) from a paper's
`page_analyses`/`PaperAnalysis`, traceable back to specific pages.
Likely the same pattern as `build_paper_analysis`: the Analysis Agent
reasons about which observations are actually important evidence
(judgment, not computation), and a small deterministic tool validates
the result(s) against the `Evidence` schema and assigns
`evidence_id`s. Worth deciding whether evidence gets attached back
into the paper's `PaperAnalysis.evidence` list at this step (closing
that loop from Entry 5) or stays a separate collection - needs a
decision before writing code.
