# OncoHawk contributor and agent guardrails

## Scope

This file applies to the entire repository. It governs contributor workflow,
change control, and evidence claims. It does not define scientific behavior.
Scientific requirements belong in explicitly approved specifications when those
documents exist.

OncoHawk is intended to be a Nextflow pipeline for AML/MDS whole-genome
sequencing, and tumor-only analysis is the current working scope. These
statements do not settle the runtime, intended use, assay, supported inputs,
variant classes, outputs, or clinical role.

Current repository truth is:

- no implemented analytical behavior;
- no analytical or scientific validation;
- no release; and
- no basis for clinical-readiness or patient-care claims.

## Permission boundaries

Repository work requires explicit, scope-specific authorization. General
approval, discussion, planning, or statements such as "continue" do not expand
the authorized scope.

Treat these permissions as distinct:

- inspection and planning;
- local file implementation and verification;
- Git state changes, including creating or switching branches and committing;
- external changes, including issues, pushes, pull requests, releases, and
  repository settings; and
- merging.

Permission for one category does not imply permission for another. Do not begin
a later increment merely because the current increment is complete.

Stop and request a revised proposal if approved work grows materially, requires
a new scientific or architectural decision, encounters missing tooling, or
suggests a custom workaround.

## Three gates

### 1. Proposal gate

Before requesting implementation permission, perform read-only inspection and
present one issue-sized proposal containing:

1. goal and rationale;
2. exact scope;
3. explicit non-goals;
4. files expected to change;
5. external state expected to change;
6. decisions the change would make;
7. open or provisional matters it would preserve;
8. acceptance criteria;
9. tests or other verification;
10. risks and rollback; and
11. later permissions required for commit, push, pull request, merge, release,
    or repository settings.

Do not modify files, Git state, dependencies, generated resources, or external
services at this gate.

### 2. Implementation gate

After unmistakable approval of the named proposal, make only the approved local
changes and perform only the approved verification. Preserve unrelated user
work. Do not install dependencies, download data, run state-producing workflows,
or add substitutes and workarounds unless they are explicitly in scope.

Local implementation permission does not authorize a branch, commit, issue,
push, pull request, release, settings change, or merge.

### 3. Publication gate

Publication actions require explicit authorization for their stated scope.
`master` is the intended protected default branch; do not infer that protection
is configured without verification. Every change must reach `master` through
one primary issue, one short-lived branch, and one focused pull request. Required
CI checks must pass before merge. Never merge without explicit permission.

Creating an issue, creating or switching a branch, committing, pushing, opening
or editing a pull request, changing repository settings, releasing, and merging
remain separate permission boundaries unless the owner explicitly authorizes a
named combination.

Open pull requests ready for review by default. Use a draft pull request only
when the owner explicitly requests one or a concrete known blocker makes the
change unready for review. When a blocker requires draft status, state the
blocker clearly.

### Standing post-merge cleanup authorization

When the owner explicitly states that a pull request has been merged, that
statement authorizes the following post-merge cleanup without separate
permission for each listed Git or GitHub action:

1. Resolve the pull request unambiguously and verify through GitHub that it is
   merged.
2. Record its exact head repository, branch, and commit. Require a clean working
   tree, and verify that any matching local branch still points to that commit.
3. Refuse cleanup if the pull request or branch is ambiguous or unverified; if
   the working tree is dirty; or if the deletion target is a default, protected,
   or unrelated branch.
4. Delete the exact remote head branch if it still exists. Treat an already-
   absent remote branch as successfully cleaned up; stop on any other deletion
   failure.
5. Switch to `master`, fetch and prune `origin`, and update local `master` only
   with `git merge --ff-only origin/master`. Stop rather than reset, rebase,
   force, or otherwise resolve divergence automatically.
6. Delete the exact local head branch. Use ordinary deletion when possible. A
   forced local deletion is permitted only when GitHub verified the pull request
   as merged and the local branch still matched the recorded head commit before
   switching to `master`; this accommodates squash merges.
7. Verify that local `master` is clean and synchronized with `origin/master`,
   then propose one next issue-sized increment without beginning it.

This standing authorization does not authorize merging, releasing, changing
repository settings, creating the proposed next issue, or implementing or
publishing the next increment. Codex sandbox, Auto-review, managed policy, and
command-rule enforcement remain independent controls and may still deny an
action.

### Staged proposal-to-PR authorization

After a next issue-sized increment has been proposed, the owner may advance it
through these three explicit stages. Completion of one stage does not imply
acceptance of the next.

1. **Accept proposal.** When the owner unambiguously accepts the latest
   proposal, create exactly one GitHub issue containing it. Do not create a
   branch, modify files, install or download dependencies, generate resources,
   run state-producing workflows, commit, push, or open a pull request.
2. **Accept issue.** When the owner subsequently and unambiguously accepts that
   issue, create and switch to one short-lived branch, perform only its local
   implementation, and run only its approved verification. Ask all material
   questions needed to complete the issue before implementing behavior affected
   by an unresolved answer; independent work whose requirements are settled may
   continue. This stage authorizes only dependencies, downloads, generated
   resources, and state-producing workflows explicitly listed in the accepted
   issue. If answers or discoveries materially change the goal, files, external
   state, decisions, risks, dependencies, or verification, stop and present a
   revised proposal for acceptance. When local work and verification are
   complete, report that the issue appears ready; do not commit or publish.
3. **Make PR.** When the owner says `make PR` for that completed issue, stage
   only its intended files, create one focused commit, push its short-lived
   branch, open one ready-for-review pull request targeting `master`, link the
   pull request so merging it closes the primary issue, and confirm required CI
   status. This stage does not authorize merging.

At every stage, stop on ambiguity, unrelated or dirty worktree changes, failed
verification, or a scope conflict. After the owner reports the pull request as
merged, apply the standing post-merge cleanup authorization and return to a
proposal for the next increment.

## Development discipline

- Work in small, self-contained, testable, and reviewable increments.
- Do not create a broad scaffold or empty placeholders for a planned tree.
- Create a document only when the approved increment gives it substantive
  content.
- Record missing scientific details as open; never invent them to unblock work.
- Require OncoHawk-specific justification for assay design, preprocessing,
  callers, thresholds, references, validation, and reporting.
- Do not install tooling or implement a substitute when required tooling is
  unavailable without first obtaining approval.
- Do not write a custom process or workaround merely to bypass an unresolved
  dependency, upstream-component, runtime, or scientific decision.
- Preserve existing user changes and report conflicts rather than silently
  choosing a winner.

The proposed provenance, clinician-readable resource, synthetic-first testing,
nf-core module purity, HPC execution, compatibility, and optimization principles
are candidates awaiting project-owner reaffirmation. Do not present them as
approved repository policy until that confirmation occurs.

## Truth and evidence

Keep these authorities distinct:

1. Code, configuration, machine schemas, and tests provide evidence of current
   implemented behavior. Tests prove only what they assert.
2. Approved specifications define target contracts and must retain explicit
   decision states for their requirements.
3. Project plans define sequencing, dependencies, gates, and completion
   criteria; they do not define scientific behavior by themselves.
4. ADRs preserve rationale for consequential choices among real alternatives;
   they are not canonical schemas or operational instructions.

Do not describe prose as implemented behavior. Do not describe engineering-test
success as analytical validation. Do not describe a draft validation plan as
validation evidence. When authorities conflict, report the conflict and resolve
it through the applicable approval process rather than silently selecting one.

## Scientific and release claims

Keep intended use, research or clinical role, specimen and assay requirements,
variant-class scope, input/output contracts, reporting claims, and validation
requirements open until they are explicitly decided and supported by the
appropriate evidence.

Until intended use, validation, review, and release requirements are defined and
satisfied, do not call OncoHawk clinically ready or suitable for patient-care
decisions.
