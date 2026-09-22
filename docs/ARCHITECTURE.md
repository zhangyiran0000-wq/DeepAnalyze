# Architecture

## Data flow

The local HTTP server owns one active exploration. A literature client resolves
the seed and caches source metadata/passages. Direct citing and cited neighbors
of the seed and its evolving mainline anchors form the candidate pool. A discovery
call identifies challenging cases, alternative explanations and papers to read. A synthesis call proposes pairwise paper comparisons with evidence, then consolidates
those comparisons into explanatory lines. Each line has one core technical target,
a constraint/mechanism/consequence claim, a supported progression skeleton and
source-specific explanations for every member. Incomplete synthesis receives
automatic evidence-based refinement roles—targeted evidence reading, local synthesis, relation review, regrouping, and evidence feedback to discovery—within the original model-call and elapsed-time budget. Only a
complete iteration is published; an unfinished working tree retains every read
source and the run preserves an unfinished working tree if repair cannot finish before stop or budget exhaustion.

The two roles use fresh model threads and explicit structured inputs. They are
not agents voting on a shared narrative. Their outputs are proposals; paper IDs,
source metadata, quotes, chronology and graph invariants are checked separately.

```text
Seed / current mainline anchors
              |
              v
Direct citation neighbors -> Evidence selection
                                    |
                                    v
                             Synthesis proposal
                                    |
                                    v
                         Grounding + graph validation
                                    |
                                    v
                              Saved snapshot
                                    |
                         Updated mainline anchors
                                    |
                         Next discovery iteration
```

Saved snapshots also drive the timeline UI and standalone HTML exports.

## Modules

| Module | Responsibility |
| --- | --- |
| `literature.py` | Supported scholarly sources, identity resolution, source cache |
| `codex.py` | Local app-server protocol, authentication, isolated structured calls |
| `engine.py` | Discovery/synthesis cycle, budgets, incremental evidence selection |
| `graph.py` | Source-backed normalization, chronology/DAG checks, depth |
| `synthesis_quality.py` | Single-target declaration, explanatory skeleton and per-member attribution checks |
| `store.py` | Atomic local run state, immutable snapshots and branches |
| `server.py` | Loopback API, session/origin boundary, active-run conflict/stop controls, standalone exports |
| `static/` | Separate tree-map and detail-inspector modules; chronological lanes, zoom/fit, compact cards, usage and history |

## Citation-bound discovery

The seed is the initial anchor. Candidate admission requires a direct citation
relation in either direction to the seed or an anchor on the evolving mainline.
A candidate does not become an anchor just because it was discovered, cached or
read. The anchor set includes the seed and nodes connected to it through
validated, supported `addresses`, `builds_on`, or `challenges` links. Only
`related`, hypothetical, or unconnected nodes do not expand the frontier.
Reachability is undirected for anchor selection, allowing predecessor context;
the stored technical graph remains directed and retains chronology checks.

This boundary restricts which works can be considered; it does not predetermine
which explanations Agent 1 should seek. The discovery role prioritizes different
explanations, missing conditions and counterexamples to the current mainline.
Agent 2 evaluates the evidence before revising technical connections. Citation
membership alone is not proof of a shared problem, technical progress or an
author's motivation.

Citation membership is necessary but not sufficient: candidate rationales must
connect to a concrete anchor problem, a consequence of the anchor's mechanism,
or necessary background. Sharing an application domain, umbrella objective or
terminology alone is insufficient. A candidate is excluded from reading when
all its recorded anchor relationships are `shared_domain_only`; uncertain and contradictory material
remains reviewable. These classifications cannot guarantee semantic relevance,
and domain similarity alone never promotes an anchor.

Unavailable citation APIs leave an explicit retrieval gap. The engine does not
expand into unrestricted topic searches to fill the candidate quota. A sparse or
empty citation neighborhood does not establish completeness.

### Annual citation queues

The citation endpoints do not support server-side year filters. The engine scans
citation metadata pages and then maintains separate queues for each individual
year, from the seed year through the current year. It cycles through those years
before Agent 1 sees candidates. A missing year's quota is not reassigned to the
newest year. Small candidate budgets retain a year cursor between rounds. Within
a year, previously unseen candidates precede repeatedly offered candidates.
Earlier context has a small separate allocation; unknown dates never count as
covering a year.

Within the least-offered tier of each annual queue, every third offer prioritizes
later candidates sharing authors with a directly linked mainline anchor; the
other offers prefer candidates without that signal when available. The cycle
uses persisted offer counts, so small per-round budgets also rotate. Author IDs
are preferred; exact normalized names are an explicitly unverified fallback.
Contradicting IDs do not gain priority from matching names. Unknown chronology
cannot qualify as a successor. No additional provider request is made.


Scanning is independent of the candidate and reading limits: at most three
anchors, six relation requests and 2,000 metadata records per round. Citation
pages can therefore reach intermediate years beyond a crowded first page without
sending thousands of records to the model. Provider cursors and exhausted-route
state are saved. `year_coverage` distinguishes available material, pending scans,
and no matching year in the scanned neighborhood. None of these proves global
literature completeness. Requests retain available abstracts for candidate review.

## Interpreting the graph

An edge records an earlier problem, a later mechanism, the proposed consequence,
conditions and source evidence. Being nearby in embedding space, having a citation
or sharing a keyword is not enough. Multiple parents and useful branches remain
possible. A suggested relationship without sufficient evidence remains a hypothesis.

Depth counts accepted transitions on the longest path, not the number of papers.
Only supported `addresses` or `builds_on` links can increase it. Backward dates,
self-links and cycles cannot increase depth. Each year has one visual band. Within a group/year, supported dependencies form
subrows and siblings share up to three columns; overflow wraps without adding
edges or changing measured depth. Without finer dates historical ordering remains
uncertain. Individual cards have visual offsets, and sibling ordering considers
neighbor positions. Available width provides curve clearance. Cubic paths fan
out through distinct attachment points and use sampled obstacle checks and a
shared occupancy penalty; cross-column fallbacks bend through inter-row gaps.
This is heuristic routing, not a guarantee of zero crossings for arbitrary maps.
Layout is a pure projection and never edits saved research judgments.

Deterministic checks establish structural admissibility and attribution.
A separate model call then assesses proposed transitions, alternatives and shared
group claims against exact quotations and available counterevidence. Cached
reviews are keyed by the claim and its supplied source context; changed context
invalidates an earlier approval before the next interruptible call. This is a
fallible evidence assessment, not proof of scientific entailment.

Refinement compares candidates in order: explained source coverage, fewer hard
defects, reviewed chronological depth, fewer branches, then fewer singleton
groups. Previously explained sources cannot be traded away for new coverage.
A singleton is a consolidation preference, not a standalone reason to reject an
otherwise evidenced explanation. Local calls revise focus papers and their
relations; explicit regrouping calls revise only the partition. Evidence gaps
return to citation-constrained discovery when another exploration round remains.
Every trial is saved separately, while the recovery checkpoint retains the best
accepted explanation under the current evidence. Improving refinement passes continue; a complete pass without improvement
ends the local search. This greedy search is not a global optimality or
convergence guarantee.

## Persistence and reproducibility

Every completed iteration has a separate immutable JSON snapshot with evidence,
pairwise comparisons, group assignments, stable identities, gaps, metrics, change
reasons. `mainline_ids` records the current anchor-eligible mainline;
`discovery` records the `mainline_citations` mode, anchors used in that round and
per-anchor citation/reference cursors. Nodes preserve source `external_ids` and
`citation_links` with anchor identity, citation direction and source URL.
Discovery also preserves candidate rationales and the pending candidate metadata
associated with the iteration's citation cursors. Branching restores that queue;
legacy snapshots without a saved queue replay pages to avoid skipping unseen work.
Historical snapshots may omit these fields and are not rewritten. Retired keyword
configuration is ignored when normalizing a new run or branch.
Run usage distinguishes reported and unreported calls; old runs without usage stay unknown. Run
progress and working evidence caches are separate. Selecting old history does
not substitute new interpretations into it. Resuming forks the selected version;
the original exploration is retained. Changing the branch's budgets does not
rewrite the selected snapshot or its earlier judgments.

Stable persistence makes a particular result reviewable, but does not make model
generation deterministic. Different model versions, available metadata or source
revisions can produce different proposed explanations.

## Boundaries

Only the literature adapter fetches external documents, through allowlisted
HTTPS scholarly hosts with redirect checking. It never follows arbitrary model
URLs into local files or private services. Retrieved material is untrusted data.

The model receives selected public research passages and analysis context, not
the project root or private design documents. Each Codex call uses a temporary
workspace, disabled environments/connectors, a read-only policy and denied tool
requests. Authentication is delegated to Codex. Public errors do not echo raw
protocol payloads or local paths.

There is no multi-user service, hosted deployment, credential synchronization or
automatic GitHub publication. A production network deployment would need a
different authentication and isolation design.

## Runtime constraints

The server exposes `active_run_id` from state and rejects a second active exploration with a 409 `exploration_active` response. The UI can navigate to or stop that run while viewing history. Resume accepts current configuration changes while preserving the original exploration and selected snapshot.

Source packets retain the abstract even when full text is available. A grounded proposed
progression whose papers remain on separate lines triggers consolidation review;
missing historical citation alone does not disprove shared technical problem evolution.

## Evidence and temporal interpretation

Both citing and cited papers can enter the candidate pool when they are directly
connected to a current anchor. Their dates and citation directions are recorded
separately from proposed technical transitions. An older reference can supply
context, while a newer citing paper can challenge rather than extend the current
explanation. Neither role is inferred from a citation alone.

Source identity and citation metadata determine candidate eligibility. Scientific
claims still require reading and evidence checks; dates alone cannot establish
causal influence or depth.

Language is an explicit per-run `zh`/`en` setting. Model prompts request that
language for new analysis while keeping evidence verbatim. Interface translation
is local and makes no model calls. Saved historical analysis is never silently
rewritten during a language switch.

## Bounded discovery and incremental synthesis

Discovery follows direct citation relations in both directions from the seed and
its current mainline anchors. Merely discovered candidates cannot recursively
expand the frontier. Citation unavailability is reported instead of triggering
open topic candidate search. Candidate, reading, model-call and time budgets
remain independent controls on the work performed.

Prior comparisons, including contrary and unrelated judgments, are reused between
rounds. Each line declares exactly one `core_concept` and independently lists at
most five `label_nouns`. A core concept may be a technical phrase containing more
than one noun. The parser rejects explicit goal lists; it does not perform reliable
language-independent noun counting or prove semantic unity.

Every group must attribute its same explanatory claim to every member's own
verified evidence. Its supported chronological skeleton can branch; grounded
alternatives and challenges may attach directly. Pure complementary association
cannot silently extend coverage. Genuine parallel alternatives can have depth zero;
the one-paper starting case also has depth zero. Neither requires invented progress.

Repair uses the full compact tree and up to six cached source packets per attempt.
Invalid evidence records and disconnected members are prioritized together with
the seed anchor. Referenced verified quotations remain in the compact tree even
when they fall beyond the first two excerpts of a paper. It can revise claims, conditions, groups, nodes, comparisons
and edges. The first attempt and subsequent repairs share the configured model-call and
elapsed-time budget, with no separate per-round repair cap. Repair of the current incomplete round takes priority over future rounds. Every analyzed paper must
appear and be explained before a completed snapshot is published. The explained
structure must connect back to the seed through supported technical links or
grounded parallel alternatives; disconnected explanation islands are incomplete. Legacy
`deferred`/`out_of_scope` records remain readable, but cannot exempt a newly
analyzed paper from completion. On failure the working tree and sources remain
saved; previous completed snapshots remain unchanged.

These checks enforce structure, coverage and quote attribution. Semantic validity,
single-target meaning and explanatory depth still depend on model interpretation
and require evaluation on real research cases. Passing the checks is not proof
of a correct or deep scientific explanation.

The interface uses a dark navy workspace theme, supports sidebar collapse and dismissible notices. Trash is reversible until the explicitly confirmed `POST /api/trash/purge` operation permanently removes the displayed run IDs. New model-call records include completion timestamps and elapsed duration; older records may lack those fields.


## Semantic prompt entry points

The model-facing prompts are inline in `src/deepanalyze/engine.py`:
`_exploration_prompt`, `_synthesis_prompt`, and `_revision_prompt`. Graph schemas
and deterministic validation are separate from the model's semantic judgments.
The implementation does not train a network or solve the research-compression
objective globally; prompt-driven synthesis remains an experimental component.


An unfinished synthesis is inspectable in the local workspace and can seed an
explicit repair-only branch; visibility does not change completion status. Each
new synthesis/revision output is saved before the completion gate. Direct short
passage references are resolved only against retrieved endpoint-owned passages;
unknown, metadata-only, ambiguous, or oversized passage references cannot silently
supply evidence. Both endpoint attribution and semantic-quality requirements
remain independent of this identifier normalization.
