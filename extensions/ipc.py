import logging
import json

import discord
from discord.ext import commands, ipc

logger = logging.getLogger(__name__)

class IpcRoutes(commands.Cog):
    '''
    A cog handling all IPC for the website.
    '''

    def __init__(self, bot):
        self.bot = bot

    async def get_role_dict(self, guild:discord.Guild, ptype:str=None) -> dict:
        '''
        Helper function
        Transforms the output of get_perms into a dict of roles, for easier
        transmission over IPC. If no ptype is specified, all guild roles are returned as a dict.
        The dict contains the ID as a key, the rolename as value.
        '''
        if ptype:
            role_ids = await self.bot.get_cog("Permissions").get_perms(guild, ptype)
            roles = []
            for role_id in role_ids:
                role = guild.get_role(role_id)
                if role:
                    roles.append(role)
        else:
            roles = guild.roles

        if roles and len(roles) > 0:
            role_dict = {}
            for role in roles:
                role_dict[role.id] = role.name
            return role_dict

    async def get_module_status(self, guild_id:int, module_name:str) -> bool:
        '''
        Helper function
        Returns a boolean indicating if a module is enabled or not.
        If there is no entry for a given module, then it falls back to True.

        '''
        record = await self.bot.caching.get(table="modules", guild_id=guild_id, module_name=module_name)
        if record:
            return record[0]["is_enabled"]
        else:
            return True


    @ipc.server.route()
    async def check_for_guild(self, data) -> bool:
        '''Determine if a guild exists'''

        guild = self.bot.get_guild(data.guild_id)
        if guild:
            return True
        else:
            return False


    @ipc.server.route()
    async def get_dash_noguild_info(self, data) -> dict:
        guild_ids = data.guild_ids
        guild_dict = {}
        for guild_id in guild_ids:
            guild = self.bot.get_guild(guild_id)
            if guild:
                guild_dict[guild.id] = {
                    "id": guild.id,
                    "name": guild.name,
                    "icon_url": guild.icon.url
                }
        return guild_dict


    @ipc.server.route()
    async def get_dash_homescreen_info(self, data) -> dict:
        '''
        Contains basic information to be displayed in the
        dashboard home-page like membercount, channelcount,
        and a server icon URL.
        '''
        guild = self.bot.get_guild(data.guild_id)
        response = {
            "id": guild.id,
            "name": guild.name,
            "icon_url": guild.icon.url,
            "member_count": guild.member_count,
            "channel_count": len(guild.channels),
            "role_count": len(guild.roles),
            "nickname": guild.me.nick
        }
        return response


    @ipc.server.route()
    async def change_basic_settings(self, data) -> None:
        '''
        data must contain the following:
        data.guild_id - the guild's ID affected
        data.nickname (Opt) - a nickname to change to
        '''
        try:
            guild = self.bot.get_guild(data.guild_id)
            await guild.me.edit(nick=data.nickname)
        except Exception as e:
            logger.error(f"Error occured applying settings received from IPC: {e}")

    @ipc.server.route()
    async def set_permissions(self, data) -> None:
        '''
        Function to set permissions for a specific ptype over IPC.
        Gets a guild_id, a ptype, and a list of role_ids to set.
        role_ids is exhaustive and contains all IDs to be set.
        '''
        guild = self.bot.get_guild(data.guild_id)
        ptype = data.ptype
        role_ids = data.role_ids
        await self.bot.get_cog("Permissions").set_perms(guild, ptype, role_ids)

    @ipc.server.route()
    async def set_module(self, data) -> None:
        '''
        Function to toggle a module over IPC.
        '''
        guild_id = data.guild_id
        module_name = data.module_name
        is_enabled = data.is_enabled

        await self.bot.pool.execute('''
        INSERT INTO modules (guild_id, module_name, is_enabled)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id, module_name) DO
        UPDATE SET is_enabled = $3
        ''', guild_id, module_name, is_enabled)
        await self.bot.caching.refresh(table="modules", guild_id=guild_id)


    @ipc.server.route()
    async def get_moderation_settings(self, data) -> dict:
        guild = self.bot.get_guild(data.guild_id)
        module_enabled = await self.get_module_status(guild.id, "moderation")
        permitted_role_dict = await self.get_role_dict(guild, "mod_permitted")
        all_role_dict = await self.get_role_dict(guild)
        mod_settings_dict = {}

        records = await self.bot.caching.get(table="mod_config", guild_id=guild.id)
        mod_settings_dict = {
            "dm_users_on_punish" : records[0]["dm_users_on_punish"] if records else True,
            "clean_up_mod_commands" : records[0]["clean_up_mod_commands"] if records else False
        }

        response = {
            "id": guild.id,
            "name": guild.name,
            "icon_url": guild.icon.url,
            "module_enabled": module_enabled,
            "mod_permitted": permitted_role_dict,
            "mod_settings": mod_settings_dict,
            "all_roles": all_role_dict,
            "mute_role_id": str(records[0]["mute_role_id"]) if records else None
            }
        return response

    @ipc.server.route()
    async def set_moderation_settings(self, data) -> None:
        guild_id = data.guild_id
        mod_settings = data.mod_settings

        await self.bot.pool.execute('''
        INSERT INTO mod_config (guild_id, dm_users_on_punish, clean_up_mod_commands)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id) DO
        UPDATE SET dm_users_on_punish = $2, clean_up_mod_commands = $3''',
        guild_id, mod_settings["dm_users_on_punish"], mod_settings["clean_up_mod_commands"])
        await self.bot.caching.refresh(table="mod_config", guild_id=guild_id)
    
    @ipc.server.route()
    async def set_mute_role(self, data) -> None:
        guild_id = data.guild_id
        mute_role_id = data.mute_role_id

        await self.bot.pool.execute('''INSERT INTO mod_config (guild_id, mute_role_id)
        VALUES ($1, $2)
        ON CONFLICT (guild_id) DO
        UPDATE SET mute_role_id = $2
        ''', guild_id, mute_role_id)
        await self.bot.caching.refresh(table="mod_config", guild_id=guild_id)

    @ipc.server.route()
    async def get_automod_settings(self, data) -> dict:
        guild = self.bot.get_guild(data.guild_id)
        module_enabled = await self.get_module_status(guild.id, "moderation")
        excluded_role_dict = await self.get_role_dict(guild, "automod_excluded")
        all_role_dict = await self.get_role_dict(guild)

        automod_policies = await self.bot.get_cog("Moderation").get_policies(guild.id)


        response = {
            "id": guild.id,
            "name": guild.name,
            "icon_url": guild.icon.url,
            "module_enabled": module_enabled,
            "automod_excluded": excluded_role_dict,
            "automod_policies": automod_policies,
            "all_roles": all_role_dict,

        }
        return response

    @ipc.server.route()
    async def set_automod_policies(self, data) -> None:
        guild_id = data.guild_id
        policies = data.policies
        existing_policies = await self.bot.get_cog("Moderation").get_policies(guild_id)
        existing_policies.update(policies)


        await self.bot.pool.execute('''
        INSERT INTO mod_config (
            guild_id, 
            automod_policies
            )
        VALUES ($1, $2)
        ON CONFLICT (guild_id) DO
        UPDATE SET automod_policies = $2
        ''',
        guild_id, json.dumps(existing_policies))
        await self.bot.caching.refresh(table="mod_config", guild_id=guild_id)


    @ipc.server.route()
    async def set_automod_escalate_policy(self, data) -> None:
        guild_id = data.guild_id
        escalate_policy = data.policy

        automod_policies = await self.bot.get_cog("Moderation").get_policies(data.guild_id)
        automod_policies["escalate"] = escalate_policy

        await self.bot.pool.execute('''
        INSERT INTO mod_config (guild_id, automod_policies)
        VALUES ($1, $2)
        ON CONFLICT (guild_id) DO
        UPDATE SET automod_policies = $2
        ''', guild_id, json.dumps(automod_policies))
        await self.bot.caching.refresh(table="mod_config", guild_id=guild_id)


def setup(bot):
    logger.info("Adding cog: IpcRoutes...")
    bot.add_cog(IpcRoutes(bot))