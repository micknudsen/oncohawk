// Bundle assembly has no upstream nf-core equivalent; tool steps remain pristine.
process REFERENCE_BUNDLE {
    container 'python@sha256:a5bab0ff300f91231c2e68bf73a8a8d60762ac39ce1c50eaf6803e4c38a9062b'

    input:
    path fasta
    path index
    path validation
    val metadata
    val versions
    path packager
    val reference_label

    output:
    path 'bundle/*'

    script:
    """
    python3 '${packager}' '${fasta}' '${index}' '${validation}' '${metadata}' '${versions}'
    """
}
