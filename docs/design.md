# Oncohawk — alignment milestone design

Fresh session started 2026-11-01. The [requirements](requirements.md) contain the accepted restart brief. This document tracks only decisions needed for milestone 1.

**Status: milestone-1 scope decisions complete through Q8; initial implementation completed.** The [implementation plan](implementation-plan.md) and [acceptance record](milestone-1-acceptance.md) document that work. The [2026-11-01 pipeline-directory design](#pipeline-directory-separation--2026-11-01) is historical and superseded by the [2026-11-10 shared-dispatcher design](#public-workflow-architecture-review--2026-11-10). See the [dispatcher implementation checkpoint](#dispatcher-implementation-checkpoint--2026-11-10) for the first migration slice.

The milestone spec is published as [GitHub issue #1](https://github.com/micknudsen/oncohawk/issues/1), with the confirmed workflow-level testing boundaries.

The user's subsequent [execution-environment clarification](#execution-environment-clarification--2026-11-01) is also accepted.

## Minimal path

```text
NCBI FASTA + GRC exclusions BED -> mask reference -> prepare bwa-mem2 indexes -> reference bundle
Sequencing inputs -> Cutadapt (optional adapters + length filtering) -> mapping with reference bundle
  -> combine sample rows -> library-aware duplicate marking -> coordinate-sorted, indexed BAM per sample
```

The aligner, reference inputs, sequencing-input layout, preprocessing, mapping settings, and alignment deliverable are settled in Q1–Q8. The implementation plan groups the remaining routine choices and concrete acceptance checks.

## Decision dependencies

- Reference and aligner choices determine reference-bundle assets.
- Input and read-group requirements determine necessary preprocessing and mapping inputs.
- Alignment output requirements determine finishing steps and acceptance assertions.

Discuss one consequential unresolved decision at a time. Stop when this path is actionable; routine implementation details do not need individual questions.

## Q1 — Aligner for milestone 1

**Status: accepted on 2026-11-01.**

Should we use **bwa-mem2** for milestone 1?

Decision: use bwa-mem2. nf-core provides [reference indexing](https://nf-co.re/modules/bwamem2_index) and [mapping](https://github.com/nf-core/modules/blob/master/modules/nf-core/bwamem2/mem/main.nf) modules, providing a path that can use pristine upstream modules. The initial reference bundle will contain bwa-mem2 indexes.

Module support was checked against primary sources on 2026-11-01. Local Mac/Docker execution has not been tested. Q2 settles the reference inputs, Q7 the output contract, and Q8 the mapping settings.

## Q2 — Reference for milestone 1

**Status: accepted with the user's replacement on 2026-11-01.**

Decision: use the exact NCBI GRCh38 no-ALT analysis-set FASTA and matching GRC exclusions BED linked in [requirements](requirements.md#reference-preparation). Hard-mask the excluded regions with `N` bases before indexing, preserving sequence names, lengths, and coordinates. The masked sequence is the alignment reference.

The user replaced the proposed GENCODE primary-assembly FASTA with these explicit resources. No GENCODE reference was accepted. Both sources use the GRCh38 assembly, but different reference distributions must not be assumed interchangeable.

The earlier proposal was based on [GENCODE's primary-assembly download](https://www.gencodegenes.org/human/release_49.html). Reference preparation remains limited to alignment assets; no annotation resources are added.

Implementation evidence checked on 2026-11-01: [nf-core bedtools/maskfasta](https://nf-co.re/modules/bedtools_maskfasta/) accepts FASTA and BED inputs. [Bedtools documentation](https://bedtools.readthedocs.io/en/latest/content/tools/maskfasta.html) specifies `N` replacement as the default, with matching sequence IDs required. This supplies a suitable upstream step before index generation; no module was installed or run.

Reference evidence: [UCSC's support discussion reproducing NCBI's README](https://groups.google.com/a/soe.ucsc.edu/g/genome/c/RI7uDc7oG80) describes existing analysis-set masking, including chrY pseudoautosomal regions. The requested GRC exclusions add corrections for false duplications and contamination ([GRC explanation](https://genomeref.blogspot.com/2021/07/one-of-these-things-doest-belong.html)); the [U2AF1 study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8950341/) documents applying this mask with bedtools and reindexing. These corrections are separate from the analysis set's existing masks.

Verification limit: direct NCBI FTP access was unavailable during research. No full FASTA download, sequence-level comparison with GENCODE, BED-byte inspection, or checksum validation was performed. Check actual BED sequence membership when preparing the bundle: GRC's broader correction description includes an ALT scaffold that a no-ALT reference may omit.

## Q3 — Sequencing-input interface

**Status: accepted on 2026-11-01.**

Should milestone 1 accept a single sample sheet with one row per gzipped paired-end FASTQ pair and its read-group metadata?

Decision: use one sample sheet. Each row identifies R1/R2 files, sample, library, flowcell, and lane. Multiple rows may belong to the same sample. Each pair must contain reads belonging to one read group. This provides the mapping inputs and grouping information together; the exact sheet syntax and derived read-group values can be specified in the implementation plan.

The user also suggested an optional key-value column for additional row settings, such as adapter sequences. Q4 makes that suggestion concrete without selecting trimming behavior.

## Q4 — Optional row settings

**Status: accepted on 2026-11-01.**

Should we add an optional `options` column containing semicolon-separated `key=value` entries and accepting only documented keys?

Decision: add the optional `options` column. Initially support `r1_adapter` and `r2_adapter`. Allow blank cells; reject malformed entries, unknown keys, and repeated keys. An illustrative cell is:

```text
r1_adapter=AGATCGGAAGAGC;r2_adapter=AGATCGGAAGAGC
```

This decision settles serialization and basic validation only; Q5 settles adapter removal and per-mate settings. Q6 settles read filtering. Routine parser details belong in the implementation plan rather than separate interview questions.

## Q5 — Adapter removal

**Status: accepted on 2026-11-01.**

Should we use Cutadapt for adapter removal only when adapter sequences are supplied in the sample sheet?

Decision: use the pristine nf-core Cutadapt module. Treat `r1_adapter` and `r2_adapter` as regular 3′ adapter sequences for their respective mates. Either may be supplied alone. Remove the supplied adapters; when neither is supplied, skip adapter removal. Do not infer adapter sequences automatically. Q6 separately defines length and quality-filtering policy and confirms that the shared Cutadapt step still runs without adapters.

Primary sources checked on 2026-11-01: the [nf-core module](https://github.com/nf-core/modules/blob/master/modules/nf-core/cutadapt/main.nf) forwards configurable arguments and adds no length/quality filter by default. [Cutadapt's paired-end documentation](https://cutadapt.readthedocs.io/en/stable/guide.html#trimming-paired-end-reads) supports `-a` for R1 and `-A` for R2, including either alone. [Filtering documentation](https://cutadapt.readthedocs.io/en/stable/guide.html#filtering-reads) confirms that adapter removal alone retains reads even when trimmed to zero length. No filtering threshold or exact tool/module version is selected by this decision.

## Q6 — Minimal read filtering

**Status: accepted on 2026-11-01.**

Should we require both mates to be at least **15 bp** after optional adapter removal, with no additional quality trimming in milestone 1?

Decision: discard the whole pair if either mate is shorter than 15 bp; exactly 15 bp passes. Apply the same rule to every input pair, including already-trimmed reads and rows without adapter settings. Use one shared, pristine nf-core Cutadapt step for all rows. This removes empty/very short reads and keeps preprocessing consistent while preserving pairs. Do not add quality trimming in milestone 1.

Implementation evidence checked on 2026-11-01: [Cutadapt's guide](https://cutadapt.readthedocs.io/en/stable/guide.html#filtering-reads) documents length filtering after read modifications and pair removal with `-m 15 --pair-filter=any`; quality trimming requires a separate option. Filtering without adapters is supported ([official changelog](https://cutadapt.readthedocs.io/en/stable/changes.html#v1-7-2014-11-25)). The 15 bp threshold is the accepted workflow policy, not a Cutadapt requirement or an established optimal threshold.

The user asked whether inputs without adapters could share the same step. Yes: configure the module's supported `task.ext.args` per row, always including `-m 15 --pair-filter=any` and adding `-a`/`-A` only for supplied adapters. The [upstream module source](https://github.com/nf-core/modules/blob/master/modules/nf-core/cutadapt/main.nf) supports this without modification or a custom preprocessing module. Illustrative adapter-free command:

```sh
cutadapt -m 15 --pair-filter=any \
  -o R1.filtered.fastq.gz -p R2.filtered.fastq.gz \
  R1.fastq.gz R2.fastq.gz
```

This is a documented command shape, not an executed test. The nf-core module supplies threads, output names, and logging.

## Q7 — Alignment deliverable

**Status: accepted on 2026-11-01.**

Should milestone 1 produce one coordinate-sorted, indexed BAM per sample, with duplicates marked per library?

Decision: combine the sample's rows while preserving read groups. Detect duplicates across lanes/read groups belonging to the same library, keep different libraries separate for duplicate detection, and retain duplicate reads with their flags set. Produce one coordinate-sorted, indexed BAM per sample. This defines the sample-level alignment endpoint.

Primary sources checked on 2026-11-01: nf-core provides [samtools/merge](https://nf-co.re/modules/samtools_merge) and [picard/markduplicates](https://nf-co.re/modules/picard_markduplicates). [Picard's library-ID implementation](https://github.com/broadinstitute/picard/blob/master/src/main/java/picard/sam/markduplicates/util/LibraryIdGenerator.java) uses read-group `LB` values to identify libraries. Duplicate marking must see all relevant reads from a library together; exact module composition remains an implementation detail.

## Q8 — Mapping settings

**Status: accepted on 2026-11-01.**

Should mapping enable supplementary soft clipping with `-Y`, assign each FASTQ pair's read-group header with `-R`, and otherwise use bwa-mem2's default mapping settings?

Decision: enable `-Y`, supply read-group headers through `-R`, and otherwise use default mapping settings. Soft clipping retains the complete read supplied to the aligner in supplementary records, including clipped bases. Here that means the preprocessed read, after any adapter removal. Read-group headers carry the agreed sample/library metadata into the BAM. Resource settings and supported module configuration remain implementation details.

Primary sources checked on 2026-11-01: [bwa-mem2's options](https://github.com/bwa-mem2/bwa-mem2/blob/master/src/fastmap.cpp#L588-L603) document `-Y` and `-R`; the [nf-core mapping module](https://github.com/nf-core/modules/blob/master/modules/nf-core/bwamem2/mem/main.nf#L24-L44) accepts both through `task.ext.args`. No module modification is needed. The next step is review of the small implementation plan, rather than more routine option questions.

## Execution-environment clarification — 2026-11-01

The user clarified that development takes place locally on a Mac using Docker and synthetic data; the Mac lacks memory for bwa-mem2 on the entire human reference. Production runs on a SLURM HPC with Apptainer. Recorded this directly in [requirements](requirements.md#execution-environments) and the [plan](implementation-plan.md#execution-environments), without reopening the interview.

Local tests use a small synthetic reference, matching BED, and reads. Full NCBI reference preparation and alignment target the HPC. Workflow logic and upstream modules stay shared, with profiles and test inputs providing the environment/data differences. ARM64 container compatibility remains an early local check independent of the reduced-reference memory footprint.

## Testing-boundary confirmation — 2026-11-01

During the explicitly requested to-spec synthesis, the user confirmed two public testing boundaries: reference inputs to a prepared reference bundle, and a prepared bundle plus sample sheet/FASTQs to final BAMs. Add one end-to-end composition test and assert observable outputs/errors rather than private helper structure. This confirms the testing approach without reopening the milestone interview or selecting implementation internals.

## HPC acceptance clarification — 2026-11-01

During ticket planning, the user specified that they will check SLURM/Apptainer operation informally along the way and report problems. HPC tests must never be formal acceptance criteria. Removed the proposed standalone HPC-verification ticket; production profiles and usage instructions belong to the reference-preparation and alignment slices.

Formal workflow acceptance remains based on compact synthetic tests with Docker locally and in required CI. Do not wait for HPC access, results, or sign-off to complete tickets or the milestone. No reported HPC problem means no HPC blocker; record actual evidence accurately without calling silence a verified run. This clarification supersedes the earlier proposal for a required full-reference HPC verification run.

## Pipeline directory separation — 2026-11-01

**Historical status: accepted and authorized on 2026-11-01. The separate public entrypoints were superseded by the shared-dispatcher decision on 2026-11-10. Configuration isolation, reference provenance, and the pre-release compatibility policy remain applicable.**

Give reference preparation and alignment separate pipeline directories, each with its own `main.nf` and `nextflow.config`: `pipelines/reference/` and `pipelines/alignment/`. Selecting a pipeline should load its process configuration without selectors belonging only to the other pipeline.

The user accepted a clean migration to `nextflow run pipelines/reference` and `nextflow run pipelines/alignment`, removing the root `reference.nf` and `alignment.nf` entrypoints without compatibility wrappers. Update documentation, tests, and their callers together. Shared modules remain shared. The user confirmed the complete migration scope before implementation. Update the public workflow tests to reject unmatched-process-selector warnings and verify reference provenance and the output defaults.

Ask only one question per interview round.

### Default output directories

**Status: accepted on 2026-11-01.**

Reference preparation defaults to `reference`; alignment defaults to `alignments`. Both pipelines allow `--outdir` to override the default. The output-directory name does not rename the reference-bundle domain concept.

### Reference source provenance

**Status: accepted on 2026-11-01.**

Reference bundles record source hashes for reference-preparation files and the shared files used by reference preparation. Exclude files belonging exclusively to the separate alignment workflow, including its entrypoint and process configuration. Replace the current broad configuration-file collection accordingly; editing alignment-only files must not change the reference source-hash set or values. Repository commit identity remains separate provenance and may change after any commit.

### Cluster configuration separation

**Status: accepted on 2026-11-01.**

Keep cluster-specific settings (SLURM partition and account, Nextflow work directory, and Apptainer cache directory) in one shared site configuration. Keep process-specific CPU, memory, and time settings in separate reference-preparation and alignment resource files. Each pipeline loads only its own process-resource settings, so a shared site configuration does not introduce selectors for the other pipeline.

### Pre-release compatibility policy

**Status: accepted on 2026-11-01.**

Before the first official pipeline release, backward compatibility must never constrain changes. Every commit may break functionality, including existing commands, configuration, interfaces, and artifact formats. Do not add compatibility wrappers or migration machinery solely to preserve earlier pre-release behavior. Keep current documentation and tests consistent with the intended behavior; permission to break compatibility does not remove validation requirements. This policy applies to pre-release development generally, not only the pipeline-directory migration.

## Public workflow architecture review — 2026-11-10

**Status at the design checkpoint on 2026-11-10: accepted; final shared understanding confirmed, including sample-first output grouping and `results/execution/`. Implementation had not been authorized or started at that checkpoint.**

The synthesized specification is published as [GitHub issue #25](https://github.com/micknudsen/oncohawk/issues/25), labeled `ready-for-agent`. It carries forward the accepted public workflow and configuration testing boundaries through the root dispatcher. Publication does not authorize implementation.

On 2026-11-10, the specification was split into three sequential implementation issues: [#26 — shared dispatcher, configuration isolation, and reference provenance](https://github.com/micknudsen/oncohawk/issues/26), [#27 — sample-first analysis outputs](https://github.com/micknudsen/oncohawk/issues/27), and [#28 — enabled execution diagnostics](https://github.com/micknudsen/oncohawk/issues/28). Each includes its own tests and documentation and is intended for one focused PR, merged after required CI passes before the next issue starts. Issue #25 remains the parent acceptance specification. The first slice temporarily retains the existing analysis output layout; the second and third complete the accepted output organization. This sequence did not revise the final design or start implementation.

Later on 2026-11-10, the user authorized implementing the open issues one at a time using the implement skill, creating a PR for each, fixing CI failures, and merging only after all CI tests pass. The user also authorized a separate PR for the existing documentation changes. This subsequent instruction authorizes the implementation sequence without changing the accepted design.

The user reaffirmed the intended three-workflow structure and accepted the public names `prepare_reference_bundle`, `prepare_knowledge_bundle`, and `oncohawk`, selected through the shared root `main.nf`. The existing requirements already place alignment within the report-generation workflow and defer knowledge preparation beyond milestone 1. At the design checkpoint, the standalone alignment entrypoint implemented that milestone portion; it does not establish a fourth conceptual workflow.

This review revises the public entrypoint structure accepted on 2026-11-01. The reason for that earlier separation was isolation of workflow-specific process configuration. The earlier record contained no accepted shared-dispatcher decision; Q1–Q5 below establish the new design while preserving configuration isolation.

### Q1 — Dispatch behavior

**Status: accepted on 2026-11-10; design decision only.**

The shared entrypoint selects exactly one of `prepare_reference_bundle`, `prepare_knowledge_bundle`, or `oncohawk` per invocation. Bundle preparation is invoked explicitly; `oncohawk` consumes prepared bundles. The dispatcher does not automatically chain preparation and analysis. This does not expand the current alignment milestone to require a knowledge bundle.

### Q2 — Workflow selection syntax

**Status: accepted on 2026-11-10; design decision only.**

Use `--workflow` with the three accepted workflow names. Omitting it selects `oncohawk`; explicitly specifying `--workflow oncohawk` selects the same workflow. Bundle preparation requires `--workflow prepare_reference_bundle` or `--workflow prepare_knowledge_bundle`. The usual analysis invocation therefore does not need a workflow selector.

### Q3 — Deferred knowledge preparation

**Status: accepted on 2026-11-10; design decision only.**

Until knowledge preparation is implemented, selecting `prepare_knowledge_bundle` must fail immediately with a clear not-yet-implemented error. Recognizing its name must not produce an empty bundle or silently run a different workflow.

### Q4 — Analysis output layout

**Status: revised sample-first layout accepted on 2026-11-10; design decision only.**

Use `results` as the default `oncohawk` output directory; `--outdir` overrides that root. The initial choice to put all samples' BAMs and indexes under `results/alignments/` was reconsidered and superseded by the sample-first layout below.

Group sample deliverables under `results/samples/<sample>/`, with artifact-type subdirectories such as `alignments/`. The current milestone publishes `<sample>.bam` and `<sample>.bam.bai` under `results/samples/<sample>/alignments/`, retaining sample IDs in filenames so copied files remain identifiable. Future variants and reports belong alongside those alignments within each sample directory. Keep any enabled run-wide diagnostics or summaries in a separate `results/execution/` namespace. The name `execution` was accepted in place of `run` on 2026-11-10. Sample-first grouping keeps one sample's deliverables together for inspection, transfer, and archiving. This output-organization decision does not authorize variant calling, reporting, new diagnostic generation, or empty placeholder directories. The current alignment-only scope and default reference-bundle destination are unchanged.

### Q5 — Internal workflow layout

**Status: accepted on 2026-11-10; design decision only.**

Keep root `main.nf` responsible for workflow selection and top-level publication, with the three workflow implementations in `workflows/prepare_reference_bundle.nf`, `workflows/prepare_knowledge_bundle.nf`, and `workflows/oncohawk.nf`. The knowledge workflow is initially only the explicit not-yet-implemented failure. Root `nextflow.config` selects shared and workflow-specific settings from `conf/`; shared process modules remain under `modules/`.

Preserve configuration isolation and reference-only provenance boundaries when changing the layout: selecting one workflow must not load process selectors belonging only to another, and changes to analysis-only sources must not affect the reference source-hash set. Input requirements remain specific to the selected workflow. These are existing constraints, not additional analysis scope.

### Shared-understanding checkpoint

The intended migration exposes only the root dispatcher, replacing the separate `pipelines/reference` and `pipelines/alignment` public entrypoints without compatibility wrappers, consistent with the accepted pre-release policy. Existing analysis remains alignment-only and needs a sample sheet and prepared reference bundle, with no knowledge-bundle requirement yet. Reference preparation keeps its current inputs and default `reference` output directory. Tests and operator documentation must follow the new entrypoint and analysis output layout while preserving workflow behavior, readable task tags, download reuse, and provenance boundaries. The user confirmed this combined design on 2026-11-10. At that checkpoint, the design interview was complete and implementation remained a separate task; the subsequent authorization is recorded above.

## Dispatcher implementation checkpoint — 2026-11-10

The first implementation slice, [#26](https://github.com/micknudsen/oncohawk/issues/26), moves selection and top-level publication to root `main.nf`, with workflow implementations under `workflows/` and selected configuration under `conf/`. It removes the former standalone pipeline entrypoints. Omitted and explicit `oncohawk` selection share the alignment path; reference preparation remains explicit; unknown names and deferred knowledge preparation fail before tasks or unrelated input validation.

This slice deliberately retains flat BAM/index publication and default `alignments`, while reference preparation retains its default `reference` destination and bundle format. The sample-first `results` layout accepted in Q4 is delivered by #27; enabled diagnostic placement follows in #28. This staged implementation does not revise the final design or introduce deferred analysis features. Required CI and acceptance evidence must be checked on the corresponding PR; this checkpoint makes no new validation or merge claim.

## Bundle validation during analysis — 2026-11-11

### Q1 — Everyday validation

**Status: accepted on 2026-11-11; design decision only, not implemented.**

Normal analysis runs check the bundle manifest's structure and supported format
version and confirm that required artifact files exist. They do not read artifact
contents or calculate artifact checksums during startup. Missing required files
must still fail before processing reads. Full integrity verification requires an
explicit action, selected through the flag accepted in Q2 below.

This revises the current implementation's unconditional reference FASTA and
BWA-MEM2 index hashing before Cutadapt. The observed submission-host CPU and I/O
cost and code inspection are recorded in
[the startup investigation](research/2026-11-11-alignment-startup-checksums.md).
Existing FASTQ path and metadata checks remain applicable. This decision does
not introduce a knowledge-bundle requirement for the alignment milestone.

### Q2 — Explicit checksum verification

**Status: accepted on 2026-11-11; design decision only, not implemented.**

The `--verify_bundle_checksums` flag enables full integrity verification before
an `oncohawk` run continues to processing reads. It defaults to off. When enabled,
verify all required bundle artifacts against their manifest checksums and fail
on any mismatch.

### Q3 — Verification execution location

**Status: accepted on 2026-11-11; design decision only, not implemented.**

Keep optional checksum verification in the Nextflow launcher on the submission
host for now. Stream one artifact at a time, retaining the current bounded-memory,
sequential approach. The user considers this acceptable for explicitly requested
verification. Do not introduce a separate executor-managed verification task.
When requested, verification runs once per invocation, including resumed runs,
and must succeed before read-processing tasks can start.

### Shared-understanding checkpoint

**Status: accepted on 2026-11-11; final shared understanding confirmed. Implementation has not been authorized.**

The implementation should make artifact-content verification conditional on
`--verify_bundle_checksums`, defaulting to off, while preserving manifest checks,
required-file checks, and sample-sheet/FASTQ path validation. Keep the reference
bundle format and preparation-time checksum generation unchanged. The current
alignment milestone consumes only the reference bundle; this change does not
add knowledge-bundle functionality.

Acceptance checks should establish that default startup performs no artifact
content reads for validation; malformed or unsupported manifests and missing
required artifacts still fail before read processing; and explicit verification
accepts valid artifacts and rejects checksum mismatches before Cutadapt starts.
Update the current corruption regression and operator documentation to describe
both modes. A normal run is not expected to detect content corruption during
startup; downstream tools may still reject corrupt inputs.

The user confirmed the combined design on 2026-11-11, completing this design
interview. Implementation requires a separate instruction.

The synthesized specification is published as
[GitHub issue #33](https://github.com/micknudsen/oncohawk/issues/33), labeled
`ready-for-agent`. The user also confirmed the existing public alignment-workflow
acceptance tests as the testing seam on 2026-11-11. Publication does not authorize
implementation.

On 2026-11-11, the user approved one complete implementation slice for this
specification. It is published as
[sub-issue #34](https://github.com/micknudsen/oncohawk/issues/34), labeled
`ready-for-agent`, with no blockers. The single PR should deliver both validation
modes, public-workflow tests, and operator documentation together. No prerequisite
refactor is needed. Ticket publication does not authorize implementation.

Later on 2026-11-11, the user authorized a documentation PR merged after passing
CI, followed by implementation of #34 with the implement skill and a separate
PR merged after passing CI. The documentation PR is
[#35](https://github.com/micknudsen/oncohawk/pull/35), merged as `3db405b` after
the required Tests and validation check passed. This subsequent authorization
supersedes the earlier implementation-authorization checkpoint without changing
the accepted design.

## Deferred

Knowledge compilation, variant calling, variant reconciliation, annotation, reporting, and their resources remain outside this milestone.
