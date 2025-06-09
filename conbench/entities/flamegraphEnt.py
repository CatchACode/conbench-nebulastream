from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, String, ForeignKey
from ..dbsession import Base 

class Flamegraph(Base):
    __tablename__ = "flamegraph"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    run_id: Mapped[str] = mapped_column(ForeignKey, nullable=False)
