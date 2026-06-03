/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    TRIM_AND_MAP_FASTQ
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Trims paired-end reads with cutadapt and streams interleaved FASTQ
    directly into bwa-mem2, then sorts with samtools to produce a
    coordinate-sorted lane-level BAM ready for downstream duplicate
    marking. The `@RG` line is injected from `meta.read_group`.

    The index is passed as a directory (`params.ref_data_genome_bwamem2_index`).
    The FASTA file is passed separately so bwa-mem2 can use it as the index
    prefix (the index files must share the same basename in the same directory,
    which is guaranteed by PREPARE_REFERENCE).

    One task per (sample, library, lane) row. Lane-level BAMs are merged
    and deduplicated downstream.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process TRIM_AND_MAP_FASTQ {

    tag { meta.id }

    label 'process_high'

    container "${params.preprocess_container}"

    input:
    tuple val(meta), path(reads_1), path(reads_2)
    tuple path(fasta), path(index_dir)

    output:
    tuple val(meta), path("${meta.id}.bam"), emit: bam
    path "${meta.id}.cutadapt.log",         emit: log
    path 'versions.yml',                     emit: versions

    script:
    def adapter_r1 = params.adapter_r1
    def adapter_r2 = params.adapter_r2
    // Reserve one thread for samtools sort.
    def sort_threads = Math.max(1, (task.cpus as int) - 1)
    """
    set -euo pipefail

    cutadapt \\
        -j 1 \\
        -a ${adapter_r1} \\
        -A ${adapter_r2} \\
        --minimum-length 35 \\
        --interleaved \\
        -o - \\
        ${reads_1} ${reads_2} \\
        2> ${meta.id}.cutadapt.log \\
    | bwa-mem2 mem \\
        -t ${task.cpus} \\
        -p \\
        -R '${meta.read_group}' \\
        -K 100000000 \\
        -Y \\
        ${index_dir}/${fasta.name} \\
        - \\
    | samtools sort \\
        -@ ${sort_threads} \\
        -o ${meta.id}.bam \\
        -

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        cutadapt: \$(cutadapt --version)
        bwa-mem2: \$(bwa-mem2 version 2>&1 | grep -oE '[0-9]+\\.[0-9]+(\\.[0-9]+)?' | head -n1)
        samtools: \$(samtools --version | head -n1 | awk '{print \$2}')
    END_VERSIONS
    """
}
