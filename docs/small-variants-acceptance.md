# Initial small variant acceptance

The accepted scope is [specification #45](https://github.com/micknudsen/oncohawk/issues/45), implemented by [#46](https://github.com/micknudsen/oncohawk/issues/46). This addition extends default analysis; the historical [alignment milestone record](milestone-1-acceptance.md) remains evidence for its original scope.

## Public acceptance boundaries

| Requirement | Evidence in the public CLI tests |
| --- | --- |
| Masked-reference FASTA index, dictionary, checksums, source and executed-tool provenance | `test_reference.py`: masked/indexed bundle and source-isolation cases |
| Real FASTQ-to-BAM-to-VCF, planted SNV and short insertion, correct alleles/sample and regional index query | `test_calls_planted_snv_and_insertion_with_readable_regional_index` |
| Real rejected record retained with `base_qual` FILTER; independent no-call sample and indexes | `test_retains_rejected_calls_and_isolates_a_no_call_sample` |
| All-filtered reads produce header-only BAM and VCF with usable indexes | Existing empty-BAM case extended in `test_alignment.py` |
| Correctly attributed BAM/VCF artifacts survive another sample's filter failure | `test_completed_variants_remain_usable_when_another_sample_filter_fails` |
| Existing read groups, library-aware duplicates, adapters, supplementary sequences, input rejection, collision protection and source preservation | Retained alignment/reference/dispatch regression suites |
| Added tasks use selected-workflow resources, native overrides/caps, bounded retries and opt-in diagnostics | Configuration, retry and analysis diagnostic tests |
| Upstream module integrity | `scripts/check_modules.py` compares all installed bytes to pinned Git objects |

## Execution evidence, 2026-11-15

Targeted local Docker checks passed on the development Mac with Nextflow 26.10.6, Java 21.0.13+9 and Python 3.12.16: planted SNV and insertion (44 s), real rejected-call and no-call sample isolation (56 s), existing empty-BAM scenarios (77 s), per-sample filter-failure publication (57 s), all five configuration tests (20 s), all ten resource/retry tests (30 s), and forged internal-state/native-output override rejection (35 s). The reference bundle contract test passed (20 s). These timings describe compact fixtures, not production performance.

The four added modules were installed with nf-core CLI 4.2.1 at upstream revision `20c6e6407f63748003b47f92837b64fb0a53ffa4`. Real tasks used samtools 1.25, Picard 3.5.0 and GATK 4.7.0.0; reference bundles record executed reference-tool versions. All 84 installed upstream module files matched their pinned Git objects.

The Q19 fixture uses real paired FASTQs, alignment, calling and default filtering. No caller output or FILTER label is injected. The positive fixture asserts independent planted truth, and both fixtures query final tabix indexes. PASS records are tumor-only candidates; they are not confirmed somatic variants.

An initial full local run exposed the upstream GATK temporary-directory conversion defect in the retained spaced-launch regression. Per-task native scratch was added through configuration. Both additive/replacement site configurations and relative/symlinked output paths then passed the unchanged public regression (83 s); both independent review axes found no issues in this correction. The earlier run was stopped after this known failure, and a complete corrected run was started.

Full local suite and required Linux CI results will be recorded after execution. Full-human-reference and SLURM/Apptainer runs remain informal operator checks and are not claimed by this record.
