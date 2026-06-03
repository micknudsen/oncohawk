/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    INDEX_GENOME
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Builds a bwa-mem2 index from a reference FASTA. Emits the original
    FASTA plus the five index files (.0123, .amb, .ann, .bwt.2bit.64, .pac)
    as a single tuple so they always travel together.

    For GRCh38 (~3 Gb) this takes ~40 min and ~70 GB of memory.
    For the test chr22 subset (50 kb) it takes ~1 second and a few MB.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process INDEX_GENOME {

    label 'process_high_memory'

    container "${params.preprocess_container}"

    input:
    path fasta

    output:
    tuple path(fasta), path("${fasta}.0123"),
                       path("${fasta}.amb"),
                       path("${fasta}.ann"),
                       path("${fasta}.bwt.2bit.64"),
                       path("${fasta}.pac"),         emit: index
    path 'versions.yml',                             emit: versions

    script:
    """
    set -euo pipefail

    bwa-mem2 index '${fasta}'

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        bwa-mem2: \$(bwa-mem2 version 2>&1 | grep -oE '[0-9]+\\.[0-9]+(\\.[0-9]+)?' | head -n1)
    END_VERSIONS
    """
}
