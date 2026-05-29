/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CUTADAPT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Paired-end adapter trimming with cutadapt. One task per (sample,
    library, lane) row from the samplesheet.

    Adapter sequences default to TruSeq R1/R2 but can be overridden via
    `params.adapter_r1` / `params.adapter_r2`.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process CUTADAPT {

    tag { meta.id }

    label 'process_medium'

    container 'quay.io/biocontainers/cutadapt:5.2--py311h26ae33e_1'

    input:
    tuple val(meta), path(reads_1), path(reads_2)

    output:
    tuple val(meta), path("${meta.id}_trimmed_R1.fastq.gz"),
                     path("${meta.id}_trimmed_R2.fastq.gz"), emit: reads
    path "${meta.id}.cutadapt.log",                          emit: log
    path 'versions.yml',                                     emit: versions

    script:
    def adapter_r1 = params.adapter_r1
    def adapter_r2 = params.adapter_r2
    """
    set -euo pipefail

    cutadapt \\
        -j ${task.cpus} \\
        -a ${adapter_r1} \\
        -A ${adapter_r2} \\
        --minimum-length 35 \\
        -o ${meta.id}_trimmed_R1.fastq.gz \\
        -p ${meta.id}_trimmed_R2.fastq.gz \\
        ${reads_1} ${reads_2} \\
        > ${meta.id}.cutadapt.log

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        cutadapt: \$(cutadapt --version)
    END_VERSIONS
    """
}
