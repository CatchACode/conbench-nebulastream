import marshmallow
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, ForeignKey
from typing import Any, Dict, List, Optional, Tuple, Union, cast
import sqlalchemy as s

import conbench.util
import conbench.units
from ..entities._entity import (
    Base,
    EntityMixin,
    EntitySerializer,
    NotNull,
    Nullable,
    genprimkey,
    to_float,
)

from ..entities.commit import (
    Commit,
    CommitSerializer,
    TypeCommitInfoGitHub,
    backfill_default_branch_commits,
    get_github_commit_metadata,
)

class Flamegraph(Base):
    __tablename__ = "flamegraph"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    run_id: Mapped[str] = mapped_column(String, nullable=False)

    run_reason: Mapped[Optional[str]] = Nullable(s.Text)

    commit_id: Mapped[Optional[str]] = Nullable(s.ForeignKey("commit.id"))
    commit: Mapped[Optional[Commit]] = relationship("Commit", lazy="joined")


class _FlamegraphsCreateSchema(marshmallow.Schema):
    name = marshmallow.fields.String(required=True)
    file = marshmallow.fields.Raw(required=True, metadata={"type": "file"})
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
    commit_id = marshmallow.fields.String(allow_none=True)



class FlamegraphFacadeSchema:
    create = _FlamegraphsCreateSchema()