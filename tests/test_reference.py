"""Acceptance tests through the public reference-preparation workflow."""

import gzip
import hashlib
import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class ReferencePreparationTests(unittest.TestCase):
    def setUp(self):
        root = PROJECT / ".local" / "tests"
        root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix="reference-", dir=root))
        self.fasta = self.directory / "source.fa.gz"
        with gzip.open(self.fasta, "wt") as handle:
            handle.write(">chr1 description\nACGTACGTACGTACGTACGT\n>chr2\nTTTTCCCCAAAAGGGG\n")
        self.bed = self.directory / "exclusions.bed"
        self.bed.write_text("chr1\t4\t8\nchr2\t0\t2\n")
        self.bundle = self.directory / "bundle"
        self.run_count = 0

    def prepare(self, *arguments, launch_directory=None, default_output=False):
        self.run_count += 1
        command = [
            os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT / "pipelines/reference"),
            "-profile", "docker,test",
            "-with-trace", str(self.directory / f"trace-{self.run_count}.tsv"),
            "--fasta", str(self.fasta), "--bed", str(self.bed),
            *(["--outdir", str(self.bundle)] if not default_output else []), *arguments,
        ]
        result = subprocess.run(command, cwd=launch_directory or self.directory, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (self.directory / f"workflow-{self.run_count}.log").write_text(result.stdout)
        self.assertNotIn("There's no process matching config selector", result.stdout)
        return result

    def test_prepares_masked_indexed_bundle(self):
        result = self.prepare(launch_directory=PROJECT)
        self.assertEqual(result.returncode, 0, result.stdout)
        sequences = {}
        for line in (self.bundle / "reference.fa").read_text().splitlines():
            if line.startswith(">"):
                name = line[1:].split()[0]
                sequences[name] = ""
            else:
                sequences[name] += line
        self.assertEqual(sequences, {
            "chr1": "ACGTNNNNACGTACGTACGT", "chr2": "NNTTCCCCAAAAGGGG",
        })
        expected = {"reference.fa" + suffix for suffix in
                    [".0123", ".amb", ".ann", ".bwt.2bit.64", ".pac"]}
        self.assertEqual({p.name for p in (self.bundle / "bwamem2").iterdir()}, expected)
        self.assertTrue(all(p.stat().st_size > 0 for p in (self.bundle / "bwamem2").iterdir()))
        self.assertEqual((self.bundle / "bwamem2/reference.fa.amb").read_text().splitlines(),
                         ["36 2 2", "4 4 N", "20 2 N"])
        manifest = json.loads((self.bundle / "bundle.json").read_text())
        self.assertEqual(manifest["format_version"], 1)
        self.assertEqual(manifest["fasta"], "reference.fa")
        self.assertEqual(manifest["bwamem2_index"], "bwamem2/reference.fa")
        self.assertEqual(manifest["omitted_bed_entries"], [])
        self.assertEqual(manifest["sources"]["fasta"]["uri"], str(self.fasta))
        self.assertEqual(manifest["sources"]["fasta"]["sha256"], hashlib.sha256(self.fasta.read_bytes()).hexdigest())
        self.assertEqual(manifest["sources"]["bed"]["sha256"], hashlib.sha256(self.bed.read_bytes()).hexdigest())
        self.assertEqual(manifest["workflow"]["nextflow"], "26.10.4")
        self.assertEqual({entry["tool"] for entry in manifest["tools"]}, {"gunzip", "bedtools", "bwamem2"})
        self.assertTrue(all(entry["version"] for entry in manifest["tools"]))
        self.assertEqual(set(manifest["modules"]), {"gunzip", "bedtools/maskfasta", "bwamem2/index"})
        hashes = manifest["workflow"]["source_sha256"]
        self.assertIn("pipelines/reference/main.nf", hashes)
        self.assertIn("pipelines/reference/nextflow.config", hashes)
        self.assertIn("conf/common.config", hashes)
        self.assertIn("bin/validate_reference.py", hashes)
        self.assertIn("modules/nf-core/bwamem2/index/main.nf", hashes)
        self.assertFalse(any(path.startswith("pipelines/alignment/") for path in hashes))
        self.assertFalse(any(path.startswith("conf/containers_") for path in hashes))
        for source, checksum in hashes.items():
            self.assertFalse(Path(source).is_absolute())
            self.assertEqual(hashlib.sha256((PROJECT / source).read_bytes()).hexdigest(), checksum)
        for artifact, checksum in manifest["checksums"].items():
            self.assertFalse(Path(artifact).is_absolute())
            self.assertEqual(hashlib.sha256((self.bundle / artifact).read_bytes()).hexdigest(), checksum)

    def test_defaults_to_reference_in_launch_directory(self):
        result = self.prepare(default_output=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.directory / "reference/bundle.json").is_file())

    def test_rejects_unknown_bed_contig(self):
        self.bed.write_text("chrTypo\t0\t2\n")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("BED line 1: unknown contig 'chrTypo'", result.stdout)
        self.assertFalse((self.bundle / "bundle.json").exists())

    def test_rejects_invalid_bed_coordinates(self):
        for interval in ["-1\t2", "4\t21", "8\t4", "4\t4", "x\t8"]:
            with self.subTest(interval=interval):
                self.bed.write_text(f"chr1\t{interval}\n")
                result = self.prepare()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("BED line 1: invalid coordinates", result.stdout)
                self.assertFalse((self.bundle / "bundle.json").exists())

    def test_acquires_http_inputs_with_checksums(self):
        original = self.fasta
        expected = hashlib.sha256(original.read_bytes()).hexdigest()
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(self.directory))
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                self.fasta = f"{base}/source.fa.gz"
                self.bed = f"{base}/exclusions.bed"
                result = self.prepare("--fasta_sha256", expected)
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(result.returncode, 0, result.stdout)
        manifest = json.loads((self.bundle / "bundle.json").read_text())
        self.assertEqual(manifest["sources"]["fasta"]["uri"], self.fasta)
        self.assertEqual(manifest["sources"]["fasta"]["sha256"], expected)
        self.assertEqual(manifest["sources"]["fasta"]["verified_checksum"], f"sha256:{expected}")

    def test_acquisition_rejects_checksum_mismatch(self):
        result = self.prepare("--fasta_sha256", "0" * 64)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("FASTA checksum mismatch", result.stdout)
        self.assertFalse((self.bundle / "bundle.json").exists())

    def test_records_explicit_ncbi_alt_omission(self):
        self.bed.write_text(
            'track name="GRC exclusions"\nchr10_KI270825v1_alt\t0\t188315\tcontamination\nchr1\t4\t8\n'
        )
        result = self.prepare("--allow_ncbi_alt_omission", "true")
        self.assertEqual(result.returncode, 0, result.stdout)
        manifest = json.loads((self.bundle / "bundle.json").read_text())
        self.assertEqual(len(manifest["omitted_bed_entries"]), 1)
        omitted = manifest["omitted_bed_entries"][0]
        self.assertEqual([omitted[key] for key in ["line", "contig", "start", "end"]],
                         [2, "chr10_KI270825v1_alt", 0, 188315])
        self.assertIn("operator", omitted["reason"])
        self.assertIsNone(manifest["sources"]["fasta"]["verified_checksum"])

    def test_rejects_undeclared_or_changed_alt_omission(self):
        cases = [("chr10_KI270825v1_alt", 188315, []),
                 ("chr10_KI270825v1_alt", 188315, ["--allow_ncbi_alt_omission", "false"]),
                 ("chr10_KI270825v1_alt", 188314, ["--allow_ncbi_alt_omission", "true"]),
                 ("chr10_KI270826v1_alt", 188315, ["--allow_ncbi_alt_omission", "true"])]
        for contig, end, options in cases:
            with self.subTest(contig=contig, end=end, options=options):
                self.bed.write_text(f"{contig}\t0\t{end}\n")
                result = self.prepare(*options)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("unknown contig", result.stdout)
                self.assertFalse((self.bundle / "bundle.json").exists())

    def test_accepts_uncompressed_reference_without_changing_input(self):
        original = gzip.decompress(self.fasta.read_bytes())
        self.fasta = self.directory / "reference.fa"
        self.fasta.write_bytes(original)
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.fasta.read_bytes(), original)
        self.assertIn("ACGTNNNNACGTACGTACGT", (self.bundle / "reference.fa").read_text())

    def test_does_not_overwrite_existing_output(self):
        self.bundle.mkdir()
        sentinel = self.bundle / "bundle.json"
        sentinel.write_text("existing bundle")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("output directory already exists", result.stdout)
        self.assertEqual(sentinel.read_text(), "existing bundle")

    def test_rejects_empty_fasta_name_clearly(self):
        with gzip.open(self.fasta, "wt") as handle:
            handle.write(">   \nACGT\n")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("FASTA line 1: missing sequence name", result.stdout)
        self.assertFalse((self.bundle / "bundle.json").exists())


if __name__ == "__main__":
    unittest.main()
