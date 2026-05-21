#!/usr/bin/env bash
#
# bootstrap.sh — one-line installer for maven-test-picker.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/kaiqueBahmad/maven-test-picker/main/bootstrap.sh | bash
#
# Environment variables:
#   MTP_REPO     git URL of the repo (default: https://github.com/kaiqueBahmad/maven-test-picker.git)
#   MTP_BRANCH   branch/tag to checkout (default: main)
#   MTP_DIR      where to clone the repo (default: ~/.local/share/maven-test-picker)
#   MTP_PREFIX   passed to install.sh as --prefix (optional)
#
set -euo pipefail

REPO="${MTP_REPO:-https://github.com/kaiqueBahmad/maven-test-picker.git}"
BRANCH="${MTP_BRANCH:-main}"
TARGET_DIR="${MTP_DIR:-$HOME/.local/share/maven-test-picker}"
PREFIX="${MTP_PREFIX:-}"

if [[ -t 1 ]]; then
    BOLD=$'\033[1m'; BLUE=$'\033[34m'; GREEN=$'\033[32m'
    YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
    BOLD=""; BLUE=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

info() { echo "${BLUE}==>${RESET} $*"; }
ok()   { echo "${GREEN}✓${RESET} $*"; }
warn() { echo "${YELLOW}!${RESET} $*"; }
err()  { echo "${RED}✗${RESET} $*" >&2; }

if ! command -v git >/dev/null 2>&1; then
    err "git not found. Install git first."
    exit 1
fi

if [[ -d "$TARGET_DIR/.git" ]]; then
    info "Existing checkout found at $TARGET_DIR — updating..."
    git -C "$TARGET_DIR" fetch --quiet origin "$BRANCH"
    git -C "$TARGET_DIR" checkout --quiet "$BRANCH"
    git -C "$TARGET_DIR" pull --quiet --ff-only origin "$BRANCH"
    ok "Repo updated"
elif [[ -e "$TARGET_DIR" ]]; then
    err "$TARGET_DIR exists but isn't a git repo. Remove it or set MTP_DIR=..."
    exit 1
else
    info "Cloning $REPO into $TARGET_DIR..."
    mkdir -p "$(dirname "$TARGET_DIR")"
    git clone --quiet --branch "$BRANCH" --depth 1 "$REPO" "$TARGET_DIR"
    ok "Repo cloned"
fi

cd "$TARGET_DIR"
chmod +x install.sh

if [[ -n "$PREFIX" ]]; then
    ./install.sh --prefix "$PREFIX"
else
    ./install.sh
fi
