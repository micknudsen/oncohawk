/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    GUNZIP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Decompresses a gzipped file and emits the uncompressed filename.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process GUNZIP {

    label 'process_low'

    container 'quay.io/biocontainers/gzip:1.11'

    input:
    path gz_file

    output:
    path "${gz_file.getFileName().toString().endsWith('.gz') ? gz_file.getFileName().toString()[0..-4] : gz_file.getFileName().toString()}", emit: uncompressed
    path 'versions.yml', emit: versions

    script:
    def gz_name = gz_file.getFileName().toString()
    """
    set -euo pipefail

    gzip -df '${gz_name}'

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        gzip: \$(gzip --version | head -n1 | awk '{print \$2}')
    END_VERSIONS
    """
}