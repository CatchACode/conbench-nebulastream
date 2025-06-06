import collections
import functools
import logging
import math
import time
from typing import Dict, List, Tuple, TypedDict, TypeVar

import flask
import numpy as np
import numpy.polynomial
import orjson
import pandas as pd

import conbench.numstr
import conbench.units

from conbench.app import app
from conbench.app._endpoint import authorize_or_terminate
from conbench.bmrt import BMRTBenchmarkResult, TBenchmarkName, bmrt_cache
from conbench.config import Config
from conbench.outlier import remove_outliers_by_iqrdist

@app.route("/flamegraph")
def flame_graphs():
    runs = [
        {
            "timestamp": "2025-06-01 10:00",
            "result": "40",
            "reason": "Nightly Benchmark",
            "hardware": "Github Runner"
        },
        {
            "timestamp": "2025-06-02 12:30",
            "result": "1",
            "reason": "Testing conbench hotfix",
            "hardware": "Some Cool Machine"
        },
        {
            "timestamp": "2025-06-03 09:15",
            "result": "n/a",
            "reason": "test",
            "hardware": "Github Runner"
        }
    ]
    return flask.render_template("flamegraphs.html", runs = runs, person = "Sheikh ALI Tareq MUSAWIE")

@app.route("/upload-flamegraph")
def upload_fg():
    return flask.render_template("uploadFlamegraphs.html")