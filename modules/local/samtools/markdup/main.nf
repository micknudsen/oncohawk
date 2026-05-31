/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    MARKDUP_LIBRARY
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Groups lane-level BAMs by (sample, library), merges lane BAMs within each
    library, and performs duplicate marking with samtools markdup.

    Duplicate marking is intentionally done per library (LB), not per sample.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process MARKDUP_LIBRARY {

    tag { meta.id }

    label 'process_high'

    container "${params.preprocess_container}"

    input:
    tuple val(meta), path(bams)

    output:
    tuple val(meta), path("${meta.id}.bam"), emit: bam
    path 'versions.yml',                    emit: versions

    script:
    // Reserve one thread for compression/indexing helpers.
    def tool_threads = Math.max(1, (task.cpus as int) - 1)
    def markdup_optical_distance = params.markdup_optical_distance
    def bam_list = bams.collect { bam -> "'${bam}'" }.join(' ')
    """
    set -euo pipefail

    samtools merge \
        -@ ${tool_threads} \
        -u \
        - \
        ${bam_list} \
    | samtools markdup \
        -@ ${tool_threads} \
        -S \
        -d ${markdup_optical_distance} \
        -s \
        - \
        ${meta.id}.bam

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samtools: \$(samtools --version | head -n1 | awk '{print \$2}')
    END_VERSIONS
    """
}
