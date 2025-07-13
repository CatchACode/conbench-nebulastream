import flask
from sqlalchemy import select
from ..app import rule
from ..app._endpoint import AppEndpoint, authorize_or_terminate
from conbench.config import Config
from conbench.entities.flamegraph import Flamegraph
from conbench.dbsession import current_session

class ViewFlamegraph(AppEndpoint):
    """
    This is API that handles the frontend view of a single flamegraph
    """
    decorators = [authorize_or_terminate]
    def get(self, id: int) -> flask.Response:
        """
        Renders the view of a single flamegraph
        :param id: of flamegraph entity
        :return: rendered template
        """
        # retrieve data from DB
        query = select(Flamegraph).where(Flamegraph.id == id)
        flamegraph = current_session.scalar(query)

        if flamegraph is None:
            return self.redirect("app.index")

        hardware_dict = None
        if flamegraph:
            hardware_dict = flamegraph.hardware.serialize()
            hardware_dict.pop("links")

        # Render the template with the flamegraph data
        return self.render_template(
            "flamegraph.html",
            application=Config.APPLICATION_NAME,
            title="Flamegraph",
            flamegraph=flamegraph,
            hardware=hardware_dict,
        )


rule(
    "/flamegraphs/<id>/",
    view_func=ViewFlamegraph.as_view("flamegraph"),
    methods=["GET", "POST"],
)
