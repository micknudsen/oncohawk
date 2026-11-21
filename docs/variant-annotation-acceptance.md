# RefSeq consequence annotation acceptance

This record covers [specification #51](https://github.com/micknudsen/oncohawk/issues/51) and [implementation issue #52](https://github.com/micknudsen/oncohawk/issues/52), dated 2026-11-21. It extends the historical alignment and small-variant milestones; their earlier acceptance records remain unchanged. PR delivery and required Linux CI are separate final checks.

## Resources and native behavior

The pristine nf-core VEP module was installed with CLI 4.2.1 at `20c6e6407f63748003b47f92837b64fb0a53ffa4`. Real Docker execution qualified VEP 116.3 / APIs 116 with the exact image and resource checksums documented in the [bundle guide](reference-bundle.md#annotation-resources-and-compatibility).

The complete official 26,409,563,680-byte RefSeq archive was streamed once during implementation to calculate SHA256. The four committed fixture members (two transcript blocks, original metadata, and original synonyms) match the complete extraction byte for byte. Routine tests require only the compact [committed fixture](../tests/data/vep116/README.md), not a whole-human download. The sparse genomic fixture preserves original coordinates and exact bases around tested transcripts. Its provenance identifies which distant bases are deliberately N-padded.

The source cache declares its RefSeq dataset separately from Ensembl release 116. MANE v1.5 is sourced separately from the matching release's core metadata because original cache metadata lacks that field. Nothing was added to the original cache metadata to manufacture provenance.

Two selected-version behaviors affected configuration: empty VCFs require `--format vcf`; explicit `--skipped_variants_file STDERR` names a literal file, so diagnostics retain the native default stderr streams. A mismatch with `--check_ref --dont_skip` can return success and native CHECK_REF=failed while preserving the supplied REF. An unsupported contig can retain an intergenic consequence, so empty CSQ or an intergenic term is not a unique failure diagnosis.

The fixture guide records a representation-sensitive initiation-codon deletion result. Native output is preserved. The full calling test uses an independently specified downstream Trp8 deletion for unambiguous HGVSc/HGVSp assertions.

## Acceptance mapping

| #52 criterion | Evidence boundary |
| --- | --- |
| 1–2: exact software/data pins and separate genomic references | `modules.json`, bundle guide, fixture `provenance.json`; full-source hashes and real container qualification. |
| 3: portable explicit preparation; offline default consumption | `test_prepares_masked_indexed_bundle`, `test_default_analysis_calls_and_annotates_known_snv_and_indel`; dispatcher/configuration regressions. |
| 4: verified acquisition and reuse | `test_annotation_sources_reuse_verified_downloads_across_preparations`; existing proxy, CA, concurrency, corruption, interrupted-transfer, and reuse tests continue through the shared downloader. |
| 5: aliases, lengths, known bases, gaps and unmatched contigs | Ten public preparation tests in `test_annotation_preparation.py`, including hidden-by-masking disagreement, ambiguous aliases, explicit gap counts, and patch-scaffold non-aliases. |
| 6: manifest, checksums, provenance, prepared immutable indexes | Public preparation assertions and source-isolation test; the full annotation workflow hashes every bundle artifact before/after concurrent sample use. |
| 7–8: early malformed/legacy/missing/incompatible checks; optional integrity | Public dispatcher tests plus existing alignment manifest, missing-artifact, unreadable-artifact/default-lightweight, and checksum-on-resume tests extended to all new artifacts. |
| 9: pristine default VEP composition; isolation/resources/retries | Public full workflow, configuration tests, native resource/retry probes, and upstream module integrity check. |
| 10–12: known RefSeq, all eligible consequences, MANE, native fields and limited scope | The public default FASTQ test includes a Contexts sample with both MANE roles, NR, non-MANE NM and model-only loci. A resumed public configuration control without transcript exclusions confirms genuine XM/XR models; native tests provide supporting detail. |
| 13–14: separate indexed outputs and record/allele/sample/FILTER preservation | Full default calling test; existing planted-call, rejected-call, sample layout, source preservation and override tests; native multiallelic preservation assertions. |
| 15–16: native diagnostics and reference-check behavior | Controlled real VEP tests assert retained unsupported/mismatch records, native CHECK_REF, and absence of a literal diagnostic sidecar; logs remain distinct from per-record interpretation. |
| 17: partial results and sample attribution | `test_annotation_failure_retains_original_calls_and_completed_other_sample`, plus existing output protection and caller/filter failure tests. |
| 18: public preparation → FASTQ → annotation with independent SNV/INDEL expectations | `test_default_analysis_calls_and_annotates_known_snv_and_indel`: B3GALT6 c.4A>C / p.Lys2Gln and c.22_24del / p.Trp8del, sample identity, all records preserved, and both regional indexes readable. |
| 19: actual RefSeq cache with both MANE roles and transcript classes | Untouched release-116 cache fixture; the public Contexts sample asserts both MUTYH MANE coding consequences, NR inclusion, model exclusion, non-MANE retention and model-only record retention. |
| 20: sequence context | Public MXRA8 transcript/genome correction and chr1/1 aliases; `test_public_annotation_uses_independent_unmasked_indel_context` pairs identical alignment/FASTQs with annotation references differing only at the adjacent base outside REF: c.5del unmasked versus c.4del masked, with identical original callsets. The masked annotation is an experimental N-gap control, not the default production source. Expectations derive independently from exon/CDS coordinates and genomic sequence. |
| 21: rejected/intergenic/unsupported/empty/multiple/failure cases | Public rejected-plus-empty multi-sample test, Contexts intergenic/unsupported records and native warning, and annotation failure test; native mismatch controls separately establish reference-check semantics. |
| 22–23: public regression seams; compact real Docker locally and required Linux CI | Existing CLI/configuration tests extended without internal channel mocks. Focused native VEP tests are supporting sequence/diagnostic evidence; they do not replace the complete public default workflow test. |
| 24: operator and domain documentation | README, alignment/bundle guides, root glossary, and this separate dated record. |
| 25: focused protected delivery | Required PR CI, protected squash merge, and issue closure are verified during delivery; no merge or cluster execution is claimed by local tests. |

## Validation status

Focused real Docker checks establish the complete public SNV/INDEL path, rejected and empty indexed outputs, annotation-failure partial publication, resource preparation compatibility/provenance, and controlled native sequence behavior. All 10 preparation test methods have passed. Configuration isolation and native resource/retry tests pass; all 94 installed nf-core files matched upstream immediately after installation.

The complete local suite ran **121 tests in 2761.057 seconds: 120 passed and one failed**. The sole failure was an existing unreadable-artifact test assuming checksum verification must encounter `reference.fa` first. Verification correctly rejected the first annotation-cache artifact instead. The test now requires an actual checksum-listed artifact path while preserving the nonzero-exit, no-task-submission and validation-order assertions; its focused public rerun passed in **27.026 seconds**. Runtime code did not change after the complete run began. The complete local invocation remains recorded as failed; it is not represented as an all-green rerun.

Both independent final Standards and Spec reviews report no findings, including the one-line test repair. All **94 installed nf-core module files** match their pinned upstream revisions. Python compilation and whitespace checks pass. Required Linux CI on the repaired final head remains a delivery check. Full-reference preparation and SLURM/Apptainer execution have not been run as formal acceptance; neither is a required gate for this issue.
