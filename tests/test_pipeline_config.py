"""Check configuration isolation without requiring production cluster access."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
REFERENCE_PROCESSES = {"GUNZIP", "REFERENCE_VALIDATE", "BEDTOOLS_MASKFASTA",
                       "BWAMEM2_INDEX", "REFERENCE_BUNDLE"}
ALIGNMENT_PROCESSES = {"CUTADAPT", "BWAMEM2_MEM", "SAMTOOLS_MERGE",
                       "PICARD_MARKDUPLICATES", "SAMTOOLS_INDEX"}


class PipelineConfigurationTests(unittest.TestCase):
    def test_profiles_and_site_overrides_remain_pipeline_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            for pipeline, foreign in [("reference", ALIGNMENT_PROCESSES),
                                      ("alignment", REFERENCE_PROCESSES)]:
                for profile in ["docker,test", "slurm"]:
                    with self.subTest(pipeline=pipeline, profile=profile):
                        command = [os.environ.get("NEXTFLOW", "nextflow"), "config",
                                   str(PROJECT / "pipelines" / pipeline),
                                   "-profile", profile, "-flat"]
                        if profile == "slurm":
                            command[1:1] = ["-c", str(PROJECT / "conf/site.example.config")]
                        result = subprocess.run(command, cwd=directory, text=True,
                                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        self.assertEqual(result.returncode, 0, result.stdout)
                        for process in foreign:
                            self.assertNotIn(f"withName:{process}", result.stdout)
                        expected = "reference" if pipeline == "reference" else "alignments"
                        self.assertIn(f"params.outdir = '{expected}'", result.stdout)
                        if profile == "slurm":
                            self.assertIn("process.executor = 'slurm'", result.stdout)
                            self.assertIn("apptainer.enabled = true", result.stdout)
                            self.assertIn("process.queue = 'REPLACE_WITH_PARTITION'", result.stdout)
                            process = "BWAMEM2_INDEX" if pipeline == "reference" else "BWAMEM2_MEM"
                            memory = "128 GB" if pipeline == "reference" else "64 GB"
                            self.assertIn(f"process.'withName:{process}'.memory = '{memory}'", result.stdout)
                        else:
                            self.assertIn("docker.enabled = true", result.stdout)
                            self.assertIn("process.maxForks = 1", result.stdout)


if __name__ == "__main__":
    unittest.main()
