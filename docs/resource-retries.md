# SLURM resource retries

The `slurm` profile enables the same bounded exit-status retry convention used by
[nf-core/Sarek](https://github.com/nf-core/sarek/blob/786a11bb4f989751d1c4bb87908ffc6096635ff3/conf/base.config)
for both reference preparation and alignment. Normal local Docker execution does
not enable this policy.

A task with exit status **130–145, 104, or 175–177** gets **one retry**: at most
two attempts. Other failures use Nextflow's `finish` strategy: running tasks may
finish, then the workflow exits unsuccessfully. An unsuccessful retry also
leaves the workflow unsuccessful. Each task retains its own retry allowance;
there is no aggregate process error limit.

These exit statuses are a broad community convention, not proof that a task ran
out of time or memory. Cancellation or another termination may also qualify.
Longer time and larger allocations cannot fix every failure. A retry starts the
task again; it does not extend a running SLURM job or promise tool checkpoints.
Inspect task logs and traces when diagnosing a failure.

## Default requests

The first attempt retains the allocations in the selected workflow's resource
configuration. On retry, memory and wall time double. Default CPU requests above
one also double; default one-CPU requests stay at one CPU.

| Task | First attempt | Retry, before any caps |
| --- | --- | --- |
| Alignment with bwa-mem2 | 8 CPUs, 64 GB, 12 hours | 16 CPUs, 128 GB, 24 hours |
| Reference indexing | 1 CPU, 128 GB, 24 hours | 1 CPU, 256 GB, 48 hours |

These remain starting allocations, not measured full-reference requirements.
Shared fallback defaults are 1 CPU, 2 GB, and 1 hour initially, then 1 CPU, 4 GB,
and 2 hours on retry. No extra configuration file is needed merely to enable
retries under SLURM.

## Optional cluster caps

Oncohawk sets no global production maxima. SLURM enforces its own partition,
account, and QoS limits; Oncohawk does not discover them automatically. To cap
requests explicitly, add native Nextflow settings to the cluster configuration
loaded with `-c`, for example:

```groovy
process.resourceLimits = [cpus: 16, memory: 256.GB, time: 48.h]
```

These values are illustrative, not Oncohawk defaults or verified limits for your
cluster. Confirm suitable limits for your execution environment.

Nextflow clamps requests to configured caps before submission, on both initial
and retry attempts. A task may retry with unchanged capped requests. There is no
custom cap-conflict error or stop-at-cap rule; the one-retry budget still applies.
See [Nextflow resourceLimits](https://docs.seqera.io/nextflow/reference/process/directives/resource-limits).

## Resource overrides

Use standard Nextflow configuration and the existing workflow-specific resource
selectors. A fixed override stays fixed across attempts:

```groovy
process {
    withName: BWAMEM2_MEM {
        memory = 96.GB
    }
}
```

A dynamic override can preserve growth, subject to any configured caps:

```groovy
process {
    withName: BWAMEM2_MEM {
        memory = { 96.GB * task.attempt }
    }
}
```

For reference preparation, use its own selectors, for example:

```groovy
process {
    withName: BWAMEM2_INDEX {
        cpus = 1
        memory = { 128.GB * task.attempt }
        time = { 24.h * task.attempt }
    }
}
```

The attempt number starts at one. CPU and time overrides follow the same fixed
versus dynamic distinction. Configuration precedence and the supported `-c` and
project-including `-C` forms retain their normal Nextflow behavior. No custom
pipeline parameters wrap these settings.

## Changing or disabling retries

Use native Nextflow directives in configuration. To disable automatic recovery
while allowing already-running work to finish:

```groovy
process.errorStrategy = 'finish'
```

A process selector can limit that override to one process. To change the retry
budget, set `process.maxRetries` to the desired positive count. Such operator
changes replace the default policy; they do not retune the fixed or dynamic
resource expressions automatically. See [Nextflow retry guidance](https://docs.seqera.io/nextflow/process/#dynamic-task-resources).

## Verification boundary

Compact local and CI tests exercise the real SLURM-profile retry configuration
through the public Nextflow CLI. Harmless resource probes check resolved requests;
small Docker reference-preparation and alignment runs check recovery and final
artifacts. These tests do not establish a particular cluster's signal behavior,
resource requirements, or willingness to accept the requested allocation.
