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

@app.route("/flamegraphs", methods=["GET"])
def flame_graphs():
    runs = {"nebulastream/test": [
        {
            "run_id" : 1,
            "time_for_table": 1,
            "result_count": 0,
            "run_reason": "dict",
            "hardware_name": "Python Dict",
            "commit": {
                "author_avatar_url": None,
                "author_name": "Python Dict",
                "commit_url": "https://google.com",
                "hash": "1234567890",
                "commit_message_short": "Short commit message from the python Dict",
            }
        }
    ]}
    return flask.render_template("flamegraphs.html", reponame_runs_map_sorted = runs)

@app.route("/upload-flamegraph", methods=["GET", "POST"])
def upload_fg():
    return flask.render_template("uploadFlamegraphs.html")