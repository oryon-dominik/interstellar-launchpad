#!/bin/sh
# launchpad, stage 0 — any POSIX shell with curl or wget:
#
#   curl -LsSf https://raw.githubusercontent.com/oryon-dominik/interstellar-launchpad/trunk/install.sh | sh
#   wget -qO- https://raw.githubusercontent.com/oryon-dominik/interstellar-launchpad/trunk/install.sh | sh
#
# Installs uv, then runs the launchpad through it; uv brings its own Python.
set -eu

source="${LAUNCHPAD_SOURCE:-https://github.com/oryon-dominik/interstellar-launchpad/archive/refs/heads/trunk.zip}"
PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    else
        wget -qO- https://astral.sh/uv/install.sh | sh
    fi
fi

# This script arrived on stdin. The launchpad asks questions, so it reads the terminal instead.
exec uvx --refresh-package launchpad --from "$source" launchpad </dev/tty
