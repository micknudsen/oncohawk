nextflow.enable.dsl=2

include { VALIDATE_SAMPLESHEET } from './subworkflows/local/validate_samplesheet'

workflow {
    if( !params.input ) {
        error "Missing required parameter: --input <sample-sheet.csv>"
    }

    VALIDATE_SAMPLESHEET(params.input)
}
