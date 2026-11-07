"""
GOD SWING — MASTER RUNNER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scans the complete NIFTY 500 universe (all 501 stocks)
Uses the 5-Layer Deep Analysis Engine:
  - Weekly & Monthly CPR
  - Fibonacci Golden Pocket (0.618 - 0.65)
  - Volume Surge & Retest Analysis
  - Order Flow / Cumulative Volume Delta (CVD)
  - Relative Strength & 21/50/200 EMAs

Usage:
  python3 run_all.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from swing_scanner_v2 import run_deep_scan

if __name__ == "__main__":
    run_deep_scan()
