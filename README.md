# Oncohawk

Oncohawk is a Nextflow workflow for tumor-only short-read DNA WGS analysis. The first implemented milestone slice prepares a reusable **reference bundle**: a hard-masked FASTA, matching bwa-mem2 indexes, and provenance. Sequencing-to-BAM alignment and downstream analysis are separate milestone slices.

Use Nextflow **26.10.4**, Java **21.0.13+9**, Python **3.12** for tests, and a running Docker installation for local development. Containers supply the bioinformatics tools; Conda execution is unsupported. The [reference-bundle guide](docs/reference-bundle.md) describes installation pins, inputs, outputs, and production use.

Run the compact acceptance tests from the checkout:

```bash
python3 -m unittest discover -s tests -v
```

These tests run real reference preparation with Docker through the public workflow interface. The `docker,test` profiles limit execution to compact fixtures; full-human-reference runs belong on the production cluster.

Prepare a bundle from your own small fixture:

```bash
nextflow run . -profile docker,test \
  --fasta /path/to/small.fa.gz \
  --bed /path/to/exclusions.bed \
  --outdir /path/to/new-bundle
```

The production `slurm` profile uses Apptainer and the same workflow and pristine nf-core modules. See the [site configuration example](conf/site.example.config) and [cluster instructions](docs/reference-bundle.md#production-with-slurm-and-apptainer). Formal acceptance uses local Docker and required CI; HPC checks are informal and never gate ticket or milestone completion.

Project scope and accepted decisions are in [requirements](docs/requirements.md), [design](docs/design.md), and the root [glossary](GLOSSARY.md).
