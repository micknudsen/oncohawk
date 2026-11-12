"""Exercise startup validation through the public root entrypoint."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class WorkflowDispatchTests(unittest.TestCase):
    def run_workflow(self, directory, arguments=(), config=()):
        return subprocess.run([
            os.environ.get("NEXTFLOW", "nextflow"), *config, "run", str(PROJECT), *arguments,
        ], cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def test_profile_parameter_suggests_native_option_before_missing_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([
                os.environ.get("NEXTFLOW", "nextflow"), "run", str(PROJECT),
                "--profile", "slurm",
            ], cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("Unsupported pipeline parameters: --profile", result.stdout)
            self.assertIn("Use -profile", result.stdout)
            self.assertNotIn("Alignment requires", result.stdout)
            self.assertNotIn("Submitted process", result.stdout)

    def test_rejects_all_unknown_names_in_order_for_each_workflow_selection(self):
        for selection, foreign in [([], "fasta"), (["--workflow", "oncohawk"], "fasta"),
                                   (["--workflow", "prepare_reference_bundle"], "input")]:
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as directory:
                result = self.run_workflow(directory, [*selection, "--zeta", "1", "--profile", "slurm",
                                                       "--_typo=1", "--outidr", "wrong",
                                                       f"--{foreign}", "wrong"])
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(f"Unsupported pipeline parameters: --_typo, --{foreign}, --outidr, --profile, --zeta.",
                              result.stdout)
                self.assertIn("Use -profile", result.stdout)
                self.assertNotIn("Alignment requires", result.stdout)
                self.assertNotIn("Submitted process", result.stdout)
                self.assertFalse((Path(directory) / "results").exists())
                self.assertFalse((Path(directory) / "reference").exists())

    def test_rejects_unknown_names_from_parameter_files_and_configuration(self):
        for selection in [[], ["--workflow", "oncohawk"], ["--workflow", "prepare_reference_bundle"]]:
            for source in ["parameters", "-c", "-C"]:
                with self.subTest(selection=selection, source=source), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / ("params.json" if source == "parameters" else "site.config")
                    if source == "parameters":
                        path.write_text(json.dumps({"profile": "slurm", "_unknown": True, "outidr": "wrong"}))
                        arguments = [*selection, "-params-file", str(path)]
                        config = []
                    else:
                        path.write_text((f"includeConfig '{PROJECT / 'nextflow.config'}'\n" if source == "-C" else "")
                                        + "params { profile = 'slurm'; _unknown = true; outidr = 'wrong' }\n")
                        arguments = selection
                        config = [source, str(path)]
                    result = self.run_workflow(directory, arguments, config)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("Unsupported pipeline parameters: --_unknown, --outidr, --profile.", result.stdout)
                    self.assertIn("Use -profile", result.stdout)
                    self.assertNotIn("Alignment requires", result.stdout)
                    self.assertNotIn("Submitted process", result.stdout)

    def test_supported_options_keep_native_profiles_and_configuration_precedence(self):
        for source in ["parameters", "-c", "-C"]:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / ("params.json" if source == "parameters" else "site.config")
                if source == "parameters":
                    path.write_text(json.dumps({"workflow": "prepare_reference_bundle", "outdir": "from-file"}))
                    arguments = ["-params-file", str(path)]
                    config = []
                else:
                    path.write_text("params.workflow = 'prepare_reference_bundle'\n"
                                    + (f"includeConfig '{PROJECT / 'nextflow.config'}'\n" if source == "-C" else "")
                                    + "params.outdir = 'from-file'\nprocess.cpus = 2\n")
                    arguments = []
                    config = [source, str(path)]
                result = self.run_workflow(directory, [*arguments, "--workflow", "oncohawk",
                                                       "--outdir", "from-cli", "--verify_bundle_checksums", "false",
                                                       "-profile", "docker,test"], config)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Alignment requires --input and --reference_bundle", result.stdout)
                self.assertNotIn("Unsupported pipeline parameters", result.stdout)
                self.assertNotIn("Submitted process", result.stdout)
                self.assertFalse((Path(directory) / "from-file").exists())
                self.assertFalse((Path(directory) / "from-cli").exists())

    def test_existing_output_guard_preserves_files_before_parameter_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results"
            sentinel = output / "execution/dag.html"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_bytes(b"previous diagnostic")
            result = self.run_workflow(directory, ["--profile", "slurm", "-with-dag", "dag.html"])
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("Alignment output directory already exists", result.stdout)
            self.assertNotIn("Submitted process", result.stdout)
            self.assertEqual(sentinel.read_bytes(), b"previous diagnostic")
            self.assertEqual(sorted(path.relative_to(output).as_posix() for path in output.rglob("*")),
                             ["execution", "execution/dag.html"])

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
