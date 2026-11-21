// No upstream module validates the compatibility of the two reference roles.
process ANNOTATION_PREPARE {
    container 'python@sha256:a5bab0ff300f91231c2e68bf73a8a8d60762ac39ce1c50eaf6803e4c38a9062b'

    input:
    path source_fasta, stageAs: 'alignment_source.fa'
    path masked_fasta, stageAs: 'alignment_masked.fa'
    path annotation_fasta, stageAs: 'annotation_source.fa'
    path annotation_fai, stageAs: 'annotation_source.fa.fai'
    path annotation_archive, stageAs: 'annotation_source'
    path cache_archive, stageAs: 'cache.tar.gz'
    val policy
    path preparer
    val reference_label

    output:
    path 'annotation', emit: assets

    script:
    """
    python3 prepare_annotation.py alignment_source.fa alignment_masked.fa annotation_source.fa \\
        annotation_source.fa.fai annotation_source cache.tar.gz '${policy}'
    """
}
