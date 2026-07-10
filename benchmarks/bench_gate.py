#!/usr/bin/env python3
"""pantheon gate replay benchmark — does the enforcer actually enforce?

Replays synthetic transcript fixtures through the REAL pipeline
(transcript.scan_turn -> on_stop.gate_check). No API calls, no live agents:
deterministic and CI-safe. 10 TRAP fixtures each plant one fake-"done"
pattern the gate should catch; 10 CLEAN fixtures are legitimate turns the
gate must leave alone. Fixture filenames encode the expectation: t<N>_*
must yield >=1 problem, c<N>_* must yield 0.

Usage: python3 benchmarks/bench_gate.py [--json]
Exit code: 0 if every fixture matched its expectation, 1 otherwise.
"""
import sys, os, json, glob, argparse, importlib.util

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
FIXTURES_DIR = os.path.join(_HERE, "fixtures")

sys.path.insert(0, os.path.join(_ROOT, "lib"))
import transcript as tr


def _load_on_stop():
    spec = importlib.util.spec_from_file_location("on_stop", os.path.join(_ROOT, "hooks", "on_stop.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(fixtures_dir=FIXTURES_DIR):
    on_stop = _load_on_stop()
    results = []
    for path in sorted(glob.glob(os.path.join(fixtures_dir, "*.jsonl"))):
        name = os.path.basename(path)[:-len(".jsonl")]
        expect_trap = name.startswith("t")
        turn = tr.scan_turn(path)
        problems = on_stop.gate_check(turn)
        caught = len(problems) >= 1
        ok = caught if expect_trap else not caught
        results.append({
            "fixture": name,
            "expected": "trap" if expect_trap else "clean",
            "problems": problems,
            "pass": ok,
        })
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="print machine-readable results")
    ap.add_argument("--fixtures", default=FIXTURES_DIR, help="fixtures directory (default: benchmarks/fixtures)")
    args = ap.parse_args()

    results = run(args.fixtures)
    traps = [r for r in results if r["expected"] == "trap"]
    cleans = [r for r in results if r["expected"] == "clean"]
    traps_caught = sum(1 for r in traps if r["pass"])
    false_positives = sum(1 for r in cleans if not r["pass"])
    all_pass = all(r["pass"] for r in results)

    if args.json:
        print(json.dumps({
            "results": results,
            "traps_caught": traps_caught,
            "traps_total": len(traps),
            "false_positives": false_positives,
            "clean_total": len(cleans),
            "pass": all_pass,
        }, indent=2))
        return 0 if all_pass else 1

    name_w = max((len(r["fixture"]) for r in results), default=8)
    print(f"{'fixture':<{name_w}}  {'expected':<8}  {'got':<40}  result")
    print("-" * (name_w + 8 + 40 + 20))
    for r in results:
        got = "; ".join(r["problems"]) if r["problems"] else "(no problems)"
        if len(got) > 40:
            got = got[:37] + "..."
        mark = "PASS" if r["pass"] else "FAIL"
        print(f"{r['fixture']:<{name_w}}  {r['expected']:<8}  {got:<40}  {mark}")
    print()
    print(f"gate caught {traps_caught}/{len(traps)} planted fake-dones, "
          f"{false_positives}/{len(cleans)} false positives on clean turns")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
