/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    WGET_GENOME
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Downloads a reference genome FASTA from a URL (typically the GRCh38
    no-alt analysis set from NCBI), gunzips it, and emits the resulting
    uncompressed FASTA. The output filename is derived from the URL.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process WGET_GENOME {

    label 'process_low'

    // We reuse the bwa-mem2 BioContainer here because it already ships wget +
    // gzip, saving us from pulling a second image just to fetch a file.
    container 'quay.io/biocontainers/bwa-mem2:2.2.1--he70b90d_8'

    input:
    val url

    output:
    path "${out_name}", emit: fasta
    path 'versions.yml', emit: versions

    script:
    // Strip a single trailing .gz if present to get the final FASTA filename.
    def gz_name  = url.tokenize('/').last()
    out_name = gz_name.endsWith('.gz') ? gz_name[0..-4] : gz_name
    """
    set -euo pipefail

    wget --no-verbose --tries=3 -O '${gz_name}' '${url}'

    if [[ '${gz_name}' == *.gz ]]; then
        gunzip --force '${gz_name}'
    fi

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        wget: \$(wget --version | head -n1 | awk '{print \$3}')
        gzip: \$(gzip --version | head -n1 | awk '{print \$NF}')
    END_VERSIONS
    """
}
