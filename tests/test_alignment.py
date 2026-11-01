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
            os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT),
            "-profile", "docker,test", "--fasta", str(fasta), "--bed", str(bed),
            "--outdir", str(cls.bundle),
        ], cwd=cls.reference_directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (cls.reference_directory / "preparation.log").write_text(result.stdout)
        if result.returncode:
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
        with self.sheet.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)

    def align(self):
        self.run_count += 1
        result = subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT / "alignment.nf"),
            "-profile", "docker,test", "-with-trace", f"trace-{self.run_count}.tsv",
            "--reference_bundle", str(self.bundle), "--input", str(self.sheet),
            "--outdir", str(self.output),
        ], cwd=self.directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (self.directory / f"alignment-{self.run_count}.log").write_text(result.stdout)
        return result

    def samtools(self, *arguments):
        return subprocess.check_output([
            "docker", "run", "--rm", "--platform=linux/amd64",
            "-v", f"{self.output}:/data:ro", SAMTOOLS, "samtools", *arguments,
        ], text=True)

    def assert_bam_pairs(self, expected):
        records = [line.split("\t") for line in self.samtools("view", "/data/S1.bam").splitlines()]
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
        result = self.align()
        self.assertEqual(result.returncode, 0, result.stdout)
        records = [line.split("\t") for line in self.samtools("view", "/data/S1.bam").splitlines()]
        self.assertEqual([(r[0], r[2], int(r[3])) for r in records],
                         [("known", "chr1", 101), ("known", "chr1", 301)])
        header = self.samtools("view", "-H", "/data/S1.bam")
        self.assertIn("SO:coordinate", header)
        group = next(line for line in header.splitlines() if line.startswith("@RG\t"))
        self.assertIn("\tSM:S1", group)
        self.assertIn("\tLB:L1", group)
        self.assertIn("\tPU:FC1.1", group)
        identifier = next(field[3:] for field in group.split("\t") if field.startswith("ID:"))
        self.assertTrue(all(f"RG:Z:{identifier}" in record for record in records))
        self.assertEqual(len(self.samtools("view", "/data/S1.bam", "chr1:101-150").splitlines()), 1)

    def test_valid_sample_name_cannot_collide_with_internal_mapped_bam(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples(sample="input1.mapped")
        result = self.align()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.samtools("view", "-c", "/data/input1.mapped.bam").strip(), "2")
        self.assertIn("\tSM:input1.mapped", self.samtools("view", "-H", "/data/input1.mapped.bam"))

    def test_already_trimmed_input_names_are_preserved(self):
        self.r1 = self.directory / "input1_1.trim.fastq.gz"
        self.r2 = self.directory / "input1_2.trim.fastq.gz"
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        expected = [hashlib.sha256(path.read_bytes()).hexdigest() for path in [self.r1, self.r2]]
        self.samples()
        result = self.align()
        self.assertEqual([hashlib.sha256(path.read_bytes()).hexdigest() for path in [self.r1, self.r2]], expected)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.samtools("view", "-c", "/data/S1.bam").strip(), "2")

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
        self.assertFalse((self.output / "S1.bam").exists())

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
        records = [line.split("\t") for line in self.samtools("view", "/data/S1.bam").splitlines()]
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
        records = [line.split("\t") for line in self.samtools("view", "/data/S1.bam").splitlines()]
        self.assertEqual(len(records), 4)
        duplicate_names = [record[0] for record in records if int(record[1]) & 1024]
        self.assertEqual(len(duplicate_names), 2)
        self.assertEqual(len(set(duplicate_names)), 1)
        self.assertEqual([int(record[3]) for record in records], [501, 501, 801, 801])

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
        records = [line.split("\t") for line in self.samtools("view", "/data/S1.bam").splitlines()]
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
                self.assertEqual(self.samtools("view", "-c", "/data/S1.bam").strip(), "0")
                self.assertEqual(self.samtools("view", "/data/S1.bam", "chr1:1-6000"), "")
                self.assertIn("\tSM:S1", self.samtools("view", "-H", "/data/S1.bam"))

    def test_rejects_multiple_rows_explicitly(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        with self.sheet.open("a") as handle:
            handle.write(self.sheet.read_text().splitlines()[1] + "\n")
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Unsupported input: expected exactly one sample-sheet row", result.stdout)
        self.assertFalse((self.output / "S1.bam").exists())

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
                self.assertFalse((self.output / "S1.bam").exists())

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
                self.assertFalse((self.output / "S1.bam").exists())

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
                self.output = self.directory / label
                self.samples(fastq_1="../reads, folder/R1.fastq.gz",
                             fastq_2="../reads, folder/R2.fastq.gz", options=options)
                result = self.align()
                self.assertEqual(result.returncode, 0, result.stdout)
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
                self.assertFalse((self.output / "S1.bam").exists())

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
                self.assertFalse((self.output / "S1.bam").exists())
        self.samples()
        with gzip.open(self.r2, "wt") as handle:
            handle.write("@different_name/2\nACGTACGTACGTACGT\n+\nIIIIIIIIIIIIIIII\n")
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Error executing process > 'CUTADAPT", result.stdout)
        self.assertFalse((self.output / "S1.bam").exists())
        self.assertFalse((self.output / "S1.bam.bai").exists())

    def test_rejects_unsupported_or_corrupt_reference_bundle(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        self.bundle = Path(shutil.copytree(self.bundle, self.directory / "bundle"))
        manifest_path = self.bundle / "bundle.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["format_version"] = 99
        manifest_path.write_text(json.dumps(manifest))
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Unsupported reference-bundle format_version", result.stdout)
        self.assertFalse((self.output / "S1.bam").exists())
        manifest["format_version"] = 1
        manifest_path.write_text(json.dumps(manifest))
        with (self.bundle / "reference.fa").open("a") as handle:
            handle.write("A\n")
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Reference-bundle checksum mismatch: reference.fa", result.stdout)
        self.assertFalse((self.output / "S1.bam").exists())

    def test_preserves_existing_output_directory(self):
        self.reads([("known", self.chr1[100:200], reverse_complement(self.chr1[300:400]))])
        self.samples()
        self.output.mkdir()
        sentinel = self.output / "S1.bam"
        sentinel.write_text("existing data")
        result = self.align()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Alignment output directory already exists", result.stdout)
        self.assertEqual(sentinel.read_text(), "existing data")
        self.assertFalse((self.output / "S1.bam.bai").exists())


if __name__ == "__main__":
    unittest.main()
