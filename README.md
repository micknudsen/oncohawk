# oncohawk
Nextflow-based pipeline for tumor-only inference of somatic variation in myeloid malignancies

## WGET_GENOME container (GHCR)

This repository includes a dedicated Miniconda-based container recipe for the `WGET_GENOME` module:

- `containers/wget-genome/environment.yml`
- `containers/wget-genome/Dockerfile`

GitHub Actions workflow `build-wget-genome-image.yml` builds and pushes to GHCR:

- `ghcr.io/<owner>/oncohawk-wget-genome`

After a workflow run, copy the digest from the job output and pin the module container in `nextflow.config`:

```groovy
params {
	wget_genome_container = 'ghcr.io/<owner>/oncohawk-wget-genome:latest@sha256:<digest>'
}
```

The module reads this value via `params.wget_genome_container`, so no module code changes are needed when updating tags/digests.
