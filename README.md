# Oncohawk

Oncohawk is a Nextflow workflow for tumor-only short-read DNA WGS analysis. It prepares a reusable **reference bundle** and aligns gzipped FASTQ pairs to produce one coordinate-sorted, indexed BAM per sample with duplicates marked and retained. A sample sheet can combine multiple samples, libraries, lanes, and FASTQ chunks, with optional adapter settings for each mate in each row. Read groups are preserved, and duplicate detection combines lanes within each library while keeping distinct libraries separate. Downstream analysis remains deferred.

The [milestone 1 acceptance record](docs/milestone-1-acceptance.md) maps the completed scope to tests, merged implementation PRs, and recorded local/CI results as of 2026-11-01.

Use Nextflow **26.10.5**, Java **21.0.13+9**, Python **3.12** for tests, and a running Docker installation for local development. Containers supply the bioinformatics tools; Conda execution is unsupported. The [reference-bundle guide](docs/reference-bundle.md) and [alignment guide](docs/alignment.md) describe inputs, outputs, runtime pins, and production use.

Run the compact acceptance tests from the checkout:

```bash
python3 -m unittest discover -s tests -v
```

These tests run real reference preparation, alignment, and their composition with Docker through the public workflow interfaces. The `docker,test` profiles limit execution to compact fixtures; full-human-reference runs belong on the production cluster.

Launch the repository root with `nextflow run .`. Each invocation selects one workflow:

| Selection | Behavior | Default output directory |
| --- | --- | --- |
| Omit `--workflow`, or use `--workflow oncohawk` | Align the sample sheet against an existing reference bundle. | `results` |
| `--workflow prepare_reference_bundle` | Prepare a reusable reference bundle explicitly. | `reference` |
| `--workflow prepare_knowledge_bundle` | Fail immediately with a not-yet-implemented error. | None |

Unknown workflow names fail before tasks start. Analysis requires no knowledge bundle and does not prepare missing bundles automatically. Override the selected output root with `--outdir`; relative paths resolve from the launch directory. To launch elsewhere, replace `.` with the checkout path.

Root `main.nf` owns selection and publication; implementations live in `workflows/`. Root `nextflow.config` loads shared and selected-workflow settings from `conf/`, preserving process-selector isolation. Modules remain shared. The former `pipelines/reference` and `pipelines/alignment` entrypoints are removed.

Analysis publishes `<sample>.bam` and `<sample>.bam.bai` under `results/samples/<sample>/alignments/`. An `--outdir` override replaces only `results`, retaining that sample layout and the filenames. No variant/report placeholders or diagnostics are created by this layout. Placement of explicitly enabled diagnostics under `results/execution/` follows in [#28](https://github.com/micknudsen/oncohawk/issues/28).

Reference URLs use a persistent, integrity-checked download store, defaulting to `downloads` in the launch directory. Set `--downloads_dir /persistent/path` to share it across runs independently of Nextflow work directories and `-resume`. See [persistent downloads](docs/reference-bundle.md#persistent-downloads) for integrity, concurrency, and cluster setup.

Before the first official pipeline release, every commit may break functionality; backward compatibility is not maintained.

Prepare a bundle from your own small fixture:

```bash
nextflow run . --workflow prepare_reference_bundle -profile docker,test \
  --fasta /path/to/small.fa.gz \
  --exclusions_bed /path/to/exclusions.bed \
  --outdir /path/to/new-bundle
```

Align small paired-end fixtures against that prepared bundle:

```bash
nextflow run . -profile docker,test \
  --input /path/to/samples.csv \
  --reference_bundle /path/to/new-bundle \
  --outdir /path/to/new-results
```

Use the [sample-sheet examples](docs/alignment.md#sample-sheet) for one pair or multiple samples and a fresh output directory. All pairs pass through Cutadapt; after optional row-local adapter removal, both mates must be at least 15 bp. Each input FASTQ may appear only once in the sheet.

The production `slurm` profile uses Apptainer and the same workflow and pristine nf-core modules. See the [site configuration example](conf/site.example.config) and [cluster instructions](docs/reference-bundle.md#production-with-slurm-and-apptainer). Formal acceptance uses local Docker and required CI; HPC checks are informal and never gate ticket or milestone completion.

Project scope and accepted decisions are in [requirements](docs/requirements.md), [design](docs/design.md), and the root [glossary](GLOSSARY.md).
