# DeepAnalyze

**Find the problems that connect research progress.**

Start with one paper. DeepAnalyze discovers related work, asks what the current
explanation fails to account for, and builds an evidence-linked map of technical
transitions. Time runs from top to bottom. Colored lanes represent discovered
research groups, each with a common problem, progression and open problem; connections explain which earlier problem a later method
addresses.

This is an early, local-first research prototype. It provides a repeatable workflow
and auditable evidence, not a guarantee that an inferred history is correct.

## Run locally

Requires **Python 3.11+**. The offline demo and web server have no third-party
Python dependencies, no JavaScript build step, and no external font/CDN requests.

```sh
python main.py
```

Open [the local workspace](http://127.0.0.1:8765). Choose **Explore an illustrative
demo** to inspect the tree, evidence sidebar and version history without a model
account or network access. Demo papers and their evidence are explicitly synthetic.

```sh
python main.py --demo
python main.py --port 9000
```

You can also install the package:

```sh
python -m pip install -e .
deepanalyze
```

Optional PDF extraction (arXiv HTML is tried first):

```sh
python -m pip install -e ".[pdf]"
```

## Live research with Codex

Install a current [Codex CLI](https://learn.chatgpt.com/docs/quickstart) and make
`codex` available on PATH. An alternative executable can be selected using the
`DEEPANALYZE_CODEX` environment variable. DeepAnalyze controls its local app-server
through the [documented JSON-RPC protocol](https://learn.chatgpt.com/docs/app-server).
It does not require a separate agent framework.

1. Open **Connect Codex**. Reuse an existing local login, choose ChatGPT sign-in,
   or enter an API key in the local connection dialog.
2. Enter a paper title, DOI, or arXiv URL. A precise identifier avoids ambiguous
   title matches. Newer work is discovered during research; there is no fixed endpoint.
3. Set the round, candidate, reading, model-call and time limits. The progress candidate count is the deduplicated literature pool scanned so far; the configured “Candidates / round” value is the per-round offer budget sent to Agent 1. Defaults are 10 rounds,
   30 candidates, 10 reads, 100 model calls and 300 minutes; reads are capped at 30 and
   candidates at 60. The default model is `gpt-5.6-luna`; a blank model field also uses
   Luna. A different model requires
   an explicit selection instead of inheriting a potentially expensive runtime default.
   Research calls use medium reasoning effort, overriding any global ultra setting.
4. Start the exploration. Inspect evidence, open gaps and uncertain connections.
   Stop at any point; completed snapshots remain available.
5. Select a saved version to review its original judgments, branch from it, or
   export it as a self-contained HTML document. Resuming creates a new branch
   without rewriting the original snapshots.
6. Use **Delete** beside a finished exploration to move it into **Trash**.
   **Restore** returns its original history and snapshots; active runs must finish
   or stop before deletion. Nothing is automatically purged.

Start directly from the paper. Candidates must directly cite, or be cited by,
the seed or a paper on its evolving mainline. A newly discovered candidate does
not become a discovery anchor merely by appearing in the candidate pool or being
read.

[ChatGPT login and API-key authentication](https://learn.chatgpt.com/docs/auth)
use different billing arrangements. The application does not switch between them
automatically. Signing in/out changes the selected Codex runtime's account.
Credentials are managed by Codex, not saved in research snapshots.

Live research requires a Codex version that supports explicitly disabled
environments. If that capability cannot be verified, it fails closed rather than
granting the model access to your files. Analysis uses ephemeral threads and
only supplied source text; shell, browsing, apps and configured connectors are
disabled for these threads. Scholarly retrieval is done by the application.

## What the first version does

- Retrieves public metadata through Semantic Scholar, arXiv and Crossref, with
  caching and request pacing. Candidate discovery follows direct citation links
  in both directions from the seed and its evolving mainline anchors. Finding a
  candidate does not automatically turn it into an anchor for further expansion.
- Keeps candidate admission separate from technical interpretation. Agent 1 seeks
  different explanations, omissions and counterexamples among citation-linked
  work; Agent 2 decides how the evidence changes the mainline. A citation alone
  does not establish a technical progression or prove historical motivation.
- Reports missing citation data and retrieval failures. If citation APIs are
  unavailable, it does not widen the candidate boundary through an open topic
  search fallback.
- Alternates discovery of omissions/counterexamples with synthesis of technical
  problem transitions. Existing judgments and selected passages are reused so
  every round does not reread an entire corpus.
- Checks paper identities, quoted passages, temporal consistency, duplicate edges
  and cycles before counting supported connections toward depth.
- Keeps uncertain relationships visible. Quotation matching establishes that a
  passage occurs in a source, **not that its interpretation is scientifically true**.
- Preserves every completed iteration as an immutable snapshot, including lanes,
  colors, evidence, gaps and changes. A resumed version becomes a separate branch.
- Uses separate tree-map and detail-inspector modules. The map shows compact paper
  cards with short names, clamped summaries and known institutional affiliations;
  the inspector preserves full details and lets you inspect the
  shared problem, mechanism change, remaining gap and evidence behind each comparison. Chronological maps grow with the page and support manual zoom and width fitting. Multiple responses can share a colored lane and
  appear side by side; supported dependencies create subrows within a year.
  Missing affiliations stay unknown; they are not guessed.
- Switch interface language between Chinese and English. New live analyses use
  the selected language; existing saved prose and original source quotations remain
  unchanged. The offline demo uses fixed synthetic English source content.

The research loop uses distinct evidence and explanation roles under one shared budget: targeted evidence reading, local synthesis, relation-evidence review, mainline regrouping, and evidence feedback to discovery. These roles run sequentially as needed; a final pass still requires every analyzed source to be explained. The first version uses structured model proposals plus deterministic checks.
It **does not implement a globally optimal solver** for the deepest explanatory
tree or prove convergence of the research loop. A deeper accepted graph remains
a proposal to review, not an independent measure of scientific understanding.

## Current limits


Paper-level observations are shown when present: the author-stated problem, reported gains, evaluation protocol, limitations and costs, and positioning against prior work. Each observation carries its basis (author claim, reported experiment, model inference, or unknown) and evidence IDs. Initial reading is a research-judgment summary from available abstract/full text; targeted rereading can add evidence but does not replace that initial pass.

Full text is currently attempted for arXiv HTML/PDF. Other sources may remain
abstract-only or metadata-only; the UI preserves that distinction. Optional PDF
extraction is text-only and can lose equations, tables and scanned content.
Source APIs may rate-limit requests or lack recent publications. A capped run
does not imply that the literature is complete.

Both authors' claims and model interpretations can be wrong. Technical
compatibility does not prove historical influence. No experiments are reproduced.
The evidence checks cannot establish semantic entailment or discover every hidden
assumption. These are central areas for further evaluation, alongside relation
stability across models and runs.

Work limits bound iterations, candidates, reads and model calls. Only one exploration
can run at a time; the workspace exposes its active run ID and offers direct go/stop
actions when you are viewing another run. Reported token usage is marked incomplete
when calls remain unreported, and legacy runs with no usage record remain unknown. A time limit is
checked between operations and used as the model deadline; an in-flight source
request may finish after that limit. This is not a guaranteed currency cap.
Currency cost is unknown when the provider supplies no price information.

## Privacy and publishing

The server listens only on `127.0.0.1`. Its file routes serve a fixed asset list,
not your project directory. Mutations require a session token and pass local-host
and origin checks. Request bodies and runtime stderr are not logged.

### Private phone access with Tailscale

Connect the computer and phone to the same tailnet. Keep the research service
running on port 8765, then start its separate local gateway (replace the example
origin with the computer's Tailscale DNS name):

    python scripts/serve_private.py --public-origin https://computer.example.ts.net
    tailscale serve --bg --https=443 http://127.0.0.1:8766

Tailscale may ask the tailnet administrator to enable Serve/HTTPS first.
Open the HTTPS origin on the phone with Tailscale connected. Serve access follows
your tailnet access policy; keep it limited to your intended devices/users.
The gateway and research server both bind to loopback. The gateway validates
the configured Host and Origin before forwarding to the fixed local backend;
the backend still checks the session token on mutations. It can start without
restarting or interrupting research. No Funnel or public port exposure is needed.

Keep the computer awake and both Python processes running. Tailscale's background
Serve configuration persists across reboot, but these Python processes must be
started again. Disable this route with the following command:

    tailscale serve --https=443 off


Runtime data is stored in `.deepanalyze/` by default. Source documents, cached
passages, saved runs, private intent documents, `.env` files and credentials are
excluded from Git/public archives. Live source text and research inputs are sent
to the selected model provider; metadata services receive search queries.
Downloaded HTML exports contain the selected research snapshot, including its
evidence excerpts. Review research content before sharing it.

Build a source archive using the explicit public-file allowlist:

```sh
python scripts/build_public_archive.py
```

This produces `dist/DeepAnalyze-source.zip`. It does not upload anything. The
archive excludes local research documents and all runtime data, even when present
in the checkout. No automatic publication workflow is configured.

## Development

```sh
python -m unittest discover -s tests -t . -v
```

Tests use controlled providers and temporary local stores. They cover evidence
and chronology validation, snapshots/branching, model protocol handling, source
fallbacks and the local API boundary without spending model quota.

See [the architecture](docs/ARCHITECTURE.md) and [API contract](docs/API.md).
The public code is licensed under MIT.

## Current research and workspace behavior

Live discovery stays within the direct citation neighborhood of the seed and its
current mainline anchors. Both citing and cited papers can become candidates.
The anchor set contains the seed and papers connected to it through validated,
supported `addresses`, `builds_on`, or `challenges` links. Merely related,
hypothetical, or unconnected candidates do not extend the frontier. Anchor
reachability permits either direction so predecessor context remains possible;
this does not reverse the directed technical graph.

Citation membership is necessary but not sufficient. A retained direction must
connect to an anchor's concrete technical problem, consequences of its mechanism,
or necessary background. Shared application domains, terminology or broad
objectives alone do not establish that connection. Explicit same-domain-only
candidates are excluded from reading, while uncertainty and counterevidence stay
reviewable. These checks do not guarantee semantic correctness or promote a paper
to an anchor without supported technical links.

Agent 1 uses this bounded pool to challenge the current explanation, not merely
to find more agreement. Sparse incremental comparisons reuse prior work and focus
on new or changed sources, with up to two challenged old comparison pairs audited
per round. Explanation repair continues while the configured model-call and time budgets remain, using bounded source windows while preserving the complete compact tree. It can correct claims and links as well as group membership. These controls bound exploration; they do not prove improved scientific
quality or complete coverage.

Snapshots may record source dispositions such as `included`, `deferred`, `out_of_scope`, and `pending`, so omitted read sources remain reviewable rather than silently treated as irrelevant. The workspace uses a dark navy theme, supports collapsing the sidebar, and allows dismissing notices. The tree keeps its normal scale and extends the page vertically as it grows, rather than using an inner vertical scrollbar. Year bands wrap papers according to available width; selecting a year, intent group or paper focuses its connections. The detail inspector remains a separate sticky pane. Manual zoom remains available. Rejected connections stay in the audit details but are not drawn as tree arrows.

Finished runs can be moved to Trash and restored. Permanent deletion requires `POST /api/trash/purge` with an explicit body such as `{"run_ids":["..."] ,"confirm":true}`; only the displayed IDs may be supplied and the operation is irreversible. New model-call records include `completed_at` and `elapsed_seconds`; older records may not contain them.

### Annual discovery and complete explanation

Candidate selection now cycles through each year from the seed to the present,
using separately paged direct citation metadata. Missing years retain their own
gaps instead of being filled with the newest papers. Earlier context stays
bounded. This does not add model calls per year or expand the reading limit.

Every explanatory line has one core technical target and a specific relation
between a constraint, a mechanism and its consequence. All analyzed papers must
be accounted for with source evidence and a place in the tree. Incomplete explanations are revised automatically within the configured total
model-call and elapsed-time budget; there is no separate per-round repair cap.
If coverage remains incomplete when the run stops or its budget is exhausted, the run saves
the working draft, which remains visible with its validation failures. It is not
published as a complete iteration. These are
structural safeguards, not a guarantee that a model's explanation is deep or true.

Selecting a paper, year or line highlights its direct neighbor papers as well as
its incident arrows. The tree grows with the document at natural scale.


### Author continuity and prompt locations

Within each annual citation queue, roughly one in three candidate offers favors
later work sharing authors with a directly linked mainline anchor. The other two
prefer other teams when available; less-seen candidates still take precedence.
Matching author IDs are stronger than name overlap, which is explicitly marked
unverified. This is a retrieval heuristic, not evidence of technical inheritance.
It does not add model calls or widen the citation boundary.

The semantic analysis remains prompt-driven. `src/deepanalyze/engine.py` defines
`_exploration_prompt` (Agent 1), `_synthesis_prompt` (Agent 2), and
`_revision_prompt` (synthesis repair). Deterministic checks enforce evidence
attribution, structure, coverage and budgets; they do not implement a trained
research optimizer or guarantee explanatory depth.

The viewer staggers individual cards within year bands and uses available space
for connection clearance. Cubic curves use separate attachment points and favor
unoccupied routes around cards. Dense graphs can still have crossing curves;
selecting a paper highlights its direct neighbors and incident connections.
Layout changes never change research depth or saved technical judgments.


### When synthesis stops before completing an iteration

The workspace shows the saved working tree, paper evidence, and specific
validation failures. It labels the tree unfinished; completed snapshots remain
separate and unchanged. Targeted evidence rereads, local updates, relation review, and regrouping continue automatically while the configured model-call and time budgets remain; they stop only when those budgets or the run stop conditions are reached. Distant frozen graph regions are not rewritten during a local repair, and an unresolved gap can return to discovery for a bridge candidate.

**Continue synthesis** resumes a stopped unfinished draft with the remaining run budget. It starts from cached papers and the retained analysis, rereads unavailable evidence when necessary, and can return unresolved gaps to the remaining exploration rounds. The source run remains unchanged except for its continuation pointer. This button starts no work until clicked.
Each new normalized synthesis attempt is also retained in local analysis history.
Short exact source-passage IDs can be cited directly; the entire passage must be
at most 2,000 characters and is preserved as source-bound evidence.
