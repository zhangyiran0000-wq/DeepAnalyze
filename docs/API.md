# Local API and data contract

The application binds to loopback. JSON mutations use `X-DeepAnalyze-Token`
from `GET /api/state`. No credentials are included in run data or exports.

## Endpoints

- `GET /api/state`: `{version, csrf_token, runs: [run], active_run_id, default_config}`.
- `GET /api/auth/status`: `{available, authenticated, mode, error?}`. No email.
- `POST /api/auth/login`: `{method: "chatgpt" | "apiKey", api_key?: string}`;
  returns a supported login URL/identifier or authenticated status.
- `POST /api/auth/logout`: sign out of the selected local Codex runtime.
- `POST /api/runs`: `{seed, mode: "live" | "demo", config}`; returns a run. Only one live/demo exploration may be active at a time.
- `GET /api/runs/{id}`: the complete run and latest completed snapshot.
- `POST /api/runs/{id}/trash`: `{}`; reversibly remove a finished run from history.
- `GET /api/trash`: a list of compact trashed-run records.
- `POST /api/runs/{id}/restore`: `{}`; restore a trashed run without starting it.
- `POST /api/runs/{id}/stop`: stop at a safe boundary/cancel a model turn.
- `POST /api/runs/{id}/resume`: `{snapshot_id, config?}`; creates a new run branch from the selected snapshot with supplied configuration updates. Existing snapshots are not rewritten.
- `GET /api/runs/{id}/snapshots/{snapshot_id}`: one immutable snapshot.
- `GET /api/runs/{id}/export?snapshot={snapshot_id}`: standalone HTML.

Run configuration: `max_iterations` (default 10), `candidates_per_round` (30;
maximum 60), `read_per_round` (10; maximum 30), `max_model_calls` (100),
`max_seconds` (18000), `model` (defaults to `gpt-5.6-luna`; a blank value also
selects Luna), and `language` (`zh` by default, or `en`). These are limits, not
completion promises. Research model calls use medium reasoning effort. Legacy
`scope_keywords` configuration is ignored during normalization; saved historical
runs and snapshots are not rewritten.

Run fields: `id, seed, mode, config, status, phase, iteration, created_at,
updated_at, stop_reason, parent, progress, events, snapshots, latest_snapshot, usage, calls`.
Usage contains `input_tokens, output_tokens, cached_input_tokens, total_tokens,
reasoning_output_tokens, reported_calls, unreported_calls`; old runs without recorded
usage remain unknown rather than being shown as zero. A 409 conflict returns
`code: "exploration_active"` and `active_run_id`.
Progress contains `candidates, read, included, model_calls, elapsed_seconds` and optional `pending_synthesis` for newly read sources awaiting a saved decision. Legacy runs omit that count.
Events contain `at, phase, message`. Snapshot summaries contain
`id, iteration, created_at, depth, node_count, edge_count`.

Snapshot fields: `id, iteration, created_at, seed_id, scope, mainline_ids, discovery, groups, nodes,
edges, comparisons, synthesis_quality, gaps, changes, metrics, review_notes, demo, language?, source_dispositions?, temporal_coverage?`.

- Group: `id, label, description, color, common_problem, progression, open_problem, separation_reason`. Model proposals also supply `member_ids` and `merge_from`; saved node `group_ids` contain the resulting membership. New groups also include `core_concept`, `label_nouns` (1-5 declared terms), `explanatory_claim` (`constraint`, `mechanism`, `consequence`), `spine`, `member_support`, and `explanation_quality`. Evidence-based refinement uses targeted evidence reading, local synthesis, relation review, regrouping, and evidence feedback to discovery; it continues automatically within the original model-call and elapsed-time budget.
- Node: `id, title, short_name, year, date, url, authors, affiliations,
  group_ids, problem, mechanism, solves, results, limitations, assumptions,
  uncertainties, evidence, source_status, added_iteration`.
  Optional contextual metadata: `context_role: "background"`, `context_for`
  (later paper ID), `context_problem`, `context_reason`, `context_evidence_quote`;
  `forward_citation_of` can occur in legacy records and records a discovery route,
  not a supported technical edge. `external_ids` stores source identity mappings.
  `citation_links` contains `{anchor_id, direction, source_url}`, where `direction`
  is `cites_anchor` or `cited_by_anchor`. These links document candidate eligibility,
  not accepted technical transitions.
- Evidence: `id, quote, source_url, location, kind, verified`.
- Edge: `id, source, target, kind, problem, mechanism, consequence,
  evidence_ids, status, rationale, conditions, historical_influence`. Historical influence is `documented`, `unknown`, or `not_claimed`; it is distinct from an interpreted technical response.
- Comparison: `id, source, target, shared_problem, earlier_limitation, later_change, remaining_gap, relation, group_action, rationale, evidence_ids, grounded`.
- Synthesis quality records singleton fragmentation and unapplied merge decisions.
- Gap: `id, description, paper_ids`.
- Change: `kind, target_id, reason`.
- Metrics: `depth, node_count, edge_count, supported_edges`.
- Mainline IDs: seed plus nodes connected through validated, supported
  `addresses`, `builds_on`, or `challenges` links; discovery reachability treats
  these links as undirected without changing their saved technical direction.
- Discovery: `{mode: "mainline_citations", anchor_ids: [...], cursors: {...}}`.
  `anchor_ids` records the anchors used in the iteration; each cursor stores
  `citations` and `references` offsets for an anchor. Historical snapshots can
  omit these fields.

Edge kinds are `addresses`, `builds_on`, `challenges`, `related`. Status is
`supported`, `hypothesis`, or `rejected`. Only grounded, acyclic,
chronologically compatible `addresses`/`builds_on` transitions count toward
depth. Quote presence verifies attribution, not the truth of a scientific claim.

## Citation-bound candidate admission

Live exploration starts directly from a seed. Its candidate boundary is the
union of papers that directly cite or are cited by the seed or its evolving
mainline anchors. Discovered, cached or read candidates do not become anchors
merely by entering the candidate pool. A candidate must connect to the seed's
mainline through supported `addresses`, `builds_on`, or `challenges` links;
`related` or hypothetical links alone do not extend the anchor set.

Agent 1 seeks different explanations, omissions and counterexamples inside this
boundary. A citation establishes eligibility for consideration, not a supported
technical connection. Synthesis still needs source evidence for problem changes,
mechanisms and consequences. Missing or unavailable citation data is reported;
the engine does not admit open topic-search results as a fallback when citation
APIs are unavailable.

Candidate rationales identify a concrete anchor problem and a `problem_relation`:
`same_problem`, `mechanism_consequence`, `necessary_background`,
`shared_domain_only`, or `uncertain`. Citation membership is necessary but not
sufficient for technical relevance. Candidates whose recorded anchor relationships are all `shared_domain_only` are
excluded from reading; uncertainty and contradictory results remain reviewable.
A generic application-domain overlap does not justify an anchor or technical edge.
The classification is a model judgment, not a guarantee of semantic correctness.

`discovery.candidate_rationales` saves the inspected claim, different account and
selection reason per candidate/anchor. `discovery.pending_candidates` saves the
unread or deferred candidate metadata corresponding to that iteration's cursors.
A resumed branch restores this queue before advancing; older snapshots without
the queue replay citation pages rather than skipping unsaved candidates.

The keyword-suggestion endpoint and keyword-selection workflow have been removed.
Historical snapshots can retain retired fields as part of their original record;
they are not rewritten or converted into evidence for new candidate admission.

## Python interfaces

`CodexClient(workspace: Path, executable: str | None = None)` provides
`status()`, `login(method, api_key=None)`, `logout()`, `close()`, and
`generate(prompt, schema=None, model=None, on_event=None, cancel_event=None,
timeout=600, on_usage=None, reasoning_effort=None)`. Generation returns `{data: dict, usage: dict, thread_id: str}`;
it emits concise public progress strings via `on_event` and never logs secrets.

`LiteratureClient(cache_dir: Path)` provides `resolve(seed) -> paper`,
`search(query, limit=10, *, year_from=None, sort="relevance") -> list[paper]`
(`sort` also accepts `newest`),
`related(paper, limit=10, *, direction="both") -> list[paper]`
(`direction`: `citations`, `references`, or `both`),
and `read(paper) -> paper`. Paper fields include `id, title, short_name, year,
date, url, abstract, authors, affiliations, external_ids, source_status,
passages`. A passage contains `id, text, location, url`. Missing full text is
explicit. Cached source extraction is reused.

`RunStore(root: Path)` provides `create(seed, config, mode="live", parent=None)`,
`get(run_id)`, `list_runs()`, `update(run_id, **patch)`,
`event(run_id, phase, message)`, `add_snapshot(run_id, snapshot)`,
`snapshot(run_id, snapshot_id)`, `resume(run_id, snapshot_id, config=None)`, and
`recover_interrupted()`. Snapshots are immutable and forked runs preserve history.

`ResearchEngine(provider, literature, store).run(run_id, cancel_event)` executes
a bounded live or clearly labeled synthetic demonstration workflow.

Trash moves the complete private run directory, preserving immutable snapshots and working evidence. The active worker cannot be trashed (`409 run_active`). Restoration rejects ID collisions. Permanent deletion is documented under Trash purge below.

### Research discovery and disposition

Live discovery retrieves direct citing and cited neighbors of the seed and its
current mainline anchors. Candidate discovery alone does not promote a paper to
an anchor. Agent 1 prioritizes work that can challenge or offer a different
explanation from the current mainline. Incremental comparisons reuse prior
analysis and send only new or changed material plus a bounded set of challenged old
comparison pairs for audit. Explanation repair revisits bounded source windows
and can revise claims, memberships, nodes, comparisons and links. These limits describe workflow behavior, not a
proof of improved scientific quality.

Snapshots may expose `source_dispositions` with `included`, `deferred`, `out_of_scope`, or `pending` values. New model-call records may contain `completed_at` and `elapsed_seconds`; older records can omit them.

### Trash purge

- `POST /api/trash/purge`: irreversible body `{run_ids: ["..."], confirm: true}`. The server accepts only explicitly displayed trash IDs and requires confirmation. Trash and restore remain reversible until this endpoint is used.

The literature interface is:

`search(query, limit=10, *, year_from=None, year_to=None, sort="relevance")`.

`year_from` and `year_to` are inclusive; `sort` accepts `relevance` or `newest`.

### Completion and yearly discovery

New completed live snapshots have `completion_status: "complete"`. All read
sources must be present and explained; deferred/out-of-scope declarations do not
exempt them. A run that stops before satisfying this within its model-call or time budget ends with its unfinished working tree preserved; the stop reason distinguishes budget exhaustion from an execution failure. Its unfinished tree is
stored locally as `synthesis_draft`. The run-detail endpoint exposes its normalized
analysis as `working_snapshot`, separately from the last completed snapshot. Raw
extraction-cache contents remain private. Existing snapshots are unchanged.

`groups[*].core_concept` names one technical target. `label_nouns` limits declared
title noun terms independently of that target. `member_support` records
`paper_id, claim_connection, evidence_ids`; `spine` records
`source, target, claim_connection`. `explanation_quality` contains `group_id,
status, spine_depth, covered_member_ids, unexplained_member_ids, issues`.
Status is `evidence_linked` or `incomplete`; it is not semantic proof.

Paper nodes may include `research_observations` with `kind` (`claimed_problem`, `demonstrated_gain`, `evaluation_protocol`, `limitation`, `positioning`), `statement`, `basis` (`author_claim`, `reported_experiment`, `model_inference`, `unknown`), and `evidence_ids`. These are displayed as attributed observations; the UI does not infer motivations such as leaderboard chasing or mentorship. Initial reading remains the paper-level judgment summary, while targeted rereading supplies additional evidence and does not replace it.

`discovery` now saves `scan_state`, `offered_counts`, `year_cursor`, `year_order`,
`year_coverage`, and `scan_complete` in addition to citation cursors and pending
candidates. A coverage row contains `year, candidates, read, included, offered,
pool_status`. Pool status is `available`, `pending_scan`, or
`none_found_in_scanned_neighborhood`. Unknown publication years do not cover a year.

The literature adapter additionally provides:

- `neighbor_page(paper, direction, *, offset=0, limit=100, include_total=False, metadata_only=False)` returning `papers, offset, next_offset, total`.
- `neighbor_count(paper, direction)` returning an exact-identity citation/reference count.

The relation page maximum is 1,000 records. The live engine scans at most 2,000
metadata records and six relation requests per round, separately from the model
candidate and reading limits. Annual filtering is local because the citation and
reference endpoints do not expose a year filter. `metadata_only=True` omits
abstracts/authors for callers that only need lightweight scanning.


### Author continuity metadata

Paper metadata and normalized nodes may contain `author_ids`, using provider
namespaces such as `s2:<authorId>`. Old snapshots may omit them. Candidate packets
include `authors` and `author_continuity`: `score, anchor_id, basis, shared_authors`.
`basis` is `author_id`, `name_overlap_unverified`, or `none`. Discovery saves the
nonzero signals for the current candidate shortlist in `author_priority`, keyed
by paper ID. These fields explain retrieval priority only and never establish a
technical edge or promote a candidate to a mainline anchor.


### Inspecting and retrying unfinished synthesis

`GET /api/runs/{id}` may include `working_snapshot` and includes
`can_retry_synthesis`. The former is a normalized analysis tree with
`completion_status: "incomplete"`, never a completed snapshot or raw paper cache.
`POST /api/runs/{id}/retry-synthesis` with `{}` creates a continuation branch that shares the original exploration budget.
`POST /api/runs/{id}/reanalyze` requires a body with an explicit fresh `config`; it creates an independent branch that reanalyzes only the original run's readable cached sources under the new budget. It requires an idle run and authentication, preserves the original run and discovery cache, and never carries over budget usage.
It requires an idle worker and existing authentication. It first restores the
saved sources and unfinished tree without retrieval, revises automatically,
and then resumes the original remaining exploration rounds after validation.
Calls and running time used by every recovery ancestor are counted once, including
legacy recovery branches. An exhausted original budget cannot be reset through
this endpoint. A draft can have only one recovery successor; older checkpoints
cannot start sibling recoveries, even after their successor is deleted. Separate snapshot branches remain independent new explorations.
`GET /api/runs/{id}` also returns `synthesis_budget` with `limits` (the original
configuration), `model_calls_used`, `elapsed_seconds_used`,
`remaining_model_calls`, `remaining_seconds`, and the absolute `iteration_limit`.
`progress` and token usage remain local to each run record; cumulative spending
is stored as `budget_carry` on continuation branches.
`parent.recovery` is `synthesis`; `parent.draft_id` identifies the source draft.

Future run records include `synthesis_attempts`, a list of normalized-attempt
summaries (`id, iteration, role, attempt, created_at, node_count, quality`). The
corresponding full normalized results are retained under the private run's
`analysis` directory. Failed attempts do not enter `snapshots` or change its
completed-iteration count.
