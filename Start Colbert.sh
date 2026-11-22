#!/usr/bin/env bash
# Linux: double-click this file and choose "Run in Terminal" (or run it from a terminal) to start Colbert.
exec "$(dirname "$(readlink -f "$0")")/tools/start.sh" "$@"
