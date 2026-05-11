import unittest
from unittest.mock import patch

from pulse.prompt_context import compose_prompt, gather_context


class TestGatherContext(unittest.TestCase):
    def test_includes_cwd_and_app(self):
        with patch("pulse.prompt_context.get_frontmost_app", return_value="Terminal"):
            ctx = gather_context()
        self.assertIn("cwd", ctx)
        self.assertEqual(ctx["app"], "Terminal")

    def test_target_included_when_provided(self):
        with patch("pulse.prompt_context.get_frontmost_app", return_value="Terminal"):
            ctx = gather_context(target="claude_left")
        self.assertEqual(ctx["target"], "claude_left")

    def test_target_absent_when_not_provided(self):
        with patch("pulse.prompt_context.get_frontmost_app", return_value="Terminal"):
            ctx = gather_context()
        self.assertNotIn("target", ctx)

    def test_git_info_present_in_git_repo(self):
        with patch("pulse.prompt_context.get_frontmost_app", return_value="default"), \
             patch("pulse.prompt_context._git_info", return_value={"branch": "main", "uncommitted_changes": False}):
            ctx = gather_context()
        self.assertEqual(ctx["branch"], "main")

    def test_git_info_absent_outside_repo(self):
        with patch("pulse.prompt_context.get_frontmost_app", return_value="default"), \
             patch("pulse.prompt_context._git_info", return_value={}):
            ctx = gather_context()
        self.assertNotIn("branch", ctx)


class TestComposePrompt(unittest.TestCase):
    def _compose(self, text, target=None, *, branch=None, dirty=False):
        git = {"branch": branch, "uncommitted_changes": dirty} if branch else {}
        with patch("pulse.prompt_context.get_frontmost_app", return_value="Terminal"), \
             patch("pulse.prompt_context._git_info", return_value=git):
            return compose_prompt(text, target)

    def test_text_appears_first(self):
        result = self._compose("Review this.")
        self.assertTrue(result.startswith("Review this."))

    def test_context_block_present(self):
        result = self._compose("Do something.")
        self.assertIn("Context:", result)
        self.assertIn("- app: Terminal", result)

    def test_target_line_present_when_given(self):
        result = self._compose("Fix bug.", target="claude_left")
        self.assertIn("- target: claude_left", result)

    def test_target_line_absent_when_not_given(self):
        result = self._compose("Fix bug.")
        self.assertNotIn("- target:", result)

    def test_branch_line_present(self):
        result = self._compose("Check.", branch="feature/x")
        self.assertIn("- branch: feature/x", result)

    def test_uncommitted_changes_line_present(self):
        result = self._compose("Check.", branch="main", dirty=True)
        self.assertIn("- uncommitted changes: yes", result)

    def test_uncommitted_changes_line_absent_when_clean(self):
        result = self._compose("Check.", branch="main", dirty=False)
        self.assertNotIn("uncommitted changes", result)

    def test_no_target_no_branch_minimal_output(self):
        result = self._compose("Hello.")
        lines = result.splitlines()
        self.assertEqual(lines[0], "Hello.")
        self.assertEqual(lines[1], "")
        self.assertEqual(lines[2], "Context:")

    def test_full_output_ordering(self):
        result = self._compose("Review.", target="claude_right", branch="main", dirty=True)
        lines = result.splitlines()
        context_idx = lines.index("Context:")
        target_line = next(l for l in lines if "target" in l)
        app_line = next(l for l in lines if "app" in l)
        branch_line = next(l for l in lines if "branch" in l)
        dirty_line = next(l for l in lines if "uncommitted" in l)
        # target must come before app, branch, dirty
        self.assertLess(lines.index(target_line), lines.index(app_line))
        self.assertLess(lines.index(branch_line), lines.index(dirty_line))
        self.assertGreater(lines.index(target_line), context_idx)


if __name__ == "__main__":
    unittest.main()
