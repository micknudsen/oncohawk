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
        prepare_references   Download and index the GRCh38 reference genome

    Required arguments (for --workflow oncohawk):
        --input              Path to samplesheet CSV
                             Columns: sample,library,instrument,flowcell,lane,fastq_1,fastq_2
        --genome_fasta       Path to indexed reference FASTA
                             (or run --workflow prepare_references first)

    Optional arguments:
        --outdir             Output directory (default: 'results')
        --reference_dir      Directory for reference genome + indexes (default: 'references')
        --publish_dir_mode   How to publish files: copy, symlink, link (default: 'copy')

    Profiles (-profile, comma-separated):
        test                 Minimal synthetic dataset for local development
        hpc                  SLURM-based HPC configuration
        docker               Run processes in Docker containers
        singularity          Run processes in Singularity containers
        debug                Extra diagnostics, do not clean work dir

    Examples:
        # Run on the bundled synthetic test data
        nextflow run main.nf -profile test,docker

        # Prepare GRCh38 references (download + index)
        nextflow run main.nf --workflow prepare_references -profile hpc,singularity

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
include { PREPARE_REFERENCES  } from './workflows/prepare_references'

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
    else if (params.workflow == 'prepare_references') {
        PREPARE_REFERENCES()
    }
    else {
        error "Unknown workflow: '${params.workflow}'. " +
              "Valid options are: 'oncohawk', 'prepare_references'. " +
              "See `nextflow run main.nf --help` for usage."
    }

}



/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    THE END
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
