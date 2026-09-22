from pathlib import Path
import unittest


class StaticUiContractTests(unittest.TestCase):
    def test_zoom_controls_have_matching_markup_and_bindings(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "src" / "deepanalyze" / "static" / "index.html").read_text(encoding="utf-8")
        js = (root / "src" / "deepanalyze" / "static" / "app.js").read_text(encoding="utf-8")
        for element_id in ("zoom-out", "zoom-label", "zoom-in", "zoom-reset", "zoom-fit"):
            self.assertIn(f'id="{element_id}"', html)
            self.assertIn(f'$("{element_id}")', js)
        self.assertIn('id="language-select"', html)
        self.assertIn('language:preferredLanguage', js)
        self.assertIn('id="language-boundary"', html)
        for element_id in ("sidebar-toggle", "notice-dismiss", "trash-empty", "trash-purge-dialog", "trash-purge-confirm"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("/api/trash/purge", js)
        self.assertIn("trashPurgeIds", js)
        self.assertIn("openTrashPurge", js)
        self.assertIn("value=cancel", js)
        self.assertIn('/static/layout.js', html)
        self.assertIn('DeepAnalyzeLayout.plan', js)
        self.assertIn("overviewFit: true", js)
        self.assertIn("availableWidth", js)
        self.assertNotIn("scheduleOverviewFit", js)
        self.assertIn("function fitZoom()", js)
        self.assertIn("function applyZoom(value, manual = true)", js)



if __name__ == "__main__":
    unittest.main()
