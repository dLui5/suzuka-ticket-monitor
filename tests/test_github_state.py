import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import github_state


class GitHubStateTests(unittest.TestCase):
    def test_fresh_runner_restores_state_and_pushes_only_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            remote = root / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            first = root / "runner1"
            first.mkdir()
            original = Path.cwd()
            try:
                os.chdir(first)
                github_state.git("init")
                github_state.git("remote", "add", "origin", str(remote))
                github_state.restore()
                self.assertFalse(Path("state.json").exists())
                Path("state.json").write_text('{"available": ["02"]}\n')
                github_state.save()
                first_commit = github_state.git("ls-remote", "origin", github_state.BRANCH)
                # A new runner has no local state or remote refs.
                second = root / "runner2"
                second.mkdir()
                os.chdir(second)
                github_state.git("init")
                github_state.git("remote", "add", "origin", str(remote))
                github_state.restore()
                self.assertEqual(Path("state.json").read_text(), '{"available": ["02"]}\n')
                github_state.save()
                self.assertEqual(github_state.git("ls-remote", "origin", github_state.BRANCH), first_commit)
                Path("state.json").write_text('{"available": []}\n')
                github_state.save()
                self.assertNotEqual(github_state.git("ls-remote", "origin", github_state.BRANCH), first_commit)
                self.assertEqual(github_state.git("ls-tree", "--name-only", "FETCH_HEAD"), "state.json")
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
