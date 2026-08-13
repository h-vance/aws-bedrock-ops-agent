import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrontendStaticTests(unittest.TestCase):
    def test_model_output_fields_are_escaped_before_rendering(self):
        html = (ROOT / "static" / "index.html").read_text()

        self.assertIn("${escapeHtml(h.hypothesis)}", html)
        self.assertIn("${escapeHtml(h.check_command)}", html)
        self.assertIn("${escapeHtml(data.customer_comms_draft)}", html)
        self.assertIn("${recommendedChecks.map(c => `<li>${escapeHtml(c)}</li>`).join(\"\")}", html)
        self.assertNotIn("<div class=\"hypothesis-text\">${h.hypothesis}</div>", html)
        self.assertNotIn("<div class=\"comms\">${data.customer_comms_draft}</div>", html)

    def test_escape_html_handles_quotes_and_nullish_values(self):
        html = (ROOT / "static" / "index.html").read_text()

        self.assertIn("String(str ?? \"\")", html)
        self.assertIn(".replace(/\"/g, \"&quot;\")", html)
        self.assertIn(".replace(/'/g, \"&#39;\")", html)


if __name__ == "__main__":
    unittest.main()
