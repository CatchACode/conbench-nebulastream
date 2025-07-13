import os
import marshmallow
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String
from typing import Any, Dict, Optional
import sqlalchemy as s
from datetime import datetime, timezone

from ..config import UPLOAD_FOLDER
from conbench.dbsession import current_session

import conbench.util
import conbench.units
from .benchmark_result import commit_fetch_info_and_create_in_db_if_not_exists, SchemaGitHubCreate
from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,

)

from ..entities.commit import (
    Commit,
    CommitSerializer,
    TypeCommitInfoGitHub,
)

from ..entities.hardware import (
    Cluster,
    ClusterSchema,
    Hardware,
    HardwareSerializer,
    Machine,
    MachineSchema,
)

class Flamegraph(Base, EntityMixin):
    """
    Flamegraph entity
    """
    __tablename__ = "flamegraph"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Name of the flamegraph, e.g. "Nexmark"
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Path to the flamegraph file, from the directory where they are saved.
    file_path: Mapped[str] = mapped_column(String, nullable=True)
    # An arbitrary string to group results by CI run. There are no assertions that this
    # string is non-empty.
    run_id: Mapped[str] = mapped_column(String, nullable=False)

    run_reason: Mapped[Optional[str]] = Nullable(s.Text)

    commit_id: Mapped[Optional[str]] = Nullable(s.ForeignKey("commit.id"))
    commit: Mapped[Optional[Commit]] = relationship("Commit", lazy="joined")

    # Non-empty URL to the repository without trailing slash.
    # Note(JP): maybe it is easier to think of this as just "repo_url" because
    # while it is not required that each result is associated with a particular
    # commit, but instead it is required to be associated with a (one!) code
    # repository as identified by its user-given repository URL.
    commit_repo_url: Mapped[str] = NotNull(s.Text)

    hardware_id: Mapped[str] = NotNull(s.String(50), s.ForeignKey("hardware.id"))
    hardware: Mapped[Hardware] = relationship("Hardware", lazy="joined")
    timestamp: Mapped[datetime] = NotNull(s.DateTime(timezone=False))


    def delete_flamegraph_svg(self):
        filepath = os.path.join(UPLOAD_FOLDER, self.file_path)
        os.remove(filepath)

    def delete(self):
        self.delete_flamegraph_svg()
        current_session.delete(self)
        current_session.commit()


    @staticmethod
    def create(data_dict) -> "Flamegraph":
        """
        Create a Flamegraph entity from the provided data dictionary.
        This is assumed to be called after the form data has been validated using 'validate_formdata'.
        """
        result_data_for_db: Dict = {}

        if "machine_info" in data_dict:
            hardware = Machine.get_or_create(data_dict["machine_info"])
        else:
            hardware = Cluster.get_or_create(data_dict["cluster_info"])

        user_given_commit_info: TypeCommitInfoGitHub = data_dict["github"]
        repo_url = user_given_commit_info["repo_url"]
        commit = None
        if user_given_commit_info["commit_hash"] is not None:
            commit = commit_fetch_info_and_create_in_db_if_not_exists(
                user_given_commit_info
            )
        result_data_for_db["file_path"] = None
        result_data_for_db["name"] = data_dict["name"]
        result_data_for_db["run_id"] = data_dict["run_id"]
        result_data_for_db["run_reason"] = data_dict["run_reason"]
        result_data_for_db["timestamp"] = data_dict["timestamp"]
        result_data_for_db["hardware_id"] = hardware.id
        result_data_for_db["commit_id"] = commit.id if commit else None
        result_data_for_db["commit_repo_url"] = repo_url

        flamegraph = Flamegraph(**result_data_for_db)
        flamegraph.save()

        return flamegraph

    @staticmethod
    def validate_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates and potentially creates other entities required for instantiation of new flamegraph entity
        :param data:
        :return: Dict ready to use for creating flamegraph entity
        """
        if "cluster_info" not in data and "machine_info" not in data:
            raise ValueError(
                "Exactly one of `machine_info` and `cluster_info` must be provided."
            )
        elif "cluster_info" in data:
            hardware = Cluster.get_or_create(data["cluster_info"])
        elif "machine_info" in data:
            hardware = Machine.get_or_create(data["machine_info"])
        else:
            raise ValueError(
                "Exactly one of `machine_info` and `cluster_info` must be provided."
            )

        if "github" not in data:
            raise ValueError(
                "GitHub commit information is required. Please provide `github` field."
            )
        user_given_commit_info: TypeCommitInfoGitHub = data["github"]
        repo_url = user_given_commit_info["repo_url"]
        commit = None
        if user_given_commit_info["commit_hash"] is not None:
            commit = commit_fetch_info_and_create_in_db_if_not_exists(
                user_given_commit_info
            )
        if "run_id" not in data:
            raise ValueError("Run ID is required. Please provide `run_id` field.")
        if "timestamp" not in data:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        else:
            try:
                datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S UTC")
                timestamp = data["timestamp"]
            except ValueError:
                raise ValueError(
                    "Timestamp must be in the format 'YYYY-MM-DD HH:MM:SS UTC'."
                )
        return {
            "run_id": data["run_id"],
            "run_reason": data["run_reason"] if "run_reason" in data else None,
            "timestamp": timestamp,
            "hardware_id": hardware.id,
            "commit_id": commit.id if commit else None,
            "commit_repo_url": repo_url,
        }

    def to_dict_for_json_api(flamegraph, include_joins=True):
        """
        :param include_joins:
        :return: Dict representation of flamegraph entity
        """
        out_dict = {
            "id": flamegraph.id,
            "name": flamegraph.name,
            "file_path": flamegraph.file_path,
            "run_id": flamegraph.run_id,
            "run_reason": flamegraph.run_reason,
        }

        if include_joins:
            if flamegraph.commit:
                commit_dict = CommitSerializer().many._dump(flamegraph.commit)
                commit_dict.pop("links", None)
            else:
                commit_dict = None

            hard_ware_dict = HardwareSerializer().one.dump(flamegraph.hardware)
            hard_ware_dict.pop("links", None)

            out_dict["commit"] = commit_dict
            out_dict["hardware"] = hard_ware_dict

        return out_dict

    def ui_commit_short_msg(self) -> str:
        if self.commit is None:
            return "n/a"
        return conbench.util.short_commit_msg(self.commit.message)

class _FlamegraphsCreateSchema(marshmallow.Schema):
    """
    Describes the Schema
    """
    name = marshmallow.fields.String(required=True)
    run_id = marshmallow.fields.String(
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Arbitrary identifier that you can use to group benchmark results.
                Typically used for a "run" of benchmarks (i.e. a single run of a CI
                pipeline) on a single commit and hardware. Required.

                The API does not ensure uniqueness (and, correspondingly, does not
                detect collisions). If your use case relies on this grouping construct
                then use a client-side ID generation scheme with negligible likelihood
                for collisions (e.g., UUID type 4 or similar).

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same `run_tags`, `run_reason`, hardware, and commit.
                There is no technical enforcement of this on the server side, so some
                behavior may not work as intended if this assumption is broken by the
                client.
                """
            )
        },
    )
    run_reason = marshmallow.fields.String(
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Reason for the run (optional, does not need to be unique). A
                low-cardinality tag like `"commit"` or `"pull-request"`, used to group
                and filter runs, with special treatment in the UI and API.

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same `run_reason`. There is no technical enforcement
                of this on the server side, so some behavior may not work as intended if
                this assumption is broken by the client.
                """
            )
        },
    )
    # `AwareDateTime` with `default_timezone` set to UTC: naive datetimes are
    # set this timezone.
    timestamp = marshmallow.fields.AwareDateTime(
        required=True,
        format="iso",
        default_timezone=timezone.utc,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                A datetime string indicating the time at which the benchmark
                was started. Expected to be in ISO 8601 notation.
                Timezone-aware notation recommended. Timezone-naive strings are
                interpreted in UTC. Fractions of seconds can be provided but
                are not returned by the API. Example value:
                2022-11-25T22:02:42Z. This timestamp defines the default
                sorting order when viewing a list of benchmarks via the UI or
                when enumerating benchmarks via the /api/benchmarks/ HTTP
                endpoint.
                """
            )
        },
    )
    machine_info = marshmallow.fields.Nested(
        MachineSchema().create,
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Precisely one of `machine_info` and `cluster_info` must be provided.

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same hardware. There is no technical enforcement of
                this on the server side, so some behavior may not work as intended if
                this assumption is broken by the client.
                """
            )
        },
    )
    cluster_info = marshmallow.fields.Nested(
        ClusterSchema().create,
        required=False,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                Precisely one of `machine_info` and `cluster_info` must be provided.

                The Conbench UI and API assume that all benchmark results with the same
                `run_id` share the same hardware. There is no technical enforcement of
                this on the server side, so some behavior may not work as intended if
                this assumption is broken by the client.
                """
            )
        },
    )
    github = marshmallow.fields.Nested(
        SchemaGitHubCreate(),
        required=True,
        metadata={
            "description": conbench.util.dedent_rejoin(
                """
                GitHub-flavored commit information. Required.

                Use this object to tell Conbench with which specific state of
                benchmarked code (repository identifier, possible commit hash) the
                BenchmarkResult is associated.
                """
            )
        },
    )

class FlamegraphFacadeSchema:
    """
    Handles Schemas for backend API docs
    """
    create = _FlamegraphsCreateSchema()
    #update = _FlamegraphsUpdateSchema()

class _Serializer(EntitySerializer):
    def _dump(self, flamegraph):
        return flamegraph.to_dict_for_json_api()

class FlamegraphSerializer(EntitySerializer):
    """
    For serializing Flamegraph entities. Either one() or many()
    """
    one = _Serializer()
    """
    serialize a single flamegraph entity
    """
    many = _Serializer(many=True)
    """
    serialize multiple flamegraph entities
    """