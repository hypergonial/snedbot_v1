from dataclasses import dataclass


@dataclass
class Tag:
    """
    Represents a tag object.
    """

    guild_id: int
    tag_name: str
    tag_owner_id: int
    tag_aliases: list
    tag_content: str
