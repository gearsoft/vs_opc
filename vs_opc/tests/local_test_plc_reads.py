"""Module wrapper to run the top-level tests/local_test_plc_reads.py via
python -m vs_opc.tests.local_test_plc_reads

This wrapper locates the project's top-level `tests/local_test_plc_reads.py`
script and runs it with runpy so the script continues to behave as before but
is runnable as a module inside the `vs_opc` package.
"""
from pathlib import Path
import runpy
import sys

# The repository layout is: <repo>/vs_opc/ (project root) and the package under
# <repo>/vs_opc/vs_opc/. The top-level tests folder lives at <repo>/vs_opc/tests
# so compute the path relative to this file and execute the script.
here = Path(__file__).resolve()
project_root = here.parents[2]
script = project_root / 'tests' / 'local_test_plc_reads.py'
if not script.exists():
    raise FileNotFoundError(f"Smoke test script not found at {script}")

# Execute the script in its own __main__ context (same as running the file).
runpy.run_path(str(script), run_name='__main__')
