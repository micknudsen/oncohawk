"""Annotation resource preparation through the public Nextflow interface."""

import io
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class AnnotationPreparationTests(unittest.TestCase):
    def setUp(self):
        root = PROJECT / ".local/tests"
        root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix="annotation-preparation-", dir=root))
        self.source = self.directory / "source.fa"
        self.source.write_text(">chr1\nACGTACGT\n")
        self.annotation = self.directory / "annotation.fa"
        self.annotation.write_text(">1\nACGTACGT\n")
        self.exclusions = self.directory / "mask.bed"
        self.exclusions.write_text("chr1\t1\t2\n")
        self.cache = PROJECT / "tests/data/vep116/refseq-cache.tar.gz"
        self.bundle = self.directory / "bundle"
        self.run_count = 0

    def prepare(self, *arguments):
        self.run_count += 1
        result = subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT),
            "--workflow", "prepare_reference_bundle", "-profile", "docker,test",
            "--fasta", str(self.source), "--exclusions_bed", str(self.exclusions),
            "--annotation_fasta", str(self.annotation), "--vep_cache", str(self.cache),
            "--outdir", str(self.bundle), *arguments,
        ], cwd=self.directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (self.directory / f"preparation-{self.run_count}.log").write_text(result.stdout)
        return result

    def invalid_archive(self, entries):
        # Deliberately invalid archive fixtures test rejection, never annotation.
        self.cache = self.directory / "invalid-cache.tar.gz"
        with tarfile.open(self.cache, "w:gz") as archive:
            for name, data in entries.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    def test_rejects_cache_from_another_release_during_preparation(self):
        self.invalid_archive({"homo_sapiens_refseq/115_GRCh38/info.txt":
                              b"assembly\tGRCh38\nspecies\thomo_sapiens\n"})
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Annotation input error: expected a human RefSeq cache at homo_sapiens_refseq/116_GRCh38", result.stdout)
        self.assertFalse((self.bundle / "bundle.json").exists())

    def test_rejects_cache_metadata_with_incompatible_species_or_assembly(self):
        for species, assembly in [("mus_musculus", "GRCh38"), ("homo_sapiens", "GRCh37")]:
            with self.subTest(species=species, assembly=assembly):
                self.invalid_archive({"homo_sapiens_refseq/116_GRCh38/info.txt":
                                      f"assembly\t{assembly}\nspecies\t{species}\n".encode()})
                result = self.prepare()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Annotation input error: cache metadata must identify homo_sapiens / GRCh38", result.stdout)
                self.assertFalse((self.bundle / "bundle.json").exists())

    def test_verifies_annotation_source_bytes_before_unpacking(self):
        self.cache = self.directory / "damaged-cache.tar.gz"
        self.cache.write_bytes(b"not an archive")
        for parameter, label in [("annotation_fasta_sha256", "Annotation FASTA"),
                                 ("vep_cache_sha256", "VEP cache")]:
            with self.subTest(parameter=parameter):
                result = self.prepare(f"--{parameter}", "0" * 64)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(f"Annotation input error: {label} checksum mismatch (sha256)", result.stdout)
                self.assertFalse((self.bundle / "bundle.json").exists())

    def test_rejects_unexplained_genomic_base_disagreement(self):
        self.annotation.write_text(">1\nACGTTCGT\n")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Annotation input error: unexplained genomic-base disagreement at chr1:5 (1:5)", result.stdout)
        self.assertFalse((self.bundle / "bundle.json").exists())

    def test_prepares_references_with_iupac_ambiguity_codes(self):
        # chr1:248752514 in the default pair has alignment M and annotation N.
        self.source.write_text(">chr1\nMmRYSWKMBDHVN\n>chr2\nRa\n")
        self.annotation.write_text(">1\nNArYSWKMBDHVA\n>2\nRA\n")
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads((self.bundle / "annotation/compatibility.json").read_text())
        first, second = report["contigs"]
        self.assertEqual(first["compatible_ambiguous_bases"], 11)
        self.assertEqual(first["matching_known_bases"], 0)
        self.assertEqual(first["source_gap_bases"], 1)
        self.assertEqual(first["annotation_gap_bases"], 1)
        self.assertEqual(second["matching_known_bases"], 1)
        self.assertEqual(second["compatible_ambiguous_bases"], 1)
        self.assertEqual(report["alignment_masked_bases"]["chr1"], 1)
        self.assertEqual((self.bundle / "annotation/reference.fa").read_bytes(), self.annotation.read_bytes())

    def test_prepares_portable_annotation_assets_with_separate_resource_versions(self):
        source_bytes = self.source.read_bytes()
        annotation_bytes = self.annotation.read_bytes()
        result = self.prepare("--annotation_fasta_sha256", hashlib.sha256(annotation_bytes).hexdigest(),
                              "--vep_cache_sha256", hashlib.sha256(self.cache.read_bytes()).hexdigest())
        self.assertEqual(result.returncode, 0, result.stdout)
        manifest = json.loads((self.bundle / "bundle.json").read_text())
        metadata = manifest["annotation"]
        self.assertEqual(metadata["software_version"], "116.3")
        self.assertEqual(metadata["cache_version"], 116)
        self.assertEqual(metadata["species"], "homo_sapiens_refseq")
        self.assertEqual(metadata["refseq_version"],
                         "GCF_000001405.40-RS_2025_08 - GCF_000001405.40_GRCh38.p14_genomic.gff")
        self.assertEqual(metadata["mane_version"], "MANE v1.5")
        self.assertEqual(metadata["mane_version_source"],
                         "https://ftp.ensembl.org/pub/release-116/mysql/homo_sapiens_core_116_38/meta.txt.gz")
        self.assertEqual((self.bundle / metadata["fasta"]).read_bytes(), annotation_bytes)
        self.assertTrue((self.bundle / metadata["fasta_index"]).is_file())
        self.assertEqual((self.bundle / metadata["synonyms"]).read_text(), "1\tchr1\n")
        self.assertEqual((self.bundle / "reference.fa").read_text(), ">chr1\nANGTACGT\n")
        self.assertEqual(self.source.read_bytes(), source_bytes)
        self.assertEqual(self.annotation.read_bytes(), annotation_bytes)
        with tarfile.open(self.cache, "r:gz") as source:
            for member in source:
                if member.isfile():
                    relative = f"annotation/cache/{member.name}"
                    self.assertEqual((self.bundle / relative).read_bytes(), source.extractfile(member).read())
                    self.assertIn(relative, manifest["checksums"])
        for kind in ["annotation_fasta", "vep_cache"]:
            self.assertEqual(manifest["sources"][kind]["verified_checksum"],
                             "sha256:" + manifest["sources"][kind]["sha256"])

    def test_records_masks_assembly_gaps_aliases_and_unmatched_contigs(self):
        self.source.write_text(">chr1\nACGTNNACGT\n>chrM\nATGC\n>chrUn_KI270442v1\nAACG\n"
                               ">chr1_KN123v1_fix\nTTTT\n>chr2\nGGGG\n")
        self.annotation.write_text(">1\nACGTANNCGT\n>MT\nATGC\n>KI270442.1\nAACG\n>HG123_PATCH\nTTTT\n")
        self.exclusions.write_text("chr1\t1\t3\nchr2\t0\t1\n")
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads((self.bundle / "annotation/compatibility.json").read_text())
        self.assertEqual(report["aliases"], {"chr1": "1", "chrM": "MT", "chrUn_KI270442v1": "KI270442.1"})
        self.assertEqual(report["alignment_masked_bases"],
                         {"chr1": 2, "chrM": 0, "chrUn_KI270442v1": 0, "chr1_KN123v1_fix": 0, "chr2": 1})
        self.assertEqual(report["unmatched_alignment_contigs"], {"chr1_KN123v1_fix": 4, "chr2": 4})
        self.assertEqual(report["unmatched_annotation_contigs"], {"HG123_PATCH": 4})
        chromosome = next(contig for contig in report["contigs"] if contig["alignment"] == "chr1")
        self.assertEqual(chromosome, {"alignment": "chr1", "annotation": "1", "length": 10,
                                      "matching_known_bases": 7, "compatible_ambiguous_bases": 0, "source_gap_bases": 1,
                                      "annotation_gap_bases": 1, "shared_gap_bases": 1})
        self.assertIn("N", report["assembly_gap_policy"])
        self.assertEqual((self.bundle / "annotation/reference.fa").read_bytes(), self.annotation.read_bytes())

    def test_rejects_incomplete_cache_without_transcript_blocks(self):
        with tarfile.open(self.cache, "r:gz") as source:
            info = source.extractfile("homo_sapiens_refseq/116_GRCh38/info.txt").read()
        self.invalid_archive({"homo_sapiens_refseq/116_GRCh38/info.txt": info})
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Annotation input error: RefSeq cache contains no transcript blocks", result.stdout)
        self.assertFalse((self.bundle / "bundle.json").exists())

    def test_rejects_ambiguous_aliases_lengths_and_disagreement_hidden_by_masking(self):
        cases = [
            (">chr1\nACGTACGT\n", ">1\nACGTACG\n", "contig length mismatch"),
            (">chr1\nACGTACGT\n>1\nACGTACGT\n", ">1\nACGTACGT\n", "ambiguous contig aliases"),
            (">chr1\nACGTACGT\n", ">1\nACGTACGT\n>chr1\nACGTACGT\n", "ambiguous contig aliases"),
            (">chr1\nACGTACGT\n", ">1\nAAGTACGT\n", "unexplained genomic-base disagreement at chr1:2"),
            (">chr1\nARGTACGT\n", ">1\nAYGTACGT\n", "unexplained genomic-base disagreement at chr1:2"),
        ]
        for source, annotation, message in cases:
            with self.subTest(message=message):
                self.source.write_text(source)
                self.annotation.write_text(annotation)
                result = self.prepare()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Annotation input error: " + message, result.stdout)
                self.assertFalse((self.bundle / "bundle.json").exists())

    def test_does_not_alias_patch_scaffolds_to_chromosomes(self):
        self.source.write_text(">chr1_KN123v1_fix\nACGTACGT\n")
        self.exclusions.write_text("chr1_KN123v1_fix\t1\t2\n")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Annotation input error: alignment and annotation references have no matching contigs", result.stdout)

    def test_rejects_archive_paths_and_links_without_replacing_sources(self):
        sentinel = self.directory / "sentinel.txt"
        sentinel.write_bytes(b"preserved source")
        for kind in ["absolute", "traversal", "symlink", "hardlink"]:
            with self.subTest(kind=kind):
                self.cache = self.directory / "unsafe-cache.tar.gz"
                with tarfile.open(self.cache, "w:gz") as archive:
                    name = (str(sentinel) if kind == "absolute" else
                            "homo_sapiens_refseq/116_GRCh38/../../sentinel.txt" if kind == "traversal" else
                            "homo_sapiens_refseq/116_GRCh38/link")
                    member = tarfile.TarInfo(name)
                    if kind in ["symlink", "hardlink"]:
                        member.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
                        member.linkname = str(sentinel)
                        archive.addfile(member)
                    else:
                        member.size = 7
                        archive.addfile(member, io.BytesIO(b"changed"))
                result = self.prepare()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Annotation input error:", result.stdout)
                self.assertFalse((self.bundle / "bundle.json").exists())
                self.assertEqual(sentinel.read_bytes(), b"preserved source")


if __name__ == "__main__":
    unittest.main()
