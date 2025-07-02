import collections
import functools
import logging
import math
import os
import time
from typing import Dict, List, Tuple, TypedDict, TypeVar

import flask as f
import numpy as np
import numpy.polynomial
import orjson
import pandas as pd
from sqlalchemy import select
from conbench.app import app

from ..api._docs import spec
from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ._resp import json_response_for_byte_sequence, resp400

from ..dbsession import current_session  
from ..entities.flamegraph import Flamegraph, FlamegraphFacadeSchema, FlamegraphSerializer

class FlamegraphListAPI(ApiEndpoint):
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
        summary: Upload a flamegraph SVG file
        description: |
          Submit a Flamegraph within a specific run.

          If the Run (as defined by its Run ID) is not known yet in the database,
          it gets implicitly created using details provided in this request.
          If the Run ID matches an existing run, then the Flamegraph is added to it.
        requestBody:
          required: true
          content:
            multipart/form-data:
              schema:
                type: object
                required:
                  - file
                  - name
                  - run_id
                  - github
                properties:
                  file:
                    type: string
                    format: binary
                    description: The SVG file of the flamegraph to upload.
                  name:
                    type: string
                    description: A human-readable name for the flamegraph.
                  run_id:
                    type: string
                    description: The ID of the run this flamegraph belongs to.
                  run_reason:
                    type: string
                    description: A reason for the run
                  timestamp:
                    type: string
                    description: Timestamp of the run
                    format: iso
                  machine_info:
                    type: string
                    description: JSON string with machine information. Precisely one of `machine_info` and `cluster_info` must be provided.
                  cluster_info:
                    type: string
                    description: JSON string with cluster information. Precisely one of `machine_info` and `cluster_info` must be provided.
                  github:
                    type: string
                    description: JSON string with GitHub commit information.
        responses:
          201:
            description: Successfully uploaded
        tags:
          - Flamegraphs
        """
        form_data = f.request.form.to_dict()

        if "file" not in f.request.files:
            self.abort_400_bad_request("Flamegraph file missing")

        file = f.request.files["file"]
        if not file or not file.filename.endswith(".svg"):
            self.abort_400_bad_request("File format must be an SVG")
        timestamp = int(time.time())
        save_path = os.path.join("/tmp/flamegraphs", f"{timestamp}_{file.filename}")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        file.save(save_path)

        data_dict = Flamegraph.validate_formdata(form_data)
        flamegraph = Flamegraph.create(data_dict)


        return self.response_201_created(self.serializer.one.dump(flamegraph))

class FlamegraphEntityAPI(ApiEndpoint):
    def get(self) -> f.Response:
        """
        ---
        tags:
          - Flamegraphs
        """
        pass

    def put(self) -> f.Response:
        """
        ---
        tags:
          - Flamegraphs
        """
        pass

    def delete(self) -> f.Response:
        """
        ---
        tags:
          - Flamegraphs
        """
        pass

flamegraph_list_view = FlamegraphListAPI.as_view("flamegraphs")
flamegraphs_entity_view = FlamegraphEntityAPI.as_view("flamegraph")

rule(
    "/flamegraphs/",
    view_func=flamegraph_list_view,
    methods=["GET", "POST"],
)

rule(
    "/flamegraphs/<flamegraph_result_id>/",
    view_func=flamegraphs_entity_view,
    methods=["GET", "DELETE", "PUT"],
)

spec.components.schema(
    "FlamegraphCreate", schema=FlamegraphFacadeSchema.create
)