"""Test-wide settings that keep plotting headless and deterministic."""

import os


os.environ.setdefault("MPLBACKEND", "Agg")
