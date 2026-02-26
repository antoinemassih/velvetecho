"""Tests for cache serialization"""

import pytest
from datetime import datetime, date
from uuid import UUID, uuid4
from decimal import Decimal

from velvetecho.cache.serialization import CacheSerializer


def test_serialize_basic_types():
    """Test serialization of basic Python types"""
    serializer = CacheSerializer()

    data = {
        "string": "hello",
        "int": 42,
        "float": 3.14,
        "bool": True,
        "none": None,
        "list": [1, 2, 3],
        "dict": {"a": 1},
    }

    json_str = serializer.dumps(data)
    restored = serializer.loads(json_str)

    assert restored == data


def test_serialize_uuid():
    """Test UUID serialization"""
    serializer = CacheSerializer()

    uid = uuid4()
    data = {"id": uid}

    json_str = serializer.dumps(data)
    restored = serializer.loads(json_str)

    # UUID becomes string
    assert restored["id"] == str(uid)


def test_serialize_datetime():
    """Test datetime serialization"""
    serializer = CacheSerializer()

    now = datetime(2024, 1, 1, 12, 0, 0)
    data = {"created_at": now}

    json_str = serializer.dumps(data)
    restored = serializer.loads(json_str)

    # datetime becomes ISO string
    assert restored["created_at"] == "2024-01-01T12:00:00"


def test_serialize_date():
    """Test date serialization"""
    serializer = CacheSerializer()

    today = date(2024, 1, 1)
    data = {"date": today}

    json_str = serializer.dumps(data)
    restored = serializer.loads(json_str)

    assert restored["date"] == "2024-01-01"


def test_serialize_decimal():
    """Test Decimal serialization"""
    serializer = CacheSerializer()

    data = {"price": Decimal("19.99")}

    json_str = serializer.dumps(data)
    restored = serializer.loads(json_str)

    # Decimal becomes float
    assert restored["price"] == 19.99


def test_serialize_set():
    """Test set serialization"""
    serializer = CacheSerializer()

    data = {"tags": {1, 2, 3}}

    json_str = serializer.dumps(data)
    restored = serializer.loads(json_str)

    # set becomes list
    assert set(restored["tags"]) == {1, 2, 3}


def test_serialize_bytes():
    """Test bytes serialization"""
    serializer = CacheSerializer()

    data = {"data": b"hello"}

    json_str = serializer.dumps(data)
    restored = serializer.loads(json_str)

    # bytes becomes base64 string
    import base64
    assert base64.b64decode(restored["data"]) == b"hello"


def test_dumps_bytes():
    """Test dumps_bytes method"""
    serializer = CacheSerializer()

    data = {"test": "value"}
    result = serializer.dumps_bytes(data)

    assert isinstance(result, bytes)
    assert result == b'{"test": "value"}'


def test_loads_bytes():
    """Test loads_bytes method"""
    serializer = CacheSerializer()

    json_bytes = b'{"test": "value"}'
    result = serializer.loads_bytes(json_bytes)

    assert result == {"test": "value"}
