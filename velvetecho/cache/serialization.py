"""JSON serialization with support for UUID, datetime, and other Python types"""

import json
from datetime import datetime, date
from uuid import UUID
from typing import Any
from decimal import Decimal


class CacheSerializer:
    """
    JSON serializer with support for Python types.

    Handles:
    - UUID → string
    - datetime/date → ISO format
    - Decimal → float
    - set → list
    - bytes → base64

    Example:
        serializer = CacheSerializer()
        data = {"id": UUID("..."), "created_at": datetime.now()}
        json_str = serializer.dumps(data)
        restored = serializer.loads(json_str)
    """

    @staticmethod
    def _default(obj: Any) -> Any:
        """Custom JSON encoder for Python types"""
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, bytes):
            import base64

            return base64.b64encode(obj).decode("utf-8")
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def dumps(self, obj: Any) -> str:
        """Serialize object to JSON string"""
        return json.dumps(obj, default=self._default)

    def loads(self, s: str) -> Any:
        """Deserialize JSON string to object"""
        return json.loads(s)

    def dumps_bytes(self, obj: Any) -> bytes:
        """Serialize object to JSON bytes"""
        return self.dumps(obj).encode("utf-8")

    def loads_bytes(self, b: bytes) -> Any:
        """Deserialize JSON bytes to object"""
        return self.loads(b.decode("utf-8"))
