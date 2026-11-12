include { PREPARE_KNOWLEDGE_BUNDLE } from './workflows/prepare_knowledge_bundle'
include { PREPARE_REFERENCE_BUNDLE } from './workflows/prepare_reference_bundle'
include { ONCOHAWK } from './workflows/oncohawk'

workflow {
    main:
    if (!(params.workflow in ['oncohawk', 'prepare_reference_bundle', 'prepare_knowledge_bundle']))
        error("Unknown workflow '${params.workflow}'; choose oncohawk, prepare_reference_bundle or prepare_knowledge_bundle")
    if (params.workflow == 'prepare_knowledge_bundle')
        PREPARE_KNOWLEDGE_BUNDLE()
    supported = ['workflow', 'outdir'] + (params.workflow == 'oncohawk'
        ? ['input', 'reference_bundle', 'verify_bundle_checksums']
        : ['fasta', 'exclusions_bed', 'downloads_dir', 'download_ca_bundle',
           'fasta_sha256', 'exclusions_bed_sha256', 'fasta_identity', 'exclusions_bed_identity'])
    if (params.workflow == 'oncohawk') {
        if (!(params._oncohawk_output_path instanceof java.nio.file.Path))
            error('Invalid internal output-directory state; do not override _oncohawk_output_path')
        supported += '_oncohawk_output_path'
    }
    unsupported = params.keySet().findAll { name -> !(name in supported) }.sort()
    if (unsupported) {
        correction = 'profile' in unsupported ? ' Use -profile (single dash) to select a Nextflow configuration profile.' : ''
        error("Unsupported pipeline parameters: ${unsupported.collect { name -> '--' + name }.join(', ')}.${correction}")
    }
    reference = channel.empty()
    completed = channel.empty()
    if (params.workflow == 'prepare_reference_bundle') {
        PREPARE_REFERENCE_BUNDLE()
        reference = PREPARE_REFERENCE_BUNDLE.out.bundle.flatten()
    }
    if (params.workflow == 'oncohawk') {
        ONCOHAWK()
        completed = ONCOHAWK.out.samples
    }

    publish:
    reference_bundle = reference
    samples = completed
}

output {
    reference_bundle {
        path { artifact ->
            artifact >> artifact.name
        }
        mode 'copy'
        overwrite false
    }
    samples {
        path { meta, _bam, _bai -> "samples/${meta.sample}/alignments/" }
        mode 'copy'
        overwrite false
    }
}
