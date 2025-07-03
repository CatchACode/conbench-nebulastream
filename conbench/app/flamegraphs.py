import collections
import functools
import logging
import math
import time
from time import strftime
from datetime import datetime, timezone
from typing import Dict, List, Tuple, TypedDict, TypeVar

import flask
from sqlalchemy import select
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
from conbench.dbsession import current_session
from conbench.outlier import remove_outliers_by_iqrdist
from conbench.entities.flamegraph import Flamegraph

"""
This is the frontend app endpoint for viewing multiple flamegraphs as a table
"""

@app.route("/flamegraphs", methods=["GET"])
def flame_graphs():

    query = select(Flamegraph).order_by(Flamegraph.run_id.desc()).limit(100)
    flamegraphs = current_session.scalars(query).all()

    return flask.render_template("flamegraphs.html", flamegraphs=flamegraphs, application=Config.APPLICATION_NAME, title="Flamegraphs")

@app.route("/upload-flamegraph", methods=["GET", "POST"])
def upload_fg():
    return flask.render_template("uploadFlamegraphs.html")