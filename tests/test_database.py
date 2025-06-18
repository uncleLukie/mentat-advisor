# SPDX-Identifier: MIT
"""Unit tests for src.core.database.MentatDB."""
import pytest
from tinydb.storages import MemoryStorage
from src.core.database import MentatDB

@pytest.fixture()
def db():
    # use TinyDB's in-memory backend so no file IO happens
    mem_db = MentatDB()
    mem_db.db.storage = MemoryStorage()   # :contentReference[oaicite:1]{index=1}
    mem_db.resources_table.clear()
    mem_db.settings_table.clear()
    return mem_db

def test_insert_and_get_resource(db):
    db.resources_table.insert({"id": "spice", "name": "Spice", "demand": "low"})
    assert db.get_resource("spice")["name"] == "Spice"

@pytest.mark.parametrize("level", ["high", "medium", "low"])
def test_set_demand(db, level):
    db.resources_table.insert({"id": "water", "name": "Water", "demand": "low"})
    db.set_demand("water", level)
    assert db.get_resource("water")["demand"] == level

def test_settings_roundtrip(db):
    db.set_setting("foo", 42)
    assert db.get_setting("foo") == 42
