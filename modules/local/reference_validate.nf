// No upstream module validates the reference bundle's FASTA/BED compatibility contract.
process REFERENCE_VALIDATE {
    container 'python@sha256:a5bab0ff300f91231c2e68bf73a8a8d60762ac39ce1c50eaf6803e4c38a9062b'

    input:
    path fasta, stageAs: 'unmasked.fa'
    path bed, stageAs: 'exclusions.bed'
    path archive, stageAs: 'unmasked_source'
    val policy
    path validator

    output:
    path 'validated.bed', emit: bed
    path 'validation.json', emit: report
    path fasta, emit: fasta

    script:
    """
    python3 '${validator}' '${fasta}' exclusions.bed unmasked_source '${policy}'
    """
}
