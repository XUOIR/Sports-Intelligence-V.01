from datetime import datetime
from .config import PACIFIC

def now() -> datetime:
    return datetime.now(PACIFIC)

def aware(value: datetime | str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return dt.astimezone(PACIFIC)
