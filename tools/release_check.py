#!/usr/bin/env python3
"""Release-0.1 preflight: read a branch and print every P0/P3 condition as PASS, FAIL, INFO or SKIP.

The script is read-only: it never tags, pushes, merges, publishes or edits a workflow.  Files are read with
``git show <branch>:<path>`` so the working tree does not affect a check.  Exit status is 1 when any check fails.
"""
import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *map(str, args)], capture_output=True, text=True)


def read_branch_file(repo, branch, path):
    result = git(repo, "show", "%s:%s" % (branch, path))
    return result.stdout if result.returncode == 0 else None


def branch_has(repo, branch, path):
    return git(repo, "cat-file", "-e", "%s:%s" % (branch, path)).returncode == 0


def one_line(text):
    return " ".join(str(text).split())


def table_cells(line):
    text = line.strip()
    if not text.startswith("|") or not text.endswith("|"):
        if not text.startswith("|"):
            return None
    text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [cell.strip() for cell in text.split("|")]


def separator_row(line):
    cells = table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def p0_jobs(roadmap):
    """The first ``| Job | ... |`` table's job names, or (None, None) when there is no such table."""
    lines = roadmap.splitlines()
    for index, line in enumerate(lines):
        cells = table_cells(line)
        if cells and cells[0].strip("*` ").lower() == "job":
            jobs = []
            for row in lines[index + 1:]:
                if table_cells(row) is None:
                    break
                if separator_row(row):
                    continue
                row_cells = table_cells(row)
                if not row_cells:
                    continue
                name = row_cells[0].strip().strip("`")
                if name and name.lower() != "job":
                    jobs.append(name)
            return jobs, line.strip()
    return None, None


def p1_done_condition(roadmap):
    match = re.search(r"^##\s*P1\b.*$", roadmap, re.M)
    if not match:
        return None
    rest = roadmap[match.end():]
    following = re.search(r"^##\s", rest, re.M)
    section = rest[:following.start()] if following else rest
    for line in section.splitlines():
        if "done when" in line.lower():
            text = one_line(re.sub(r"[*`]", "", line).lstrip("- "))
            return re.sub(r"^done when:\s*", "", text, flags=re.I)
    return None


def comparison_figures(comparison):
    for line in comparison.splitlines()[:20]:
        if "AIL commit" in line or ("commit" in line and "tasks" in line):
            return one_line(line.strip("# "))
    match = re.search(r"AIL commit[^\n]*", comparison)
    return one_line(match.group(0)) if match else None


def count_open_differences(differences):
    """Rows whose status column is ``open`` or empty, across every table that has a status column.

    The record uses several table layouts and some of its tables continue after a blank line without
    repeating the header, so the most recent header is kept until another header replaces it.
    """
    lines = differences.splitlines()
    total = 0
    status_index = None
    header_width = 0
    index = 0
    while index < len(lines):
        cells = table_cells(lines[index])
        if cells is None:
            index += 1
            continue
        if separator_row(lines[index]):
            index += 1
            continue
        if index + 1 < len(lines) and separator_row(lines[index + 1]):
            found = None
            for column, cell in enumerate(cells):
                if cell.strip("*` ").lower() == "status":
                    found = column
                    break
            status_index = found
            header_width = len(cells)
            index += 2
            continue
        if status_index is None:
            index += 1
            continue
        if status_index == header_width - 1 and len(cells) > header_width:
            status = cells[-1]
        elif status_index < len(cells):
            status = cells[status_index]
        else:
            status = ""
        if status.strip("*` ").lower() in ("", "open"):
            total += 1
        index += 1
    return total


def check_version(repo, branch):
    text = read_branch_file(repo, branch, "packaging/ail_lang/__init__.py")
    if text is None:
        return None, "cannot read packaging/ail_lang/__init__.py on %s" % branch
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    if not match:
        return None, "no __version__ in packaging/ail_lang/__init__.py"
    return match.group(1), None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only release-0.1 preflight.")
    parser.add_argument("--repo", default=str(ROOT), help="repository directory (default: this checkout)")
    parser.add_argument("--branch", default="origin/integ", help="branch or ref to read (default: origin/integ)")
    parser.add_argument("--remote", default="origin", help="remote name for main and the commit count")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--online", action="store_true", help="ask GitHub for the latest tests.yml run")
    parser.add_argument("--build", action="store_true", help="build the wheel into a temporary directory")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    branch = args.branch
    remote = args.remote
    main_ref = ("%s/main" % remote) if remote else "main"
    version, version_error = check_version(repo, branch)
    checks = []

    def add(number, name, status, reason):
        checks.append({"number": number, "name": name, "status": status, "reason": one_line(reason)})

    # 1. final version
    if version_error:
        add(1, "version", "FAIL", version_error)
    elif re.search(r"(?:^|[.\-]|(?<=\d))(?:dev|a|b|rc)\d*", version.split("+", 1)[0]):
        add(1, "version", "FAIL", "%s is a development version" % version)
    else:
        add(1, "version", "PASS", "%s is a final release" % version)

    # 2. changelog heading for the version
    changelog = read_branch_file(repo, branch, "CHANGELOG.md")
    if changelog is None:
        add(2, "changelog", "FAIL", "CHANGELOG.md is missing")
    elif version is None:
        add(2, "changelog", "FAIL", "cannot look up a version heading without a version")
    else:
        heading = re.search(r"^#{1,6}\s+.*?(?<![\w.])v?%s(?![\w.+-])" % re.escape(version), changelog, re.M)
        if heading:
            add(2, "changelog", "PASS", "CHANGELOG.md has a heading for %s" % version)
        else:
            add(2, "changelog", "FAIL", "CHANGELOG.md has no heading for %s" % version)

    # 3. licenses
    license_files = [name for name in ("LICENSE-MIT", "LICENSE-APACHE") if branch_has(repo, branch, name)]
    pyproject = read_branch_file(repo, branch, "pyproject.toml")
    license_line = pyproject is not None and re.search(
        r'^license\s*=\s*["\']MIT OR Apache-2\.0["\']\s*$', pyproject, re.M)
    if len(license_files) == 2 and license_line:
        add(3, "licenses", "PASS", "MIT OR Apache-2.0 and both license files")
    else:
        missing = [name for name in ("LICENSE-MIT", "LICENSE-APACHE") if name not in license_files]
        pieces = []
        if missing:
            pieces.append("missing " + ", ".join(missing))
        if not license_line:
            pieces.append('pyproject.toml does not declare license = "MIT OR Apache-2.0"')
        add(3, "licenses", "FAIL", "; ".join(pieces))

    # 4. third-party notices
    if branch_has(repo, branch, "THIRD_PARTY_NOTICES.md"):
        add(4, "notices", "PASS", "THIRD_PARTY_NOTICES.md exists")
    else:
        add(4, "notices", "FAIL", "THIRD_PARTY_NOTICES.md is missing (job relnotice1)")

    # 5. each ROADMAP P0 job has a merge on the branch
    roadmap = read_branch_file(repo, branch, "docs/ROADMAP.md")
    if roadmap is None:
        add(5, "p0-merges", "FAIL", "docs/ROADMAP.md is missing on %s" % branch)
    else:
        jobs, header = p0_jobs(roadmap)
        log = git(repo, "log", "--format=%s", branch, "--")
        if not jobs:
            add(5, "p0-merges", "FAIL",
                "no '| Job |' P0 table in docs/ROADMAP.md" + (" (header: %s)" % header if header else ""))
        elif log.returncode != 0:
            add(5, "p0-merges", "FAIL", "cannot read commits on %s" % branch)
        else:
            subjects = log.stdout.splitlines()
            missing = [job for job in jobs
                       if not any(("integrate " + job) in subject or ("job-" + job + "-") in subject
                                  for subject in subjects)]
            if missing:
                add(5, "p0-merges", "FAIL", "missing merge for " + ", ".join(missing))
            else:
                add(5, "p0-merges", "PASS", "all %d P0 jobs have a merge on %s" % (len(jobs), branch))

    # 6. P1 done condition and the latest comparison figures
    done = p1_done_condition(roadmap) if roadmap is not None else None
    comparison = read_branch_file(repo, branch, "docs/COMPARISON.md")
    figures = comparison_figures(comparison) if comparison is not None else None
    if done is None:
        reason = "no P1 done condition found in docs/ROADMAP.md"
    else:
        reason = "P1 done when: " + done
    if figures:
        reason += "; comparison: " + figures
    else:
        reason += "; docs/COMPARISON.md has no figures" if comparison is not None else "; docs/COMPARISON.md is missing"
    add(6, "p1-figures", "INFO", reason)

    # 7. open or empty DIFFERENCES rows
    differences_path = None
    for candidate in ("DIFFERENCES.md", "docs/spec/DIFFERENCES.md"):
        if branch_has(repo, branch, candidate):
            differences_path = candidate
            break
    if differences_path is None:
        add(7, "differences", "FAIL", "DIFFERENCES.md is missing")
    else:
        open_count = count_open_differences(read_branch_file(repo, branch, differences_path))
        if open_count == 0:
            add(7, "differences", "PASS", "0 open or empty rows in %s" % differences_path)
        else:
            add(7, "differences", "FAIL", "%d open or empty rows in %s" % (open_count, differences_path))

    # 8. clean branch and the integ/main commit count (always INFO)
    status = git(repo, "status", "--porcelain", "--untracked-files=no")
    clean = status.returncode == 0 and not status.stdout.strip()
    count = git(repo, "rev-list", "--count", "%s..%s" % (main_ref, branch))
    if count.returncode == 0:
        add(8, "branch", "INFO", "%s is %s commits ahead of %s; working tree %s"
            % (branch, count.stdout.strip(), main_ref, "clean" if clean else "dirty"))
    else:
        add(8, "branch", "INFO", "cannot count %s..%s: %s; working tree %s"
            % (main_ref, branch, one_line(count.stderr.strip()) or "git error",
               "clean" if clean else "dirty"))

    # 9. the release tag is absent or points at main
    if version is None:
        add(9, "tag", "FAIL", "cannot check the tag without a version")
    else:
        tag = "v" + version
        tagged = git(repo, "rev-parse", "-q", "--verify", "refs/tags/%s^{commit}" % tag)
        if tagged.returncode != 0:
            add(9, "tag", "PASS", "no tag %s yet" % tag)
        else:
            tag_sha = tagged.stdout.strip()
            on_main = git(repo, "rev-parse", "-q", "--verify", main_ref)
            if on_main.returncode == 0 and on_main.stdout.strip() == tag_sha:
                add(9, "tag", "PASS", "tag %s points at %s" % (tag, main_ref))
            elif on_main.returncode == 0:
                add(9, "tag", "FAIL", "tag %s points at %s, not %s" % (tag, tag_sha[:12], main_ref))
            else:
                add(9, "tag", "FAIL", "tag %s exists but %s is unknown" % (tag, main_ref))

    # 10. latest tests.yml run on the branch head
    if not args.online:
        add(10, "ci", "SKIP", "not requested (use --online)")
    elif shutil.which("gh") is None:
        add(10, "ci", "FAIL", "gh is not installed")
    else:
        short_branch = branch
        if short_branch.startswith("refs/remotes/"):
            short_branch = short_branch.split("/", 2)[2]
        if remote and short_branch.startswith(remote + "/"):
            short_branch = short_branch[len(remote) + 1:]
        head = git(repo, "rev-parse", "-q", "--verify", branch)
        run = subprocess.run(["gh", "run", "list", "--workflow", "tests.yml", "--branch", short_branch,
                              "--limit", "1", "--json", "conclusion,headSha"],
                             cwd=str(repo), capture_output=True, text=True)
        if run.returncode != 0:
            add(10, "ci", "FAIL", "gh run list failed: " + (one_line(run.stderr.strip()) or "unknown error"))
        else:
            try:
                runs = json.loads(run.stdout)
            except ValueError:
                runs = None
            if not runs:
                add(10, "ci", "FAIL", "no tests.yml run found for %s" % short_branch)
            else:
                latest = runs[0]
                latest_sha = str(latest.get("headSha", ""))
                conclusion = str(latest.get("conclusion", "") or "")
                if head.returncode == 0 and latest_sha != head.stdout.strip():
                    add(10, "ci", "FAIL", "latest tests.yml run is %s, not branch head %s"
                        % (latest_sha[:12], head.stdout.strip()[:12]))
                elif conclusion == "success":
                    add(10, "ci", "PASS", "tests.yml succeeded on %s" % latest_sha[:12])
                else:
                    add(10, "ci", "FAIL", "latest tests.yml run on %s is %s"
                        % (short_branch, conclusion or "unknown"))

    # 11. build the wheel and check its file name
    if not args.build:
        add(11, "wheel", "SKIP", "not requested (use --build)")
    elif version is None:
        add(11, "wheel", "FAIL", "cannot check a wheel name without a version")
    else:
        archive = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", branch],
                                 capture_output=True)
        if archive.returncode != 0:
            add(11, "wheel", "FAIL", "git archive %s failed: %s"
                % (branch, one_line(archive.stderr.decode("utf-8", "replace"))))
        else:
            with tempfile.TemporaryDirectory(prefix="ail-release-check-") as work:
                source = Path(work) / "src"
                wheel_dir = Path(work) / "wheel"
                source.mkdir()
                wheel_dir.mkdir()
                try:
                    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tar:
                        try:
                            tar.extractall(source, filter="data")
                        except TypeError:
                            tar.extractall(source)
                except (tarfile.TarError, OSError) as error:
                    add(11, "wheel", "FAIL", "cannot unpack %s: %s" % (branch, error))
                else:
                    backend = source / "packaging" / "ail_wheel_backend.py"
                    code = ("import importlib.util,sys\n"
                            "spec=importlib.util.spec_from_file_location('ail_wheel_backend',sys.argv[1])\n"
                            "module=importlib.util.module_from_spec(spec)\n"
                            "spec.loader.exec_module(module)\n"
                            "print(module.build_wheel(sys.argv[2]))\n")
                    build = subprocess.run([sys.executable, "-c", code, str(backend), str(wheel_dir)],
                                           capture_output=True, text=True, timeout=900)
                    if build.returncode != 0:
                        detail = one_line(build.stderr.strip().splitlines()[-1] if build.stderr.strip() else "")
                        add(11, "wheel", "FAIL", "wheel build failed" + (": " + detail if detail else ""))
                    else:
                        names = [line.strip() for line in build.stdout.splitlines() if line.strip()]
                        name = names[-1] if names else ""
                        if name and version in name:
                            add(11, "wheel", "PASS", "built " + name)
                        else:
                            add(11, "wheel", "FAIL", "wheel name %r does not contain %s" % (name, version))

    passed = sum(1 for item in checks if item["status"] == "PASS")
    failed = sum(1 for item in checks if item["status"] == "FAIL")
    info = sum(1 for item in checks if item["status"] == "INFO")
    skipped = sum(1 for item in checks if item["status"] == "SKIP")
    summary = "%d pass, %d fail, %d info/skip" % (passed, failed, info + skipped)

    if args.json:
        print(json.dumps({"checks": checks, "pass": passed, "fail": failed, "info": info,
                          "skip": skipped, "summary": summary}, indent=2))
    else:
        width = max(len(item["name"]) for item in checks)
        for item in checks:
            print("%-4s  %2d %-*s  %s" % (item["status"], item["number"], width, item["name"],
                                          item["reason"]))
        print(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
