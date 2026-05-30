# oncohawk
Nextflow-based pipeline for tumor-only inference of somatic variation in myeloid malignancies

## WGET_GENOME container (GHCR)

This repository includes a dedicated Miniconda-based container recipe for the `WGET_GENOME` module:

- `containers/wget/environment.yml`
- `containers/wget/Dockerfile`

GitHub Actions workflow `build-wget-image.yml` builds and pushes to GHCR:

- `ghcr.io/<owner>/oncohawk-wget`

After a workflow run, copy the digest from the job output and pin the module container in `nextflow.config`:

```groovy
params {
	wget_container = 'ghcr.io/<owner>/oncohawk-wget:latest@sha256:<digest>'
}
```

The module reads this value via `params.wget_container`, so no module code changes are needed when updating tags/digests.
