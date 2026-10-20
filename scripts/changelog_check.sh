#!/bin/sh
# DFMAIN-78: a branch must add its entry under `## [Unreleased]` in CHANGELOG.md. Catches the case where a release
# lands on main while the branch is open: the rebase merges cleanly, but the entry ends up under the released version.
set -eu

DEFAULT_BRANCH=${CI_DEFAULT_BRANCH:-main}

# GitLab job logs render ANSI colors too; NO_COLOR turns them off.
if [ -z "${NO_COLOR:-}" ]; then
    OK=$(printf '\033[32mOK\033[0m')
    FAIL=$(printf '\033[31mFAIL\033[0m')
    NOTE=$(printf '\033[1mNote:\033[0m')
else
    OK=OK
    FAIL=FAIL
    NOTE=Note:
fi

test -f CHANGELOG.md || { echo "$FAIL: CHANGELOG.md not found. This job expects a Keep a Changelog file in the repo root."; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# Intentional opt-out: [skip changelog-check] / [skip-changelog-check] in the title of the branch's open merge request.
# A branch pipeline only gets the title through the API, so this only runs in CI. No merge request yet (first push)
# means nothing to skip. If the title cannot be read the job fails: it cannot tell whether the branch opted out.
if [ -n "${CI_JOB_TOKEN:-}" ]; then
    code=$(curl -sS --get -o "$tmp/mrs.json" -w '%{http_code}' --header "JOB-TOKEN: $CI_JOB_TOKEN" \
        --data-urlencode "source_branch=$CI_COMMIT_BRANCH" --data-urlencode "state=opened" \
        "$CI_API_V4_URL/projects/$CI_PROJECT_ID/merge_requests") || code=000
    if [ "$code" != "200" ]; then
        echo "$FAIL: could not read the merge request title (HTTP $code), so the check cannot tell whether this branch opted out. Retry this job."
        exit 1
    fi
    titles=$(jq -r '.[].title' "$tmp/mrs.json") || { echo "$FAIL: unexpected answer from the merge request API. Retry this job."; exit 1; }
    if printf '%s\n' "$titles" | grep -qiE '\[skip[ -]changelog[ -]check\]'; then
        echo "SKIPPED: [skip changelog-check] found in the title of this branch's merge request."
        exit 0
    fi
fi

# A CI clone has no origin/main yet. Locally the check stays read-only and uses the origin/main already there.
if [ -n "${CI:-}" ]; then
    git fetch --quiet origin "$DEFAULT_BRANCH"
else
    echo "Compared with origin/$DEFAULT_BRANCH @ $(git log -1 --format='%h, %cr' "origin/$DEFAULT_BRANCH")."
    echo "$NOTE CI uses the latest $DEFAULT_BRANCH - run \`git fetch origin $DEFAULT_BRANCH\` first, or the pipeline may fail."
fi
BASE=$(git merge-base "origin/$DEFAULT_BRANCH" HEAD)

# Line numbers (in the CHANGELOG.md on disk, the file the next step reads) of everything the branch added.
# Against the working tree, not HEAD: locally the file may hold uncommitted edits (always with jj), which shift lines.
git diff --unified=0 --no-color "$BASE" -- CHANGELOG.md | awk '
  /^@@/ {
    match($0, /\+[0-9]+(,[0-9]+)?/)
    split(substr($0, RSTART + 1, RLENGTH - 1), r, ",")
    for (i = 0; i < (r[2] == "" ? 1 : r[2]); i++) print r[1] + i
  }' > "$tmp/added-lines.txt"

# An added entry (not blank, not a heading) must sit under `## [Unreleased]`.
awk -v ok="$OK" -v fail="$FAIL" -v added="$tmp/added-lines.txt" '
  BEGIN { while ((getline n < added) > 0) added_at[n] = 1 }
  /^## / {
    section = $0
    if (added_at[NR] && tolower($0) ~ /^## \[unreleased\]/) created++
  }
  added_at[NR] && $0 !~ /^[[:space:]]*$/ && $0 !~ /^#/ {
    if (tolower(section) ~ /^## \[unreleased\]/) unreleased++
    else { stray++; strays = strays sprintf("  line %d, under \"%s\": %s\n", NR, (section == "" ? "(no section)" : section), $0) }
  }
  END {
    # Any line added under a released version fails, even next to a proper [Unreleased] entry.
    if (stray > 0) {
      print fail ": this branch adds line(s) outside \"## [Unreleased]\" in CHANGELOG.md:"
      printf "%s", strays
      print "A release probably landed on main after the entry was written - move the entry to [Unreleased]."
    }
    else if (unreleased > 0) { printf "%s: this branch adds %d line(s) under [Unreleased].\n", ok, unreleased; exit 0 }
    # After a release the section is gone; a branch that creates it again is fine, even before any entry is under it.
    else if (created > 0) { print ok ": this branch creates the [Unreleased] section, with no lines under it yet."; exit 0 }
    else print fail ": this branch adds no entry under \"## [Unreleased]\" in CHANGELOG.md."
    print "Intentional? Put [skip changelog-check] in the merge request title, then retry this job."
    exit 1
  }' CHANGELOG.md
