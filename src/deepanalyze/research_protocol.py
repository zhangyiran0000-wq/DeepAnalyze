"""Shared synthesis contract for evidence-based changes in research understanding."""

ASSESSMENT_RULES = (
    "Separate the author's claimed problem from what the available results actually demonstrate. "
    "Populate research_assessment with claimed_problem, demonstrated_result, conditions, unresolved, own-source evidence_ids, "
    "and outcome: demonstrated, partial, not_tested (evaluation does not test the claim), contradicted (affirmative contrary evidence), "
    "or unknown (available material cannot decide). Outcome concerns the stated claim within recorded conditions, not the entire field. "
    "Judge outcome against the paper's own explicit claim, not the broader seed goal or a later paper's ambitions. "
    "A demonstrated narrow result remains demonstrated under its stated conditions; an untested downstream use is a boundary, not automatically a partial failure. "
    "Do not turn missing evidence into failure, proposals into established solutions, or benchmark gains into real-world guarantees. "
    "Do not speculate about author motives. A small gain can cross a meaningful threshold; a negative result can change the explanation. "
)

MAINLINE_RULES = (
    "Use explanation_model=knowledge_transitions_v1 for every group. A mainline explains how understanding of ONE concrete research question changes. "
    "Keep all analyzed papers as nodes, but do not make every contribution a turning point. Different mechanisms and evaluation tools may belong to successive stages of the same question. "
    "Choose root_id as the first evidenced stage represented in the group. In spine retain only supported chronological addresses/builds_on/challenges links "
    "that change a justified belief, feasible capability, or failure boundary. Every step has source,target,claim_connection,before,after,transition_type "
    "(advance, revision, reframing). A paper lacking a later feature is not evidence of a defect. Identical or paraphrased changes across several papers form ONE stage. "
    "A new testable proposal or a tool that changes what can be measured may be a reframing step, without claiming it solved the problem. "
    "member_support covers EVERY member: paper_id,claim_connection,own-source evidence_ids, role (advance,revision,proposal,incremental,replication,tooling), "
    "stage_anchor_id,knowledge_change,removal_effect,attachment_evidence_ids. Root and spine vertices are stage anchors and point stage_anchor_id to themselves. "
    "Every other member attaches DIRECTLY to a root/spine anchor for the SAME concrete question, with attachment_evidence_ids from BOTH sources. "
    "Attachments express an explanatory place, not historical influence or a new evolution edge; they add coverage but NO depth. "
    "Incremental and replication papers attach to a stage and never become spine targets just to lengthen a chain. Keep valuable alternatives and counterexamples visible. "
    "knowledge_change states the precise new inference or that the work only reinforces/refines existing evidence. removal_effect applies a deletion test "
    "relative to the other retained papers: what inference, practical feasibility threshold, or failure boundary would be lost? No loss means supporting material, not low-quality science. "
    "These roles are relative to the current explanation and may change with evidence; no citation-count or leaderboard ranking decides them. "
    "explanatory_claim describes the initial constraint, the evolution of responses (mechanism), and the bounded conclusion or remaining gap (consequence); "
    "it must not falsely assert that all members use the same mechanism or demonstrate the same gain. Keep each field concise and preserve uncertainties. "
)
