include { PREPARE_KNOWLEDGE_BUNDLE } from './workflows/prepare_knowledge_bundle'
include { PREPARE_REFERENCE_BUNDLE } from './workflows/prepare_reference_bundle'
include { ONCOHAWK } from './workflows/oncohawk'

workflow {
    main:
    if (!(params.workflow in ['oncohawk', 'prepare_reference_bundle', 'prepare_knowledge_bundle']))
        error("Unknown workflow '${params.workflow}'; choose oncohawk, prepare_reference_bundle or prepare_knowledge_bundle")
    if (params.workflow == 'prepare_knowledge_bundle')
        PREPARE_KNOWLEDGE_BUNDLE()
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
