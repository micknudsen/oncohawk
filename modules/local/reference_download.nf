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
    env 'http_proxy'
    env 'https_proxy'

    output:
    tuple val(kind), path('download.json'), emit: source

    script:
    def store = downloads_dir.replace("'", "'\"'\"'")
    def ca_option = ca_bundle ? "--ca-bundle '${ca_bundle}'" : ''
    """
    python3 '${downloader}' '${store}' '${asset}' ${ca_option}
    """
}
