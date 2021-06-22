import logging

import discord
from discord.ext import commands, ipc

class IpcRoutes(commands.Cog):
    '''
    A cog handling all IPC for the website.
    Heavy WIP
    '''
    def __init__(self, bot):
        self.bot = bot

    @ipc.server.route()
    async def get_guild_for_ipc(self, data):
        guild = self.bot.get_guild(data.guild_id)
        return guild


def setup(bot):
    logging.info("Adding cog: IpcRoutes...")
    bot.add_cog(IpcRoutes(bot))