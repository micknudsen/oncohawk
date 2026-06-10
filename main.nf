#!/usr/bin/env nextflow

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ONCOHAWK
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Nextflow-based pipeline for tumor-only inference of somatic variation
    in myeloid malignancies (AML/MDS).
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

nextflow.enable.dsl = 2

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    HELP / VERSION
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

def helpMessage() {
    log.info """\

    ONCOHAWK  —  ${workflow.manifest.version}
    ${workflow.manifest.description}

    Usage:
        nextflow run main.nf -profile <profile> --workflow <workflow> [options]

    Workflows (--workflow):
        oncohawk             Main analysis workflow (default)
        prepare_reference   Download and index the GRCh38 reference genome

    Required arguments (for --workflow oncohawk):
        --input              Path to samplesheet CSV
                             Columns: sample,library,flowcell,lane,fastq_1,fastq_2
        --genome_fasta       Path to indexed reference FASTA
                             (or run --workflow prepare_reference first)

    Optional arguments:
        --outdir             Output directory (default: 'results')
        --reference_dir      Directory for reference genome + indexes (default: 'references')
        --publish_dir_mode   How to publish files: copy, symlink, link (default: 'copy')

    Profiles (-profile, comma-separated):
        hpc                  SLURM-based HPC configuration
        docker               Run processes in Docker containers
        singularity          Run processes in Singularity containers
        debug                Extra diagnostics, do not clean work dir

    Examples:
        # Prepare GRCh38 references (download + index)
        nextflow run main.nf --workflow prepare_reference -profile hpc,singularity

        # Run the main workflow with a custom samplesheet
        nextflow run main.nf -profile hpc,singularity \\
            --input samplesheet.csv --genome_fasta /path/to/genome.fa

    """.stripIndent()
}

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT WORKFLOWS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

include { ONCOHAWK            } from './workflows/oncohawk'
include { PREPARE_REFERENCE  } from './workflows/prepare_reference'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    MAIN ENTRY POINT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow {

    if (params.help) {
        helpMessage()
        return
    }

    if (params.version) {
        log.info "${workflow.manifest.name} v${workflow.manifest.version}"
        return
    }

    if (params.workflow == 'oncohawk') {
        ONCOHAWK()
    }
    else if (params.workflow == 'prepare_reference') {
        PREPARE_REFERENCE()
    }
    else {
        error "Unknown workflow: '${params.workflow}'. " +
              "Valid options are: 'oncohawk', 'prepare_reference'. " +
              "See `nextflow run main.nf --help` for usage."
    }

}



/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
