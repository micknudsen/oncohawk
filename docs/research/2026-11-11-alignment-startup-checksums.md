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
