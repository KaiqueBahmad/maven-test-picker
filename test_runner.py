#!/usr/bin/env python3
"""
maven-test-picker

Lista testes de um projeto Maven (Micronaut, Spring Boot, JUnit puro) e
permite seleção interativa com filtro live antes de rodar via Maven.

Bindings:
  ↑↓        navega
  espaço    marca/desmarca classe ou método
  /         abre/limpa filtro
  enter     (filtrando) aplica filtro; (senão) roda os selecionados
  esc       cancela digitação do filtro / limpa filtro travado
  q, ctrl+c sai sem rodar
"""
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import javalang
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.styles import Style


# ───────────────────────── descoberta do projeto ─────────────────────────
def find_project_root(start: Path) -> Optional[Path]:
    """Sobe a árvore de diretórios até achar um pom.xml."""
    for d in [start, *start.parents]:
        if (d / "pom.xml").exists():
            return d
    return None


def resolve_project_root() -> Path:
    invoked_from = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    invoked_from = invoked_from.resolve()
    root = find_project_root(invoked_from)
    if root is None:
        print(f"Error: no pom.xml found in {invoked_from} or any parent directory.")
        print("Run maven-test-picker from inside a Maven project.")
        sys.exit(1)
    return root


# ───────────────────────── scan ─────────────────────────
def has_annotation(node, *names):
    return any(a.name in names for a in (node.annotations or []))


@dataclass
class TestClass:
    fqcn: str
    simple_name: str
    is_integration: bool       # @MicronautTest, @SpringBootTest, etc
    integration_tag: str       # ex: "Micronaut", "Spring"
    methods: list[str] = field(default_factory=list)


INTEGRATION_ANNOTATIONS = {
    "MicronautTest": "Micronaut",
    "SpringBootTest": "Spring",
    "WebMvcTest": "Spring/WebMvc",
    "DataJpaTest": "Spring/JPA",
    "QuarkusTest": "Quarkus",
}

TEST_METHOD_ANNOTATIONS = ("Test", "ParameterizedTest", "RepeatedTest", "TestFactory")


def detect_integration(cls) -> tuple[bool, str]:
    for ann, label in INTEGRATION_ANNOTATIONS.items():
        if has_annotation(cls, ann):
            return True, label
    return False, ""


def find_test_dirs(root: Path) -> list[Path]:
    """Encontra todos os src/test/java (suporta multi-módulo)."""
    dirs = list(root.rglob("src/test/java"))
    return [d for d in dirs if d.is_dir()]


def scan_tests(root: Path) -> list[TestClass]:
    results: list[TestClass] = []
    for test_dir in find_test_dirs(root):
        for java_file in test_dir.rglob("*.java"):
            try:
                tree = javalang.parse.parse(java_file.read_text(encoding="utf-8"))
            except (javalang.parser.JavaSyntaxError, UnicodeDecodeError):
                continue

            pkg = tree.package.name if tree.package else ""
            for _, cls in tree.filter(javalang.tree.ClassDeclaration):
                methods = [
                    m.name for m in cls.methods
                    if has_annotation(m, *TEST_METHOD_ANNOTATIONS)
                ]
                if methods:
                    is_int, tag = detect_integration(cls)
                    fqcn = f"{pkg}.{cls.name}" if pkg else cls.name
                    results.append(TestClass(
                        fqcn=fqcn,
                        simple_name=cls.name,
                        is_integration=is_int,
                        integration_tag=tag,
                        methods=sorted(methods),
                    ))
    results.sort(key=lambda t: t.fqcn)
    return results


# ───────────────────────── TUI ─────────────────────────
@dataclass
class Row:
    kind: str        # "class" | "method"
    class_idx: int
    method: Optional[str] = None


class Selector:
    def __init__(self, tests: list[TestClass]):
        self.tests = tests
        self.selected_classes: set[int] = set()
        self.selected_methods: set[tuple[int, str]] = set()
        self.filter_text = ""
        self.filter_buffer = Buffer()
        self.filter_active = False   # digitando filtro?
        self.filter_locked = False   # filtro aplicado, navegando
        self.cursor = 0
        self.rows: list[Row] = []
        self._rebuild_rows()

    def _method_matches(self, method: str) -> bool:
        if not self.filter_text:
            return True
        return self.filter_text.lower() in method.lower()

    def _class_visible(self, t: TestClass) -> tuple[bool, list[str]]:
        if not self.filter_text:
            return True, t.methods
        matched = [m for m in t.methods if self._method_matches(m)]
        if matched:
            return True, matched
        if self.filter_text.lower() in t.simple_name.lower():
            return True, t.methods
        return False, []

    def _rebuild_rows(self):
        self.rows = []
        for i, t in enumerate(self.tests):
            visible, methods = self._class_visible(t)
            if not visible:
                continue
            self.rows.append(Row("class", i))
            for m in methods:
                self.rows.append(Row("method", i, m))
        if self.cursor >= len(self.rows):
            self.cursor = max(0, len(self.rows) - 1)

    def toggle_current(self):
        if not self.rows:
            return
        row = self.rows[self.cursor]
        if row.kind == "class":
            if row.class_idx in self.selected_classes:
                self.selected_classes.remove(row.class_idx)
            else:
                self.selected_classes.add(row.class_idx)
        else:
            key = (row.class_idx, row.method)
            if key in self.selected_methods:
                self.selected_methods.remove(key)
            else:
                self.selected_methods.add(key)

    def is_selected(self, row: Row) -> bool:
        if row.kind == "class":
            return row.class_idx in self.selected_classes
        return (row.class_idx, row.method) in self.selected_methods

    def resolve_targets(self) -> list[str]:
        """
        Regra: classe marcada com filtro ativo roda só os métodos visíveis;
        sem filtro, roda a classe inteira. Métodos individuais nunca duplicam
        algo já coberto por uma classe inteira.
        """
        targets: list[str] = []
        active_filter = bool(self.filter_text.strip())
        classes_run_whole: set[int] = set()

        for idx in self.selected_classes:
            t = self.tests[idx]
            if active_filter:
                _, methods = self._class_visible(t)
                for m in methods:
                    targets.append(f"{t.fqcn}#{m}")
            else:
                targets.append(t.fqcn)
                classes_run_whole.add(idx)

        for idx, method in self.selected_methods:
            if idx in classes_run_whole:
                continue
            t = self.tests[idx]
            target = f"{t.fqcn}#{method}"
            if target not in targets:
                targets.append(target)

        return targets


def build_app(selector: Selector) -> Application:
    style = Style.from_dict({
        "header":        "bold #5fafff",
        "filter":        "bold #ffaf00",
        "filter-prompt": "bold #ffaf00",
        "footer":        "#777777",
        "cursor":        "reverse",
        "selected":      "bold #5fff5f",
        "class":         "bold #87d7ff",
        "method":        "",
        "integration":   "italic #d787ff",
        "empty":         "italic #777777",
    })

    def render_header():
        n_cls = len(selector.selected_classes)
        n_mtd = len(selector.selected_methods)
        return [(
            "class:header",
            f" Tests found: {len(selector.tests)}   "
            f"Selected: {n_cls} classes, {n_mtd} methods\n"
        )]

    def render_filter():
        if selector.filter_active:
            return [
                ("class:filter-prompt", " /"),
                ("class:filter", selector.filter_buffer.text),
                ("class:filter", "█"),
                ("class:footer", "   [enter] apply  [esc] cancel\n"),
            ]
        if selector.filter_locked:
            return [
                ("class:filter-prompt", " filter: "),
                ("class:filter", selector.filter_text),
                ("class:footer", "   [/ or esc] clear\n"),
            ]
        return [("class:footer", " (no filter)\n")]

    def render_list():
        if not selector.rows:
            return [("class:empty", "  (no tests match the filter)\n")]
        fragments = []
        for i, row in enumerate(selector.rows):
            t = selector.tests[row.class_idx]
            mark = "◉" if selector.is_selected(row) else "◯"
            is_cursor = (i == selector.cursor)

            if row.kind == "class":
                tag = f" [{t.integration_tag}]" if t.is_integration else ""
                text = f" {mark} 📦 {t.simple_name}{tag}"
            else:
                text = f"      {mark}    • {row.method}"

            if is_cursor:
                line_style = "class:cursor"
            elif selector.is_selected(row):
                line_style = "class:selected"
            elif row.kind == "class":
                line_style = "class:class"
            else:
                line_style = "class:method"

            fragments.append((line_style, text + "\n"))
        return fragments

    def render_footer():
        return [(
            "class:footer",
            " [↑↓] move  [space] toggle  [/] filter  [enter] run  [q/ctrl+c] quit\n"
        )]

    layout = Layout(HSplit([
        Window(content=FormattedTextControl(render_header), height=1),
        Window(content=FormattedTextControl(render_filter), height=1),
        Window(content=FormattedTextControl(render_list), always_hide_cursor=True),
        Window(content=FormattedTextControl(render_footer), height=1),
        Window(content=BufferControl(buffer=selector.filter_buffer), height=0),
    ]))

    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        if selector.filter_active:
            return
        if selector.cursor > 0:
            selector.cursor -= 1

    @kb.add("down")
    def _(event):
        if selector.filter_active:
            return
        if selector.cursor < len(selector.rows) - 1:
            selector.cursor += 1

    @kb.add("space")
    def _(event):
        if selector.filter_active:
            selector.filter_buffer.insert_text(" ")
            selector.filter_text = selector.filter_buffer.text
            selector._rebuild_rows()
            return
        selector.toggle_current()

    @kb.add("/")
    def _(event):
        if selector.filter_active:
            return
        if selector.filter_locked:
            selector.filter_locked = False
            selector.filter_text = ""
            selector.filter_buffer.reset()
            selector._rebuild_rows()
            return
        selector.filter_active = True

    @kb.add("escape", eager=True)
    def _(event):
        if selector.filter_active:
            selector.filter_active = False
            selector.filter_buffer.text = selector.filter_text
            return
        if selector.filter_locked:
            selector.filter_locked = False
            selector.filter_text = ""
            selector.filter_buffer.reset()
            selector._rebuild_rows()

    @kb.add("enter")
    def _(event):
        if selector.filter_active:
            selector.filter_text = selector.filter_buffer.text.strip()
            selector.filter_active = False
            selector.filter_locked = bool(selector.filter_text)
            selector._rebuild_rows()
            selector.cursor = 0
            return
        event.app.exit(result="run")

    @kb.add("backspace")
    def _(event):
        if selector.filter_active:
            selector.filter_buffer.delete_before_cursor()
            selector.filter_text = selector.filter_buffer.text
            selector._rebuild_rows()

    @kb.add("<any>")
    def _(event):
        if not selector.filter_active:
            return
        data = event.data
        if data and data.isprintable():
            selector.filter_buffer.insert_text(data)
            selector.filter_text = selector.filter_buffer.text
            selector._rebuild_rows()

    @kb.add("q")
    def _(event):
        if selector.filter_active:
            selector.filter_buffer.insert_text("q")
            selector.filter_text = selector.filter_buffer.text
            selector._rebuild_rows()
            return
        event.app.exit(result="quit")

    @kb.add("c-c")
    def _(event):
        event.app.exit(result="quit")

    return Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True,
        mouse_support=False,
    )


# ───────────────────────── execução ─────────────────────────
def run_tests(project_root: Path, targets: list[str]):
    if not targets:
        print("Nothing selected.")
        return

    results = []
    for i, target in enumerate(targets, 1):
        print(f"\n{'═' * 60}")
        print(f"[{i}/{len(targets)}] Running: {target}")
        print("═" * 60)
        proc = subprocess.run(
            ["mvn", "test", f"-Dtest={target}", "-DfailIfNoTests=false"],
            cwd=project_root,
        )
        results.append((target, proc.returncode == 0))

    print(f"\n{'═' * 60}")
    print("SUMMARY")
    print("═" * 60)
    for target, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}  {target}")

    failed = sum(1 for _, ok in results if not ok)
    sys.exit(1 if failed else 0)


# ───────────────────────── main ─────────────────────────
def main():
    project_root = resolve_project_root()
    print(f"Scanning Maven project at {project_root}...")

    tests = scan_tests(project_root)
    if not tests:
        print("No tests found.")
        sys.exit(0)

    selector = Selector(tests)
    app = build_app(selector)
    result = app.run()

    if result != "run":
        sys.exit(0)

    targets = selector.resolve_targets()
    run_tests(project_root, targets)


if __name__ == "__main__":
    main()
