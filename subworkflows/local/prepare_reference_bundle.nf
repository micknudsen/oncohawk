nextflow.enable.dsl=2

include { WGET } from '../../modules/nf-core/wget/main'
include { GUNZIP } from '../../modules/nf-core/gunzip/main'
include { BEDTOOLS_MASKFASTA } from '../../modules/nf-core/bedtools/maskfasta/main'

process VERIFY_REFERENCE_DOWNLOADS {
    tag 'default-grch38'
    container 'community.wave.seqera.io/library/coreutils_grep_gzip_lbzip2_pruned:838ba80435a629f8'

    input:
    tuple val(meta), path(fasta), path(exclusions), val(fasta_md5), val(exclusions_md5)

    output:
    tuple val(meta), path('source.fna.gz'), emit: fasta
    tuple val(meta), path('exclusions.bed'), emit: exclusions

    script:
    """
    printf '%s  %s\\n' '${fasta_md5}' '${fasta}' | md5sum --check --status
    printf '%s  %s\\n' '${exclusions_md5}' '${exclusions}' | md5sum --check --status
    ln -s '${fasta}' source.fna.gz
    ln -s '${exclusions}' exclusions.bed
    """

    stub:
    """
    touch source.fna.gz exclusions.bed
    """
}

process ASSEMBLE_REFERENCE_BUNDLE {
    tag 'oncohawk-reference-hg38-beta-1'
    publishDir params.outdir, mode: 'copy', overwrite: false

    input:
    path masked_fasta
    val fasta_url
    val fasta_md5
    val exclusions_url
    val exclusions_md5

    output:
    path 'reference'

    script:
    def fasta_name = 'GCA_000001405.15_GRCh38_no_alt_analysis_set.masked.fna'
    """
    mkdir -p reference/fasta
    cp '${masked_fasta}' "reference/fasta/${fasta_name}"
    sha256sum "reference/fasta/${fasta_name}" | cut -d ' ' -f 1 > masked.sha256
    cat > reference/manifest.json <<EOF
    {
      "bundle_id": "oncohawk-reference-hg38-beta-1",
      "source_fasta_url": "${fasta_url}",
      "source_fasta_md5": "${fasta_md5}",
      "exclusions_bed_url": "${exclusions_url}",
      "exclusions_bed_md5": "${exclusions_md5}",
      "masking": "bedtools maskfasta with zero-based, half-open BED intervals",
      "masked_fasta_sha256": "\$(cat masked.sha256)"
    }
    EOF
    """
}

workflow PREPARE_REFERENCE_BUNDLE {
    main:
    def fasta_url = 'https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz'
    def fasta_md5 = 'a08035b6a6e31780e96a34008ff21bd6'
    def exclusions_url = 'https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_GRC_exclusions.bed'
    def exclusions_md5 = 'bf5c011e0342f355422144eb3547b5d0'
    downloads = WGET(channel.of(
        [[id: 'GCA_000001405.15_GRCh38_no_alt_analysis_set'], fasta_url, 'fna.gz'],
        [[id: 'GCA_000001405.15_GRCh38_GRC_exclusions'], exclusions_url, 'bed']
    ))
    fasta_download = downloads.outfile.filter { meta, _path -> meta.id.contains('no_alt_analysis_set') }
    exclusions_download = downloads.outfile.filter { meta, _path -> meta.id.contains('GRC_exclusions') }
    verified = VERIFY_REFERENCE_DOWNLOADS(fasta_download.combine(exclusions_download).map { _fasta_meta, fasta, _exclusions_meta, exclusions -> tuple([id: 'grch38'], fasta, exclusions, fasta_md5, exclusions_md5) })
    decompressed = GUNZIP(verified.fasta)
    masked = BEDTOOLS_MASKFASTA(verified.exclusions, decompressed.gunzip.map { _meta, fasta -> fasta })
    ASSEMBLE_REFERENCE_BUNDLE(masked.fasta.map { _meta, fasta -> fasta }, fasta_url, fasta_md5, exclusions_url, exclusions_md5)

}
