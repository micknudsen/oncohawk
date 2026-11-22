# Prepare a reference bundle

The reference-preparation entry point, `nextflow run . --workflow prepare_reference_bundle`, validates reference inputs, decompresses a gzipped FASTA, hard-masks BED intervals with `N`, and builds bwa-mem2 indexes, a FASTA index, and a sequence dictionary from that exact masked sequence. It also prepares a matching RefSeq-only VEP cache and a separate unmasked Ensembl annotation FASTA/index, validates compatibility, and publishes the reusable bundle after successful validation and tool execution. This selection runs only reference preparation; it needs no sample sheet and does not run analysis. Selecting `prepare_knowledge_bundle` instead fails immediately because knowledge compilation is deferred. Replace `.` with the checkout path to launch from another directory; relative input and output paths resolve from the launch directory.

## Runtime pins

Use Java **21.0.13+9** and [Nextflow **26.10.6**](https://github.com/nextflow-io/nextflow/releases/tag/v26.10.6). The standalone release asset `nextflow-26.10.6-dist` has SHA256 `80e5332f37cd9a3b328fb843271209e090d91a7813f238e92f4efe3b5ee5d8d9`; the required CI workflow verifies this digest before execution. Python **3.12** runs the standard-library acceptance tests. Docker supplies local task execution; production requires SLURM and Apptainer.

The modules were installed with nf-core CLI **4.2.1** at upstream revision `20c6e6407f63748003b47f92837b64fb0a53ffa4`, recorded in [modules.json](../modules.json). `gunzip`, `bedtools/maskfasta`, `bwamem2/index`, `samtools/faidx`, and `picard/createsequencedictionary` remain pristine, including their upstream container pins. Actual Docker execution reported gzip **1.13**, bedtools **2.31.1**, and bwa-mem2 **2.2.1**. The upstream bwa-mem2 Conda environment declares 2.3, but that environment is not executed: Conda is unsupported. The manifest records executed versions rather than inferring them from unused environment metadata.

The custom download, validation, and packaging steps implement Oncohawk's input and bundle contracts; their runtime is Python **3.12.16** (Bookworm), pinned as `python@sha256:a5bab0ff300f91231c2e68bf73a8a8d60762ac39ce1c50eaf6803e4c38a9062b`. The digest-only reference works with Docker and Apptainer; combining a tag and digest is rejected by Apptainer. Bioinformatics operations remain in the pristine upstream modules. Executed tool versions and workflow source hashes are recorded in each bundle.

Required CI checks every installed module file against its pinned upstream Git object, including missing or added files. Upstream snapshots contain trailing whitespace, so `.gitattributes` exempts only `modules/nf-core/` from whitespace formatting checks; the stricter upstream integrity check protects those bytes. Project code and documentation retain whitespace checks.

## Inputs and masking

Reference preparation accepts only the pipeline parameter names below plus
`workflow`. Analysis-only parameters such as `input`, `reference_bundle`, and
`verify_bundle_checksums` are rejected before input processing or task submission.
The [strict parameter policy](../README.md) applies to CLI, parameter files, and
configuration files, including previously ignored custom parameters. Select a
Nextflow profile with `-profile` (one dash); `--profile` fails with a correction.

| Parameter | Meaning |
| --- | --- |
| `--fasta` | Local `.fa`/`.fa.gz` or a downloadable FASTA URL. Defaults to the selected NCBI no-ALT analysis set below. |
| `--exclusions_bed` | Local exclusions BED or downloadable BED URL. Defaults to the matching NCBI exclusions below. |
| `--annotation_fasta` | Local unmasked `.fa`/`.fa.gz` or URL; defaults to Ensembl release-116 GRCh38 primary assembly. This is separate from the alignment FASTA. |
| `--vep_cache` | Local `.tar.gz` or URL containing a genuine compatible human GRCh38 RefSeq-only cache 116. |
| `--annotation_fasta_sha256`, `--vep_cache_sha256` | Expected SHA256 for custom annotation sources; hashes cover original compressed bytes. Official source checksums are fixed. |
| `--annotation_fasta_identity`, `--vep_cache_identity` | Optional dataset/release/assembly identity objects for custom sources, following the existing source-identity rules. RefSeq versions come from cache metadata; MANE provenance comes separately from pinned matching-release core metadata. |
| `--outdir` | New directory for the completed bundle; default `reference`. Choose a fresh destination for each bundle. |
| `--downloads_dir` | Persistent source-download store on a local/shared filesystem; default `downloads` relative to the launch directory. Independent of `-work-dir` and `--outdir`. |
| `--download_ca_bundle` | Optional local/shared PEM file containing additional trusted CA certificates. Defaults to `SSL_CERT_FILE` from the launch environment when set. Staged into download containers. |
| `--fasta_sha256`, `--exclusions_bed_sha256` | Optional expected SHA256 values for custom source files, checked before preparation. For `.gz` input, hash the compressed source bytes. |
| `--fasta_identity`, `--exclusions_bed_identity` | Optional JSON objects with `dataset`, `release`, and/or `assembly` strings for custom sources; retained in store and bundle provenance. Also accept maps in a Nextflow params file. Official identity cannot be overridden. |

For example, attach custom source identity with `--fasta_identity '{"dataset":"lab-reference","release":"v2","assembly":"GRCh38"}'`. Omitted fields remain unspecified; changing any supplied identity field selects a distinct store entry.

Download tasks use the basename of the individual asset's URL path, followed by its kind, as their display label in console output, traces, and execution reports. For example: `REFERENCE_DOWNLOAD (custom.fa.gz / fasta)`, `(exclusions.bed / exclusions_bed)`, `(annotation.fa.gz / annotation_fasta)`, or `(refseq-cache.tar.gz / vep_cache)`. Query strings and fragments are excluded from these labels. Other reference-preparation tasks use the original alignment FASTA basename, including its extension, to identify the bundle being prepared: `custom.fa.gz` gives `REFERENCE_VALIDATE (custom.fa.gz)` and `REFERENCE_BUNDLE_ASSEMBLE (custom.fa.gz)`. The built-in alignment reference uses `GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz`. There is no label option. Bundle labels stay the same through decompression and masking; ALIGNMENT_FASTA_DECOMPRESS, ALIGNMENT_FASTA_MASK, and ALIGNMENT_MAPPER_INDEX receive their tags through pipeline configuration, leaving upstream modules unchanged. Display labels do not set assembly/source identity, change artifact filenames, or select a new download-store entry.

The label is carried as task input metadata, so adopting these labels can invalidate older Nextflow task caches even with `-resume`; verified source downloads remain reusable.

On 2026-11-08, four targeted reference tests passed on Nextflow 26.10.5, Java 21, and the pinned Docker images (49 seconds): local compressed and uncompressed inputs, the built-in source basename (through a rejecting local proxy without fetching production data), and remote basename labels excluding query/fragment with download reuse and unchanged source identity. Both pipeline-configuration tests, Nextflow lint (existing upstream deprecation warnings), Python compilation, and whitespace checks passed. The full suite, CI, and SLURM/Apptainer execution were not run for this change.

The production defaults are the [GRCh38 no-ALT analysis-set FASTA with UCSC IDs](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz) and [GRC exclusions BED](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_GRC_exclusions.bed). Their [NCBI checksum metadata](https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/md5checksums.txt), verified on 2026-11-01, gives FASTA MD5 `a08035b6a6e31780e96a34008ff21bd6` and BED MD5 `bf5c011e0342f355422144eb3547b5d0`. Default acquisition verifies these values.

Exclusions BED coordinates are zero-based, half-open. Masking preserves sequence names, lengths, coordinates, and unmasked bases. If a contig in the exclusions BED is absent from the FASTA, its intervals are skipped and each is recorded in `omitted_exclusions_bed_entries` with its line number, contig, coordinates, and reason `"Contig missing in FASTA"`. This applies to all inputs, including the default NCBI files. Malformed intervals and coordinates outside an existing contig still cause an error.

Input filenames may contain letters, digits, dots, underscores, and hyphens; parent directory paths may contain spaces. Each input identifies one file, not a wildcard collection. Existing output directories are rejected to prevent mixed or overwritten bundles. Remote source checksums are checked before decompression; validation also checks original source bytes before masking/indexing.

## Persistent downloads

See the [process naming guide](process-names.md) for the workflow names, underlying tools, and migration of existing site configuration selectors. Equivalent alignment and annotation steps use parallel names such as `ALIGNMENT_FASTA_INDEX` and `ANNOTATION_FASTA_INDEX`.

Both the default NCBI sources and custom HTTP, HTTPS, or FTP URLs go through the observable `REFERENCE_DOWNLOAD` task. URLs are passed as values, so Nextflow does not stage them remotely first. Local files bypass this store entirely and are neither copied into it nor modified. The launcher resolves `--downloads_dir` to an absolute filesystem path; use an absolute path when sharing a store across launch directories:

```bash
nextflow run . --workflow prepare_reference_bundle -profile docker \
  --downloads_dir /path/to/persistent/downloads \
  --outdir /path/to/new-bundle
```

Nextflow task caching (`-resume`) reuses successful task executions in a work directory. The download store instead retains original source bytes independently of those tasks and completed bundles. Fresh runs, deletion of task caches/work directories, and edits to validation, masking, indexing, or packaging do not require another download of a valid stored asset. Acquisition checks run even with `-resume`, so task caching cannot bypass store integrity checks. Prepared derivatives and indexes are rebuilt according to ordinary task-caching rules. There is no `storeDir` directive; [Nextflow recommends explicit workflow reuse logic](https://docs.seqera.io/nextflow/reference/process/directives/store-dir).

Each store key hashes the original URI, source kind, expected checksums, and dataset/release/assembly identity. Different URLs or expected checksums therefore remain distinct even when their basenames match. Official inputs record the NCBI dataset, `GCA_000001405.15` release, and GRCh38 assembly and always enforce the pinned MD5 values above, plus a SHA256 if supplied. SHA256 and MD5 are recorded over the **original downloaded bytes**, including compression. The bundle keeps the original URI and source checksums rather than identifying the store path as the source.

A custom source without an expected checksum records a computed SHA256 on first acquisition. Subsequent hits hash all stored bytes and compare integrity metadata before reuse. This detects subsequent corruption; it does **not** establish publisher authenticity or detect upstream changes at an unchanged URL. Supply an expected SHA256 whenever available. To intentionally acquire changed unpinned content at the same URL, remove its store entry while no runs use it, or select a new store.

Transfers use temporary files and become complete only when metadata is atomically committed to reference a complete immutable generation. A checksum mismatch never replaces a valid entry. Missing, incomplete, or corrupt entries are reported and reacquired; a failed replacement leaves existing generations intact and fails preparation. Network errors and truncated transfers have at most three attempts with a 60-second socket timeout and short backoff; checksum mismatches fail immediately. Task time limits bound overall runtime.

Concurrent requests for one key acquire ownership by atomically creating its `.lock/` directory while checking or acquiring it. Other keys can proceed independently. The filesystem must support atomic directory creation and renames visible across clients. Normal exits, failures, and SIGTERM release ownership. A hard kill or node crash may leave `.lock/owner.json`, which records the container hostname, PID, and start time. A waiting task fails with the lock path after one hour; ownership is never stolen based on age because a legitimate large transfer may take hours. For stale ownership, stop all runs accessing that entry, check the recorded owner against active container/SLURM jobs (PIDs are container-local), then remove only that entry's `.lock/` directory and rerun. If ownership cannot be established, ask the cluster operator before removing it. Orphan partial files are never treated as complete.

To inspect entries, read `<downloads_dir>/<key>/metadata.json`: it records the asset identity, generation, byte size, and checksums. Its `generation` names the subdirectory containing the source's original basename. No metadata means no completed entry. With all readers and writers stopped, remove an entire `<key>/` directory to force reacquisition. Remove the whole store to reclaim everything. Interrupted transfers may leave `.partial-*` directories; superseded generations and unreferenced files may also remain. They are ignored and may be removed while the store is idle. There is no automatic eviction or derivative caching, and no gnomAD acquisition in this workflow.

Store hits require sequential reads of the entire source, so multi-gigabyte inputs still incur hashing and filesystem I/O. Reference validation hashes sources again; avoiding network downloads does not eliminate decompression, validation, masking, indexing, or bundle publication costs.

The launcher must be able to create/read the store and read task results. Download tasks require outbound source access on the machine executing them: the Docker host/container locally, or SLURM compute nodes in production. On a hit no source network request is made. Container-image acquisition may separately require network access. Docker explicitly mounts the store read/write and runs acquisition with the task host's UID/GID, so the launcher can read the completed source directories on Linux as well as macOS. Docker Desktop must permit sharing that host path. Apptainer explicitly binds the store at the same absolute path. Submission host and compute nodes must see it and the work/output paths consistently, with suitable directory permissions for all participating users. Colons, commas, and newlines in the store path are rejected because they conflict with container bind syntax.

For compute nodes that require a proxy, export `HTTP_PROXY`/`HTTPS_PROXY` or their lowercase equivalents before launching Nextflow. `NO_PROXY`/`no_proxy` is also forwarded for hosts that should bypass the proxy. For each pair, a present lowercase value takes precedence, including an explicitly empty value; uppercase is used only when lowercase is absent. The resolved value is exported under both spellings in each `REFERENCE_DOWNLOAD` job, including inside its container, by shell-quoted exports in the task script. If neither spelling is set, both are exported empty. These intentional empty values do not produce Nextflow environment-input warnings. Use the proxy URL supplied by your cluster administrators, for example:

```bash
export HTTP_PROXY='http://proxy.example.org:3128'
export HTTPS_PROXY="$HTTP_PROXY"
# Rerun your reference-preparation command, adding -resume if appropriate.
```

An empty lowercase `http_proxy` or `https_proxy` disables that proxy even if its uppercase counterpart is nonempty. An empty `no_proxy` suppresses an uppercase bypass list. This follows Python's proxy-selection semantics; the CGI safeguard also ignores uppercase-only `HTTP_PROXY` when the launch environment contains `REQUEST_METHOD`. Avoid conflicting definitions across cases: the Nextflow launcher and other tools may use different precedence from the Python download job. See the [proxy environment investigation](research/2026-11-06-proxy-environment.md) for the verified client differences.

If the proxy uses a private CA, the download container also needs that CA certificate. The workflow reads the launch environment's `SSL_CERT_FILE`, stages the referenced PEM file as `download-ca.pem`, and loads its certificates alongside the container's default trusted CAs. Merely forwarding an absolute host path is insufficient when the container cannot access that file. For a cluster that supplies its trusted bundle at `/etc/ssl/certs/ca-bundle.crt`, use:

```bash
export SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt
# Rerun your reference-preparation command with the proxy variables set.
```

An explicit `--download_ca_bundle /shared/path/approved-ca-bundle.pem` overrides `SSL_CERT_FILE`. The PEM must be readable from the launch host and available for normal Nextflow file staging on compute nodes. `CURL_CA_BUNDLE`, `REQUESTS_CA_BUNDLE`, and `GIT_SSL_CAINFO` are not used by this Python downloader. TLS certificate and hostname checks stay enabled; an untrusted chain or hostname mismatch fails immediately with CA-configuration guidance instead of retrying the same TLS failure. Use the CA bundle approved by the cluster administrator. This setting covers source downloads; container-image acquisition has its own trust configuration. Python's [SSL context documentation](https://docs.python.org/3.12/library/ssl.html#ssl.SSLContext.load_verify_locations) describes loading additional trusted certificates.

## Local Docker example

Start Docker, put the pinned Nextflow executable on `PATH`, and select the pinned Java runtime. From the repository root, create an illustrative small input:

```bash
python3 - <<'PY'
import gzip
from pathlib import Path
example = Path('.local/reference-example')
example.mkdir(parents=True, exist_ok=True)
with gzip.open(example / 'small.fa.gz', 'wt') as handle:
    handle.write('>chr1\nACGTACGTACGTACGTACGT\n>chr2\nTTTTCCCCAAAAGGGG\n')
(example / 'exclusions.bed').write_text('chr1\t4\t8\nchr2\t0\t2\n')
(example / 'annotation.fa').write_text('>1\nACGTACGTACGTACGTACGT\n>2\nTTTTCCCCAAAAGGGG\n')
PY
nextflow run . --workflow prepare_reference_bundle -profile docker,test \
  --fasta .local/reference-example/small.fa.gz \
  --exclusions_bed .local/reference-example/exclusions.bed \
  --annotation_fasta .local/reference-example/annotation.fa \
  --vep_cache tests/data/vep116/refseq-cache.tar.gz \
  --outdir .local/reference-example/bundle
```

This synthetic 36-base example exercises bundle preparation, not biological consequences. The committed real-cache/sequence fixture and public annotation tests establish those separately. All example inputs above are local; no whole-human resources are downloaded.

The `docker` profile uses `--platform=linux/amd64`, including on Apple Silicon. The `test` profile limits local execution to two CPUs and 4 GiB total task memory, with at most one task per process; the indexing task requests 2 GiB. These settings serve compact fixtures, not the human reference.

On 2026-11-01, an initial real masking/indexing/provenance test passed under Docker 29.9.2 on an ARM64 Mac with a 10-CPU, approximately 7.75-GiB Docker VM. That observation establishes execution of the compact path; it is not a peak-resource measurement or full-reference benchmark. Run the public acceptance suite with `python3 -m unittest discover -s tests -v`; the required CI job runs the same command on Linux with real containers.

A subsequent trace of the 36-base fixture on the same date measured 19.8 MB peak RSS for indexing (1.1 GB peak virtual memory) and at most 35.6 MB peak RSS across these five tasks. The test harness retains per-run logs and traces under `.local/tests/`. These fixture measurements do not estimate human-reference requirements.

On 2026-11-05, the persistent-download enhancement passed all **44** tests in `python3 -m unittest discover -s tests -v` (843 seconds), including controlled HTTP request counts for fresh-run reuse, downstream edits, concurrent acquisition, changed identities/checksums, interrupted transfers, and corrupt/incomplete entries. Nextflow lint and Python compilation passed, and all 55 installed nf-core files matched their pinned upstream revisions. This local run used Nextflow 26.10.4, Docker 29.9.2, the installed Java 25.0.5.0.3 launcher runtime, and Python 3.9.6 for the test harness; tasks used the pinned containers above. CI retains Java 21/Python 3.12 and was not run for this local commit. Native Linux host permissions and SLURM/Apptainer execution were not exercised here; no production reference was downloaded.

The initial Linux PR validation on 2026-11-06 exposed a test-fixture cleanup permission error on Docker-created downstream work files. The reference-test fixture now enables `docker.fixOwnership` so the cache-deletion regression can remove those files as the host user. CI results for this enhancement are tracked in [PR #19](https://github.com/micknudsen/oncohawk/pull/19).

On 2026-11-06, explicit proxy forwarding passed six targeted local tests with Nextflow 26.10.4, Java 21, and Docker 29.9.2: HTTP acquisition through a proxy, HTTPS CONNECT routing (with deliberate tunnel rejection), direct acquisition/reuse, local reference preparation, container pins, and pipeline configuration isolation. Both proxy regressions failed before the fix. Nextflow lint passed with existing upstream deprecation warnings, and all 55 pinned nf-core files matched upstream. The full suite, CI, and SLURM/Apptainer execution were not rerun for this change.

The same day's CA-trust follow-up reproduced `self-signed certificate in certificate chain` with a temporary local CA. Ten targeted tests then passed (89 seconds), covering `SSL_CERT_FILE` staging, an explicit CA bundle, rejection of untrusted chains, hostname mismatches and invalid PEM, plus the six proxy/direct-input/configuration checks above. Nextflow lint and Python compilation passed with the same local toolchain. The cluster's actual CA bundle, SLURM/Apptainer execution, CI, and the full suite were not exercised; the cluster rerun remains necessary.

The subsequent proxy-casing correction passed 17 targeted tests: 14 download-job cases covering both spellings, precedence, explicit empty values, bypass settings, the CGI safeguard and CA forwarding, plus local-file preparation and two configuration checks. The three uppercase HTTP/HTTPS/bypass regressions failed before the correction. Nextflow lint, Python compilation, and whitespace checks passed. The full suite, CI, and cluster execution were not run for this correction; see the [dated investigation](research/2026-11-06-proxy-environment.md).

## Production with SLURM and Apptainer

The SLURM profile enables [community-style resource retries](resource-retries.md): one retry with growing resource requests, optional native caps, and standard configuration overrides. First-attempt allocations remain unchanged; ordinary local Docker behavior is unchanged.

Copy [conf/site.example.config](../conf/site.example.config) to a local site configuration, then replace its partition, optional account, and shared paths. The submission host and compute nodes must see the work directory, download store, input files, output destination, and Apptainer cache. The shared site file contains no process-name selectors. For the selected reference workflow, the `slurm` profile automatically loads [reference process allocations](../conf/prepare_reference_bundle_resources.config). These are starting allocations, not measured cluster requirements. To customize them, copy that resource file and pass it as a second configuration file; keep it specific to reference preparation.

```bash
mkdir -p .local
cp conf/site.example.config .local/site.config
cp conf/prepare_reference_bundle_resources.config .local/reference-resources.config
# Edit the shared site settings and reference resource allocations for your cluster.
nextflow run . --workflow prepare_reference_bundle -profile slurm -c .local/site.config,.local/reference-resources.config \
  --downloads_dir /shared/PROJECT/oncohawk/downloads \
  --outdir /shared/PROJECT/oncohawk/bundles/grch38-no-alt
```

Omitting `--fasta` and `--exclusions_bed` selects the checksum-verified NCBI sources. To use local copies, provide both paths. The `slurm` profile enables Apptainer automatic mounts and uses the same workflow and modules as Docker. See Nextflow's [executor guidance](https://docs.seqera.io/nextflow/executor) and [container guidance](https://docs.seqera.io/nextflow/container).

HPC execution is checked informally by the operator. HPC access, runs, evidence, and sign-off never gate formal acceptance or completion. No cluster run is claimed here.

## Published bundle

```text
reference/
├── reference.fa
├── reference.fa.fai
├── reference.dict
├── bwamem2/
│   ├── reference.fa.0123
│   ├── reference.fa.amb
│   ├── reference.fa.ann
│   ├── reference.fa.bwt.2bit.64
│   └── reference.fa.pac
├── annotation/
│   ├── reference.fa
│   ├── reference.fa.fai
│   ├── chr_synonyms.txt
│   ├── compatibility.json
│   ├── resource_metadata.json
│   └── cache/homo_sapiens_refseq/116_GRCh38/...
└── bundle.json
```

`bundle.json` starts with `bundle_format_version: 3`, identifying the format of the entire reference bundle, followed by relative `fasta`, `fasta_index`, `sequence_dictionary`, and `bwamem2_index` paths, SHA256 artifact checksums, source URIs and checksums under `sources.fasta`, `sources.exclusions_bed`, `sources.annotation_fasta`, and `sources.vep_cache`, sequence lengths, omitted BED entries, tool/module versions, and workflow identity/source hashes. Source hashes use repository-relative paths and cover reference-preparation sources and shared files used by preparation, including the root dispatcher and configuration. Analysis-only and knowledge-only workflow/configuration sources are excluded; changing them does not change the reference source-hash inventory or values. The module inventory records only reference modules, so analysis-only module-pin changes do not change reference source identity; the mixed `modules.json` file is not hashed wholesale. The repository commit is recorded separately. Format 1 and 2 bundles must be rebuilt explicitly; no legacy conversion is provided. The FASTA index and dictionary derive from the masked FASTA, and the dictionary uses the portable `reference.fa` URI. The bwa-mem2 index path is a prefix; all five index files accompany it. Keep the manifest and artifacts together when moving a bundle. A process failure is a failed preparation, not a completed bundle; inspect the Nextflow task log before retrying into a new output destination.

## Annotation resources and compatibility

The selected consumer is VEP **116.3**, installed through the pristine `ensemblvep/vep` module at `20c6e6407f63748003b47f92837b64fb0a53ffa4`. The image is `community.wave.seqera.io/library/ensembl-vep_perl-math-cdf_htslib_gzip_tar:43f77a48cc79bf38`, qualified with digest `sha256:2294ff1ab149218bb9337722d3fbde0844a290874c7adec6121ff92d856c3729`. The bundle records expected consumer identity separately from versions of tools actually executed during preparation.

Production sources are the [RefSeq-only cache 116](https://ftp.ensembl.org/pub/release-116/variation/indexed_vep_cache/homo_sapiens_refseq_vep_116_GRCh38.tar.gz) and the [unmasked GRCh38 primary-assembly FASTA](https://ftp.ensembl.org/pub/release-116/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz). The cache archive's SHA256 is `0427dd48d05d15be2486ceffff047be8153ea5e7b65391918d25efcb054f7f77`. The FASTA's original compressed SHA256 is `d8c3af0094a7bba6125763bad779ec18a81483c739c6ed122094bdf86c187b92`. Source URLs/checksums and RefSeq/MANE data versions are retained separately from Ensembl release 116. The cache declares RefSeq `GCF_000001405.40-RS_2025_08 - GCF_000001405.40_GRCh38.p14_genomic.gff`. Its original `info.txt` does not declare a MANE version: **MANE v1.5** comes from matching [release-116 core metadata](https://ftp.ensembl.org/pub/release-116/mysql/homo_sapiens_core_116_38/meta.txt.gz), whose SHA256 is `b4755176b563f043c12770ece6e27d7dba729579101d76144732917732b0686e`; the manifest records that separate provenance without editing the cache metadata. The NCBI alignment input and masked result are preserved exactly.

Preparation checks unambiguous contig aliases, equal lengths for mapped contigs, and agreement of every corresponding known A/C/G/T genomic base. It recognizes exact names, UCSC primary-chromosome aliases, and accession-based UCSC scaffold equivalents; patch scaffolds are not treated as chromosome aliases. It rejects ambiguous aliases, length disagreements, and differing known bases. Unmatched contigs on both sides are recorded, and at least one corresponding contig is required. There is no liftover or REF repair.

An `N` in either original FASTA denotes an unknown assembly base. The compatibility report counts source-only, annotation-only, and shared `N` positions, including an `N` opposite an ambiguity code. At all other positions, the two DNA IUPAC symbols must share at least one possible base. For example, `M` (A or C) is compatible with `A` and incompatible with `G`. The report records compatible positions involving an ambiguity code in `compatible_ambiguous_bases` and exact A/C/G/T matches in `matching_known_bases`. Comparison ignores letter case. A separate comparison between the original and masked alignment FASTAs counts imposed masks and rejects every substitution except a change to `N`.

The annotation FASTA index is built once during preparation, and all cache files and annotation assets receive SHA256 entries. Paths in the manifest remain portable. Sample processing uses these existing resources and does not rebuild their indexes. Default analysis validates metadata, paths, and file inventory without reading the full FASTA/cache contents; `--verify_bundle_checksums` verifies all artifact bytes before reads are processed, including on resume.

All four remote sources use the same persistent download-store integrity checks, proxy handling, and trusted-CA configuration. A new bundle can reuse verified source downloads independently of Nextflow work-directory reuse. This does not promise that every alignment-index task will be reused after a bundle or pipeline update. Large resource validation and publication still require I/O and disk space; the cache archive and extracted cache are separate disk requirements.
