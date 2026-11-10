"""Persist non-secret monitor state on an isolated Git branch, without checkout."""

import argparse
import subprocess
from pathlib import Path

BRANCH = "refs/heads/monitor-state"
LOCAL = "refs/remotes/origin/monitor-state"


def git(*args, input=None):
    return subprocess.run(["git", *args], input=input, text=True,
                          capture_output=True, check=True).stdout.strip()


def restore():
    result = subprocess.run(["git", "ls-remote", "--exit-code", "origin", BRANCH],
                            capture_output=True, text=True)
    if result.returncode == 2:
        print("First run: no saved state branch yet.")
        return
    result.check_returncode()
    git("fetch", "--no-tags", "origin", f"{BRANCH}:{LOCAL}")
    Path("state.json").write_text(git("show", f"{LOCAL}:state.json") + "\n")
    print("Restored monitor state.")


def save():
    path = Path("state.json")
    if not path.exists():
        return
    previous = subprocess.run(["git", "rev-parse", "--verify", LOCAL], capture_output=True, text=True)
    parent = previous.stdout.strip() if previous.returncode == 0 else None
    content = path.read_text()
    if parent and git("show", f"{parent}:state.json") == content.strip():
        print("Alert state unchanged.")
        return
    blob = git("hash-object", "-w", "--stdin", input=content)
    tree = git("mktree", input=f"100644 blob {blob}\tstate.json\n")
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    args = ["commit-tree", tree, "-m", "Update ticket monitor state"]
    if parent:
        args += ["-p", parent]
    commit = git(*args)
    git("push", "origin", f"{commit}:{BRANCH}")
    print("Saved monitor state.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["restore", "save"])
    args = parser.parse_args()
    try:
        {"restore": restore, "save": save}[args.action]()
    except subprocess.CalledProcessError:
        print("State synchronization failed. Check repository contents-write permission and branch rules.")
        raise SystemExit(1)
