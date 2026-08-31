"""Prove the two arms of the benchmark run byte-identical solver code.

The experiment is only controlled if the solving logic is provably the same on
both sides of the seam. This compares the *source text* of every solver
function in `cli/puzzle.py` and `mcp_server.py` against
`shared/solvers_reference.py`, and exits non-zero on any difference.

    python verify_solvers.py
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "shared" / "solvers_reference.py"
FUNCTIONS = ["solve_spelling_bee", "solve_crossword_pattern", "_score_guess", "solve_wordle"]
TARGETS = {"cli/puzzle.py": HERE / "cli" / "puzzle.py", "mcp_server.py": HERE / "mcp_server.py"}


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    reference = load(REFERENCE, "_ref_solvers")
    failures = []
    for label, path in TARGETS.items():
        module = load(path, "_cmp_" + path.stem)
        for fn in FUNCTIONS:
            want = inspect.getsource(getattr(reference, fn))
            got = inspect.getsource(getattr(module, fn))
            status = "identical" if want == got else "DIFFERS"
            print(f"{label:<16} {fn:<24} {status}  ({len(got)} bytes)")
            if want != got:
                failures.append(f"{label}:{fn}")

    if failures:
        print(f"\nFAIL — {len(failures)} solver(s) drifted: {', '.join(failures)}")
        return 1
    print(f"\nOK — {len(FUNCTIONS)} solvers byte-identical across {len(TARGETS)} implementations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
