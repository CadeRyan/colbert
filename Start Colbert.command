#!/usr/bin/env bash
# macOS: double-click this file to start Colbert.
# The first time, macOS may say it can't verify the file: right-click it, choose Open, then Open.
exec "$(dirname "$0")/tools/start.sh" "$@"
