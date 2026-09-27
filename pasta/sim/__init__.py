"""PastaTester: an agent-based economy for testing the stability thesis.

Run ``python -m pasta.sim --help``. See ``docs/SIMULATION-RESULTS.md`` for findings.
"""

from pasta.sim.economy import Economy, SimConfig, Shock, run_simulation  # noqa: F401

__all__ = ["Economy", "SimConfig", "Shock", "run_simulation"]
