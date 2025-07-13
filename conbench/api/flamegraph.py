import flask_login
import os

import flask as f
import orjson
import uuid
from sqlalchemy import select
from werkzeug.utils import secure_filename

from ..api._docs import spec
from ..api import rule
from ..api._endpoint import ApiEndpoint, maybe_login_required
from ._resp import json_response_for_byte_sequence, resp400

from ..dbsession import current_session
from ..entities._entity import NotFound
from ..entities.flamegraph import Flamegraph, FlamegraphFacadeSchema, FlamegraphSerializer

from ..config import UPLOAD_FOLDER, ALLOWED_EXTENSIONS

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


class FlamegraphValidationMixin:
    def validate_flamegraph(self, schema):
        return self.validate(schema)


class FlamegraphListAPI(ApiEndpoint, FlamegraphValidationMixin):
    """
    API that handles requests for all flamegraphs entities: get flamegraphs and create new one
    """

    # conbench utils for validation and serialization
    serializer = FlamegraphSerializer
    schema = FlamegraphFacadeSchema

    # Annotations handle auth
    @maybe_login_required
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
        # Set query for table in view
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
        # fetch entities
        flamegraph_results = current_session.scalars(query).all()

        if len(flamegraph_results) == page_size:
            next_page_cursor = flamegraph_results[-1].id
        else:
            next_page_cursor = None

        # transform in json
        jsonbytes: bytes = orjson.dumps(
            {
                "data": [r.to_dict_for_json_api() for r in flamegraph_results],
                "metadata": {"next_page_cursor": next_page_cursor}
            },
            option=orjson.OPT_INDENT_2,
        )

        return json_response_for_byte_sequence(jsonbytes, 200)

    @flask_login.login_required
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

        # validate data
        data = self.validate_flamegraph(self.schema.create)

        # create entity
        flamegraph = Flamegraph.create(data)

        # return created entity
        return self.response_201_created(self.serializer.one.dump(flamegraph))


"""
API that handles request corresponding to a single flamegraph entity
"""


class FlamegraphEntityAPI(ApiEndpoint):
    # More conbench utils
    serializer = FlamegraphSerializer
    schema = FlamegraphFacadeSchema

    # internal method to fetch entity by id
    def _get(self, flamegraph_id):
        try:
            benchmark = Flamegraph.one(id=flamegraph_id)
        except NotFound:
            self.abort_404_not_found()
        return benchmark

    @maybe_login_required
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

    @flask_login.login_required
    def delete(self, flamegraph_result_id: int) -> f.Response:
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
        flamegraph = self._get(flamegraph_result_id)
        flamegraph.delete()
        return self.response_204_no_content()

    @flask_login.login_required
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

            # create unique filename based on svg name and uuid
            filename_prefix = secure_filename(file.filename).split('.')[0]
            filename_suffix = uuid.uuid4().hex
            filename = filename_prefix + filename_suffix + ".svg"

            # save to UPLOAD_FOLDER/flamegraphs/
            root_rel_filepath = os.path.join(UPLOAD_FOLDER, 'flamegraphs', filename)
            upload_rel_filepath = os.path.join('flamegraphs', filename)
            file.save(root_rel_filepath)

            # Find entity
            flamegraph = self._get(flamegraph_result_id)

            # Delete if updating path
            if flamegraph.file_path is not None and flamegraph.file_path is not "":
                if os.path.exists(os.path.join(UPLOAD_FOLDER, flamegraph.file_path)):
                    os.remove(os.path.join(UPLOAD_FOLDER, flamegraph.file_path))

            # update path
            flamegraph.file_path = upload_rel_filepath
            current_session.add(flamegraph)
            current_session.commit()

            return self.get(flamegraph_result_id)  # return the flamegraphs details after upload
        return self.abort_400_bad_request("Invalid file type")  # return if invalid file


# Internal stuff so conbench registers views and routes
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
    methods=["GET", "DELETE", "PUT", "POST"],
)

spec.components.schema(
    "FlamegraphCreate", schema=FlamegraphFacadeSchema.create
)
