"""Exercise selection errors through the public root entrypoint."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class WorkflowDispatchTests(unittest.TestCase):
    def test_cli_selection_takes_precedence_with_added_and_replacement_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "selection.config"
            for flag in ["-c", "-C"]:
                with self.subTest(flag=flag):
                    config.write_text("params.workflow = 'prepare_reference_bundle'\n" +
                                      (f"includeConfig '{PROJECT / 'nextflow.config'}'\n" if flag == "-C" else ""))
                    result = subprocess.run([
                        os.environ.get("NEXTFLOW", "nextflow"), flag, str(config),
                        "run", str(PROJECT), "--workflow", "prepare_knowledge_bundle",
                    ], cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("prepare_knowledge_bundle is not yet implemented", result.stdout)
                    self.assertNotIn("Submitted process", result.stdout)
                    self.assertNotIn("There's no process matching config selector", result.stdout)
                    self.assertFalse((Path(directory) / "reference").exists())

    def test_knowledge_workflow_reports_unimplemented_without_other_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT),
                "--workflow", "prepare_knowledge_bundle", "--outdir", "knowledge",
            ], cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("prepare_knowledge_bundle is not yet implemented", result.stdout)
            self.assertNotIn("requires --input", result.stdout)
            self.assertNotIn("Submitted process", result.stdout)
            self.assertFalse((Path(directory) / "knowledge").exists())

    def test_unknown_workflow_fails_before_inputs_or_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT),
                "--workflow", "typo", "-with-trace", "trace.tsv",
            ], cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("Unknown workflow 'typo'", result.stdout)
            self.assertNotIn("requires --input", result.stdout)
            self.assertNotIn("Submitted process", result.stdout)
            self.assertFalse((Path(directory) / "reference").exists())
            self.assertFalse((Path(directory) / "alignments").exists())


if __name__ == "__main__":
    unittest.main()
