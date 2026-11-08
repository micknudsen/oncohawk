// Persistent acquisition needs integrity verification and an atomic store commit.
process REFERENCE_DOWNLOAD {
    tag "$kind"
    cache false
    container 'python@sha256:a5bab0ff300f91231c2e68bf73a8a8d60762ac39ce1c50eaf6803e4c38a9062b'
    containerOptions {
        def mount = "'${downloads_dir.replace("'", "'\"'\"'")}:${downloads_dir.replace("'", "'\"'\"'")}'"
        workflow.containerEngine == 'docker' ? "--user \$(id -u):\$(id -g) -v $mount" :
            (workflow.containerEngine in ['apptainer', 'singularity'] ? "--bind $mount" : '')
    }

    input:
    tuple val(kind), val(asset)
    val downloads_dir
    path downloader
    path ca_bundle, stageAs: 'download-ca.pem'
    val proxy_environment
    val reference_label

    output:
    tuple val(kind), path('download.json'), emit: source

    script:
    def store = downloads_dir.replace("'", "'\"'\"'")
    def ca_option = ca_bundle ? "--ca-bundle '${ca_bundle}'" : ''
    // Empty values are intentional; env inputs warn about them during task preparation.
    // Export inside the container so inherited settings cannot override launch-time choices.
    def proxy_exports = proxy_environment.collect { name, value ->
        "export ${name}='${value.replace("'", "'\"'\"'")}'"
    }.join('\n')
    """
    ${proxy_exports}
    python3 '${downloader}' '${store}' '${asset}' ${ca_option}
    """
}
