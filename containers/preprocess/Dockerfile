FROM continuumio/miniconda3:24.11.1-0

COPY containers/preprocess/environment.yml /tmp/environment.yml

RUN conda env create -n preprocess -f /tmp/environment.yml \
    && conda clean -afy

ENV CONDA_DEFAULT_ENV=preprocess
ENV PATH=/opt/conda/envs/preprocess/bin:${PATH}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN cutadapt --version \
    && bwa-mem2 version \
    && samtools --version | head -n1
