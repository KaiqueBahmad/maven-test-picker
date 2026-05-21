#!/usr/bin/env bash
#
# install.sh — sets up maven-test-picker on your system.
#
# What it does:
#   1. Checks prerequisites (python3, poetry, mvn).
#   2. Installs Python dependencies via Poetry.
#   3. Creates a symlink in a directory on your PATH so you can run
#      `maven-test-picker` from anywhere.
#
# Usage:
#   ./install.sh                    # interactive, picks best install dir
#   ./install.sh --prefix DIR       # install symlink into DIR
#   ./install.sh --uninstall        # remove the symlink
#   ./install.sh --help
#
set -euo pipefail

# ───────── colors ─────────
if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'
    GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BLUE=$'\033[34m'; RESET=$'\033[0m'
else
    BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""
fi

info()  { echo "${BLUE}==>${RESET} $*"; }
ok()    { echo "${GREEN}✓${RESET} $*"; }
warn()  { echo "${YELLOW}!${RESET} $*"; }
err()   { echo "${RED}✗${RESET} $*" >&2; }

# ───────── paths ─────────
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
REPO_DIR="$(dirname "$SCRIPT_PATH")"
COMMAND_NAME="maven-test-picker"
COMMAND_SOURCE="$REPO_DIR/$COMMAND_NAME"

# ───────── args ─────────
PREFIX=""
UNINSTALL=0

usage() {
    cat <<EOF
${BOLD}maven-test-picker installer${RESET}

Usage:
  ./install.sh                  Install (auto-detect a PATH directory).
  ./install.sh --prefix DIR     Install symlink into DIR.
  ./install.sh --uninstall      Remove the installed symlink.
  ./install.sh --help           Show this message.

Examples:
  ./install.sh
  ./install.sh --prefix ~/.local/bin
  ./install.sh --prefix /usr/local/bin     # may need sudo
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prefix)    PREFIX="${2:-}"; shift 2 ;;
        --prefix=*)  PREFIX="${1#*=}"; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        -h|--help)   usage; exit 0 ;;
        *)           err "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# ───────── prerequisite checks ─────────
check_prereqs() {
    local missing=0

    if ! command -v python3 >/dev/null 2>&1; then
        err "python3 not found. Install Python 3.10+."
        missing=1
    else
        local py_version
        py_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        ok "python3 found ($py_version)"
        # Garante 3.10+
        if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
            err "Python 3.10+ required (found $py_version)."
            missing=1
        fi
    fi

    if ! command -v poetry >/dev/null 2>&1; then
        err "poetry not found. Install: https://python-poetry.org/docs/#installation"
        missing=1
    else
        ok "poetry found ($(poetry --version 2>/dev/null))"
    fi

    if ! command -v mvn >/dev/null 2>&1; then
        warn "mvn not found in PATH. maven-test-picker won't work until you install Maven."
        # Não é fatal pra instalação, só pra execução
    else
        ok "mvn found"
    fi

    if [[ $missing -eq 1 ]]; then
        err "Fix the issues above and try again."
        exit 1
    fi
}

# ───────── PATH directory detection ─────────
pick_install_dir() {
    # Se o usuário passou --prefix, usa
    if [[ -n "$PREFIX" ]]; then
        PREFIX="${PREFIX/#\~/$HOME}"  # expande ~
        mkdir -p "$PREFIX"
        echo "$PREFIX"
        return
    fi

    # Procura candidatos comuns na ordem de preferência
    local candidates=(
        "$HOME/.local/bin"
        "$HOME/bin"
    )

    for d in "${candidates[@]}"; do
        if [[ ":$PATH:" == *":$d:"* ]]; then
            mkdir -p "$d"
            echo "$d"
            return
        fi
    done

    # Nada no PATH; usa ~/.local/bin e avisa
    local fallback="$HOME/.local/bin"
    mkdir -p "$fallback"
    warn "No standard bin dir on PATH. Using $fallback (you may need to add it to PATH)."
    echo "$fallback"
}

# ───────── operations ─────────
do_uninstall() {
    info "Uninstalling maven-test-picker..."
    local removed=0
    local search_dirs=("$HOME/.local/bin" "$HOME/bin" "/usr/local/bin")
    if [[ -n "$PREFIX" ]]; then
        PREFIX="${PREFIX/#\~/$HOME}"
        search_dirs=("$PREFIX")
    fi

    for d in "${search_dirs[@]}"; do
        local target="$d/$COMMAND_NAME"
        if [[ -L "$target" || -f "$target" ]]; then
            rm -f "$target"
            ok "Removed $target"
            removed=1
        fi
    done

    if [[ $removed -eq 0 ]]; then
        warn "No installed symlink found."
    fi
    exit 0
}

do_install() {
    info "Installing maven-test-picker from $REPO_DIR"

    check_prereqs

    if [[ ! -f "$COMMAND_SOURCE" ]]; then
        err "Wrapper not found: $COMMAND_SOURCE"
        err "Make sure you're running install.sh from inside the repo."
        exit 1
    fi

    chmod +x "$COMMAND_SOURCE"

    # Instala deps Python
    info "Installing Python dependencies..."
    (cd "$REPO_DIR" && poetry install --quiet --no-root)
    ok "Dependencies installed"

    # Cria o symlink
    local install_dir
    install_dir="$(pick_install_dir)"
    local target="$install_dir/$COMMAND_NAME"

    if [[ -L "$target" ]]; then
        local current
        current="$(readlink -f "$target")"
        if [[ "$current" == "$COMMAND_SOURCE" ]]; then
            ok "Symlink already in place at $target"
        else
            warn "$target points to $current — overwriting"
            ln -sf "$COMMAND_SOURCE" "$target"
            ok "Symlink updated: $target → $COMMAND_SOURCE"
        fi
    elif [[ -e "$target" ]]; then
        err "$target exists and is not a symlink. Refusing to overwrite."
        err "Remove it manually or use --prefix to install elsewhere."
        exit 1
    else
        ln -s "$COMMAND_SOURCE" "$target"
        ok "Symlink created: $target → $COMMAND_SOURCE"
    fi

    # Avisa se o dir não tá no PATH
    if [[ ":$PATH:" != *":$install_dir:"* ]]; then
        warn "$install_dir is not in your PATH."
        echo ""
        echo "  Add this to your shell rc file (~/.bashrc or ~/.zshrc):"
        echo ""
        echo "    ${BOLD}export PATH=\"$install_dir:\$PATH\"${RESET}"
        echo ""
        echo "  Then reload: source ~/.bashrc"
    fi

    echo ""
    ok "${BOLD}Installation complete!${RESET}"
    echo ""
    echo "  Run ${BOLD}$COMMAND_NAME${RESET} from inside any Maven project."
    echo "  ${DIM}cd ~/projetos/my-maven-app && $COMMAND_NAME${RESET}"
}

# ───────── entry ─────────
if [[ $UNINSTALL -eq 1 ]]; then
    do_uninstall
else
    do_install
fi
