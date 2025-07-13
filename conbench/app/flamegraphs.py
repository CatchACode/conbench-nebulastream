import flask
from sqlalchemy import select

from conbench.app import app
from conbench.config import Config
from conbench.dbsession import current_session
from conbench.entities.flamegraph import Flamegraph

@app.route("/flamegraphs", methods=["GET"])
def flame_graphs():
    """
    This is the frontend app endpoint for viewing multiple flamegraphs as a table
    """

    query = select(Flamegraph).order_by(Flamegraph.run_id.desc()).limit(100)
    flamegraphs = current_session.scalars(query).all()

    return flask.render_template("flamegraphs.html", flamegraphs=flamegraphs, application=Config.APPLICATION_NAME, title="Flamegraphs")