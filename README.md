# maven-test-picker

> Interactive TUI to pick and run Maven tests — live filter, multi-select, per-method execution.

Stop typing `mvn test -Dtest=SomeLongClassName#someMethodName` by hand. Browse with arrows, select with space, run with enter.

Works with any JUnit 5 project on Maven (Micronaut, Spring Boot, plain JUnit, multi-module — all fine).

```
 Tests found: 12   Selected: 0 classes, 0 methods
 (no filter)
 ◯ 📦 EnvironmentControllerTest [Micronaut]
       ◯    • shouldCreateEnvironment
       ◯    • shouldRejectInvalidPayload
       ◯    • shouldListAllEnvironments
 ◯ 📦 AwsClientFactoryTest
       ◯    • shouldUseHardcodedCredentials
 [↑↓] move  [space] toggle  [/] filter  [enter] run  [q/ctrl+c] quit
```

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/kaiqueBahmad/maven-test-picker/main/bootstrap.sh | bash
```

Clones into `~/.local/share/maven-test-picker`, installs deps with Poetry, symlinks into `~/.local/bin` (or `~/bin`). Re-run to update.

Customize via env vars:

```bash
MTP_PREFIX=/usr/local/bin     # where to put the symlink
MTP_BRANCH=v0.2.0             # specific branch or tag
MTP_DIR=~/tools/mtp           # custom clone location
```

**Requirements:** Python 3.10+, [Poetry](https://python-poetry.org/), Maven on `PATH`, JUnit 5.

<details>
<summary>Manual install</summary>

```bash
git clone https://github.com/kaiqueBahmad/maven-test-picker.git ~/projetos/maven-test-picker
cd ~/projetos/maven-test-picker
./install.sh                          # auto-detect PATH dir
./install.sh --prefix ~/.local/bin    # specific dir
./install.sh --uninstall              # remove
```

</details>

## Usage

From anywhere inside a Maven project:

```bash
maven-test-picker
```

It walks up to find `pom.xml`, scans every `src/test/java` under the project root, and shows the picker.

### Keys

| Key | Action |
|---|---|
| `↑` `↓` | Move |
| `space` | Toggle class or method |
| `/` | Start filtering (live) |
| `enter` while filtering | Apply filter |
| `esc` | Cancel / clear filter input |
| `enter` | Run selected |
| `q` / `ctrl+c` | Quit |

### Filtering

Case-insensitive substring match against class **and** method names. A class shows up if any of its methods match. If you select a class while a filter is active, **only the visible methods run** — handy for "run every `create*` test in the codebase".

### Output

Each target runs as its own `mvn test -Dtest=...`, in sequence. Selections are deduplicated (selecting a class plus methods inside it won't double-run). You get a summary at the end:

```
════════════════════════════════════════════════════════════
SUMMARY
════════════════════════════════════════════════════════════
  ✅ PASS  com.example.EnvironmentControllerTest#shouldCreateEnvironment
  ❌ FAIL  com.example.AwsClientFactoryTest#shouldUseHardcodedCredentials
```

Exit code is `0` if everything passed, `1` otherwise.

## Features

- `@Test`, `@ParameterizedTest`, `@RepeatedTest`, `@TestFactory` — all discovered
- Framework integration tests tagged in the UI (`@MicronautTest`, `@SpringBootTest`, `@WebMvcTest`, `@DataJpaTest`, `@QuarkusTest`)
- Multi-module aware
- Static parsing via [`javalang`](https://github.com/c2nes/javalang) — no JVM needed for discovery, fast on large codebases
- TUI built on [`prompt_toolkit`](https://python-prompt-toolkit.readthedocs.io/)

## Limitations

- **JUnit 5 only.** Adding JUnit 4 means extending the annotation list — small change.
- **Maven only.** Gradle would mean swapping the command in `run_tests` (`./gradlew test --tests "FQCN.method"`). PRs welcome.
- **Sequential execution.** Each target spawns its own `mvn` process — reliable, but slower than batching.
- **`@TestFactory` dynamic tests not enumerated.** The factory method is listed; its generated cases aren't.

## Development

```bash
git clone https://github.com/kaiqueBahmad/maven-test-picker.git
cd maven-test-picker
poetry install
poetry run python test_runner.py /path/to/maven-project
```

The path argument is optional; defaults to `$PWD`.

## License

MIT
