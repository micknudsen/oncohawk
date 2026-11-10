"""Real acceptance tests through the public alignment workflow."""

import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
SAMTOOLS = "community.wave.seqera.io/library/htslib_samtools:1.25--704fb80d75745bd4"


def reverse_complement(sequence):
    return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]


def read_groups(header):
    return [dict(field.split(":", 1) for field in line.split("\t")[1:])
            for line in header.splitlines() if line.startswith("@RG\t")]


class AlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = PROJECT / ".local/tests"
        root.mkdir(parents=True, exist_ok=True)
        cls.reference_directory = Path(tempfile.mkdtemp(prefix="alignment-reference-", dir=root))
        generator = random.Random(271828)
        cls.chr1 = "".join(generator.choices("ACGT", k=6000))
        cls.chr2 = "".join(generator.choices("ACGT", k=6000))
        fasta = cls.reference_directory / "source.fa.gz"
        with gzip.open(fasta, "wt") as handle:
            handle.write(f">chr1\n{cls.chr1}\n>chr2\n{cls.chr2}\n")
        bed = cls.reference_directory / "mask.bed"
        bed.write_text("chr1\t4000\t4010\n")
        cls.bundle = cls.reference_directory / "bundle"
        result = subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT), "--workflow", "prepare_reference_bundle",
            "-profile", "docker,test", "--fasta", str(fasta), "--exclusions_bed", str(bed),
            "--outdir", str(cls.bundle),
        ], cwd=cls.reference_directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (cls.reference_directory / "preparation.log").write_text(result.stdout)
        if result.returncode or "There's no process matching config selector" in result.stdout:
            raise AssertionError(result.stdout)

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="alignment-", dir=PROJECT / ".local/tests"))
        self.sheet = self.directory / "samples.csv"
        self.output = self.directory / "results"
        self.r1 = self.directory / "R1.fastq.gz"
        self.r2 = self.directory / "R2.fastq.gz"
        self.run_count = 0

    def reads(self, pairs):
        for path, mate in [(self.r1, 1), (self.r2, 2)]:
            with gzip.open(path, "wt") as handle:
                for name, first, second in pairs:
                    sequence = first if mate == 1 else second
                    handle.write(f"@{name}/{mate}\n{sequence}\n+\n{'I' * len(sequence)}\n")

    def samples(self, **changes):
        row = dict(sample="S1", library="L1", flowcell="FC1", lane="1",
                   fastq_1=str(self.r1), fastq_2=str(self.r2))
        row.update(changes)
        self.sample_rows([row])

    def sample_rows(self, rows):
        with self.sheet.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def align(self, launch_directory=None, default_output=False, workflow=None, config=None, trace=False,
              diagnostics=False, outdir=None, config_mode="-c", arguments=()):
        self.run_count += 1
        diagnostic_flags = (["-with-trace", "trace.tsv", "-with-report", "report.html",
                             "-with-timeline", "timeline.html", "-with-dag", "dag.html"]
                            if diagnostics else
                            ["-with-trace", "trace.tsv"]
                            if trace else [])
        result = subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"),
            *([config_mode, str(config)] if config else []), "run", str(PROJECT),
            "-profile", "docker,test",
            *diagnostic_flags,
            "--reference_bundle", str(self.bundle), "--input", str(self.sheet),
            *(["--outdir", str(outdir if outdir is not None else self.output)] if not default_output else []),
            *(["--workflow", workflow] if workflow else []),
            *arguments,
        ], cwd=launch_directory or self.directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (self.directory / f"alignment-{self.run_count}.log").write_text(result.stdout)
        self.assertNotIn("There's no process matching config selector", result.stdout)
        self.assertNotIn("WARN: Unrecognized config option", result.stdout)
        return result

    def samtools(self, *arguments):
        return subprocess.check_output([
            "docker", "run", "--rm", "--platform=linux/amd64",
            "-v", f"{self.output}:/data:ro", SAMTOOLS, "samtools", *arguments,
        ], text=True)

    def assert_sample_tree(self, samples, diagnostics=()):
        expected = ["samples"]
        if diagnostics:
            expected.extend(["execution", *[f"execution/{name}" for name in diagnostics]])
        for sample in samples:
            expected.extend([
                f"samples/{sample}", f"samples/{sample}/alignments",
                f"samples/{sample}/alignments/{sample}.bam",
                f"samples/{sample}/alignments/{sample}.bam.bai",
            ])
        self.assertEqual(sorted(str(path.relative_to(self.output)) for path in self.output.rglob("*")),
                         sorted(expected))

    def assert_bam_pairs(self, expected, sample="S1"):
        records = [line.split("\t") for line in self.samtools("view", f"/data/samples/{sample}/alignments/{sample}.bam").splitlines()]
        self.assertEqual(len(records), len(expected) * 2)
        observed = {}
        for record in records:
            flag = int(record[1])
            self.assertFalse(flag & (256 | 2048), record)
            self.assertTrue(flag & 1, record)
            self.assertIn(flag & (64 | 128), [64, 128], record)
            mate = 1 if flag & 64 else 2
            observed[record[0], mate] = reverse_complement(record[9]) if flag & 16 else record[9]
        self.assertEqual(observed, {(name, mate): sequence
                                    for name, first, second in expected
                                    for mate, sequence in [(1, first), (2, second)]})

    def test_reference_to_bam_maps_known_pair_with_read_group(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        result = self.align(launch_directory=PROJECT)
        self.assertEqual(result.returncode, 0, result.stdout)
        records = [line.split("\t") for line in self.samtools("view", "/data/samples/S1/alignments/S1.bam").splitlines()]
        self.assertEqual([(r[0], r[2], int(r[3])) for r in records],
                         [("known", "chr1", 101), ("known", "chr1", 301)])
        header = self.samtools("view", "-H", "/data/samples/S1/alignments/S1.bam")
        self.assertIn("SO:coordinate", header)
        group = next(line for line in header.splitlines() if line.startswith("@RG\t"))
        self.assertIn("\tSM:S1", group)
        self.assertIn("\tLB:L1", group)
        self.assertIn("\tPU:FC1.1", group)
        identifier = next(field[3:] for field in group.split("\t") if field.startswith("ID:"))
        self.assertTrue(all(f"RG:Z:{identifier}" in record for record in records))
        self.assertEqual(len(self.samtools("view", "/data/samples/S1/alignments/S1.bam", "chr1:101-150").splitlines()), 1)

    def test_defaults_to_sample_outputs_under_results_in_launch_directory(self):
        self.reads([("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        result = self.align(default_output=True, trace=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(sorted(str(path.relative_to(self.output)) for path in self.output.rglob("*")), [
            "samples", "samples/S1", "samples/S1/alignments",
            "samples/S1/alignments/S1.bam", "samples/S1/alignments/S1.bam.bai",
        ])
        self.assert_bam_pairs([("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.assertEqual(len(self.samtools("view", "/data/samples/S1/alignments/S1.bam",
                                          "chr1:101-150").splitlines()), 1)
        self.assertFalse((self.directory / "alignments").exists())
        for pattern in ("trace*", "report*", "timeline*", "dag*"):
            self.assertEqual(list(self.directory.glob(pattern)), [])

    def test_enabled_diagnostics_describe_execution_under_default_results(self):
        pairs = [("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))]
        self.reads(pairs)
        self.samples()
        result = self.align(default_output=True, diagnostics=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_sample_tree(["S1"], ["trace.tsv", "report.html", "timeline.html", "dag.html"])
        self.assert_bam_pairs(pairs)
        with (self.output / "execution/trace.tsv").open() as handle:
            trace = list(csv.DictReader(handle, delimiter="\t"))
        self.assertTrue(trace)
        self.assertTrue(all(task["name"].startswith("ONCOHAWK:") for task in trace))
        self.assertTrue(any("CUTADAPT (S1 / L1 / FC1 / 1 / " in task["name"] for task in trace))
        for name in ("report.html", "timeline.html", "dag.html"):
            content = (self.output / "execution" / name).read_text()
            self.assertIn("CUTADAPT", content)
            self.assertIn("BWAMEM2_MEM", content)
        for name in ("trace.tsv", "report.html", "timeline.html", "dag.html"):
            self.assertFalse((self.directory / name).exists())

    def test_enabled_diagnostics_follow_relative_output_and_site_overrides(self):
        pairs = [("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))]
        self.reads(pairs)
        self.samples()
        launch = self.directory / "external launch"
        launch.mkdir()
        (launch / "results").mkdir()
        sentinel = launch / "results/existing.txt"
        sentinel.write_text("existing default results")
        (launch / "real parent").mkdir()
        (launch / "parent link").symlink_to(launch / "real parent", target_is_directory=True)
        for mode, selected, relative in [("-c", None, "parent link/fresh results"),
                                         ("-C", "oncohawk", "unused/../custom results")]:
            with self.subTest(config_mode=mode):
                site = self.directory / f"site-{mode}.config"
                site.write_text((f"includeConfig '{PROJECT / 'nextflow.config'}'\n" if mode == "-C" else "") +
                                "process { withName: BWAMEM2_MEM { cpus = 2 } }\n")
                self.output = Path(os.path.normpath(launch / relative))
                result = self.align(launch_directory=launch, workflow=selected, config=site,
                                    config_mode=mode, outdir=relative, diagnostics=True)
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assert_sample_tree(["S1"], ["trace.tsv", "report.html", "timeline.html", "dag.html"])
                self.assert_bam_pairs(pairs)
                with (self.output / "execution/trace.tsv").open() as handle:
                    trace = list(csv.DictReader(handle, delimiter="\t"))
                self.assertTrue(any("BWAMEM2_MEM (S1 / L1 / FC1 / 1 / " in task["name"] for task in trace))
                self.assertEqual(sentinel.read_text(), "existing default results")
                self.assertEqual(sorted(path.name for path in (launch / "results").iterdir()), ["existing.txt"])
                for name in ("trace.tsv", "report.html", "timeline.html", "dag.html"):
                    self.assertFalse((launch / name).exists())

    def test_enabled_diagnostics_preserve_genuinely_existing_roots(self):
        self.reads([("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        for label, content in [("empty", {}),
                               ("sample", {"samples/S1/alignments/S1.bam": b"existing BAM"}),
                               ("diagnostic", {"execution/previous-trace.tsv": b"existing trace"})]:
            with self.subTest(existing=label):
                self.output = self.directory / label
                self.output.mkdir()
                for name, data in content.items():
                    path = self.output / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                result = self.align(diagnostics=True)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Alignment output directory already exists", result.stdout)
                self.assertNotIn("Submitted process", result.stdout)
                for name, data in content.items():
                    self.assertEqual((self.output / name).read_bytes(), data)
                self.assertFalse((self.output / "samples/S1/alignments/S1.bam.bai").exists())

    def test_output_guard_rejects_native_path_mismatch_and_supplied_internal_state(self):
        self.reads([("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        for mode in ("-output-dir", "-c", "-C"):
            with self.subTest(native_override=mode):
                destination = self.directory / f"native-output-{mode}"
                if mode == "-output-dir":
                    result = self.align(arguments=[mode, str(destination)])
                else:
                    config = self.directory / f"native-{mode}.config"
                    config.write_text((f"includeConfig '{PROJECT / 'nextflow.config'}'\n"
                                       if mode == "-C" else "") + f"outputDir = '{destination}'\n")
                    result = self.align(config=config, config_mode=mode)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Analysis output selection must use --outdir", result.stdout)
                self.assertNotIn("Submitted process", result.stdout)
                self.assertFalse(destination.exists())
        supplied = self.directory / "supplied-params.json"
        supplied.write_text(json.dumps({"_oncohawk_output_path": str(self.output)}))
        result = self.align(arguments=["-params-file", str(supplied)])
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Invalid internal output-directory state", result.stdout)
        self.assertNotIn("Submitted process", result.stdout)
        self.output.mkdir()
        sentinel = self.output / "existing.txt"
        sentinel.write_text("preserved")
        result = self.align(arguments=["-params-file", str(supplied)], diagnostics=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Alignment output directory already exists", result.stdout)
        self.assertNotIn("Submitted process", result.stdout)
        self.assertEqual(sentinel.read_text(), "preserved")

    def test_preserves_preexisting_native_diagnostic_files(self):
        self.reads([("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        execution = self.output / "execution"
        execution.mkdir(parents=True)
        previous = {name: f"previous {name}".encode() for name in
                    ("trace.tsv", "report.html", "timeline.html", "dag.html")}
        for name, content in previous.items():
            (execution / name).write_bytes(content)
        result = self.align(diagnostics=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("already exists", result.stdout)
        self.assertNotIn("Submitted process", result.stdout)
        self.assertEqual({path.relative_to(self.output).as_posix() for path in self.output.rglob("*")},
                         {"execution", *[f"execution/{name}" for name in previous]})
        for name, content in previous.items():
            self.assertEqual((execution / name).read_bytes(), content)

    def test_explicit_and_default_oncohawk_match_with_cli_and_site_overrides(self):
        pairs = [("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))]
        self.reads(pairs)
        self.samples()
        site = self.directory / "site.config"
        site.write_text("process { withName: BWAMEM2_MEM {\n"
                        "  cpus = 2\n"
                        "  memory = '1 GB'\n"
                        "} }\n"
                        "trace.fields = 'task_id,name,cpus,memory'\n")
        observed = []
        for selected, destination in [(None, "default"), ("oncohawk", "explicit")]:
            self.output = self.directory / destination
            result = self.align(workflow=selected, config=site, trace=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assert_bam_pairs(pairs)
            self.assert_sample_tree(["S1"], ["trace.tsv"])
            observed.append((self.samtools("view", "/data/samples/S1/alignments/S1.bam"),
                             self.samtools("idxstats", "/data/samples/S1/alignments/S1.bam")))
            with (self.output / "execution/trace.tsv").open() as handle:
                trace = list(csv.DictReader(handle, delimiter="\t"))
            self.assertTrue(trace)
            self.assertTrue(all(task["name"].startswith("ONCOHAWK:") for task in trace))
            mapper = next(task for task in trace if ":BWAMEM2_MEM (" in task["name"])
            self.assertEqual(mapper["cpus"], "2")
            self.assertEqual(mapper["memory"], "1 GB")
            self.assertFalse((self.directory / "reference").exists())
        self.assertEqual(observed[0], observed[1])

    def test_completed_sample_remains_published_when_another_index_task_fails(self):
        pairs = [("pair", self.chr1[100:200], reverse_complement(self.chr1[300:400]))]
        rows = []
        for sample in ["S1", "S2"]:
            self.r1 = self.directory / f"{sample}_R1.fastq.gz"
            self.r2 = self.directory / f"{sample}_R2.fastq.gz"
            self.reads(pairs)
            rows.append(dict(sample=sample, library="L1", flowcell="FC1", lane="1",
                             fastq_1=str(self.r1), fastq_2=str(self.r2)))
        self.sample_rows(rows)
        # Use a public executor hook to fail S2 only after S1 has completed.
        # Two index slots avoid depending on task submission order.
        failure = self.directory / "failure.config"
        failure.write_text("process { withName: SAMTOOLS_INDEX {\n"
                           "  maxForks = 2\n"
                           "  beforeScript = { meta.sample == 'S2' ? \""
                           "for attempt in {1..60}; do "
                           f"if test -s '{self.output}/samples/S1/alignments/S1.bam.bai'; then exit 17; fi; "
                           "sleep 1; done; exit 18\" : '' }\n"
                           "} }\n")
        result = self.align(config=failure, diagnostics=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Error executing process > 'ONCOHAWK:SAMTOOLS_INDEX (S2)'", result.stdout)
        self.assertIn("17", result.stdout)
        self.assert_bam_pairs(pairs, sample="S1")
        self.assertEqual(len(self.samtools("view", "/data/samples/S1/alignments/S1.bam",
                                          "chr1:101-150").splitlines()), 1)
        self.assert_sample_tree(["S1"], ["trace.tsv", "report.html", "timeline.html", "dag.html"])
        self.assertTrue((self.output / "samples/S1/alignments/S1.bam.bai").is_file())
        self.assertFalse((self.output / "samples/S2/alignments/S2.bam").exists())
        self.assertFalse((self.output / "samples/S2/alignments/S2.bam.bai").exists())
        with (self.output / "execution/trace.tsv").open() as handle:
            trace = list(csv.DictReader(handle, delimiter="\t"))
        self.assertTrue(any(task["name"] == "ONCOHAWK:SAMTOOLS_INDEX (S2)" and task["status"] == "FAILED"
                            for task in trace))

    def test_valid_sample_name_cannot_collide_with_internal_mapped_bam(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples(sample="input1.mapped")
        result = self.align()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.samtools("view", "-c", "/data/samples/input1.mapped/alignments/input1.mapped.bam").strip(), "2")
        self.assertIn("\tSM:input1.mapped", self.samtools("view", "-H", "/data/samples/input1.mapped/alignments/input1.mapped.bam"))

    def test_already_trimmed_input_names_are_preserved(self):
        self.r1 = self.directory / "input1_1.trim.fastq.gz"
        self.r2 = self.directory / "input1_2.trim.fastq.gz"
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        expected = [hashlib.sha256(path.read_bytes()).hexdigest() for path in [self.r1, self.r2]]
        self.samples()
        result = self.align()
        self.assertEqual([hashlib.sha256(path.read_bytes()).hexdigest() for path in [self.r1, self.r2]], expected)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.samtools("view", "-c", "/data/samples/S1/alignments/S1.bam").strip(), "2")

    def test_internal_output_prefix_is_rejected_for_source_basenames(self):
        self.r1 = self.directory / "_input1_1.trim.fastq.gz"
        self.r2 = self.directory / "_input1_2.trim.fastq.gz"
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        expected = [hashlib.sha256(path.read_bytes()).hexdigest() for path in [self.r1, self.r2]]
        self.samples()
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("safe basename", result.stdout)
        self.assertEqual([hashlib.sha256(path.read_bytes()).hexdigest() for path in [self.r1, self.r2]], expected)
        self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())

    def test_filters_whole_pairs_at_the_14_15_base_boundary(self):
        first = self.chr1[100:200]
        second = reverse_complement(self.chr1[300:400])
        self.reads([("r1_short", first[:14], second),
                    ("r2_short", first, second[:14]),
                    ("exactly15", first[:15], second[:15]),
                    ("untrimmed", first, second)])
        # Low qualities must not trigger unrequested quality trimming.
        for path in [self.r1, self.r2]:
            lines = gzip.decompress(path.read_bytes()).decode().splitlines()
            for index in range(3, len(lines), 4):
                lines[index] = "!" * len(lines[index])
            with gzip.open(path, "wt") as handle:
                handle.write("\n".join(lines) + "\n")
        self.samples()
        result = self.align()
        self.assertEqual(result.returncode, 0, result.stdout)
        records = [line.split("\t") for line in self.samtools("view", "/data/samples/S1/alignments/S1.bam").splitlines()]
        self.assertEqual(sorted(record[0] for record in records),
                         ["exactly15", "exactly15", "untrimmed", "untrimmed"])
        for record in records:
            sequence = record[9]
            if int(record[1]) & 16:
                sequence = reverse_complement(sequence)
            mate = 1 if int(record[1]) & 64 else 2
            expected = first if mate == 1 else second
            if record[0] == "exactly15":
                expected = expected[:15]
            self.assertEqual(sequence, expected)

    def test_marks_but_retains_within_library_duplicates(self):
        first = self.chr1[500:600]
        second = reverse_complement(self.chr1[800:900])
        self.reads([("original", first, second), ("duplicate", first, second)])
        self.samples()
        result = self.align()
        self.assertEqual(result.returncode, 0, result.stdout)
        records = [line.split("\t") for line in self.samtools("view", "/data/samples/S1/alignments/S1.bam").splitlines()]
        self.assertEqual(len(records), 4)
        duplicate_names = [record[0] for record in records if int(record[1]) & 1024]
        self.assertEqual(len(duplicate_names), 2)
        self.assertEqual(len(set(duplicate_names)), 1)
        self.assertEqual([int(record[3]) for record in records], [501, 501, 801, 801])

    def test_combines_lanes_by_sample_with_library_aware_duplicates(self):
        self.output = self.directory / "custom-results"
        first = self.chr1[500:600]
        second = reverse_complement(self.chr1[800:900])
        inputs = [
            ("lane1", "S1", "L1", "1"),
            ("lane2", "S1", "L1", "2"),
            ("library2", "S1", "L2", "1"),
            ("sample2", "S2", "L1", "1"),
        ]
        rows = []
        sources = {}
        for name, sample, library, lane in inputs:
            directory = self.directory / name
            directory.mkdir()
            self.r1, self.r2 = directory / "R1.fastq.gz", directory / "R2.fastq.gz"
            self.reads([(name, first, second)])
            rows.append(dict(sample=sample, library=library, flowcell="FC1", lane=lane,
                             fastq_1=str(self.r1), fastq_2=str(self.r2)))
            sources.update({path: hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in [self.r1, self.r2]})
        self.sample_rows(rows)
        result = self.align()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_sample_tree(["S1", "S2"])
        self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}, sources)
        for sample, names in [("S1", {"lane1", "lane2", "library2"}), ("S2", {"sample2"})]:
            with self.subTest(sample=sample):
                header = self.samtools("view", "-H", f"/data/samples/{sample}/alignments/{sample}.bam")
                self.assertIn("SO:coordinate", header)
                groups = read_groups(header)
                self.assertEqual(len(groups), len(names))
                by_id = {group["ID"]: group for group in groups}
                records = [line.split("\t") for line in self.samtools("view", f"/data/samples/{sample}/alignments/{sample}.bam").splitlines()]
                self.assertEqual(len(records), 2 * len(names))
                self.assertEqual({record[0] for record in records}, names)
                self.assertEqual([int(record[3]) for record in records],
                                 [501] * len(names) + [801] * len(names))
                for record in records:
                    expected = next(row for row, item in zip(rows, inputs) if item[0] == record[0])
                    identifier = next(field[5:] for field in record[11:] if field.startswith("RG:Z:"))
                    group = by_id[identifier]
                    self.assertEqual((group["SM"], group["LB"], group["PU"]),
                                     (expected["sample"], expected["library"], f"FC1.{expected['lane']}"))
                    if record[0] in {"library2", "sample2"}:
                        self.assertFalse(int(record[1]) & 1024, record)
                duplicates = [record[0] for record in records if int(record[1]) & 1024]
                self.assertEqual(len(duplicates), 2 if sample == "S1" else 0)
                if duplicates:
                    self.assertEqual(len(set(duplicates)), 1)
                    self.assertIn(duplicates[0], {"lane1", "lane2"})
                self.assertEqual(len(self.samtools("view", f"/data/samples/{sample}/alignments/{sample}.bam", "chr1:501-550").splitlines()),
                                 len(names))

    def test_adapter_settings_apply_only_to_the_selected_mates(self):
        adapter1 = "AGATCGGAAGAGCACACGTCT"
        adapter2 = "CTGTCTCTTATACACATCTC"
        first = self.chr1[100:200]
        second = reverse_complement(self.chr1[300:400])
        raw_first, raw_second = first + adapter1 + "GGTT", second + adapter2
        self.reads([("adapter", raw_first, raw_second)])
        for label, settings, expected in [
            ("r1", {"options": f"r1_adapter={adapter1}"}, (first, raw_second)),
            ("r2", {"options": f"r2_adapter={adapter2}"}, (raw_first, second)),
            ("both", {"options": f" r2_adapter = {adapter2[:-1].lower()}n ; r1_adapter = {adapter1.lower()} "},
             (first, second)),
            ("omitted", {}, (raw_first, raw_second)),
        ]:
            with self.subTest(settings=label):
                self.output = self.directory / label
                self.samples(**settings)
                result = self.align()
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assert_bam_pairs([("adapter", *expected)])

    def test_split_fastq_chunks_preserve_read_groups_when_rows_are_reordered(self):
        rows = []
        inputs = [("chunk1", "FC.1", "2"), ("chunk2", "FC.1", "2"), ("other_lane", "FC", "1.2")]
        for name, flowcell, lane in inputs:
            self.r1, self.r2 = self.directory / f"{name}_R1.fastq.gz", self.directory / f"{name}_R2.fastq.gz"
            self.reads([(name, self.chr1[500:600], reverse_complement(self.chr1[800:900]))])
            rows.append(dict(sample="S1", library="L1", flowcell=flowcell, lane=lane,
                             fastq_1=str(self.r1), fastq_2=str(self.r2)))
        previous = None
        for label, ordered in [("original", rows), ("reordered", rows[::-1])]:
            self.output = self.directory / label
            self.sample_rows(ordered)
            result = self.align(trace=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            with (self.output / "execution/trace.tsv").open() as handle:
                trace = list(csv.DictReader(handle, delimiter="\t"))
            labels = {}
            for process in ["CUTADAPT", "BWAMEM2_MEM"]:
                names = [task["name"].split(":")[-1] for task in trace
                         if task["name"].split(":")[-1].startswith(f"{process} (")]
                self.assertEqual(len(names), 3)
                labels[process] = [name[len(process) + 2:-1] for name in names]
                self.assertEqual(len(set(labels[process])), 3)
                for label_text in labels[process]:
                    self.assertRegex(label_text, r"^S1 / L1 / (FC\.1 / 2|FC / 1\.2) / [0-9a-f]{12}$")
                self.assertEqual(sum(label_text.startswith("S1 / L1 / FC.1 / 2 / ")
                                     for label_text in labels[process]), 2)
            self.assertEqual(set(labels["CUTADAPT"]), set(labels["BWAMEM2_MEM"]))
            header = self.samtools("view", "-H", "/data/samples/S1/alignments/S1.bam")
            groups = read_groups(header)
            self.assertEqual(len(groups), 2)
            self.assertEqual({group["PU"] for group in groups}, {"FC%2E1.2", "FC.1%2E2"})
            by_id = {group["ID"]: group for group in groups}
            records = [line.split("\t") for line in self.samtools("view", "/data/samples/S1/alignments/S1.bam").splitlines()]
            self.assertEqual(len(records), 6)
            self.assertEqual(sum(bool(int(record[1]) & 1024) for record in records), 4)
            identities = {}
            observed = []
            for record in records:
                identifier = next(field[5:] for field in record[11:] if field.startswith("RG:Z:"))
                group = by_id[identifier]
                self.assertEqual((group["SM"], group["LB"]), ("S1", "L1"))
                expected_unit = "FC.1%2E2" if record[0] == "other_lane" else "FC%2E1.2"
                self.assertEqual(group["PU"], expected_unit)
                identities[record[0]] = identifier
                observed.append((record[0], int(record[1]), record[2], int(record[3]), identifier))
            self.assertEqual(set(identities), {"chunk1", "chunk2", "other_lane"})
            self.assertEqual(identities["chunk1"], identities["chunk2"])
            self.assertNotEqual(identities["chunk1"], identities["other_lane"])
            current = (sorted(tuple(sorted(group.items())) for group in groups), sorted(observed),
                       sorted(labels["CUTADAPT"]))
            if previous is not None:
                self.assertEqual(current, previous)
            previous = current

    def test_reference_to_multi_sample_bams_with_mixed_adapter_rows(self):
        # setUpClass prepares the shared bundle through the public reference workflow.
        adapter1 = "AGATCGGAAGAGCACACGTCT"
        adapter2 = "CTGTCTCTTATACACATCTC"
        first = self.chr1[100:200]
        second = reverse_complement(self.chr1[300:400])
        raw_first, raw_second = first + adapter1 + "GGTT", second + adapter2
        inputs = [
            ("blank", "S1", "1", "", raw_first, raw_second),
            ("r1", "S1", "2", f"r1_adapter={adapter1}", first, raw_second),
            ("r2", "S2", "1", f"r2_adapter={adapter2}", raw_first, second),
            ("both", "S2", "2", f"r1_adapter={adapter1};r2_adapter={adapter2}", first, second),
        ]
        rows = []
        sources = {}
        for name, sample, lane, options, _, _ in inputs:
            self.r1, self.r2 = self.directory / f"{name}_R1.fastq.gz", self.directory / f"{name}_R2.fastq.gz"
            self.reads([(name, raw_first, raw_second), (f"{name}_short", first[:14], second)])
            rows.append(dict(sample=sample, library="L1", flowcell="FC1", lane=lane,
                             fastq_1=str(self.r1), fastq_2=str(self.r2), options=options))
            sources.update({path: hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in [self.r1, self.r2]})
        self.sample_rows(rows)
        result = self.align(default_output=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_sample_tree(["S1", "S2"])
        self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}, sources)
        for sample in ["S1", "S2"]:
            expected = [(name, expected_first, expected_second)
                        for name, owner, _, _, expected_first, expected_second in inputs if owner == sample]
            self.assert_bam_pairs(expected, sample)
            groups = read_groups(self.samtools("view", "-H", f"/data/samples/{sample}/alignments/{sample}.bam"))
            self.assertEqual(len(groups), 2)
            by_id = {group["ID"]: group for group in groups}
            records = [line.split("\t") for line in self.samtools("view", f"/data/samples/{sample}/alignments/{sample}.bam").splitlines()]
            for record in records:
                identifier = next(field[5:] for field in record[11:] if field.startswith("RG:Z:"))
                group = by_id[identifier]
                expected_lane = next(lane for name, _, lane, _, _, _ in inputs if name == record[0])
                self.assertEqual((group["SM"], group["LB"], group["PU"]), (sample, "L1", f"FC1.{expected_lane}"))
            self.assertEqual(len(self.samtools("view", f"/data/samples/{sample}/alignments/{sample}.bam", "chr1:101-150").splitlines()), 2)

    def test_rejects_invalid_later_rows_before_processing_valid_rows(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        sources = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in [self.r1, self.r2]}
        self.samples(options="")
        with self.sheet.open(newline="") as handle:
            original = next(csv.DictReader(handle))
        for changes, expected in [
            ({"library": ""}, "missing library"),
            ({"options": "adapter=ACGT"}, "unknown option 'adapter'"),
            ({"fastq_1": "*.gz"}, "fastq_1 must name one .gz file with a safe basename"),
            ({"options": None}, "expected 7 columns, found 6"),
        ]:
            with self.subTest(changes=changes):
                row = dict(original, **changes)
                if row["options"] is None:
                    del row["options"]
                with self.sheet.open("w", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(original)
                    writer.writerow(original.values())
                    writer.writerow(row.values())
                result = self.align()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(f"Sample-sheet row 3: {expected}", result.stdout)
                self.assertFalse(self.output.exists())
                self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}, sources)

    def test_adapter_removal_filters_pairs_after_trimming_at_14_15_bases(self):
        adapter1 = "AGATCGGAAGAGCACACGTCT"
        adapter2 = "CTGTCTCTTATACACATCTC"
        first = self.chr1[100:200]
        second = reverse_complement(self.chr1[300:400])
        self.reads([
            ("r1_short", first[:14] + adapter1, second + adapter2),
            ("r2_short", first + adapter1, second[:14] + adapter2),
            ("exactly15", first[:15] + adapter1, second[:15] + adapter2),
            ("partial", first + adapter1[:10], second + adapter2[:10]),
        ])
        self.samples(options=f"r1_adapter={adapter1};r2_adapter={adapter2}")
        result = self.align()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assert_bam_pairs([("exactly15", first[:15], second[:15]), ("partial", first, second)])

    def test_split_read_keeps_complete_sequence_with_supplementary_soft_clipping(self):
        split = self.chr1[1000:1100] + self.chr2[2000:2100]
        adapter = "AGATCGGAAGAGCACACGTCT"
        self.reads([("split", split + adapter, reverse_complement(self.chr1[1300:1400]))])
        self.samples(options=f"r1_adapter={adapter}")
        result = self.align()
        self.assertEqual(result.returncode, 0, result.stdout)
        records = [line.split("\t") for line in self.samtools("view", "/data/samples/S1/alignments/S1.bam").splitlines()]
        first_mate = [record for record in records if int(record[1]) & 64]
        self.assertEqual({(record[2], int(record[3])) for record in first_mate},
                         {("chr1", 1001), ("chr2", 2001)})
        self.assertEqual(sum(bool(int(record[1]) & 2048) for record in first_mate), 1)
        for record in first_mate:
            self.assertIn("S", record[5])
            self.assertNotIn("H", record[5])
            sequence = reverse_complement(record[9]) if int(record[1]) & 16 else record[9]
            self.assertEqual(sequence, split)

    def test_all_filtered_pairs_produce_an_empty_indexed_bam(self):
        adapter = "AGATCGGAAGAGCACACGTCT"
        for label, tail, settings in [
            ("length_only", "", {}), ("adapter", adapter, {"options": f"r1_adapter={adapter}"}),
        ]:
            with self.subTest(settings=label):
                self.output = self.directory / label
                self.reads([("discarded", self.chr1[100:114] + tail, self.chr1[300:400])])
                self.samples(**settings)
                result = self.align()
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(self.samtools("view", "-c", "/data/samples/S1/alignments/S1.bam").strip(), "0")
                self.assertEqual(self.samtools("view", "/data/samples/S1/alignments/S1.bam", "chr1:1-6000"), "")
                self.assertIn("\tSM:S1", self.samtools("view", "-H", "/data/samples/S1/alignments/S1.bam"))

    def test_rejects_repeated_fastq_pairs(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        with self.sheet.open("a") as handle:
            handle.write(self.sheet.read_text().splitlines()[1] + "\n")
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Sample-sheet row 3: FASTQ file already used in row 2", result.stdout)
        self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())

    def test_rejects_sample_names_that_collide_ignoring_case(self):
        rows = []
        for label, sample in [("upper", "S1"), ("lower", "s1")]:
            self.r1, self.r2 = self.directory / f"{label}_R1.fastq.gz", self.directory / f"{label}_R2.fastq.gz"
            self.reads([(label, self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
            rows.append(dict(sample=sample, library="L1", flowcell="FC1", lane="1",
                             fastq_1=str(self.r1), fastq_2=str(self.r2)))
        self.sample_rows(rows)
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Sample-sheet row 3: sample IDs 'S1' and 's1' differ only by case", result.stdout)
        self.assertFalse(self.output.exists())

    def test_rejects_conflicting_read_groups_for_aliased_fastqs(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        sources = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in [self.r1, self.r2]}
        self.samples()
        with self.sheet.open(newline="") as handle:
            row = next(csv.DictReader(handle))
        alias = self.directory / "alias-R1.fastq.gz"
        alias.symlink_to(self.r1)
        row.update(library="L2", fastq_1=str(alias))
        with self.sheet.open("a", newline="") as handle:
            csv.DictWriter(handle, fieldnames=list(row)).writerow(row)
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Sample-sheet row 3: FASTQ file already used in row 2", result.stdout)
        self.assertIn("repeated or conflicting read-group assignment", result.stdout)
        self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}, sources)
        self.assertFalse(self.output.exists())

    def test_rejects_missing_or_unsafe_metadata(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        for field, value, expected in [
            ("library", "", "missing library"), ("sample", "", "missing sample"),
            ("flowcell", " ", "missing flowcell"), ("lane", "", "missing lane"),
            ("sample", "bad name", "invalid sample identifier"),
            ("library", "bad/library", "invalid library identifier"),
        ]:
            with self.subTest(field=field, value=value):
                self.samples(**{field: value})
                result = self.align()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(f"Sample-sheet row 2: {expected}", result.stdout)
                self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())

    def test_rejects_ambiguous_csv_headers(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        header, row = self.sheet.read_text().splitlines()
        for content, expected in [
            (header + ",extra\n" + row + ",value\n", "Unknown sample-sheet column 'extra'"),
            (header + ",sample\n" + row + ",S2\n", "Duplicate sample-sheet column 'sample'"),
            (header.replace("library,", "") + "\n" + row.replace("L1,", "") + "\n",
             "Missing sample-sheet column 'library'"),
        ]:
            with self.subTest(expected=expected):
                self.sheet.write_text(content)
                result = self.align()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(expected, result.stdout)
                self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())

    def test_accepts_blank_options_and_paths_relative_to_quoted_sheet_location(self):
        reads = self.directory / "reads, folder"
        reads.mkdir()
        self.r1, self.r2 = reads / "R1.fastq.gz", reads / "R2.fastq.gz"
        sheets = self.directory / "sample sheets"
        sheets.mkdir()
        self.sheet = sheets / "samples.csv"
        pairs = [("known", self.chr1[100:200] + "AGATCGGAAGAGCACACGTCT",
                  reverse_complement(self.chr1[300:400]) + "CTGTCTCTTATACACATCTC")]
        self.reads(pairs)
        for label, options in [("empty", ""), ("whitespace", " ")]:
            with self.subTest(options=label):
                self.output = Path("relative results") / label
                self.samples(fastq_1="../reads, folder/R1.fastq.gz",
                             fastq_2="../reads, folder/R2.fastq.gz", options=options)
                result = self.align()
                self.output = self.directory / self.output
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assert_sample_tree(["S1"])
                self.assert_bam_pairs(pairs)

    def test_rejects_malformed_unknown_repeated_or_nonsequence_options(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        for options, expected in [
            ("r1_adapter", "malformed options"), ("=ACGT", "malformed options"),
            ("r1_adapter=", "malformed options"), ("r1_adapter=ACGT=ACGT", "malformed options"),
            ("r1_adapter=ACGT;", "malformed options"),
            ("r1_adapter=ACGT;;r2_adapter=ACGT", "malformed options"),
            ("adapter=ACGT", "unknown option 'adapter'"),
            ("r1_adapter=ACGT;r1_adapter=TGCA", "repeated option 'r1_adapter'"),
            ("r2_adapter=ACGT;r2_adapter=TGCA", "repeated option 'r2_adapter'"),
            ("r1_adapter=ACGT$", "r1_adapter must be a DNA IUPAC sequence"),
            ("r2_adapter=ACGTX", "r2_adapter must be a DNA IUPAC sequence"),
            ("r1_adapter=ACGT...TGCA", "r1_adapter must be a DNA IUPAC sequence"),
            ("r1_adapter=ACGT$(true)", "r1_adapter must be a DNA IUPAC sequence"),
            ("r1_adapter=ACGT --quality-cutoff 20", "r1_adapter must be a DNA IUPAC sequence"),
        ]:
            with self.subTest(options=options):
                self.samples(options=options)
                result = self.align()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(f"Sample-sheet row 2: {expected}", result.stdout)
                self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())

    def test_rejects_unusable_fastq_paths_and_propagates_tool_failure(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        for value, expected in [
            ("", "missing fastq_1"), (str(self.r2), "R1 and R2 must be distinct files"),
            ("*.gz", "safe basename"), ("missing.fastq.gz", "No such file or directory"),
        ]:
            with self.subTest(value=value):
                self.samples(fastq_1=value)
                result = self.align()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(expected, result.stdout)
                self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())
        self.samples()
        with gzip.open(self.r2, "wt") as handle:
            handle.write("@different_name/2\nACGTACGTACGTACGT\n+\nIIIIIIIIIIIIIIII\n")
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Error executing process > 'ONCOHAWK:CUTADAPT", result.stdout)
        self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())
        self.assertFalse((self.output / "samples/S1/alignments/S1.bam.bai").exists())

    def test_rejects_unsupported_or_corrupt_reference_bundle(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        self.bundle = Path(shutil.copytree(self.bundle, self.directory / "bundle"))
        manifest_path = self.bundle / "bundle.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["bundle_format_version"] = 99
        manifest_path.write_text(json.dumps(manifest))
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Unsupported reference-bundle bundle_format_version", result.stdout)
        self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())
        manifest["bundle_format_version"] = 1
        manifest_path.write_text(json.dumps(manifest))
        with (self.bundle / "reference.fa").open("a") as handle:
            handle.write("A\n")
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Reference-bundle checksum mismatch: reference.fa", result.stdout)
        self.assertFalse((self.output / "samples/S1/alignments/S1.bam").exists())

    def test_preserves_existing_output_directory(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        sentinel = self.output / "samples/S1/alignments/S1.bam"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("existing data")
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Alignment output directory already exists", result.stdout)
        self.assertEqual(sentinel.read_text(), "existing data")
        self.assertFalse((self.output / "samples/S1/alignments/S1.bam.bai").exists())


if __name__ == "__main__":
    unittest.main()
