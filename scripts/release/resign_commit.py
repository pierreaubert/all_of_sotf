#!/usr/bin/env python3
"""Re-sign commit history without replaying or changing source trees."""
import argparse
import datetime
import os
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("commit", nargs="?", help="Unsigned commit to repair")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--last", type=int, metavar="N", help="Re-sign every commit in the last N commits")
    scope.add_argument("--since", metavar="REF", help="Repair unsigned commits in REF..HEAD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()

    def git(*argv, data=None, env=None):
        try:
            return subprocess.check_output(
                ["git", "-C", str(repo), *argv], input=data, env=env,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as error:
            raise SystemExit(error.stderr.decode(errors="replace").strip()) from error

    branch = git("symbolic-ref", "HEAD").decode().strip()
    old_head = git("rev-parse", "HEAD").decode().strip()
    if sum([args.commit is not None, args.last is not None, args.since is not None]) != 1:
        parser.error("Choose one commit, --last N, or --since REF")
    if git("status", "--porcelain").strip():
        raise SystemExit("Repository must be clean before rewriting history.")
    committer_name = git("config", "user.name").decode().strip()
    committer_email = git("config", "user.email").decode().strip()
    if not committer_name or not committer_email:
        raise SystemExit("Configure user.name and user.email before signing.")
    boundary = None
    if args.last is not None:
        if args.last <= 0:
            parser.error("--last must be positive")
        targets = set(git("rev-list", f"--max-count={args.last}", old_head).decode().splitlines())
    elif args.since:
        boundary = git("rev-parse", "--verify", args.since + "^{commit}").decode().strip()
        git("merge-base", "--is-ancestor", boundary, old_head)
        rows = git("log", boundary + ".." + old_head, "--format=%H %G?").decode().splitlines()
        targets = {row.split()[0] for row in rows if row.split()[1] == "N"}
    else:
        target = git("rev-parse", "--verify", args.commit + "^{commit}").decode().strip()
        git("merge-base", "--is-ancestor", target, old_head)
        if git("show", "-s", "--format=%G?", target).strip() != b"N":
            raise SystemExit("Target already has a signature; use --last to re-sign signed commits.")
        targets = {target}
    if not targets:
        print("No unsigned commits in the selected push range; nothing changed.")
        return

    # Walk the full DAG and retain all merge parents, including outside the window.
    affected = []
    marked = set(targets)
    for line in git("rev-list", "--reverse", "--topo-order", "--parents", old_head).decode().splitlines():
        sha, *parents = line.split()
        if sha in targets or any(parent in marked for parent in parents):
            marked.add(sha)
            raw = git("cat-file", "commit", sha)
            headers, message = raw.split(b"\n\n", 1)
            fields = {}
            for line in headers.splitlines():
                if line.startswith(b" "):
                    continue
                key, value = line.split(b" ", 1)
                fields.setdefault(key, []).append(value)
            unsupported = set(fields) - {b"tree", b"parent", b"author", b"committer", b"gpgsig", b"encoding"}
            if unsupported:
                raise SystemExit(f"Unsupported commit headers in {sha}: {unsupported}; no history changed.")
            affected.append((sha, parents, fields, message))
    print(f"Selected {len(targets)} commits; will re-sign {len(affected)} including descendants on {branch}.")
    print(f"Committer: {committer_name} <{committer_email}>; original authors and trees preserved.")
    if boundary is None:
        print("This scope can rewrite published history; it may require a later force-with-lease push.")
    if args.dry_run:
        for sha, *_ in affected:
            print(sha)
        return

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = f"backup/before-resign-{stamp}-{os.getpid()}"
    git("branch", backup, old_head)
    print(f"Backup branch: {backup}")
    mapped = {}
    for index, (sha, parents, fields, message) in enumerate(affected, 1):
        env = dict(os.environ)
        identity = fields[b"author"][0].decode()
        match = re.fullmatch(r"(.*) <([^>]*)> (\d+ [+-]\d{4})", identity)
        if not match:
            raise SystemExit(f"Cannot parse author in {sha}; original branch unchanged.")
        env["GIT_AUTHOR_NAME"], env["GIT_AUTHOR_EMAIL"] = match[1], match[2]
        env["GIT_AUTHOR_DATE"] = "@" + match[3]
        # The person re-signing is the new committer. Keeping GitHub/bot
        # committer emails would prevent account-based signature verification.
        env["GIT_COMMITTER_NAME"] = committer_name
        env["GIT_COMMITTER_EMAIL"] = committer_email
        env["GIT_COMMITTER_DATE"] = "@" + str(int(datetime.datetime.now(datetime.timezone.utc).timestamp())) + " +0000"
        encoding = fields.get(b"encoding", [b"UTF-8"])[0].decode()
        argv = ["-c", f"i18n.commitEncoding={encoding}", "commit-tree", "-S", fields[b"tree"][0].decode()]
        for parent in parents:
            argv.extend(["-p", mapped.get(parent, parent)])
        replacement = git(*argv, data=message, env=env).decode().strip()
        git("verify-commit", replacement)
        mapped[sha] = replacement
        if index % 25 == 0 or index == len(affected):
            print(f"Signed and verified {index}/{len(affected)}", flush=True)
    new_head = mapped[old_head]
    if boundary is not None:
        git("merge-base", "--is-ancestor", boundary, new_head)
    assert git("rev-parse", old_head + "^{tree}") == git("rev-parse", new_head + "^{tree}")
    # Compare-and-swap refuses to overwrite concurrent branch updates.
    git("update-ref", "-m", "Re-sign selected commits and descendants", branch, new_head, old_head)
    print(f"New HEAD: {new_head}")
    print("Source files and merge topology preserved. Nothing pushed.")
    print("Update the aggregate AutoEQ gitlink and scripts/release/sources.json before committing the aggregate.")


if __name__ == "__main__":
    main()
