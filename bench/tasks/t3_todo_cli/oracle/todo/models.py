from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Task:
    id: int
    title: str
    done: bool = False
    due: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(id=d["id"], title=d["title"], done=d.get("done", False), due=d.get("due"))
