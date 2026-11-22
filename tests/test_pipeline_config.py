"""Check configuration isolation without requiring production cluster access."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
REFERENCE_PROCESSES = {"ANNOTATION_FASTA_DECOMPRESS", "ANNOTATION_FASTA_INDEX", "ANNOTATION_PREPARE", "REFERENCE_DOWNLOAD", "ALIGNMENT_FASTA_DECOMPRESS", "REFERENCE_VALIDATE", "ALIGNMENT_FASTA_MASK",
                       "ALIGNMENT_MAPPER_INDEX", "REFERENCE_BUNDLE_ASSEMBLE", "ALIGNMENT_FASTA_INDEX", "ALIGNMENT_SEQUENCE_DICTIONARY_CREATE"}
ALIGNMENT_PROCESSES = {"VARIANT_CONSEQUENCES_ANNOTATE", "READS_TRIM", "READS_ALIGN", "SAMPLE_ALIGNMENTS_MERGE",
                       "SAMPLE_DUPLICATES_MARK", "SAMPLE_BAM_INDEX", "VARIANTS_CALL", "VARIANTS_FILTER"}


class PipelineConfigurationTests(unittest.TestCase):
    def test_analysis_configuration_can_be_read_as_json_by_module_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                os.environ.get("NEXTFLOW", "nextflow"), "config", "-o", "json", str(PROJECT),
            ], cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            config = json.loads(result.stdout)
            self.assertEqual(config["manifest"]["name"], "micknudsen/oncohawk")
            self.assertEqual(config["params"]["outdir"], "results")
            self.assertFalse((Path(directory) / "results").exists())

    def test_local_container_pins_are_apptainer_compatible(self):
        for module in sorted((PROJECT / "modules/local").glob("*.nf")):
            with self.subTest(module=module.name):
                containers = re.findall(r"^\s*container\s+'([^']+)'", module.read_text(), re.MULTILINE)
                self.assertTrue(containers, f"Missing container declaration in {module}")
                for container in containers:
                    image, separator, digest = container.partition("@sha256:")
                    self.assertEqual(separator, "@sha256:", "Keep custom runtimes digest-pinned")
                    self.assertRegex(digest, r"^[0-9a-f]{64}$")
                    self.assertNotIn(":", image.rsplit("/", 1)[-1],
                                     "Apptainer does not support Docker references with both a tag and digest")

    def test_profiles_and_site_overrides_remain_workflow_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            for selected, foreign in [("prepare_reference_bundle", ALIGNMENT_PROCESSES),
                                      ("oncohawk", REFERENCE_PROCESSES),
                                      ("prepare_knowledge_bundle", REFERENCE_PROCESSES | ALIGNMENT_PROCESSES)]:
                for profile in ["docker,test", "slurm"]:
                    with self.subTest(workflow=selected, profile=profile):
                        # `config` has no pipeline parameter flags. Define selection before
                        # including the project, using the public configuration interface.
                        selection = Path(directory) / "selection.config"
                        selection.write_text(f"params.workflow = '{selected}'\n"
                                             f"includeConfig '{PROJECT / 'nextflow.config'}'\n")
                        if profile == "slurm":
                            with selection.open("a") as handle:
                                handle.write(f"includeConfig '{PROJECT / 'conf/site.example.config'}'\n")
                        command = [os.environ.get("NEXTFLOW", "nextflow"), "-C", str(selection),
                                   "config", str(PROJECT), "-profile", profile, "-flat"]
                        result = subprocess.run(command, cwd=directory, text=True,
                                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        self.assertEqual(result.returncode, 0, result.stdout)
                        for process in foreign:
                            self.assertNotIn(f"withName:{process}", result.stdout)
                        self.assertIn(f"params.workflow = '{selected}'", result.stdout)
                        for diagnostic in ["trace", "report", "timeline", "dag"]:
                            destination = f"{diagnostic}.directory = 'execution'"
                            if selected == "oncohawk":
                                self.assertIn(destination, result.stdout)
                            else:
                                self.assertNotIn(f"{diagnostic}.directory =", result.stdout)
                            enabled = re.search(rf"^{diagnostic}\.enabled = (.+)$",
                                                result.stdout, re.MULTILINE)
                            # An omitted enablement setting retains Nextflow's disabled default.
                            if enabled:
                                self.assertEqual(enabled.group(1), "false", result.stdout)
                        if selected != "oncohawk":
                            self.assertNotIn("params._oncohawk_output_path", result.stdout)
                        if selected != "prepare_knowledge_bundle":
                            expected = "reference" if selected == "prepare_reference_bundle" else "results"
                            self.assertIn(f"params.outdir = '{expected}'", result.stdout)
                        if profile == "slurm":
                            self.assertIn("process.executor = 'slurm'", result.stdout)
                            self.assertIn("process.maxRetries = 1", result.stdout)
                            self.assertIn("process.maxErrors = -1", result.stdout)
                            self.assertNotIn("process.resourceLimits =", result.stdout)
                            self.assertIn("apptainer.enabled = true", result.stdout)
                            self.assertIn("process.queue = 'REPLACE_WITH_PARTITION'", result.stdout)
                            if selected != "prepare_knowledge_bundle":
                                process = "ALIGNMENT_MAPPER_INDEX" if selected == "prepare_reference_bundle" else "READS_ALIGN"
                                # Runtime resource probes verify resolved attempt-specific values.
                                self.assertIn(f"process.'withName:{process}'.memory =", result.stdout)
                        else:
                            self.assertIn("docker.enabled = true", result.stdout)
                            self.assertIn("process.maxForks = 1", result.stdout)

    def test_analysis_resources_accept_additive_and_replacement_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            override = Path(directory) / "resources.config"
            for flag in ["-c", "-C"]:
                with self.subTest(config=flag):
                    override.write_text(
                        (f"includeConfig '{PROJECT / 'nextflow.config'}'\n" if flag == "-C" else "")
                        + f"includeConfig '{PROJECT / 'conf/site.example.config'}'\n"
                        + "process { withName: READS_ALIGN { cpus = 3; memory = '6 GB' } }\n")
                    command = [os.environ.get("NEXTFLOW", "nextflow"), flag, str(override),
                               "config", str(PROJECT), "-profile", "slurm", "-flat"]
                    result = subprocess.run(command, cwd=directory, text=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertEqual(result.returncode, 0, result.stdout)
                    for expected in ["process.executor = 'slurm'", "apptainer.enabled = true",
                                     "process.queue = 'REPLACE_WITH_PARTITION'",
                                     "process.'withName:READS_ALIGN'.cpus = 3",
                                     "process.'withName:READS_ALIGN'.memory = '6 GB'",
                                     "outputDir = 'results'", "trace.directory = 'execution'"]:
                        self.assertIn(expected, result.stdout)

    def test_analysis_config_inspection_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results"
            sentinel = output / "existing.txt"
            selection = Path(directory) / "selection.config"
            selection.write_text("params.workflow = 'oncohawk'\n"
                                 f"includeConfig '{PROJECT / 'nextflow.config'}'\n")
            for prefix, profile in [([], []), ([], ["-profile", "slurm"]),
                                    (["-C", str(selection)], [])]:
                with self.subTest(config=prefix, profile=profile):
                    command = [os.environ.get("NEXTFLOW", "nextflow"), *prefix,
                               "config", str(PROJECT), *profile, "-flat"]
                    fresh = subprocess.run(command, cwd=directory, text=True,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertEqual(fresh.returncode, 0, fresh.stdout)
                    self.assertFalse(output.exists())
                    output.mkdir()
                    sentinel.write_bytes(b"existing results")
                    result = subprocess.run(command, cwd=directory, text=True,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("Alignment output directory already exists", result.stdout)
                    self.assertEqual(list(output.iterdir()), [sentinel])
                    self.assertEqual(sentinel.read_bytes(), b"existing results")
                    sentinel.unlink()
                    output.rmdir()


if __name__ == "__main__":
    unittest.main()
