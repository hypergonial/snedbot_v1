import logging

import discord
from discord.ext import commands

class HomeGuild(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    async def log_error(self, ctx, error_str:str):
        '''Send a traceback message to the channel specified in config.'''
        
        error_lines = error_str.split('\n')
        paginator = commands.Paginator(prefix="```py\n")
        paginator.add_line(f"Error in guild {ctx.guild.id} during command '{ctx.command}':", empty=True)
        for line in error_lines:
            paginator.add_line(line)
        if "home_guild" in self.bot.config.keys() and "error_logging_channel" in self.bot.config.keys():
            guild = self.bot.get_guild(self.bot.config["home_guild"])
            channel = guild.get_channel(self.bot.config["error_logging_channel"])
            for page in paginator.pages:
                try:
                    await channel.send(page)
                except Exception as error:
                    logging.error(f"Failed sending traceback to logging channel: {error}"); return


def setup(bot):
    logging.info("Adding cog: HomeGuild...")
    bot.add_cog(HomeGuild(bot))