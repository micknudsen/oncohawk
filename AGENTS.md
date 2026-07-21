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
