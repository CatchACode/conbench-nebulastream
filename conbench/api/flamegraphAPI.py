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

from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required

from ..dbsession import current_session  
from ..entities.flamegraph import Flamegraph

@rule("/api/flamegraphs-upload", methods=["POST"], endpoint="flamegraphs_upload")
class FlamegraphUploadAPI(ApiEndpoint):
    def post(self):
        if "file" not in flask.request.files:
            self.abort_400_bad_request("Flamegraph file missing")

        file = flask.request.files["file"]
        if not file or not file.filename.endswith(".svg"):
            self.abort_400_bad_request("File format must be an SVG")

        name = flask.request.form.get("name")
        run_id = flask.request.form.get("run_id")

        if not name or not run_id:
            self.abort_400_bad_request("Missing name or run_id.")

        timestamp = int(time.time())
        save_path = os.path.join("/tmp/flamegraphs", f"{timestamp}_{file.filename}")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file.save(save_path)

        fg = Flamegraph(name=name, file_path=save_path, run_id=run_id)
        current_session.add(fg)
        current_session.commit()

        return flask.jsonify({
            "status": "uploaded",
            "file_path": save_path,
            "name": name,
            "run_id": run_id,
        }), 201