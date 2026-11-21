# Genuine Ensembl VEP 116 RefSeq test subset

This is a coordinate-preserving subset of actual production cache data, qualified with real VEP 116.3 in the pristine nf-core module's container. It is not a synthetic transcript model or a renamed older cache.

`refseq-cache.tar.gz` contains original, byte-preserved release 116 members `homo_sapiens_refseq/116_GRCh38/info.txt`, `chr_synonyms.txt`, and chromosome 1 blocks `1000001-2000000.gz` and `45000001-46000000.gz`. All four members were independently compared byte-for-byte against the complete sequential source-archive extraction; full source SHA256 is recorded in provenance.json.

`annotation.fa.gz` has a single contig 1, length 46,100,000. Exact official unmasked GRCh38 genomic bases remain at 900001–2100000 and 44900001–46100000 inclusive. Other positions are padded N to keep the fixture compact; original coordinates are preserved. The corresponding production annotation resource is the complete Ensembl 116 unmasked primary assembly, not this padded subset. Separate genomic chromosome 1 and primary-assembly source files were shown to have identical chromosome 1 sequences.

`provenance.json` records source URLs, resource and fixture SHA256 values, RefSeq and MANE source versions, and retained intervals. MANE v1.5 comes from the official Ensembl 116 core metadata table because upstream cache info has no MANE-version field. Do not modify upstream info to add one.

Independent expected examples:

| Genomic variant (chr1) | RefSeq expectation |
| --- | --- |
|1232282 A>C|B3GALT6 NM_080605.4:c.4A>C; NP_542172.2:p.Lys2Gln|
|1232298 CGTG>C|B3GALT6 NM_080605.4:c.22_24del; NP_542172.2:p.Trp8del|
|1232281 GAAG>G|B3GALT6 NM_080605.4:c.4_6del; NP_542172.2:p.Lys2del|
|1232281 GA>G|B3GALT6 NM_080605.4:c.5del; NP_542172.2:p.Lys2SerfsTer13|
|1353203 C>T|MXRA8 NM_001282585.1:c.*98C>A; GIVEN_REF=C, USED_REF=G, BAM_EDIT=OK|
|1386646 G>A|NR_146722.2:n.2699C>T; noncoding transcript exon; no protein HGVS|
|45334490 C>T|MUTYH Select NM_001048174.2:c.16G>A / NP_001041639.1:p.Ala6Thr; Plus Clinical NM_001128425.2:c.58G>A / NP_001121897.1:p.Ala20Thr|

At 1232281 GA>G, changing only the following genomic 1232283 A to N prevents HGVS 3-prime shifting and produces c.4del instead of c.5del. This adjacent mask lies outside the variant REF span, directly exercising the separate unmasked annotation-reference requirement.

Model-transcript positive controls are XR_007065351.1 at 1128721 and XM_047444339.1 at 1254699. A real run without predicted exclusion confirms their presence; `--exclude_predicted` removes these consequences and retains the variant records. NM/NR known transcripts without MANE also remain.

Real VEP 116.3 requires explicit `--format vcf` for an empty header-only input. With it, output bgzip compression, tabix indexing and regional query all succeed. `--dont_skip` retains unsupported-contig/mismatch inputs, although native log messages may say skipped. Unsupported contigs can emit `intergenic_variant`, so this term alone is not a resource-coverage status.

Independent expectations come from the unchanged cached exon/CDS coordinates and the separately downloaded genomic sequence. B3GALT6 coding sequence starts at genomic 1232279 with `ATG AAG CTG`: changing c.4A>C changes Lys2's AAG to CAG. Codon 8 is TGG (Trp), and deleting it produces c.22_24del / p.Trp8del; the caller's left-normalized representation is 1232298 CGTG>C. For the frameshift case, independent translation yields `MSCCGGRGGGGRR*`, giving p.Lys2SerfsTer13. MUTYH's shared site changes GCA to ACA in both listed transcripts, with their different coding offsets.

MXRA8 is on the reverse strand. Its real cache `_rna_edit` at transcript position 1494 supplies C instead of the genomic transcript-strand G; coding ends at 1396, so the resulting variant is c.*98C>A. These expectations were established before asserting the VEP results.

The Lys2 in-frame deletion example is representation-sensitive in VEP 116.3: its shown GAAG>G representation gives p.Lys2del, while Mutect2 can left-normalize across the initiation codon to 1232280 TGAA>T, for which VEP reports p.Lys2? and start-related terms despite c.4_6del. The workflow preserves this native output. The public calling/annotation test uses the downstream Trp8 deletion for an unambiguous independently specified protein result.

[The annotation acceptance record](../../../docs/variant-annotation-acceptance.md) distinguishes public Nextflow workflow tests from controlled native VEP tests. Routine tests use only these compact committed assets; no production cache or whole-human FASTA download is required.
