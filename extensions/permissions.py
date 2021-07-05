import logging

import discord
from discord.ext import commands

class Permissions(commands.Cog):
    '''
    Assigns roles to permission lists, which determine their access level.
    Implementation of checks is outside the scope of this cog.
    '''

    def __init__(self, bot):
        self.bot = bot
        self.VALID_TYPES = ["mod_permitted", "automod_excluded"]

    async def generate_perms(self, guild:discord.Guild):
        role_ids = [role.id for role in guild.roles]
        for role_id in role_ids:
            async with self.bot.pool.acquire() as con:
                await con.execute('''
                INSERT INTO permissions (guild_id, ptype, role_ids)
                VALUES ($1, $2, $3)
                ON CONFLICT(guild_id, ptype)
                DO NOTHING
                ''')
    
    async def get_perms(self, guild:discord.Guild, ptype:str):
        if ptype in self.VALID_TYPES:
            async with self.bot.pool.acquire() as con:
                results = await con.fetch('''
                        SELECT role_ids FROM permissions WHERE guild_id = $1 AND ptype = $2
                        ''', guild.id, ptype)
                if results and len(results) > 0:
                    return results[0].get("role_ids")
                else:
                    return [] #So iteration & stuff does not break
        else:
            raise ValueError("Invalid type specified.")

    async def set_perms(self, guild:discord.Guild, ptype:str, role_ids:list):
        if not role_ids: role_ids = []
        guild_role_ids = [role.id for role in guild.roles]
        if ptype in self.VALID_TYPES:
            for role_id in role_ids:
                if role_id not in guild_role_ids:
                    raise ValueError("One of the role_ids specified is invalid, or not found in the current guild.")

            async with self.bot.pool.acquire() as con:
                await con.execute('''
                INSERT INTO permissions (guild_id, ptype, role_ids)
                VALUES ($1, $2, $3) 
                ON CONFLICT (guild_id, ptype) DO
                UPDATE SET role_ids = $3''', guild.id, ptype, role_ids)
        else:
            raise ValueError("Invalid type specified.")


def setup(bot):
    logging.info("Adding cog: Permissions...")
    bot.add_cog(Permissions(bot))