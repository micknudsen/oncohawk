"""Real default-workflow annotation, plus controlled native VEP sequence cases."""

import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "tests/data/vep116"
IMAGE = "community.wave.seqera.io/library/ensembl-vep_perl-math-cdf_htslib_gzip_tar:43f77a48cc79bf38"
HTSLIB = "community.wave.seqera.io/library/htslib_samtools:1.25--704fb80d75745bd4"


def vcf(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as handle:
        lines = handle.read().splitlines()
    header = next(line for line in lines if line.startswith("#CHROM"))
    fields = next((line.split("Format: ", 1)[1].split('"', 1)[0].split("|")
                   for line in lines if line.startswith("##INFO=<ID=CSQ,")), [])
    records = [line.split("\t") for line in lines if not line.startswith("#")]
    consequences = {}
    for record in records:
        csq = next((entry[4:] for entry in record[7].split(";") if entry.startswith("CSQ=")), "")
        consequences[record[1]] = [dict(zip(fields, entry.split("|"))) for entry in csq.split(",") if entry]
    return header.split("\t")[9:], records, consequences


class AnnotationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = PROJECT / ".local/tests"
        root.mkdir(parents=True, exist_ok=True)
        cls.root = Path(tempfile.mkdtemp(prefix="annotation-", dir=root))
        cls.bundle = cls.root / "bundle"
        with gzip.open(DATA / "annotation.fa.gz", "rt") as handle:
            lines = handle.read().splitlines()
        cls.sequence = "".join(lines[1:])
        generator = random.Random(271828)
        cls.unsupported = "".join(generator.choices("ACGT", k=6000))
        source = cls.root / "alignment.fa.gz"
        cls.source = source
        with gzip.open(source, "wt") as handle:
            handle.write(">chr1\n" + "\n".join(lines[1:]) + "\n>unsupported\n" + cls.unsupported + "\n")
        bed = cls.root / "mask.bed"
        bed.write_text("# Sequence fixtures use explicitly chosen masks in separate context tests.\n")
        result = subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT),
            "--workflow", "prepare_reference_bundle", "-profile", "docker,test",
            "--fasta", str(source), "--exclusions_bed", str(bed),
            "--annotation_fasta", str(DATA / "annotation.fa.gz"),
            "--vep_cache", str(DATA / "refseq-cache.tar.gz"), "--outdir", str(cls.bundle),
        ], cwd=cls.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (cls.root / "preparation.log").write_text(result.stdout)
        if result.returncode:
            raise AssertionError(result.stdout)
        result = subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"), "config", "-o", "json", str(PROJECT),
        ], cwd=cls.root, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode:
            raise AssertionError(result.stdout)
        cls.options = shlex.split(json.loads(result.stdout)["process"]["withName:VARIANT_CONSEQUENCES_ANNOTATE"]["ext"]["args"])

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="case-", dir=self.root))

    def docker(self, image, *arguments):
        return subprocess.run([
            "docker", "run", "--rm", "--platform=linux/amd64",
            "-v", f"{self.directory}:/case", "-v", f"{self.bundle}:/bundle:ro",
            "-w", "/case", image, *arguments,
        ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def native_annotation(self, source, name="native", fasta="/bundle/annotation/reference.fa", options=None):
        """Run controlled records with the exact exported pipeline flags and prepared resources."""
        shutil.copyfile(self.bundle / "annotation/chr_synonyms.txt", self.directory / "chr_synonyms.txt")
        result = self.docker(
            IMAGE, "vep", "--input_file", source, "--output_file", f"{name}.vcf.gz",
            *(self.options if options is None else options), "--compress_output", "bgzip",
            "--fasta", fasta, "--assembly", "GRCh38", "--species", "homo_sapiens",
            "--cache", "--cache_version", "116", "--dir_cache", "/bundle/annotation/cache", "--fork", "1")
        (self.directory / f"{name}.log").write_text(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.directory / "STDERR").exists(), "Native diagnostics must remain in task logs")
        result_index = self.docker(IMAGE, "tabix", f"{name}.vcf.gz")
        self.assertEqual(result_index.returncode, 0, result_index.stdout)
        return vcf(self.directory / f"{name}.vcf.gz"), result.stdout

    def test_native_cache_transcripts_mane_corrections_and_record_retention(self):
        lines = (DATA / "cases.vcf").read_text().replace("##contig=<ID=1,", "##contig=<ID=chr1,").splitlines()
        header = [line for line in lines if line.startswith("#")]
        header.insert(-1, '##FILTER=<ID=Rejected,Description="Caller rejected">')
        header.insert(-1, '##INFO=<ID=ORIGINAL,Number=1,Type=String,Description="Preserved evidence">')
        header.insert(-1, '##contig=<ID=unsupported,length=100>')
        records = [line.split("\t") for line in lines if not line.startswith("#")]
        for record in records:
            record[0] = "chr1"
            record[7] = "ORIGINAL=source"
        records[0][6] = "Rejected"
        # This shared coding site independently changes GCA->ACA on both MANE transcripts.
        records = [record for record in records if record[1] != "45340252"]
        records += [
            ["chr1", "45334490", "MUTYH_shared", "C", "T", "60", "PASS", "ORIGINAL=source", "GT", "0/1"],
            ["chr1", "1005098", "intergenic", "C", "T", "60", "PASS", ".", "GT", "0/1"],
            ["chr1", "1232282", "multi", "A", "C,G", "60", "PASS", ".", "GT", "1/2"],
            ["unsupported", "1", "unsupported", "A", "C", "60", "Rejected", ".", "GT", "0/1"],
        ]
        records.sort(key=lambda row: (row[0], int(row[1])))
        source = self.directory / "cases.vcf"
        source.write_text("\n".join(header + ["\t".join(row) for row in records]) + "\n")
        (names, annotated, csq), diagnostics = self.native_annotation("cases.vcf")
        self.assertEqual(names, ["SAMPLE"])
        self.assertEqual([row[:7] + row[8:] for row in annotated], [row[:7] + row[8:] for row in records])
        for before, after in zip(records, annotated):
            if before[7] != ".":
                self.assertIn(before[7], after[7].split(";"))
        features = [row["Feature"] for entries in csq.values() for row in entries if row["Feature"]]
        self.assertTrue(any(name.startswith("NM_") for name in features))
        self.assertTrue(any(name.startswith("NR_") for name in features))
        self.assertFalse(any(name.startswith(("XM_", "XR_")) for name in features))
        coding = [row for row in csq["1232282"] if row["Feature"] == "NM_080605.4"]
        self.assertEqual({row["Allele"] for row in coding}, {"C", "G"})
        self.assertTrue(all(row["SYMBOL"] == "B3GALT6" and row["Gene"] == "126792" for row in coding))
        mane = {row["Feature"]: row for row in csq["45334490"]}
        self.assertEqual(mane["NM_001048174.2"]["HGVSc"], "NM_001048174.2:c.16G>A")
        self.assertEqual(mane["NM_001048174.2"]["HGVSp"], "NP_001041639.1:p.Ala6Thr")
        self.assertTrue(mane["NM_001048174.2"]["MANE_SELECT"])
        self.assertEqual(mane["NM_001128425.2"]["HGVSc"], "NM_001128425.2:c.58G>A")
        self.assertEqual(mane["NM_001128425.2"]["HGVSp"], "NP_001121897.1:p.Ala20Thr")
        self.assertTrue(mane["NM_001128425.2"]["MANE_PLUS_CLINICAL"])
        noncoding = next(row for row in csq["1386646"] if row["Feature"] == "NR_146722.2")
        self.assertEqual(noncoding["HGVSc"], "NR_146722.2:n.2699C>T")
        self.assertEqual(noncoding["HGVSp"], "")
        self.assertTrue(any(row["Feature"].startswith("NM_") and not row["MANE_SELECT"] and
                            not row["MANE_PLUS_CLINICAL"] for entries in csq.values() for row in entries))
        corrected = next(row for row in csq["1353203"] if row["Feature"] == "NM_001282585.1")
        self.assertEqual(corrected["HGVSc"], "NM_001282585.1:c.*98C>A")
        self.assertEqual((corrected["GIVEN_REF"], corrected["USED_REF"], corrected["BAM_EDIT"]), ("C", "G", "OK"))
        self.assertEqual(csq["1128721"][0]["Consequence"], "intergenic_variant")
        self.assertEqual(csq["1005098"][0]["Consequence"], "intergenic_variant")
        self.assertEqual(csq["1"][0]["Consequence"], "intergenic_variant")
        self.assertIn("unsupported", diagnostics)
        self.assertFalse({"gnomADg_AF", "gnomADe_AF", "MAX_AF", "CLIN_SIG", "PHENO", "PUBMED"}
                         & set(corrected))
        control_options = list(self.options)
        control_options.remove("--exclude_predicted")
        index = control_options.index("--transcript_filter")
        del control_options[index:index + 2]
        (_, _, models), _ = self.native_annotation("cases.vcf", name="predicted-control", options=control_options)
        self.assertTrue(any(row["Feature"].startswith("XR_") for row in models["1128721"]))
        self.assertTrue(any(row["Feature"].startswith("XM_") for row in models["1254699"]))

    def test_native_reference_mismatch_is_retained_without_ref_repair(self):
        source = self.directory / "mismatch.vcf"
        source.write_text('##fileformat=VCFv4.2\n##contig=<ID=chr1,length=46100000>\n'
                          '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n'
                          'chr1\t1232282\tmismatch\tG\tC\t60\tPASS\t.\n')
        (_, records, csq), diagnostics = self.native_annotation("mismatch.vcf")
        self.assertEqual(records[0][3:5], ["G", "C"])
        corrected = next(row for row in csq["1232282"] if row["Feature"] == "NM_080605.4")
        self.assertEqual(corrected["CHECK_REF"], "failed")
        self.assertIn("does not match", diagnostics)

    def test_native_hgvs_uses_unmasked_sequence_outside_variant_ref_span(self):
        source = self.directory / "context.vcf"
        source.write_text('##fileformat=VCFv4.2\n##contig=<ID=chr1,length=46100000>\n'
                          '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n'
                          'chr1\t1232281\tcontext\tGA\tG\t60\tPASS\t.\n')
        (_, _, csq), _ = self.native_annotation("context.vcf")
        unmasked = next(row for row in csq["1232281"] if row["Feature"] == "NM_080605.4")
        self.assertEqual(unmasked["HGVSc"], "NM_080605.4:c.5del")
        self.assertEqual(unmasked["HGVSp"], "NP_542172.2:p.Lys2SerfsTer13")
        shutil.copyfile(self.bundle / "annotation/reference.fa", self.directory / "masked.fa")
        shutil.copyfile(self.bundle / "annotation/reference.fa.fai", self.directory / "masked.fa.fai")
        _, _, offset, line_bases, line_width = (self.directory / "masked.fa.fai").read_text().split()
        offset, line_bases, line_width = map(int, (offset, line_bases, line_width))
        with (self.directory / "masked.fa").open("r+b") as handle:
            position = 1232283 - 1
            handle.seek(offset + position // line_bases * line_width + position % line_bases)
            self.assertEqual(handle.read(1), b"A")
            handle.seek(-1, 1)
            handle.write(b"N")
        (_, _, csq), _ = self.native_annotation("context.vcf", name="masked", fasta="masked.fa")
        masked = next(row for row in csq["1232281"] if row["Feature"] == "NM_080605.4")
        self.assertEqual(masked["HGVSc"], "NM_080605.4:c.4del")

    def sample_reads(self, sample, variants):
        generator = random.Random(20261121)
        mates = [self.directory / f"{sample}_R{mate}.fastq.gz" for mate in (1, 2)]
        with gzip.open(mates[0], "wt") as first, gzip.open(mates[1], "wt") as second:
            for variant, (contig, position, reference, alternate) in enumerate(variants):
                sequence = self.sequence if contig == "chr1" else self.unsupported
                self.assertEqual(sequence[position - 1:position - 1 + len(reference)], reference)
                for number in range(600):
                    start = position - 1 - generator.randrange(310)
                    fragment = sequence[start:start + generator.randrange(240, 380)]
                    offset = position - 1 - start
                    if number % 4 == 0 and offset + len(reference) <= len(fragment):
                        fragment = fragment[:offset] + alternate + fragment[offset + len(reference):]
                    for handle, mate, read in [(first, 1, fragment[:150]),
                                               (second, 2, fragment[-150:].translate(str.maketrans("ACGTN", "TGCAN"))[::-1])]:
                        handle.write(f"@{sample}_{variant}_{number}/{mate}\n{read}\n+\n{'I' * len(read)}\n")
        return [sample, "L1", "FC1", "1", *map(str, mates)]

    def sample_sheet(self, rows):
        sheet = self.directory / "samples.csv"
        with sheet.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["sample", "library", "flowcell", "lane", "fastq_1", "fastq_2"])
            writer.writerows(rows)
        return sheet

    def analyze(self, sheet, output, bundle=None, config=None, resume=False):
        result = subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"), *(["-c", str(config)] if config else []),
            "run", str(PROJECT), "-profile", "docker,test",
            "--input", str(sheet), "--reference_bundle", str(bundle or self.bundle), "--outdir", str(output),
            *(["-resume"] if resume else []),
        ], cwd=self.directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (self.directory / f"{output.name}.log").write_text(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        return result

    def preserved_callset(self, output, sample):
        directory = output / f"samples/{sample}/variants"
        original = directory / f"{sample}.mutect2.vcf.gz"
        annotated = directory / f"{sample}.mutect2.vep.vcf.gz"
        names, original_records, _ = vcf(original)
        annotated_names, records, csq = vcf(annotated)
        self.assertEqual(names, [sample])
        self.assertEqual(annotated_names, names)
        self.assertEqual([row[:7] + row[8:] for row in records],
                         [row[:7] + row[8:] for row in original_records])
        for before, after in zip(original_records, records):
            self.assertTrue(set(before[7].split(";")) <= set(after[7].split(";")))
        return original, annotated, records, csq

    def test_default_analysis_calls_and_annotates_known_snv_and_indel(self):
        unsupported_ref = self.unsupported[1500]
        unsupported_alt = "A" if unsupported_ref != "A" else "C"
        contexts = [("chr1", 45334490, "C", "T"), ("chr1", 1386646, "G", "A"),
                    ("chr1", 1353203, "C", "T"), ("chr1", 1128721, "G", "A"),
                    ("chr1", 1254699, "A", "C"), ("chr1", 1005098, "C", "T"),
                    ("unsupported", 1501, unsupported_ref, unsupported_alt)]
        sheet = self.sample_sheet([
            self.sample_reads("SNV", [("chr1", 1232282, "A", "C")]),
            self.sample_reads("INDEL", [("chr1", 1232298, "CGTG", "C")]),
            self.sample_reads("Contexts", contexts),
        ])
        output = self.directory / "results"
        before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.bundle.rglob("*") if path.is_file()}
        self.analyze(sheet, output)
        for sample, position, transcript_change, protein_change in [
            ("SNV", "1232282", "NM_080605.4:c.4A>C", "NP_542172.2:p.Lys2Gln"),
            ("INDEL", "1232298", "NM_080605.4:c.22_24del", "NP_542172.2:p.Trp8del"),
        ]:
            original, annotated, records, csq = self.preserved_callset(output, sample)
            transcript = next(row for row in csq[position] if row["Feature"] == "NM_080605.4")
            self.assertEqual(transcript["HGVSc"], transcript_change)
            self.assertEqual(transcript["HGVSp"], protein_change)
            self.assertTrue(transcript["MANE_SELECT"])
            for path in [original, annotated]:
                result = self.docker(HTSLIB, "tabix", "/case/" + str(path.relative_to(self.directory)),
                                     f"chr1:{position}-{position}")
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn(f"chr1\t{position}\t", result.stdout)
        _, _, records, csq = self.preserved_callset(output, "Contexts")
        self.assertEqual({(row[0], int(row[1]), row[3], row[4]) for row in records}, set(contexts))
        features = [row["Feature"] for entries in csq.values() for row in entries if row["Feature"]]
        self.assertTrue(any(name.startswith("NM_") for name in features))
        self.assertTrue(any(name.startswith("NR_") for name in features))
        self.assertFalse(any(name.startswith(("XM_", "XR_")) for name in features))
        mane = {row["Feature"]: row for row in csq["45334490"]}
        for name, hgvs_c, hgvs_p, flag in [
            ("NM_001048174.2", "NM_001048174.2:c.16G>A", "NP_001041639.1:p.Ala6Thr", "MANE_SELECT"),
            ("NM_001128425.2", "NM_001128425.2:c.58G>A", "NP_001121897.1:p.Ala20Thr", "MANE_PLUS_CLINICAL"),
        ]:
            self.assertEqual(mane[name]["HGVSc"], hgvs_c)
            self.assertEqual(mane[name]["HGVSp"], hgvs_p)
            self.assertTrue(mane[name][flag])
        noncoding = next(row for row in csq["1386646"] if row["Feature"] == "NR_146722.2")
        self.assertEqual((noncoding["HGVSc"], noncoding["HGVSp"]), ("NR_146722.2:n.2699C>T", ""))
        self.assertTrue(any(row["Feature"].startswith("NM_") and not row["MANE_SELECT"] and
                            not row["MANE_PLUS_CLINICAL"] for entries in csq.values() for row in entries))
        corrected = next(row for row in csq["1353203"] if row["Feature"] == "NM_001282585.1")
        self.assertEqual(corrected["HGVSc"], "NM_001282585.1:c.*98C>A")
        self.assertEqual((corrected["GIVEN_REF"], corrected["USED_REF"], corrected["BAM_EDIT"]), ("C", "G", "OK"))
        for position in ("1128721", "1005098", "1501"):
            self.assertEqual(csq[position][0]["Consequence"], "intergenic_variant")
        diagnostics = "\n".join(path.read_text() for path in (self.directory / "work").glob("*/*/.command.err"))
        self.assertIn("Chromosome unsupported not found in annotation sources or synonyms", diagnostics)
        control_options = list(self.options)
        control_options.remove("--exclude_predicted")
        index = control_options.index("--transcript_filter")
        del control_options[index:index + 2]
        config = self.directory / "model-control.config"
        config.write_text("process { withName: VARIANT_CONSEQUENCES_ANNOTATE { ext.args = " +
                          json.dumps(shlex.join(control_options)) + " } }\n")
        control_output = self.directory / "models"
        self.analyze(sheet, control_output, config=config, resume=True)
        _, _, _, models = self.preserved_callset(control_output, "Contexts")
        self.assertTrue(any(row["Feature"].startswith("XR_") for row in models["1128721"]))
        self.assertTrue(any(row["Feature"].startswith("XM_") for row in models["1254699"]))
        self.assertEqual({str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in self.bundle.rglob("*") if path.is_file()}, before)

    def test_public_annotation_uses_independent_unmasked_indel_context(self):
        # Keep the alignment source identical so real Mutect2 can call the indel.
        # The control changes only the following annotation base, outside REF.
        sheet = self.sample_sheet([self.sample_reads("Context", [("chr1", 1232281, "GA", "G")])])
        output = self.directory / "unmasked-results"
        self.analyze(sheet, output)
        original_path, _, original, csq = self.preserved_callset(output, "Context")
        self.assertTrue(any(row[1] == "1232281" and row[3:5] == ["GA", "G"] for row in original), original)
        transcript = next(row for row in csq["1232281"] if row["Feature"] == "NM_080605.4")
        self.assertEqual(transcript["HGVSc"], "NM_080605.4:c.5del")
        self.assertEqual(transcript["HGVSp"], "NP_542172.2:p.Lys2SerfsTer13")
        position = 1232283 - 1
        self.assertEqual(self.sequence[position], "A")
        masked_sequence = self.sequence[:position] + "N" + self.sequence[position + 1:]
        annotation = self.directory / "masked-annotation.fa.gz"
        with gzip.open(annotation, "wt") as handle:
            handle.write(">1\n")
            for offset in range(0, len(masked_sequence), 60):
                handle.write(masked_sequence[offset:offset + 60] + "\n")
        bed = self.directory / "mask.bed"
        bed.write_text("# Alignment is identical in both public context runs.\n")
        bundle = self.directory / "masked-annotation-bundle"
        result = subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT),
            "--workflow", "prepare_reference_bundle", "-profile", "docker,test",
            "--fasta", str(self.source), "--exclusions_bed", str(bed),
            "--annotation_fasta", str(annotation),
            "--vep_cache", str(DATA / "refseq-cache.tar.gz"), "--outdir", str(bundle),
        ], cwd=self.directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (self.directory / "masked-annotation-preparation.log").write_text(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads((bundle / "annotation/compatibility.json").read_text())
        self.assertEqual(report["alignment_masked_bases"]["chr1"], 0)
        chromosome = next(contig for contig in report["contigs"] if contig["alignment"] == "chr1")
        self.assertEqual(chromosome["annotation_gap_bases"], 1)
        self.assertEqual(hashlib.sha256((bundle / "reference.fa").read_bytes()).digest(),
                         hashlib.sha256((self.bundle / "reference.fa").read_bytes()).digest())
        control_output = self.directory / "masked-annotation-results"
        self.analyze(sheet, control_output, bundle=bundle, resume=True)
        control_path, _, _, csq = self.preserved_callset(control_output, "Context")
        self.assertEqual(vcf(control_path)[1], vcf(original_path)[1])
        transcript = next(row for row in csq["1232281"] if row["Feature"] == "NM_080605.4")
        self.assertEqual(transcript["HGVSc"], "NM_080605.4:c.4del")
        self.assertEqual(transcript["HGVSp"], "NP_542172.2:p.Lys2SerfsTer13")


if __name__ == "__main__":
    unittest.main()
