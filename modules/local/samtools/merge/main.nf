/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SAMTOOLS_MERGE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Merges lane-level BAMs into one BAM per sample.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process SAMTOOLS_MERGE {

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
    def bam_list = bams.collect { bam -> "'${bam}'" }.join(' ')
    """
    set -euo pipefail

    samtools merge \
        -@ ${tool_threads} \
        -O BAM \
        -o ${meta.id}.bam \
        ${bam_list}

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        samtools: \$(samtools --version | head -n1 | awk '{print \$2}')
    END_VERSIONS
    """
}
