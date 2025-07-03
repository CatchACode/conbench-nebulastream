import collections
import functools
import logging
import math
import os
import time
from typing import Dict, List, Tuple, TypedDict, TypeVar

import flask
import flask as f
import numpy as np
import numpy.polynomial
import orjson
import pandas as pd
from sqlalchemy import select
from conbench.app import app
from werkzeug.utils import secure_filename

from ..api._docs import spec
from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ._resp import json_response_for_byte_sequence, resp400

from ..dbsession import current_session
from ..entities._entity import NotFound
from ..entities.flamegraph import Flamegraph, FlamegraphFacadeSchema, FlamegraphSerializer

UPLOAD_FOLDER = './conbench/static/flamegraphs/'
ALLOWED_EXTENSIONS = {'svg'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class FlamegraphValidationMixin:
    def validate_flamegraph(self, schema):
        return self.validate(schema)


class FlamegraphListAPI(ApiEndpoint, FlamegraphValidationMixin):
    serializer = FlamegraphSerializer
    schema = FlamegraphFacadeSchema

    def get(self) -> f.Response:
        """
        ---
        description: |
            Return flamegraph results
        responses:
            "200": "FlamegraphList"
            "401": "401"
        parameters:
          - in: query
            name: run_id
            schema:
              type: string
            description: |
                Filter flamegraphs to one specific `run_id`.
          - in: query
            name: run_reason
            schema:
              type: string
            description: Filter results to one specific `run_reason`
        tags:
          - Flamegraphs
        """
        filters = []
        cursor_arg = f.request.args.get("cursor")
        if cursor_arg and cursor_arg != "null":
            filters.append(Flamegraph.id < cursor_arg)

        page_size = f.request.args.get("page_size", 100)
        try:
            page_size = int(page_size)
            assert 1 <= page_size <= 1000
        except Exception:
            self.abort_400_bad_request(
                "page_size must be a postive integer no greater than 1000"
            )
        query = (
            select(Flamegraph)
            .filter(*filters)
            .order_by(Flamegraph.id.desc())
            .limit(page_size)
        )
        flamegraph_results = current_session.scalars(query).all()

        if len(flamegraph_results) == page_size:
            next_page_cursor = flamegraph_results[-1].id
        else:
            next_page_cursor = None

        jsonbytes: bytes = orjson.dumps(
            {
                "data": [r.to_dict_for_json_api() for r in flamegraph_results],
                "metadata": {"next_page_cursor": next_page_cursor}
            },
            option=orjson.OPT_INDENT_2,
        )

        return json_response_for_byte_sequence(jsonbytes, 200)

    def post(self):
        """
        ---
        summary: Upload a flamegraph metadata
        description: |
          Submit a Flamegraph within a specific run.

          If the Run (as defined by its Run ID) is not known yet in the database,
          it gets implicitly created using details provided in this request.
          If the Run ID matches an existing run, then the Flamegraph is added to it.
        requestBody:
          required: true
          content:
            application/json:
              schema: FlamegraphCreate
        responses:
          201:
            description: Successfully uploaded
          400: "400"
          401: "401"
        tags:
          - Flamegraphs
        """
        data = self.validate_flamegraph(self.schema.create)

        flamegraph = Flamegraph.create(data)

        return self.response_201_created(self.serializer.one.dump(flamegraph))


class FlamegraphEntityAPI(ApiEndpoint):
    serializer = FlamegraphSerializer
    schema = FlamegraphFacadeSchema

    def _get(self, flamegraph_id):
        try:
            benchmark = Flamegraph.one(id=flamegraph_id)
        except NotFound:
            self.abort_404_not_found()
        return benchmark

    def get(self, flamegraph_result_id: int) -> f.Response:
        """
        ---
        description: |
            Get a specific Flamegraph result
        resonses:

        parameters:
          - name: flamegraph_result_id
            in: path
            required: true
            schema:
              type: integer
        tags:
          - Flamegraphs
        """
        query = select(Flamegraph).where(Flamegraph.id == flamegraph_result_id)

        flamegraph = current_session.scalar(query)

        return flamegraph.to_dict_for_json_api()

    def put(self) -> f.Response:
        """
        ---
        tags:
          - Flamegraphs
        """
        pass

    def delete(self, benchmark_result_id) -> f.Response:
        """
        ---
        description: Delete a benchmark result.
        responses:
            "204": "204"
            "401": "401"
            "404": "404"
        parameters:
          - name: benchmark_result_id
            in: path
            schema:
                type: string
        tags:
          - Flamegraphs
        """
        flamegraph = self._get()

    def post(self, flamegraph_result_id: int) -> f.Response:
        """
        ---
        summary: Upload a flamegraph SVG file
        description: |
          Upload a Flamegraph SVG for a specific flamegraph result
        parameters:
          - name: flamegraph_result_id
            in: path
            required: true
            schema:
              type: integer
        requestBody:
          required: true
          content:
            multipart/form-data:
              schema:
                type: object
                required:
                  - file
                properties:
                  file:
                    type: string
                    format: binary
                    description: The SVG file of the flamegraph to upload.
        responses:
          201:
            description: Successfully uploaded
          404:
            description: Flamegraph result not found
        tags:
          - Flamegraphs
        """
        if 'file' not in f.request.files:
            return resp400("Flamegraph file is missing")
        file = f.request.files['file']
        if file.filename == '':
            return resp400("Flamegraph file is missing")
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            flamegraph = self._get(flamegraph_result_id)
            flamegraph.file_path = f"flamegraphs/{filename}"
            current_session.add(flamegraph)
            current_session.commit()

            return self.get(flamegraph_result_id)  # return the flamegraphs details after upload

flamegraph_list_view = FlamegraphListAPI.as_view("flamegraphs")
flamegraphs_entity_view = FlamegraphEntityAPI.as_view("flamegraph")
"""
@app.route("/uploads/<name>")
def download_file(name):
    return flask.send_from_directory(UPLOAD_FOLDER, name)

rule(
    "/uploads/<name>",
    endpoint="download_file",
    build_only=True,
)
"""

rule(
    "/flamegraphs/",
    view_func=flamegraph_list_view,
    methods=["GET", "POST"],
)

rule(
    "/flamegraphs/<flamegraph_result_id>/",
    view_func=flamegraphs_entity_view,
    methods=["GET", "DELETE", "PUT", "POST"],
)

spec.components.schema(
    "FlamegraphCreate", schema=FlamegraphFacadeSchema.create
)
