FROM continuumio/miniconda3:24.11.1-0

COPY containers/wget-genome/environment.yml /tmp/environment.yml

RUN conda env create -n wget-genome -f /tmp/environment.yml \
    && conda clean -afy

ENV CONDA_DEFAULT_ENV=wget-genome
ENV PATH=/opt/conda/envs/wget-genome/bin:${PATH}

# Ensure bash semantics are available for Nextflow process scripts.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN wget --version | head -n1 \
    && gzip --version | head -n1
