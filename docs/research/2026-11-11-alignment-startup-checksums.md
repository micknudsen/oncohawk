# Alignment startup checksum activity — 2026-11-11

The user reported substantial CPU and I/O before the first Cutadapt task on a
SLURM cluster. Cluster logs, profiling data, and the exact deployed revision
were not available; this explanation is verified against the current checkout.

`workflows/oncohawk.nf` calls `alignmentReference(params.reference_bundle)`
synchronously before constructing the sample-input channel or invoking
`CUTADAPT`. That function validates `bundle.json` and streams every byte of
`reference.fa` and the five BWA-MEM2 index files (`.0123`, `.amb`, `.ann`,
`.bwt.2bit.64`, `.pac`) through SHA-256, comparing each result with the manifest.
The files are processed sequentially without loading entire files into memory.

This is workflow code executed by the Nextflow launcher, not a SLURM process.
Consequently it uses the launcher's host/allocation and is outside the resource
requests configured for individual pipeline tasks. It blocks Cutadapt startup.
There is no checksum-result cache or resume guard in this function: it runs on
every invocation reaching this code, including resumed runs, once per invocation
rather than once per sample. The amount read is the sum of the six artifact sizes;
elapsed time depends on hashing speed and effective filesystem throughput/cache.

The purpose is to reject missing or changed reference artifacts before processing
reads. This behavior is already described in `docs/alignment.md`. Sample-sheet
validation checks FASTQ paths and metadata; its row-ID SHA-256 hashes a small
metadata/path string, not FASTQ contents. The reference-download store belongs to
the separate preparation workflow and is not called by this alignment path.

This establishes a concrete explanation for the reported timing but does not
measure its contribution on the cluster or exclude other startup costs such as
container acquisition. No pipeline behavior was changed and no cluster run was
performed.

## Implementation follow-up — 2026-11-11

The investigation above describes the baseline behavior at `1dac7a3`. The accepted
policy and implementation scope are tracked in issues
[#33](https://github.com/micknudsen/oncohawk/issues/33) and
[#34](https://github.com/micknudsen/oncohawk/issues/34). Documentation PR
[#35](https://github.com/micknudsen/oncohawk/pull/35) passed required CI and was
merged before implementation began.

Implementation PR [#36](https://github.com/micknudsen/oncohawk/pull/36) makes
artifact hashing conditional on `--verify_bundle_checksums`, defaulting to off.
Seven focused public-workflow tests passed locally, including a permission-denial
test demonstrating that default startup does not open artifact contents. They
also cover explicit false, malformed manifests, missing artifacts, valid full
verification, and per-artifact corruption on resume. The initial default/false
regression failed against the old unconditional hashing before the change.
Nextflow lint reported no errors, all 55 pinned nf-core files matched upstream,
and both standards and specification review reported no findings.

At this checkpoint, the full local suite was still running. The first PR #36 CI
run, [43091806584](https://github.com/micknudsen/oncohawk/actions/runs/43091806584),
reported successful test, module-verification, cleanup, and Complete job steps,
but its overall job and required check remained in progress. Normal and force
cancellation reported it was not running, while rerun requests were rejected.
This documentation update triggers a fresh check; those successful steps alone
were not treated as a completed merge gate. No cluster performance claim follows
from the local tests or the CI step results.
