/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    BWAMEM2_MEM
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Aligns a pair of trimmed FASTQ files to a bwa-mem2 index and streams
    the output through `samtools collate`, `samtools fixmate`, and
    `samtools sort` to produce a coordinate-sorted lane-level BAM ready
    for downstream duplicate marking. The `@RG` line is injected from
    `meta.read_group`.

    The index is passed as a directory (`params.ref_data_genome_bwamem2_index`).
    The FASTA file is passed separately so bwa-mem2 can use it as the index
    prefix (the index files must share the same basename in the same directory,
    which is guaranteed by PREPARE_REFERENCE).

    One task per (sample, library, lane) row. Lane-level BAMs are merged
    and deduplicated downstream.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process BWAMEM2_MEM {

    tag { meta.id }

    label 'process_high'

    container "${params.preprocess_container}"

    input:
    tuple val(meta), path(reads_1), path(reads_2)
    tuple path(fasta), path(index_dir)

    output:
    tuple val(meta), path("${meta.id}.bam"), emit: bam
    path 'versions.yml',                     emit: versions

    script:
    // Reserve one thread for samtools sort.
    def sort_threads = Math.max(1, (task.cpus as int) - 1)
    """
    set -euo pipefail

    bwa-mem2 mem \\
        -t ${task.cpus} \\
        -R '${meta.read_group}' \\
        -K 100000000 \\
        -Y \\
        ${index_dir}/${fasta.name} \\
        ${reads_1} ${reads_2} \\
    | samtools sort \\
        -@ ${sort_threads} \\
        -o ${meta.id}.bam \\
        -

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bwa-mem2: \$(bwa-mem2 version 2>&1 | grep -oE '[0-9]+\\.[0-9]+(\\.[0-9]+)?' | head -n1)
        samtools: \$(samtools --version | head -n1 | awk '{print \$2}')
    END_VERSIONS
    """
}
