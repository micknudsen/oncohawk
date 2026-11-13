# Nextflow and nf-core resource-retry precedents — 2026-11-13

This investigation addresses how existing Nextflow projects retry resource-related
failures. It establishes documented mechanisms and concrete examples, not the
frequency of their use across all pipelines. No pipeline behavior was changed
and no cluster run was performed.

## Official Nextflow guidance

Nextflow documents dynamic resource requests combined with `errorStrategy` and
`maxRetries`. Its example increases memory and wall time linearly with
`task.attempt`, retries exit statuses 137–140, and terminates for other statuses.
The first attempt is numbered 1; the retry count excludes that initial attempt.
The same page offers previous-attempt trace metrics for resource calculations
and backoff for temporary failures. These are supported building blocks and
examples, rather than a universal scheduler-independent timeout detector.
[Official process documentation](https://docs.seqera.io/nextflow/process/#dynamic-task-resources)

For request ceilings, Nextflow provides `resourceLimits`: requests above a
configured limit are reduced before submission. This mechanism alone does not
implement an error for an initial request above the cap, or prevent a retry at an
unchanged capped allocation.
[Official resourceLimits documentation](https://docs.seqera.io/nextflow/reference/process/directives/resource-limits)

## Concrete nf-core examples

The inspected nf-core pipeline template uses a broad exit-status set:
130–145, 104, and 175–177. Matching failures retry; others use `finish`.
Its default is one retry, with `maxErrors = -1`. Memory and time grow linearly
with the attempt number, as do many CPU allocations; some labels keep CPU count
fixed. An `error_retry` label separately specifies unconditional retries and two
retries. There is no custom Slurm accounting lookup in this base file.
[nf-core/tools template base.config](https://github.com/nf-core/tools/blob/main/nf_core/pipeline-template/conf/base.config)

The inspected RNA-seq base configuration uses the same exit-status set, default
retry count, and attempt-based resource pattern. Its global starting time is four
hours, with resource labels overriding allocations.
[nf-core/rnaseq base.config](https://github.com/nf-core/rnaseq/blob/master/conf/base.config)

The inspected Sarek base configuration also uses this retry condition and default
retry count. Its global starting time is eight hours, and it contains label- and
process-specific resource overrides. This base file likewise contains no custom
Slurm accounting classifier.
[nf-core/sarek base.config](https://github.com/nf-core/sarek/blob/master/conf/base.config)

These are checked `main`/`master` branch snapshots, which can change. A released
pipeline, process-specific selector, or institutional configuration may differ.
The inspected policies classify exit statuses; they do not establish that every
retried failure was a timeout. The evidence supports calling this a concrete
nf-core convention, without claiming every Nextflow project follows it.

## Implications for the Oncohawk discussion

On 2026-11-13, an earlier design proposed SLURM-only retries in both workflows,
at most two retries, wall-time multipliers 1, 2, and 4, unchanged CPU and memory,
and a configurable 48-hour default cap. It stopped when another attempt could
not receive more time and rejected initial allocations above the cap. Those choices differ from the inspected
nf-core defaults. The user subsequently explicitly selected the simpler community
approach, superseding these custom rules.

Inference: using a bounded exit-status policy follows the documented
Nextflow mechanism and the inspected nf-core examples, without introducing
custom timeout detection. On 2026-11-13 the user confirmed the community approach:
Sarek-style broad retry selection, one retry, attempt-based resource growth, and
optional native caps through user/site configuration, without a built-in global
production cap. The SLURM-only scope for both workflows remains. The agreed
policy is recorded in [specification #40](https://github.com/micknudsen/oncohawk/issues/40),
with delivery tracked by [implementation ticket #41](https://github.com/micknudsen/oncohawk/issues/41).
At the time of this investigation, no retry implementation or cluster validation
had been performed. The specification and implementation ticket are the
canonical sources for the accepted design and delivery requirements.

## Sarek caps follow-up — 2026-11-13

A source-archive search pinned to Sarek commit
`786a11bb4f989751d1c4bb87908ffc6096635ff3` covered `conf/`, `lib/`, `docs/`,
`nextflow.config`, and `nextflow_schema.json` for `resourceLimits`, `max_cpus`,
`max_memory`, `max_time`, and `check_max`. It found no global production cap
definition in those files. This is narrower than saying Sarek cannot use caps:

- The [test profile](https://github.com/nf-core/sarek/blob/786a11bb4f989751d1c4bb87908ffc6096635ff3/conf/test.config#L12-L17)
  explicitly caps requests at 4 CPUs, 15 GB, and 2 hours.
- A [full-test Parabricks selector](https://github.com/nf-core/sarek/blob/786a11bb4f989751d1c4bb87908ffc6096635ff3/conf/test_full.config#L30-L39)
  caps its requests at 96 CPUs and 370 GB.
- The [usage tutorial](https://github.com/nf-core/sarek/blob/786a11bb4f989751d1c4bb87908ffc6096635ff3/docs/usage/variantcalling/sarek.md#L84-L100)
  gives a small-environment cap example of 2 CPUs, 6.5 GB, and 2 hours.
- The [main configuration](https://github.com/nf-core/sarek/blob/786a11bb4f989751d1c4bb87908ffc6096635ff3/nextflow.config#L325-L333)
  includes external nf-core institutional configuration. Selected external
  profiles and user configuration can supply additional caps; they were not all
  audited here.

Older Sarek releases differ. The official 3.4.1 parameters document defaults of
16 CPUs, 128 GB, and 240 hours through `max_cpus`, `max_memory`, and `max_time`.
[Sarek 3.4.1 parameters](https://nf-co.re/sarek/3.4.1/parameters)

nf-core's tools 3.0 migration guidance explains that native Nextflow
`resourceLimits` replaced its `check_max` helper and associated maximum-resource
parameters. An old release's documented defaults therefore should not be
presented as current defaults without checking its actual version.
[nf-core tools 3.0 migration guidance](https://nf-co.re/blog/2024/tools-3_0_0#the-check_max-function-has-been-removed)
