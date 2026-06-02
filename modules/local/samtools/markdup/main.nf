/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    SAMBAMBA_MARKUP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Performs duplicate marking with sambamba markdup on one merged BAM
    per sample.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process SAMBAMBA_MARKUP {

    tag { meta.id }

    label 'process_high'

    container "${params.preprocess_container}"

    input:
    tuple val(meta), path(bam)

    output:
    tuple val(meta), path("${meta.id}.bam"), emit: bam
    tuple val(meta), path("${meta.id}.bam.bai"), emit: bai
    path "${meta.id}.markdup.log",               emit: stats
    path 'versions.yml',                    emit: versions

    script:
    // Reserve one thread for compression/indexing helpers.
    def tool_threads = Math.max(1, (task.cpus as int) - 1)
    def tmp_bam = "${meta.id}.markedup.bam"
    """
    set -euo pipefail

    sambamba markdup \
        -t ${tool_threads} \
        --tmpdir . \
        ${bam} \
        ${tmp_bam} \
        2> ${meta.id}.markdup.log

    mv ${tmp_bam} ${meta.id}.bam

    samtools index \
        -@ ${tool_threads} \
        ${meta.id}.bam

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        sambamba: \$(sambamba --version 2>&1 | head -n1 | awk '{print \$2}')
        samtools: \$(samtools --version | head -n1 | awk '{print \$2}')
    END_VERSIONS
    """
}
