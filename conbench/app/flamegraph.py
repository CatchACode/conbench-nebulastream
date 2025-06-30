import collections
import functools
import logging
import math
import time
from typing import Dict, List, Tuple, TypedDict, TypeVar

import flask
from sqlalchemy import select
import numpy as np
import numpy.polynomial
import orjson
import pandas as pd

import conbench.numstr
import conbench.units

from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from conbench.bmrt import BMRTBenchmarkResult, TBenchmarkName, bmrt_cache
from conbench.config import Config
from conbench.outlier import remove_outliers_by_iqrdist
from conbench.entities.flamegraph import Flamegraph

"""
This is the frontend app endpoint for viewing a single flamegraph
"""

class ViewFlamegraph(AppEndpoint):
    decorators = [authorize_or_terminate]

    def get(self, run_id: int) -> flask.Response:

        query = select(Flamegraph).where(Flamegraph.run_id == run_id)

        # Render the template with the flamegraph data
        return self.render_template(
            "flamegraph.html"
        )


rule(
    "/flamegraphs/<run_id>/",
    view_func=ViewFlamegraph.as_view("flamegraph"),
    methods=["GET"],
)
