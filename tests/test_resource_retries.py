"""Observe the production retry policy through the public Nextflow CLI."""

import csv
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
ALIGNMENT_REQUESTS = {
    'CUTADAPT': [(4, 8, 4), (8, 16, 8)],
    'BWAMEM2_MEM': [(8, 64, 12), (16, 128, 24)],
    'SAMTOOLS_MERGE': [(2, 8, 4), (4, 16, 8)],
    'PICARD_MARKDUPLICATES': [(2, 32, 12), (4, 64, 24)],
    'SAMTOOLS_INDEX': [(2, 4, 4), (4, 8, 8)],
}
REFERENCE_REQUESTS = {
    'REFERENCE_DOWNLOAD': [(1, 2, 24), (1, 4, 48)],
    'GUNZIP': [(1, 4, 2), (1, 8, 4)],
    'REFERENCE_VALIDATE': [(1, 16, 4), (1, 32, 8)],
    'BEDTOOLS_MASKFASTA': [(1, 16, 4), (1, 32, 8)],
    'BWAMEM2_INDEX': [(1, 128, 24), (1, 256, 48)],
    'REFERENCE_BUNDLE': [(1, 4, 4), (1, 8, 8)],
}


class ResourceRetryTests(unittest.TestCase):
    def setUp(self):
        root = PROJECT / '.local/tests'
        root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix='resource-retries-', dir=root))

    def probe(self, names, workflow='oncohawk', failure=143, overrides='', config_mode='-C',
              fail_attempts=1, profile='slurm', bodies=None):
        """Run harmless task bodies with real project configuration and resources.

        The local executor's accounting capacity permits observing production-size
        requests; these echo-only tasks never allocate the requested memory.
        """
        directory = Path(tempfile.mkdtemp(prefix='run-', dir=self.directory))
        declarations = set(names) | set(REFERENCE_REQUESTS if workflow == 'prepare_reference_bundle' else ALIGNMENT_REQUESTS)
        script = directory / 'probe.nf'
        processes = []
        for name in sorted(declarations):
            exit_code = failure.get(name, 0) if isinstance(failure, dict) else failure
            body = (bodies or {}).get(name)
            if body is None:
                body = f'if [ ${{task.attempt}} -le {fail_attempts} ]; then exit {exit_code}; fi'
            processes.append(f'''process {name} {{
                input:
                val meta
                val reference_label
                val kind
                script:
                """
                printf 'RESOURCE\\t{name}\\t${{task.attempt}}\\t${{task.cpus}}\\t${{task.memory.toBytes()}}\\t${{task.time.toMillis()}}\\n'
                {body}
                """
            }}''')
        script.write_text('\n'.join(processes) + '\nworkflow {\n' + '\n'.join(
            f"{name}([task_label: 'probe', sample: 'probe'], 'probe', 'fasta')" for name in names
        ) + '\n}\n')
        config = directory / 'probe.config'
        config.write_text(
            f"params.workflow = '{workflow}'\n"
            f"includeConfig '{PROJECT / 'nextflow.config'}'\n"
            "process.executor = 'local'\n"
            "apptainer.enabled = false\n"
            "docker.enabled = false\n"
            "executor.cpus = 64\n"
            "executor.memory = '1 TB'\n"
            + overrides
        )
        result = subprocess.run([
            os.environ.get('NEXTFLOW', 'nextflow'), config_mode, str(config),
            'run', str(script), '-profile', profile,
        ], cwd=directory, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        (directory / 'probe.log').write_text(result.stdout)
        resources = []
        for output in (directory / 'work').glob('*/*/.command.out'):
            for row in csv.reader(output.read_text().splitlines(), delimiter='\t'):
                if row and row[0] == 'RESOURCE':
                    resources.append((row[1], *map(int, row[2:])))
        return result, sorted(resources)

    def test_shared_slurm_defaults_retry_once_with_growing_memory_and_time(self):
        result, resources = self.probe(['FALLBACK'])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(resources, [
            ('FALLBACK', 1, 1, 2147483648, 3600000),
            ('FALLBACK', 2, 1, 4294967296, 7200000),
        ])

    def test_alignment_processes_retain_initial_requests_and_grow_on_retry(self):
        result, resources = self.probe(list(ALIGNMENT_REQUESTS))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(resources, sorted(
            (name, attempt, cpus, gib * 1073741824, hours * 3600000)
            for name, attempts in ALIGNMENT_REQUESTS.items()
            for attempt, (cpus, gib, hours) in enumerate(attempts, 1)
        ))

    def test_reference_processes_grow_memory_and_time_with_one_cpu(self):
        result, resources = self.probe(list(REFERENCE_REQUESTS), workflow='prepare_reference_bundle')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(resources, sorted(
            (name, attempt, cpus, gib * 1073741824, hours * 3600000)
            for name, attempts in REFERENCE_REQUESTS.items()
            for attempt, (cpus, gib, hours) in enumerate(attempts, 1)
        ))

    def test_community_exit_statuses_each_receive_their_own_retry(self):
        codes = [104, *range(130, 146), 175, 176, 177]
        failures = {f'EXIT_{code}': code for code in codes}
        result, resources = self.probe(list(failures), failure=failures)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual([(row[0], row[1]) for row in resources], sorted(
            (name, attempt) for name in failures for attempt in (1, 2)
        ))

    def test_retry_budget_exhaustion_fails_after_two_attempts(self):
        result, resources = self.probe(['FALLBACK'], fail_attempts=99)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual([row[1] for row in resources], [1, 2])

    def test_nonqualifying_failure_finishes_an_already_running_task(self):
        started = self.directory / 'started'
        completed = self.directory / 'completed'
        result, resources = self.probe(['FALLBACK', 'IN_FLIGHT'], bodies={
            'FALLBACK': f'for wait in {{1..100}}; do if [ -f "{started}" ]; then exit 17; fi; sleep 0.1; done; exit 18',
            'IN_FLIGHT': f'touch "{started}"; sleep 2; touch "{completed}"',
        })
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual([(row[0], row[1]) for row in resources], [('FALLBACK', 1), ('IN_FLIGHT', 1)])
        self.assertTrue(completed.is_file(), result.stdout)

    def test_docker_profile_does_not_enable_automatic_retries(self):
        result, resources = self.probe(['FALLBACK'], profile='docker')
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual([row[1] for row in resources], [1])

    def test_native_caps_clamp_initial_and_retry_requests_without_suppressing_retry(self):
        result, resources = self.probe(['BWAMEM2_MEM'], overrides=(
            'process.resourceLimits = [cpus: 3, memory: 5.GB, time: 2.h]\n'
        ))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(resources, [
            ('BWAMEM2_MEM', 1, 3, 5368709120, 7200000),
            ('BWAMEM2_MEM', 2, 3, 5368709120, 7200000),
        ])

    def test_fixed_and_dynamic_overrides_preserve_configuration_semantics(self):
        for mode in ('-c', '-C'):
            with self.subTest(mode=mode):
                result, resources = self.probe(['CUTADAPT', 'BWAMEM2_MEM'], config_mode=mode, overrides=(
                    'process {\n'
                    '  withName: CUTADAPT { cpus = 3; memory = 5.GB; time = 2.h }\n'
                    '  withName: BWAMEM2_MEM {\n'
                    '    cpus = { 3 * task.attempt }\n'
                    '    memory = { 5.GB * task.attempt }\n'
                    '    time = { 2.h * task.attempt }\n'
                    '  }\n'
                    '}\n'
                ))
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(resources, [
                    ('BWAMEM2_MEM', 1, 3, 5368709120, 7200000),
                    ('BWAMEM2_MEM', 2, 6, 10737418240, 14400000),
                    ('CUTADAPT', 1, 3, 5368709120, 7200000),
                    ('CUTADAPT', 2, 3, 5368709120, 7200000),
                ])

    def test_native_retry_override_can_disable_recovery(self):
        result, resources = self.probe(['FALLBACK'], overrides="process.errorStrategy = 'finish'\n")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual([row[1] for row in resources], [1])


if __name__ == '__main__':
    unittest.main()
