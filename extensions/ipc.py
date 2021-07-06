import logging

import discord
from discord.ext import commands, ipc

class IpcRoutes(commands.Cog):
    '''
    A cog handling all IPC for the website.
    '''
    def __init__(self, bot):
        self.bot = bot

    async def get_role_dict(self, guild:discord.Guild, ptype:str=None):
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

    async def get_module_status(self, guild_id, module_name):
        '''
        Helper function
        Returns a boolean indicating if a module is enabled or not.
        If there is no entry for a given module, then it falls back to True.

        '''
        record = await self.bot.caching.get(table="modules", guild_id=guild_id, module_name=module_name)
        if record:
            return record["is_enabled"][0]
        else:
            return True


    @ipc.server.route()
    async def check_for_guild(self, data):
        guild = self.bot.get_guild(data.guild_id)
        if guild:
            return True
        else:
            return False


    @ipc.server.route()
    async def get_dash_noguild_info(self, data):
        guild_ids = data.guild_ids
        guild_dict = {}
        for guild_id in guild_ids:
            guild = self.bot.get_guild(guild_id)
            if guild:
                guild_dict[guild.id] = {
                    "id": guild.id,
                    "name": guild.name,
                    "icon_url": str(guild.icon_url)
                }
        return guild_dict


    @ipc.server.route()
    async def get_dash_homescreen_info(self, data):
        '''
        Contains basic information to be displayed in the
        dashboard home-page like membercount, channelcount,
        and a server icon URL.
        '''
        guild = self.bot.get_guild(data.guild_id)
        response = {
            "id": guild.id,
            "name": guild.name,
            "icon_url": str(guild.icon_url),
            "member_count": guild.member_count,
            "channel_count": len(guild.channels),
            "role_count": len(guild.roles),
            "nickname": guild.me.nick
        }
        return response


    @ipc.server.route()
    async def change_basic_settings(self, data):
        '''
        data must contain the following:
        data.guild_id - the guild's ID affected
        data.nickname (Opt) - a nickname to change to
        '''
        try:
            guild = self.bot.get_guild(data.guild_id)
            await guild.me.edit(nick=data.nickname)
        except Exception as e:
            logging.error(f"Error occured applying settings received from IPC: {e}")

    @ipc.server.route()
    async def set_permissions(self, data):
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
    async def set_module(self, data):
        '''
        Function to toggle a module over IPC.
        '''
        guild_id = data.guild_id
        module_name = data.module_name
        is_enabled = data.is_enabled

        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO modules (guild_id, module_name, is_enabled)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, module_name) DO
            UPDATE SET is_enabled = $3
            ''', guild_id, module_name, is_enabled)
        await self.bot.caching.refresh(table="modules", guild_id=guild_id)


    @ipc.server.route()
    async def get_moderation_settings(self, data):
        guild = self.bot.get_guild(data.guild_id)
        module_enabled = await self.get_module_status(guild.id, "moderation")
        permitted_role_dict = await self.get_role_dict(guild, "mod_permitted")
        all_role_dict = await self.get_role_dict(guild)
        mod_settings_dict = {}

        record = await self.bot.caching.get(table="mod_config", guild_id=guild.id)
        mod_settings_dict = {
            "dm_users_on_punish" : record["dm_users_on_punish"][0] if record else True,
            "clean_up_mod_commands" : record["clean_up_mod_commands"][0] if record else False
        }

        response = {
            "id": guild.id,
            "name": guild.name,
            "icon_url": str(guild.icon_url),
            "module_enabled": module_enabled,
            "mod_permitted": permitted_role_dict,
            "mod_settings": mod_settings_dict,
            "all_roles": all_role_dict,
            "mute_role_id": str(record["mute_role_id"][0]) if record else None
            #mute_role_id needs to be converted to str, as ints inside dicts get converted too
            }
        return response

    @ipc.server.route()
    async def set_moderation_settings(self, data):
        guild_id = data.guild_id
        mod_settings = data.mod_settings
        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO mod_config (guild_id, dm_users_on_punish, clean_up_mod_commands)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id) DO
            UPDATE SET dm_users_on_punish = $2, clean_up_mod_commands = $3''',
            guild_id, mod_settings["dm_users_on_punish"], mod_settings["clean_up_mod_commands"])
        self.bot.caching.refresh(table="mod_config", guild_id=guild_id)
    
    @ipc.server.route()
    async def set_mute_role(self, data):
        guild_id = data.guild_id
        mute_role_id = data.mute_role_id
        async with self.bot.pool.acquire() as con:
            await con.execute('''INSERT INTO mod_config (guild_id, mute_role_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO
            UPDATE SET mute_role_id = $2
            ''', guild_id, mute_role_id)
        self.bot.caching.refresh(table="mod_config", guild_id=guild_id)

    @ipc.server.route()
    async def get_automod_settings(self, data):
        guild = self.bot.get_guild(data.guild_id)
        module_enabled = await self.get_module_status(guild.id, "moderation")
        excluded_role_dict = await self.get_role_dict(guild, "automod_excluded")
        all_role_dict = await self.get_role_dict(guild)
        automod_policies_dict = {}

        record = await self.bot.caching.get(table="mod_config", guild_id=guild.id)
        automod_policies_dict = {
            "invites" : record["policies_invites"][0] if record else "disabled",
            "spam" : record["policies_spam"][0] if record else "disabled",
            "mass_mentions" : record["policies_mass_mentions"][0] if record else "disabled",
            "zalgo" : record["policies_zalgo"][0] if record else "disabled",
            "attach_spam" : record["policies_attach_spam"][0] if record else "disabled",
            "link_spam": record["policies_link_spam"][0] if record else "disabled",
            "escalate": record["policies_escalate"][0] if record else "disabled",
            }

        response = {
            "id": guild.id,
            "name": guild.name,
            "icon_url": str(guild.icon_url),
            "module_enabled": module_enabled,
            "automod_excluded": excluded_role_dict,
            "automod_policies": automod_policies_dict,
            "all_roles": all_role_dict,
            "temp_dur": record["temp_dur"][0] if record else 15,

        }
        return response

    @ipc.server.route()
    async def set_automod_policies(self, data):
        guild_id = data.guild_id
        policies = data.policies

        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO mod_config (
                guild_id, 
                policies_invites, 
                policies_spam, 
                policies_mass_mentions, 
                policies_zalgo, 
                policies_attach_spam, 
                policies_link_spam
                )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (guild_id) DO
            UPDATE SET 
                policies_invites = $2, 
                policies_spam = $3, 
                policies_mass_mentions = $4, 
                policies_zalgo = $5, 
                policies_attach_spam = $6, 
                policies_link_spam = $7''',
            guild_id, policies["invites"], policies["spam"], policies["mass_mentions"], policies["zalgo"], policies["attach_spam"], policies["link_spam"])
        await self.bot.caching.refresh(table="mod_config", guild_id=guild_id)

    @ipc.server.route()
    async def set_automod_temp_dur(self, data):
        guild_id = data.guild_id
        temp_dur = data.temp_dur

        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO mod_config (guild_id, temp_dur)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO
            UPDATE SET temp_dur = $2
            ''', guild_id, temp_dur)
        await self.bot.caching.refresh(table="mod_config", guild_id=guild_id)

    @ipc.server.route()
    async def set_automod_escalate_policy(self, data):
        guild_id = data.guild_id
        escalate_policy = data.policy

        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO mod_config (guild_id, policies_escalate)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO
            UPDATE SET policies_escalate = $2
            ''', guild_id, escalate_policy)
        await self.bot.caching.refresh(table="mod_config", guild_id=guild_id)




def setup(bot):
    logging.info("Adding cog: IpcRoutes...")
    bot.add_cog(IpcRoutes(bot))