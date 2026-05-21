# maven-test-picker

> Interactive TUI to pick and run Maven tests à la carte — with live filtering, multi-select, and per-method execution.

Stop typing `mvn test -Dtest=SomeLongClassName#someMethodName` by hand. Browse, filter, select, run.

---

## Why

Running a single test method in a Maven project means remembering the FQCN, typing it precisely, and hoping you didn't typo. Running a handful means doing that several times. `maven-test-picker` reads your test sources, lists every test class and method, and lets you pick exactly what to run with arrow keys and space bar.

Works with any JUnit 5 project on Maven — **Micronaut**, **Spring Boot**, plain JUnit, doesn't matter.

## Features

- **Browse** all test classes and their `@Test` / `@ParameterizedTest` / `@RepeatedTest` / `@TestFactory` methods
- **Multi-select** with space; mix whole classes and individual methods freely
- **Live filter** — press `/`, start typing, see results narrow as you type
- **Filter-aware execution** — select a class with a filter active and only the matching methods run
- **Smart deduplication** — selecting a class *and* methods inside it won't run anything twice
- **Per-target results** — clear pass/fail summary at the end
- Detects framework integration tests (`@MicronautTest`, `@SpringBootTest`, `@WebMvcTest`, `@DataJpaTest`, `@QuarkusTest`) and tags them in the UI
- **Multi-module aware** — finds every `src/test/java` under the project root
- **Run from anywhere** — invoke from any subdirectory of a Maven project; walks up to find `pom.xml`

## Requirements

- Python 3.10+
- [Poetry](https://python-poetry.org/) (for dependency management)
- Maven (`mvn`) on your `PATH`
- A Maven project using JUnit 5

## Install

### Quick install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/your-user/maven-test-picker/main/bootstrap.sh | bash
```

This clones the repo into `~/.local/share/maven-test-picker`, installs the Python dependencies via Poetry, and creates a symlink in a directory on your `PATH` (preferring `~/.local/bin`, then `~/bin`).

Customize via env vars:

```bash
# Different install location for the symlink
curl -fsSL https://raw.githubusercontent.com/your-user/maven-test-picker/main/bootstrap.sh \
  | MTP_PREFIX=/usr/local/bin bash

# Specific branch/tag
curl -fsSL https://raw.githubusercontent.com/your-user/maven-test-picker/main/bootstrap.sh \
  | MTP_BRANCH=v0.2.0 bash

# Custom clone location
curl -fsSL https://raw.githubusercontent.com/your-user/maven-test-picker/main/bootstrap.sh \
  | MTP_DIR=~/tools/maven-test-picker bash
```

Re-running the one-liner updates an existing install.

### Manual install

Clone the repo and run the installer:

```bash
git clone https://github.com/your-user/maven-test-picker.git ~/projetos/maven-test-picker
cd ~/projetos/maven-test-picker
./install.sh
```

The installer:

- Checks for `python3` (3.10+), `poetry`, and `mvn`
- Installs the Python dependencies via Poetry
- Creates a symlink in the first PATH directory it finds (preferring `~/.local/bin`, then `~/bin`)

### Installer options

```bash
./install.sh --prefix ~/.local/bin    # install symlink into a specific directory
./install.sh --prefix /usr/local/bin  # may need sudo
./install.sh --uninstall              # remove the symlink
./install.sh --help
```

If the chosen directory isn't on your `PATH`, the installer prints the line you need to add to your shell rc file.

## Usage

From any directory inside a Maven project:

```bash
cd ~/projetos/my-spring-app
maven-test-picker
```

The tool walks up from `$PWD` until it finds a `pom.xml`, uses that as the project root, scans every `src/test/java` under it, and shows the TUI:

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

### Key bindings

| Key | Action |
|---|---|
| `↑` / `↓` | Move cursor |
| `space` | Toggle selection (class or method) |
| `/` | Start filtering (live as you type) |
| `enter` (while filtering) | Apply filter, unlock navigation |
| `esc` | Cancel current filter input / clear active filter |
| `/` (with filter locked) | Clear filter |
| `enter` (not filtering) | Run all selected tests |
| `q` / `ctrl+c` | Quit without running |

### Filter behavior

- Matches against **method names** and **class names** (case-insensitive substring).
- A class shows up if any of its methods match, even if the class name itself doesn't.
- If you select a class **while a filter is active**, only the visible (filtered) methods run.
- Clear the filter (`/` or `esc`) to see the full list again. Existing selections are preserved.

### Example flow

1. Press `/`, type `create`
2. Only methods containing "create" remain visible, grouped under their classes
3. Press `enter` to lock the filter
4. Navigate with `↑↓`, mark whatever you want with `space`
5. Press `enter` to run

Each selected target runs as its own `mvn test -Dtest=...` invocation, in sequence. You get the full Maven output per test and a summary at the end:

```
════════════════════════════════════════════════════════════
SUMMARY
════════════════════════════════════════════════════════════
  ✅ PASS  com.example.EnvironmentControllerTest#shouldCreateEnvironment
  ❌ FAIL  com.example.AwsClientFactoryTest#shouldUseHardcodedCredentials
```

Exit code is `0` if everything passed, `1` if any test failed (CI-friendly).

## How it works

1. **Locate** — the `maven-test-picker` wrapper resolves its own real location (even via symlink) and runs Poetry from there, regardless of where you invoked the command.
2. **Find project root** — the Python script walks up from `$PWD` looking for a `pom.xml`.
3. **Scan** — walks every `src/test/java` under the project root, parses `.java` files with [`javalang`](https://github.com/c2nes/javalang), and collects classes with JUnit 5 test methods.
4. **TUI** — built on [`prompt_toolkit`](https://python-prompt-toolkit.readthedocs.io/), full-screen with custom key bindings.
5. **Execute** — each selected target becomes `mvn test -Dtest=<FQCN>` or `mvn test -Dtest=<FQCN>#<method>`. Selections are deduplicated before running.

Everything is static parsing — no JVM started for discovery, fast on large codebases.

## Limitations

- **JUnit 5 only**. JUnit 4 (`@org.junit.Test`) would need the annotation list updated — small change.
- **Maven only**. Gradle support is a small change in the `run_tests` function (`./gradlew test --tests "FQCN.method"`); PRs welcome.
- **No parallel execution**. Each target spawns its own `mvn` process sequentially. Reliable, but slower than batching everything into one Maven invocation.
- **No `@TestFactory` content discovery**. The factory method itself is listed, but its dynamically-generated tests aren't.

## Project layout

```
maven-test-picker/
├── maven-test-picker     # bash wrapper, the command itself
├── test_runner.py        # Python TUI + scanner
├── pyproject.toml        # Poetry config (javalang + prompt_toolkit)
├── poetry.lock
├── install.sh            # local installer / uninstaller
├── bootstrap.sh          # remote one-line installer (curl | bash)
└── README.md
```

## Development

```bash
git clone https://github.com/your-user/maven-test-picker.git
cd maven-test-picker
poetry install
poetry run python test_runner.py /path/to/some/maven-project
```

The script accepts the project path as an optional positional argument; without it, it uses `$PWD`.

## License

MIT
