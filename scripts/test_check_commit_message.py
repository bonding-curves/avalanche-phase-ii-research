import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from check_commit_message import coauthor_lines

ROOT = Path(__file__).resolve().parents[1]


class CommitMessageTest(unittest.TestCase):
    def test_standard_and_indented_case_variants_are_rejected(self):
        for trailer in ("Co-Authored-By: Agent <a@example.test>", "  co-authored-by : Agent", "\tCO-AUTHORED-BY: Agent"):
            with self.subTest(trailer=trailer):
                self.assertEqual(coauthor_lines("A focused change\n\n" + trailer + "\n"), [3])

    def test_ordinary_messages_and_mentions_are_allowed(self):
        self.assertEqual(coauthor_lines("docs: explain why Co-Authored-By is prohibited\n\nKeep attribution in source records.\n"), [])
        self.assertEqual(coauthor_lines(""), [])

    def test_multiple_trailers_and_crlf_are_located(self):
        self.assertEqual(coauthor_lines("subject\r\nCo-Authored-By: one\r\nCo-Authored-By: two\r\n"), [2, 3])

    def test_cli_errors_are_closed_without_echoing_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            message = Path(temporary) / "message"
            message.write_bytes(b"\xff")
            for args in ([], [str(message)], [str(message.with_name("missing"))]):
                result = subprocess.run(["python3", str(ROOT / "scripts/check_commit_message.py"), *args], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 2)

    def test_real_git_hook_rejects_bad_message_and_allows_focused_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            def git(*args):
                return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
            self.assertEqual(git("init", "-q").returncode, 0)
            git("config", "user.name", "Guard Test")
            git("config", "user.email", "guard@example.test")
            git("config", "core.hooksPath", ".githooks")
            (repo / ".githooks").mkdir()
            (repo / "scripts").mkdir()
            hook = repo / ".githooks/commit-msg"
            shutil.copy2(ROOT / ".githooks/commit-msg", hook)
            hook.chmod(0o755)
            shutil.copy2(ROOT / "scripts/check_commit_message.py", repo / "scripts/check_commit_message.py")
            (repo / "result.txt").write_text("checked result\n")
            git("add", "--", "result.txt")
            denied = git("commit", "--only", "-m", "result\n\nCo-Authored-By: Agent <a@example.test>", "--", "result.txt")
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn("remove co-author trailers", denied.stderr)
            self.assertNotEqual(git("rev-parse", "--verify", "HEAD").returncode, 0)
            allowed = git("commit", "--only", "-m", "result: checked artifact", "--", "result.txt")
            self.assertEqual(allowed.returncode, 0, allowed.stderr)


if __name__ == "__main__":
    unittest.main()
