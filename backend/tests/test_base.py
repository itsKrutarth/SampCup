from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, UniqueConstraint

from app.db.base import NAMING_CONVENTION, Base


def test_constraints_get_predictable_names() -> None:
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    Table("parent", metadata, Column("id", Integer, primary_key=True))
    child = Table(
        "child",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("code", String),
        Column("parent_id", ForeignKey("parent.id")),
        UniqueConstraint("code"),
    )
    names = {constraint.name for constraint in child.constraints}
    assert names == {"pk_child", "uq_child_code", "fk_child_parent_id_parent"}
    assert Base.metadata.naming_convention == NAMING_CONVENTION
