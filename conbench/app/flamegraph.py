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

import os
from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from conbench.bmrt import BMRTBenchmarkResult, TBenchmarkName, bmrt_cache
from conbench.config import Config
from conbench.outlier import remove_outliers_by_iqrdist
from conbench.entities.flamegraph import Flamegraph
from conbench.dbsession import current_session

"""
This is the frontend app endpoint for viewing a single flamegraph
"""

class ViewFlamegraph(AppEndpoint):
    decorators = [authorize_or_terminate]

    def get(self, id: int) -> flask.Response:

        query = select(Flamegraph).where(Flamegraph.id == id)

        flamegraph = current_session.scalar(query)

        with open('.' + flamegraph.file_path, 'r', encoding="utf-8") as f:
            svg_content = f.read()


        # Render the template with the flamegraph data
        return self.render_template(
            "flamegraph.html",
            application=Config.APPLICATION_NAME,
            title="Flamegraph",
            flamegraph=flamegraph,
            svg_content=svg_content
        )


rule(
    "/flamegraphs/<id>/",
    view_func=ViewFlamegraph.as_view("flamegraph"),
    methods=["GET", "POST"],
)
