include { GUNZIP } from '../../modules/nf-core/gunzip/main'
include { BEDTOOLS_MASKFASTA } from '../../modules/nf-core/bedtools/maskfasta/main'
include { BWAMEM2_INDEX } from '../../modules/nf-core/bwamem2/index/main'
include { REFERENCE_BUNDLE } from '../../modules/local/reference_bundle'
include { REFERENCE_VALIDATE } from '../../modules/local/reference_validate'

def encoded(value) {
    return groovy.json.JsonOutput.toJson(value).getBytes('UTF-8').encodeBase64().toString()
}

def referenceInput(value) {
    def path = file(value, checkIfExists: true)
    if (path instanceof List)
        error('Reference inputs must each identify one file, not a wildcard collection')
    if (!(path.name ==~ /[A-Za-z0-9][A-Za-z0-9_.-]*/))
        error('Reference input filenames must contain only letters, digits, dots, underscores or hyphens')
    return path
}

workflow {
    repository = projectDir.parent.parent
    if (file(params.outdir).exists())
        error('Reference bundle output directory already exists; choose a new --outdir')
    allow_alt = params.allow_ncbi_alt_omission.toString()
    if (!(allow_alt in ['true', 'false']))
        error('--allow_ncbi_alt_omission must be true or false')
    ncbi_base = 'https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/'
    official_fasta = params.fasta == ncbi_base + 'GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz'
    official_bed = params.bed == ncbi_base + 'GCA_000001405.15_GRCh38_GRC_exclusions.bed'
    policy = encoded([
        fasta: [md5: official_fasta ? 'a08035b6a6e31780e96a34008ff21bd6' : null, sha256: params.fasta_sha256],
        bed: [md5: official_bed ? 'bf5c011e0342f355422144eb3547b5d0' : null, sha256: params.bed_sha256],
        alt_omission: official_fasta && official_bed ? 'checksum-verified NCBI no-ALT source pair' :
            (allow_alt == 'true' ? 'operator-declared NCBI no-ALT omission for custom inputs' : null)
    ])
    fasta = channel.of(referenceInput(params.fasta))
    bed = channel.of(referenceInput(params.bed))
    inputs = fasta.branch { path ->
        compressed: path.name.endsWith('.gz')
        plain: true
    }
    GUNZIP(inputs.compressed.map { path -> [[id: 'reference'], path] })
    uncompressed = GUNZIP.out.gunzip.map { _meta, path -> path }.mix(inputs.plain)
    REFERENCE_VALIDATE(uncompressed, bed, fasta, policy, file("$repository/bin/validate_reference.py"))
    BEDTOOLS_MASKFASTA(REFERENCE_VALIDATE.out.bed.map { path -> [[id: 'reference'], path] }, REFERENCE_VALIDATE.out.fasta)
    BWAMEM2_INDEX(BEDTOOLS_MASKFASTA.out.fasta)
    modules = new groovy.json.JsonSlurper().parseText(file("$repository/modules.json").text)
    source_paths = [
        'pipelines/reference/*.nf', 'pipelines/reference/*.config',
        'conf/common.config', 'conf/slurm.config', 'modules.json',
        'bin/validate_reference.py', 'bin/package_reference.py', 'modules/local/*.nf',
        'modules/nf-core/gunzip/main.nf', 'modules/nf-core/bedtools/maskfasta/main.nf',
        'modules/nf-core/bwamem2/index/main.nf'
    ]
    source_hashes = source_paths.collectMany { pattern -> files("$repository/$pattern") }
        .collectEntries { path ->
            [repository.relativize(path).toString(), java.security.MessageDigest.getInstance('SHA-256').digest(path.bytes).encodeHex().toString()]
        }
    metadata = encoded([
        sources: [fasta: [uri: params.fasta.toString()], bed: [uri: params.bed.toString()]],
        workflow: [repository: workflow.manifest.name, version: workflow.manifest.version,
                   nextflow: nextflow.version.toString(), commit: workflow.commitId, source_sha256: source_hashes],
        modules: modules.repos['https://github.com/nf-core/modules.git'].modules['nf-core']
            .subMap(['gunzip', 'bedtools/maskfasta', 'bwamem2/index'])
    ])
    versions = GUNZIP.out.versions_gunzip
        .mix(BEDTOOLS_MASKFASTA.out.versions_bedtools, BWAMEM2_INDEX.out.versions_bwamem2)
        .collect(flat: false).map { entries -> encoded(entries) }
    REFERENCE_BUNDLE(
        BEDTOOLS_MASKFASTA.out.fasta.map { _meta, path -> path }, BWAMEM2_INDEX.out.index.map { _meta, path -> path },
        REFERENCE_VALIDATE.out.report, metadata, versions, file("$repository/bin/package_reference.py")
    )
}
