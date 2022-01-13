from dataclasses import dataclass


@dataclass
class Tag:
    """
    Represents a tag object.
    """

    guild_id: int
    name: str
    owner_id: int
    aliases: list
    content: str
