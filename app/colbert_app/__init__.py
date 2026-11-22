"""Colbert desktop app: runs the colbert engine on this computer, alone or with a shared ledger."""
VERSION = "0.1.0"
# engine machine-interface versions this app understands (src/main.cpp PROTOCOL)
ENGINE_PROTOCOLS = (1,)
# The project's shared ledger (docs/LEDGER.md). New installs offer to join it. Override with
# the COLBERT_LEDGER_URL environment variable, or change it on the Work tab.
PROJECT_LEDGER_URL = "https://colbert-ledger-214187368360.us-central1.run.app"
