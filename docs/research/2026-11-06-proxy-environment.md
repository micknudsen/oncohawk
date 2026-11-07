# Proxy environment variable casing

Investigated on 2026-11-06 against Oncohawk commit `dff29e0`, Python 3.12.16, and the local pinned Nextflow 26.10.4 distribution. The original findings below describe that commit; the subsequent implementation is recorded at the end.

## Findings

There is no portable rule that proxy variables must always be lowercase or always uppercase. The relevant clients have different behavior:

| Client | HTTP proxy | HTTPS proxy | Conflicting cases |
| --- | --- | --- | --- |
| Python 3.12 `urllib.request` | `http_proxy` or `HTTP_PROXY` | `https_proxy` or `HTTPS_PROXY` | Lowercase wins; an explicitly empty lowercase value suppresses uppercase. |
| curl | `http_proxy`; uppercase `HTTP_PROXY` is ignored on case-sensitive systems | `https_proxy` or `HTTPS_PROXY` | Lowercase wins. |
| Nextflow 26.10.4's bundled proxy parser | Both cases accepted | Both cases accepted | Uppercase wins in the local parser probe. |

Python documents case-insensitive discovery and lowercase precedence. With `REQUEST_METHOD` set, its CGI protection ignores uppercase `HTTP_PROXY`; uppercase `HTTPS_PROXY` is still recognized. The pinned implementation's second pass also removes a proxy when the lowercase variable exists but is empty. [Python documentation](https://docs.python.org/3.12/library/urllib.request.html#urllib.request.getproxies), [CPython 3.12.16 implementation](https://github.com/python/cpython/blob/v3.12.16/Lib/urllib/request.py#L2343-L2377).

curl's lowercase-only HTTP exception addresses the CGI `Proxy` header vulnerability. It is not a universal casing convention. Other scheme-specific proxy names accept uppercase, and lowercase takes precedence where both forms are supported. [curl proxy guide](https://everything.curl.dev/usingcurl/proxies/env.html), [curl manual](https://curl.se/docs/manpage.html#ENVIRONMENT).

Nextflow documents `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` for its runtime/JVM. These settings govern a different client from the Python program executed inside `REFERENCE_DOWNLOAD`. Nextflow's own ability to use a proxy does not establish which variables our job exports. [Nextflow environment reference](https://docs.seqera.io/nextflow/reference/env-vars/#http_proxy), [process environment inputs](https://docs.seqera.io/nextflow/process/#input-environment-variables-env).

## Verified local evidence

The pinned download image was probed using `urllib.request.getproxies()` after clearing the Python process environment and installing synthetic, credential-free values:

```text
python@sha256:a5bab0ff300f91231c2e68bf73a8a8d60762ac39ce1c50eaf6803e4c38a9062b
Python 3.12.16; Docker linux/amd64
```

Six assertions passed:

1. Uppercase-only `HTTP_PROXY` and `HTTPS_PROXY` are recognized.
2. Lowercase-only equivalents are recognized.
3. Conflicting lowercase values win.
4. Empty lowercase values suppress corresponding nonempty uppercase values.
5. `REQUEST_METHOD=GET` suppresses uppercase `HTTP_PROXY`, while retaining uppercase `HTTPS_PROXY`.
6. Uppercase `NO_PROXY` is recognized.

For Nextflow, `javap` showed that `nextflow.util.ProxyConfig.setupFromEnvironment` delegates to `io.seqera.util.net.ProxyConfig`. The bundled parser was called directly with synthetic maps using the installed Java 21 runtime:

```bash
.local/tooling/jdk-21.0.13+9-jre/Contents/Home/bin/java \
  -cp .local/tooling/bin/nextflow groovy.ui.GroovyMain -e '
import io.seqera.util.net.ProxyConfig
[
  [HTTP_PROXY:"http://upper.invalid:3128", HTTPS_PROXY:"http://upper.invalid:3129"],
  [http_proxy:"http://lower.invalid:3128", https_proxy:"http://lower.invalid:3129"],
  [HTTP_PROXY:"http://upper.invalid:3128", http_proxy:"http://lower.invalid:3128"],
  [HTTP_PROXY:"http://upper.invalid:3128", http_proxy:""]
].each { println ProxyConfig.fromEnvironment(it) }
'
```

The results selected uppercase values in the first case, lowercase in the second, and uppercase in both remaining cases. This is a parser check, not a test of Nextflow network traffic or cluster execution. The current web documentation can describe later releases; this local observation supplies the version-specific precedence evidence.

## Consequence for Oncohawk

At the investigated commit, [`pipelines/reference/main.nf`](../../pipelines/reference/main.nf) read only `http_proxy` and `https_proxy`, replacing missing values with empty strings. [`modules/local/reference_download.nf`](../../modules/local/reference_download.nf) exported those two lowercase inputs. [`bin/download_reference.py`](../../bin/download_reference.py) uses `urllib.request.urlopen`.

Consequently, that implementation did not support a launch environment containing only uppercase proxy variables through explicit job forwarding, despite Python supporting those variables. Even if uppercase values otherwise reached the container, synthesized lowercase empty values suppressed them. Adding uppercase inputs without addressing those empty lowercase exports would not fix this reliably.

Proposed correction: support both cases, including `NO_PROXY`/`no_proxy`; preserve Python's documented precedence and distinguish an unset lowercase value from an explicitly empty one. Do not replace the implementation with uppercase-only forwarding. Add container-level cases for uppercase-only input, conflicting cases, explicit empty lowercase values, and proxy bypass. Avoid conflicting values across cases when both the Nextflow launcher and Python jobs need the same proxy, because their precedence differs.

The existing `SSL_CERT_FILE` handling concerns CA trust, not proxy selection, and does not resolve this casing issue. Cluster routing and TLS behavior still require a cluster rerun after any implementation change.

## Implementation follow-up — 2026-11-06

The reference workflow now resolves HTTP, HTTPS, and proxy-bypass pairs from the launch environment. It uses lowercase when present (including empty), otherwise uppercase, and exports the resolved value under both spellings through Nextflow environment inputs. Both spellings are empty when neither was provided. This preserves Python's effective selection while giving the task a consistent environment. Uppercase-only `HTTP_PROXY` is ignored when `REQUEST_METHOD` is present, retaining Python's CGI safeguard. `SSL_CERT_FILE` staging is unchanged.

The uppercase HTTP, HTTPS, and bypass regression tests were run before implementation and all three failed through the public workflow in the pinned Docker container.

After implementation, 14 download-job tests passed (162 seconds): both proxy spellings, lowercase conflict precedence, explicitly empty HTTP/HTTPS/bypass values, uppercase bypass forwarding, the CGI safeguard, and both CA-bundle configuration routes. Local-file bundle preparation and both pipeline-configuration checks also passed, for 17 targeted tests total. Nextflow lint passed with existing upstream deprecation warnings; Python compilation and whitespace checks passed. These used Nextflow 26.10.4, Java 21, and the pinned Docker task images. The full suite, CI, and SLURM/Apptainer execution were not run for this change.

## Empty-value warning correction — 2026-11-07

The environment-input implementation above caused Nextflow to warn for each intentionally empty proxy value in every download task. An unset bypass pair therefore produced `no_proxy` and `NO_PROXY` warnings twice when downloading both FASTA and exclusions BED. The Docker-backed HTTP proxy test reproduced these warnings on both Nextflow 26.10.4 and the repository's pinned 26.10.5, despite successful acquisition. A minimal 26.10.5 task with only `env('no_proxy')`, an empty input, and a `true` script reproduced the warning without Docker or downloads.

The workflow now passes the resolved proxy settings as a value map. `REFERENCE_DOWNLOAD` exports both spellings in its task script using shell quoting, including intentional empty strings. This avoids the environment-input warning while retaining lowercase precedence, explicit disabling, the CGI safeguard, and overrides of inherited container settings. No global warning suppression is used.

The public-workflow test helper now rejects these warnings. Additional cases cover a launch environment with no proxy settings and a bypass list containing shell metacharacters, alongside the existing proxy routing, precedence, empty-value, bypass, and CA checks.

Validation used Nextflow 26.10.5, Java 21, and the pinned Docker images: all 16 download-job tests passed (167 seconds), as did both pipeline-configuration tests. The original failing HTTP proxy test also passed individually after the fix. Nextflow lint passed with three existing nf-core `when` deprecation warnings; Python compilation and whitespace checks passed. The full suite, CI, and SLURM/Apptainer execution were not run.
