import logging

from types.bot import SnedBot
from discord.ext import commands

logger = logging.getLogger(__name__)


class HomeGuild(commands.Cog):
    """Functionality for the Home server of Sned"""

    def __init__(self, bot: SnedBot):
        self.bot = bot

    async def log_error(self, error_str: str, ctx=None, event_method: str = None):
        """Send a traceback message to the channel specified in config."""

        error_lines = error_str.split("\n")
        paginator = commands.Paginator(prefix="```py\n")
        if ctx:
            paginator.add_line(
                f"Error in guild '{ctx.guild.name}' ({ctx.guild.id}) during command '{ctx.command}' executed by user '{ctx.author}' ({ctx.author.id}):",
                empty=True,
            )
        elif event_method:
            paginator.add_line(f"Ignoring exception in {event_method}:", empty=True)
        else:
            paginator.add_line(f"Uncaught exception:", empty=True)

        for line in error_lines:
            paginator.add_line(line)
        if "home_guild" in self.bot.config.keys() and "error_logging_channel" in self.bot.config.keys():
            guild = self.bot.get_guild(self.bot.config["home_guild"])
            channel = guild.get_channel(self.bot.config["error_logging_channel"])
            for page in paginator.pages:
                try:
                    await channel.send(page)
                except Exception as error:
                    logging.error(f"Failed sending traceback to logging channel: {error}")
                    return


def setup(bot: SnedBot):
    logger.info("Adding cog: HomeGuild...")
    bot.add_cog(HomeGuild(bot))
