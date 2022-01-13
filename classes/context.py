import discord
from discord.ext import commands

from classes.components import Confirm


class Context(commands.Context):
    """Custom context"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def confirm(
        self,
        message_content=None,
        *,
        embed: discord.Embed = None,
        file: discord.File = None,
        delete_after: bool = True,
        confirm_msg: str = None,
        cancel_msg: str = None
    ) -> bool:
        """Creates an interactive button-prompt to confirm an action. Returns True if user confirmed."""

        if message_content is None and embed is None:
            raise ValueError("Either content or embed must not be None.")

        if confirm_msg or cancel_msg:
            view = Confirm(self, verbose=True, confirm_msg=confirm_msg, cancel_msg=cancel_msg)
        else:
            view = Confirm(self)

        message = await self.send(content=message_content, embed=embed, file=file, view=view)
        await view.wait()

        if delete_after:
            try:
                await message.delete()
            except discord.Forbidden:
                pass

        return view.value
