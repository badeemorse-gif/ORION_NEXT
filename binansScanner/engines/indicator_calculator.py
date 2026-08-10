"""
===============================================================================
Badee Binance Scanner
Architecture : ORION
Module      : engines.indicator_calculator
Version     : 2.0.0
Status      : ORION Canonical Indicator Calculator
===============================================================================

Pure technical-indicator calculation component.

The calculator is responsible only for mathematical transformations of a
canonical OHLCV DataFrame.

It does not:
    - mutate MarketDataset state;
    - manage readiness flags;
    - perform analysis;
    - build profiles;
    - calculate scores;
    - make decisions;
    - execute trades;
    - generate reports.

===============================================================================
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
import pandas as pd
import pandas_ta as ta
