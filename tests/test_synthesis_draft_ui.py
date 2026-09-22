from pathlib import Path
import unittest

class SynthesisDraftUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.html = (root / "src" / "deepanalyze" / "static" / "index.html").read_text(encoding="utf-8")
        cls.js = (root / "src" / "deepanalyze" / "static" / "app.js").read_text(encoding="utf-8")

    def test_draft_contract_has_retry_guard_and_no_export(self):
        self.assertIn('id="retry-synthesis-button"', self.html)
        self.assertIn("working_snapshot", self.js)
        self.assertIn("can_retry_synthesis === true", self.js)
        self.assertIn("active(state.run)", self.js)
        self.assertIn("limits?.max_model_calls", self.js)
        self.assertIn("retry-synthesis", self.js)
        self.assertIn("Continue synthesis", self.js)
        self.assertIn("state.snapshotDraft", self.js)
        self.assertIn("state.snapshotDraft ? \"#\"", self.js)

    def test_draft_diagnostics_name_papers_and_groups(self):
        for key in ("Missing source connections", "Unconnected papers", "invalid_member_evidence", "missing_member_support", "missing_spine", "unexplained_members", "invalid_spine_transition"):
            self.assertIn(key, self.js)
        self.assertIn("groupLabel(item.group_id)", self.js)
        self.assertIn("titleFor(id)", self.js)

    def test_synthesis_roles_and_progress_events_are_localized(self):
        for role in ("evidence_reading", "local_synthesis", "relation_review", "regrouping", "evidence_feedback"):
            self.assertIn(role, self.js)
        for event in ("Reading targeted passages for a specific explanation gap.", "Returning evidence gaps to discovery before the next refinement.", "Comparing the revised explanation with the best saved candidate.", "Reviewing proposed technical relations against their source evidence.", "Consolidating shared problems to reduce branches and deepen the mainline."):
            self.assertIn(event, self.js)

    def test_paper_observations_are_attributed_when_present(self):
        self.assertIn("research_observations", self.js)
        for kind in ("claimed_problem", "demonstrated_gain", "evaluation_protocol", "limitation", "positioning"):
            self.assertIn(kind, self.js)
        for basis in ("author_claim", "reported_experiment", "model_inference", "unknown"):
            self.assertIn(basis, self.js)

    def test_draft_identity_is_stable_during_render_and_poll(self):
        self.assertIn('const effectiveId = state.snapshotDraft ? "__working__" : snapshot.id', self.js)
        self.assertIn('&&state.followLatest)await showLatest()', self.js)
        self.assertIn('state.snapshotDraft ? []', self.js)

if __name__ == "__main__":
    unittest.main()
