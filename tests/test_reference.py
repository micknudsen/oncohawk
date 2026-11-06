"""Acceptance tests through the public reference-preparation workflow."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import gzip
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
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
        # The fixture HTTP server runs on the host; requests must come from tasks.
        self.http_config = self.directory / "http.config"
        self.http_config.write_text(
            "docker.runOptions = '--platform=linux/amd64 --add-host=host.docker.internal:host-gateway'\n"
            # Work-directory cleanup must also handle root-owned downstream Docker outputs on Linux.
            "docker.fixOwnership = true\n")

    @contextmanager
    def http_sources(self, interrupted=None, delay=0):
        payloads = {"/source.fa.gz": self.fasta.read_bytes(), "/exclusions.bed": self.bed.read_bytes()}
        requests = Counter()
        request_lock = threading.Lock()
        interrupted = interrupted or {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                with request_lock:
                    requests[self.path] += 1
                    attempt = requests[self.path]
                payload = payloads[self.path]
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if self.path == "/source.fa.gz":
                    time.sleep(delay)
                if attempt <= interrupted.get(self.path, 0):
                    self.wfile.write(payload[:len(payload) // 2])
                    self.close_connection = True
                else:
                    self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        with http.server.ThreadingHTTPServer(("0.0.0.0", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield f"http://host.docker.internal:{server.server_port}", requests, payloads
            finally:
                server.shutdown()
                thread.join()

    def prepare(self, *arguments, launch_directory=None, default_output=False, project=PROJECT):
        self.run_count += 1
        run_number = self.run_count
        command = [
            os.environ.get("NEXTFLOW", "nextflow"), "run", str(project / "pipelines/reference"),
            "-profile", "docker,test",
            "-c", str(self.http_config),
            "-with-trace", str(self.directory / f"trace-{run_number}.tsv"),
            "--fasta", str(self.fasta), "--exclusions_bed", str(self.bed),
            *(["--outdir", str(self.bundle)] if not default_output else []), *arguments,
        ]
        result = subprocess.run(command, cwd=launch_directory or self.directory, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (self.directory / f"workflow-{run_number}.log").write_text(result.stdout)
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
        self.assertEqual(next(iter(manifest)), "bundle_format_version")
        self.assertEqual(manifest["bundle_format_version"], 1)
        self.assertEqual(manifest["fasta"], "reference.fa")
        self.assertEqual(manifest["bwamem2_index"], "bwamem2/reference.fa")
        self.assertEqual(manifest["omitted_exclusions_bed_entries"], [])
        self.assertEqual(manifest["sources"]["fasta"]["uri"], str(self.fasta))
        self.assertEqual(manifest["sources"]["fasta"]["sha256"], hashlib.sha256(self.fasta.read_bytes()).hexdigest())
        self.assertEqual(manifest["sources"]["exclusions_bed"]["sha256"], hashlib.sha256(self.bed.read_bytes()).hexdigest())
        self.assertEqual(manifest["workflow"]["nextflow"], "26.10.4")
        self.assertEqual({entry["tool"] for entry in manifest["tools"]}, {"gunzip", "bedtools", "bwamem2"})
        self.assertTrue(all(entry["version"] for entry in manifest["tools"]))
        self.assertEqual(set(manifest["modules"]), {"gunzip", "bedtools/maskfasta", "bwamem2/index"})
        hashes = manifest["workflow"]["source_sha256"]
        self.assertIn("pipelines/reference/main.nf", hashes)
        self.assertIn("pipelines/reference/nextflow.config", hashes)
        self.assertIn("conf/common.config", hashes)
        self.assertIn("bin/validate_reference.py", hashes)
        self.assertIn("bin/download_reference.py", hashes)
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

    def test_rejects_invalid_bed_coordinates(self):
        for interval in ["-1\t2", "4\t21", "8\t4", "4\t4", "x\t8"]:
            with self.subTest(interval=interval):
                self.bed.write_text(f"chr1\t{interval}\n")
                result = self.prepare()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("BED line 1: invalid coordinates", result.stdout)
                self.assertFalse((self.bundle / "bundle.json").exists())

    def test_acquires_http_inputs_with_checksums(self):
        expected = hashlib.sha256(self.fasta.read_bytes()).hexdigest()
        with self.http_sources() as (base, requests, _payloads):
            self.fasta = f"{base}/source.fa.gz"
            self.bed = f"{base}/exclusions.bed"
            result = self.prepare("--fasta_sha256", expected)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((self.directory / "downloads").is_dir())
            shutil.rmtree(self.directory / "work")
            shutil.rmtree(self.directory / ".nextflow")
            result = self.prepare("--fasta_sha256", expected,
                                  "--outdir", str(self.directory / "second-bundle"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(requests, {"/source.fa.gz": 1, "/exclusions.bed": 1})
        manifest = json.loads((self.bundle / "bundle.json").read_text())
        self.assertEqual(manifest["sources"]["fasta"]["uri"], self.fasta)
        self.assertEqual(manifest["sources"]["fasta"]["sha256"], expected)
        self.assertEqual(manifest["sources"]["fasta"]["verified_checksum"], f"sha256:{expected}")

    def test_acquisition_rejects_checksum_mismatch(self):
        result = self.prepare("--fasta_sha256", "0" * 64)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("FASTA checksum mismatch", result.stdout)
        self.assertFalse((self.bundle / "bundle.json").exists())

    def test_retries_interrupted_download_without_committing_partial_bytes(self):
        with self.http_sources(interrupted={"/source.fa.gz": 1}) as (base, requests, payloads):
            self.fasta = f"{base}/source.fa.gz"
            result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(requests["/source.fa.gz"], 2)
        manifest = json.loads((self.bundle / "bundle.json").read_text())
        self.assertEqual(manifest["sources"]["fasta"]["sha256"],
                         hashlib.sha256(payloads["/source.fa.gz"]).hexdigest())

    def test_concurrent_runs_download_each_asset_once(self):
        store = self.directory / "shared downloads"
        with self.http_sources(delay=8) as (base, requests, _payloads):
            self.fasta = f"{base}/source.fa.gz"
            self.bed = f"{base}/exclusions.bed"
            with ThreadPoolExecutor(max_workers=2) as executor:
                runs = []
                for number in range(2):
                    launch = self.directory / f"launch-{number}"
                    launch.mkdir()
                    runs.append(executor.submit(
                        self.prepare, "--downloads_dir", str(store),
                        "--outdir", str(launch / "bundle"), launch_directory=launch))
                for run in runs:
                    result = run.result(timeout=180)
                    self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(requests, {"/source.fa.gz": 1, "/exclusions.bed": 1})
        self.assertEqual((self.directory / "launch-0/bundle/reference.fa").read_bytes(),
                         (self.directory / "launch-1/bundle/reference.fa").read_bytes())

    def test_dataset_identity_changes_do_not_reuse_another_release(self):
        with self.http_sources() as (base, requests, _payloads):
            self.fasta = f"{base}/source.fa.gz"
            for release in ("v1", "v2"):
                identity = {"dataset": "fixture", "release": release, "assembly": "synthetic"}
                bundle = self.directory / release
                result = self.prepare("--fasta_identity", json.dumps(identity), "--outdir", str(bundle))
                self.assertEqual(result.returncode, 0, result.stdout)
                manifest = json.loads((bundle / "bundle.json").read_text())
                self.assertEqual(manifest["sources"]["fasta"]["identity"], identity)
        self.assertEqual(requests["/source.fa.gz"], 2)
        records = [json.loads(path.read_text()) for path in (self.directory / "downloads").glob("*/metadata.json")]
        self.assertEqual({record["asset"]["identity"]["release"] for record in records}, {"v1", "v2"})

    def test_failed_download_releases_ownership_without_a_completed_entry(self):
        interrupted = {"/source.fa.gz": 3}
        with self.http_sources(interrupted=interrupted) as (base, requests, _payloads):
            self.fasta = f"{base}/source.fa.gz"
            result = self.prepare()
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("Download failed after 3 attempts", result.stdout)
            self.assertEqual(requests["/source.fa.gz"], 3)
            store = self.directory / "downloads"
            self.assertEqual(list(store.glob("*/metadata.json")), [])
            self.assertEqual(list(store.glob("*/.lock")), [])
            self.assertEqual(list(store.glob("*/.partial-*")), [])
            self.assertFalse(self.bundle.exists())
            interrupted.clear()
            result = self.prepare()
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(requests["/source.fa.gz"], 4)

    def test_recovers_corrupt_and_incomplete_entries_even_with_resume(self):
        with self.http_sources() as (base, requests, payloads):
            self.fasta = f"{base}/source.fa.gz"
            self.bed = f"{base}/exclusions.bed"
            expected = hashlib.sha256(payloads["/source.fa.gz"]).hexdigest()
            result = self.prepare("--fasta_sha256", expected)
            self.assertEqual(result.returncode, 0, result.stdout)
            records = {}
            for path in (self.directory / "downloads").glob("*/metadata.json"):
                record = json.loads(path.read_text())
                records[record["asset"]["kind"]] = path
            fasta_metadata = records["fasta"]
            record = json.loads(fasta_metadata.read_text())
            source = fasta_metadata.parent / record["generation"] / "source.fa.gz"
            source.write_bytes(b"corrupt source bytes")
            records["exclusions_bed"].write_text("{incomplete metadata")
            result = self.prepare("-resume", "--fasta_sha256", expected,
                                  "--outdir", str(self.directory / "recovered"))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(requests, {"/source.fa.gz": 2, "/exclusions.bed": 2})
            # Missing bytes and orphan partial files must not become valid inputs either.
            record = json.loads(fasta_metadata.read_text())
            (fasta_metadata.parent / record["generation"] / "source.fa.gz").unlink()
            records["exclusions_bed"].unlink()
            partial = records["exclusions_bed"].parent / ".partial-interrupted"
            partial.mkdir()
            (partial / "exclusions.bed").write_text("chr1\t0\t20\n")
            result = self.prepare("--fasta_sha256", expected,
                                  "--outdir", str(self.directory / "recovered-missing"))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(requests, {"/source.fa.gz": 3, "/exclusions.bed": 3})
        self.assertEqual((self.bundle / "reference.fa").read_bytes(),
                         (self.directory / "recovered-missing/reference.fa").read_bytes())

    def test_uri_and_checksum_changes_cannot_alias_valid_entries(self):
        with self.http_sources() as (base, requests, payloads):
            self.fasta = f"{base}/source.fa.gz"
            result = self.prepare()
            self.assertEqual(result.returncode, 0, result.stdout)
            store = self.directory / "downloads"
            original_metadata = next(store.glob("*/metadata.json"))
            original_record = original_metadata.read_bytes()
            record = json.loads(original_record)
            original_source = original_metadata.parent / record["generation"] / "source.fa.gz"
            result = self.prepare("--fasta_sha256", "0" * 64,
                                  "--outdir", str(self.directory / "bad-checksum"))
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("checksum mismatch", result.stdout)
            self.assertEqual(requests["/source.fa.gz"], 2)
            self.assertEqual(original_metadata.read_bytes(), original_record)
            self.assertEqual(original_source.read_bytes(), payloads["/source.fa.gz"])
            self.assertEqual(len(list(store.glob("*/metadata.json"))), 1)
            self.assertEqual(list(store.glob("*/.lock")), [])
            expected = hashlib.sha256(payloads["/source.fa.gz"]).hexdigest()
            result = self.prepare("--fasta_sha256", expected,
                                  "--outdir", str(self.directory / "pinned"))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(requests["/source.fa.gz"], 3)
            payloads["/other/source.fa.gz"] = gzip.compress(b">chr1\nTTTTTTTTTTTTTTTTTTTT\n>chr2\nAAAAAAAAAAAAAAAA\n")
            self.fasta = f"{base}/other/source.fa.gz"
            result = self.prepare("--outdir", str(self.directory / "different-uri"))
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(requests["/other/source.fa.gz"], 1)
            self.assertIn("TTTTNNNNTTTTTTTTTTTT", (self.directory / "different-uri/reference.fa").read_text())
            self.assertEqual(len(list(store.glob("*/metadata.json"))), 3)

    def test_downstream_source_changes_reuse_downloads_in_fresh_runs(self):
        snapshot = self.directory / "pipeline-copy"
        for directory in ("pipelines", "modules", "bin", "conf"):
            shutil.copytree(PROJECT / directory, snapshot / directory)
        shutil.copyfile(PROJECT / "modules.json", snapshot / "modules.json")
        with self.http_sources() as (base, requests, _payloads):
            self.fasta = f"{base}/source.fa.gz"
            self.bed = f"{base}/exclusions.bed"
            result = self.prepare("--downloads_dir", "stored sources", project=snapshot)
            self.assertEqual(result.returncode, 0, result.stdout)
            changed = ("bin/validate_reference.py", "bin/package_reference.py",
                       "pipelines/reference/nextflow.config")
            for name in changed:
                with (snapshot / name).open("a") as handle:
                    handle.write("\n# Downstream code revision\n" if name.endswith(".py") else
                                 "\nprocess.withName.BEDTOOLS_MASKFASTA.ext.args = ''\n"
                                 "process.withName.BWAMEM2_INDEX.ext.args = ''\n")
            result = self.prepare("--downloads_dir", "stored sources",
                                  "--outdir", str(self.directory / "revised"), project=snapshot)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(requests, {"/source.fa.gz": 1, "/exclusions.bed": 1})
        before = json.loads((self.bundle / "bundle.json").read_text())
        after = json.loads((self.directory / "revised/bundle.json").read_text())
        for name in changed:
            self.assertNotEqual(before["workflow"]["source_sha256"][name],
                                after["workflow"]["source_sha256"][name])
        self.assertEqual(before["checksums"], after["checksums"])
        self.assertTrue((self.directory / "stored sources").is_dir())
        self.assertFalse((self.directory / "downloads").exists())

    def test_records_all_missing_exclusions_contigs(self):
        self.bed.write_text(
            'track name="exclusions"\nchr10_KI270825v1_alt\t0\t188314\tcontamination\n'
            'chr1\t4\t8\nchrMissing\t2\t7\nchrMissing\t8\t10\n'
        )
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout)
        manifest = json.loads((self.bundle / "bundle.json").read_text())
        self.assertEqual(manifest["omitted_exclusions_bed_entries"], [
            {"line": 2, "contig": "chr10_KI270825v1_alt", "start": 0, "end": 188314,
             "reason": "Contig missing in FASTA"},
            {"line": 4, "contig": "chrMissing", "start": 2, "end": 7,
             "reason": "Contig missing in FASTA"},
            {"line": 5, "contig": "chrMissing", "start": 8, "end": 10,
             "reason": "Contig missing in FASTA"},
        ])
        self.assertIn("ACGTNNNNACGTACGTACGT", (self.bundle / "reference.fa").read_text())
        self.assertIsNone(manifest["sources"]["fasta"]["verified_checksum"])

    def test_accepts_exclusions_with_only_missing_contigs(self):
        self.bed.write_text("chrMissing\t0\t5\n")
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.bundle / "reference.fa").read_text(),
                         ">chr1\nACGTACGTACGTACGTACGT\n>chr2\nTTTTCCCCAAAAGGGG\n")
        manifest = json.loads((self.bundle / "bundle.json").read_text())
        self.assertEqual(manifest["omitted_exclusions_bed_entries"], [
            {"line": 1, "contig": "chrMissing", "start": 0, "end": 5,
             "reason": "Contig missing in FASTA"},
        ])

    def test_accepts_uncompressed_reference_without_changing_input(self):
        original = gzip.decompress(self.fasta.read_bytes())
        self.fasta = self.directory / "reference.fa"
        self.fasta.write_bytes(original)
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.fasta.read_bytes(), original)
        self.assertFalse((self.directory / "downloads").exists())
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
