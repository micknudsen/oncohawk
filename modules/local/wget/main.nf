/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    WGET
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Downloads a file from a URL and emits the downloaded filename.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

process WGET {

    label 'process_low'

    container 'quay.io/biocontainers/wget:1.25.0'

    input:
    val url

    output:
    path "${url.tokenize('/').last()}", emit: downloaded
    path 'versions.yml', emit: versions

    script:
    def out_name = url.tokenize('/').last()
    def proxy_exports = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'no_proxy', 'NO_PROXY']
        .collect { key ->
            def value = System.getenv(key)
            value ? "export ${key}='${value.replace("'", "'\\''")}'" : null
        }
        .findAll { export_line -> export_line }
        .join('\n')
    """
    set -euo pipefail

    ${proxy_exports}

    wget --no-verbose --tries=3 -O '${out_name}' '${url}'

    cat <<-END_VERSIONS > versions.yml
    "${task.process}":
        wget: \$(wget --version | head -n1 | awk '{print \$3}')
    END_VERSIONS
    """
}