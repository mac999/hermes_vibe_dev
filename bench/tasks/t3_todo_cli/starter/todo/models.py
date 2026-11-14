from dataclasses import asdict, dataclass


@dataclass
class Task:
    id: int
    title: str
    done: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(id=d["id"], title=d["title"], done=d.get("done", False))
