import unittest

from deepanalyze.source_context import review_source_context


class SourceContextTests(unittest.TestCase):
    def test_verified_fragment_anchor_gets_adjacent_subject_context(self):
        papers = {"b": {"id": "b", "title": "Later", "passages": [
            {"id": "b0", "text": "Prior system X", "location": "Related"},
            {"id": "b1", "text": "crashes under bounded updates.", "location": "Related"},
            {"id": "b2", "text": "The method changes the update rule and reports results.", "location": "Results"},
            {"id": "b3", "text": "An unrelated appendix detail.", "location": "Appendix"},
        ]}}
        snapshot = {"nodes": [{"id": "b", "evidence": [{"id": "ev", "quote": "crashes under bounded updates.", "verified": True}],
            "research_assessment": {"evidence_ids": ["ev"]}}]}
        result = review_source_context(snapshot, papers, max_chars_per_paper=110)
        self.assertEqual([item["id"] for item in result["b"]], ["b0", "b1", "b2"])
        self.assertTrue(all(item["source_paper_id"] == "b" for item in result["b"]))

    def test_unverified_or_unmatched_quotes_are_excluded_and_budget_is_hard(self):
        papers = {"a": {"id": "a", "title": "A", "passages": [
            {"id": "a0", "text": "Verified short passage.", "location": "Abstract"},
            {"id": "a1", "text": "Another passage that should fit only when budget allows.", "location": "Results"},
        ]}}
        snapshot = {"nodes": [{"id": "a", "evidence": [
            {"id": "good", "quote": "Verified short passage.", "verified": True},
            {"id": "bad", "quote": "Invented unrelated quote.", "verified": False}],
            "research_assessment": {"evidence_ids": ["bad", "good"]}}]}
        result = review_source_context(snapshot, papers, max_chars_per_paper=25)
        self.assertEqual([item["id"] for item in result["a"]], ["a0"])
        self.assertLessEqual(sum(len(item["text"]) for item in result["a"]), 25)

    def test_missing_passages_is_safe(self):
        self.assertEqual(review_source_context({"nodes": [{"id": "x", "evidence": []}]}, {"x": {"id": "x"}}), {"x": []})


if __name__ == "__main__":
    unittest.main()

