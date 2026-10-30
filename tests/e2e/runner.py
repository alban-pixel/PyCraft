#!/usr/bin/env python3
"""PyCraft Vanilla 1.8 Parity & Fabric Architecture E2E Test Runner.

Provides a unified CLI runner to execute and report on the 4-tier E2E test suite:
  Tier 1: Feature Coverage (Features 1 - 33)
  Tier 2: Boundary & Corner Cases
  Tier 3: Cross-Feature Combinations
  Tier 4: Real-World Scenarios

Usage:
  python tests/e2e/runner.py                 # Run all tiers
  python tests/e2e/runner.py --tier 1        # Run only Tier 1
  python tests/e2e/runner.py --tier 2        # Run only Tier 2
  python tests/e2e/runner.py --tier 3        # Run only Tier 3
  python tests/e2e/runner.py --tier 4        # Run only Tier 4
  python tests/e2e/runner.py -v              # Run with verbose output
"""
import argparse
import os
import sys
import time
import pytest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

TIER_FILES = {
    1: os.path.join(SCRIPT_DIR, "test_tier1_features.py"),
    2: os.path.join(SCRIPT_DIR, "test_tier2_boundaries.py"),
    3: os.path.join(SCRIPT_DIR, "test_tier3_interactions.py"),
    4: os.path.join(SCRIPT_DIR, "test_tier4_scenarios.py"),
}


def parse_args():
    parser = argparse.ArgumentParser(description="PyCraft E2E Test Suite Runner")
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3, 4],
        default=None,
        help="Specify which tier to run (1-4). If omitted, runs all tiers.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose test execution output",
    )
    parser.add_argument(
        "-k",
        "--filter",
        type=str,
        default=None,
        help="Pytest expression filter (-k)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    pytest_args = ["-q"]
    if args.verbose:
        pytest_args.append("-v")
    else:
        pytest_args.append("--tb=short")

    if args.filter:
        pytest_args.extend(["-k", args.filter])

    if args.tier is not None:
        target_file = TIER_FILES[args.tier]
        pytest_args.append(target_file)
        print(f"\n=======================================================")
        print(f"  PyCraft E2E Suite: Running Tier {args.tier}")
        print(f"  Target: {os.path.relpath(target_file, PROJECT_ROOT)}")
        print(f"=======================================================\n")
    else:
        pytest_args.append(SCRIPT_DIR)
        print(f"\n=======================================================")
        print(f"  PyCraft E2E Suite: Running All Tiers (1 - 4)")
        print(f"  Target: {os.path.relpath(SCRIPT_DIR, PROJECT_ROOT)}")
        print(f"=======================================================\n")

    start_time = time.time()
    exit_code = pytest.main(pytest_args)
    duration = time.time() - start_time

    print(f"\n-------------------------------------------------------")
    print(f"E2E Suite finished in {duration:.2f}s with exit code {exit_code}")
    print(f"-------------------------------------------------------\n")
    return int(exit_code)


if __name__ == "__main__":
    sys.exit(main())
