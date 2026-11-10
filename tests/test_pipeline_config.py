"""Check configuration isolation without requiring production cluster access."""

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
REFERENCE_PROCESSES = {"REFERENCE_DOWNLOAD", "GUNZIP", "REFERENCE_VALIDATE", "BEDTOOLS_MASKFASTA",
                       "BWAMEM2_INDEX", "REFERENCE_BUNDLE"}
ALIGNMENT_PROCESSES = {"CUTADAPT", "BWAMEM2_MEM", "SAMTOOLS_MERGE",
                       "PICARD_MARKDUPLICATES", "SAMTOOLS_INDEX"}


class PipelineConfigurationTests(unittest.TestCase):
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
                        if selected != "prepare_knowledge_bundle":
                            expected = "reference" if selected == "prepare_reference_bundle" else "results"
                            self.assertIn(f"params.outdir = '{expected}'", result.stdout)
                        if profile == "slurm":
                            self.assertIn("process.executor = 'slurm'", result.stdout)
                            self.assertIn("apptainer.enabled = true", result.stdout)
                            self.assertIn("process.queue = 'REPLACE_WITH_PARTITION'", result.stdout)
                            if selected != "prepare_knowledge_bundle":
                                process = "BWAMEM2_INDEX" if selected == "prepare_reference_bundle" else "BWAMEM2_MEM"
                                memory = "128 GB" if selected == "prepare_reference_bundle" else "64 GB"
                                self.assertIn(f"process.'withName:{process}'.memory = '{memory}'", result.stdout)
                        else:
                            self.assertIn("docker.enabled = true", result.stdout)
                            self.assertIn("process.maxForks = 1", result.stdout)


if __name__ == "__main__":
    unittest.main()
