from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def test_constraints_get_predictable_names() -> None:
    class Parent(Base):
        __tablename__ = "parent"
        id: Mapped[int] = mapped_column(primary_key=True)

    class Child(Base):
        __tablename__ = "child"
        __table_args__ = (UniqueConstraint("code"),)
        id: Mapped[int] = mapped_column(primary_key=True)
        code: Mapped[str]
        parent_id: Mapped[int] = mapped_column(ForeignKey("parent.id"))

    try:
        names = {constraint.name for constraint in Child.__table__.constraints}
        assert names == {"pk_child", "uq_child_code", "fk_child_parent_id_parent"}
    finally:
        Base.metadata.remove(Child.__table__)
        Base.metadata.remove(Parent.__table__)
        Base.registry.dispose()
