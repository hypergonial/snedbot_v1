from dataclasses import dataclass
from typing import List


@dataclass
class User:
    """
    Represents a user stored inside the database.
    """

    user_id: int
    guild_id: int
    flags: dict = None
    warns: int = 0
    notes: List[str] = None
