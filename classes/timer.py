from dataclasses import dataclass


@dataclass
class Timer:
    """
    Represents a timer object.
    """

    id: int
    guild_id: int
    user_id: int
    channel_id: int
    event: str
    expires: int
    notes: str
