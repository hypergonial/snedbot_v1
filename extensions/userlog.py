import asyncio
import datetime
import json
import logging
from typing import Union

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

#TODO: Move logging setup here from extensions/setup
class Logging(commands.Cog):
    '''User-facing logging support for important server events'''

    def __init__(self, bot):
        self.bot = bot
        self.recently_edited = []
        self.recently_deleted = []
        self.frozen_guilds = [] #List of guilds where logging is temporarily suspended
        self.valid_log_events = ["ban", "kick", "mute", "message_delete", "message_delete_mod", "message_edit", "bulk_delete",
        "invites", "roles", "channels", "member_join", "member_leave", "nickname", "guild_settings", "warn"]

    async def get_log_channel(self, event:str, guild_id:int) -> int:
        '''Get logging channel associated with a given event. Returns None if no logging channel is set.'''

        if event not in self.valid_log_events: raise ValueError("Invalid event passed.")

        records = await self.bot.caching.get(table="log_config", guild_id=guild_id)
        log_channels = json.loads(records[0]["log_channels"]) if records and records[0]["log_channels"] else None
        if log_channels and event in log_channels.keys():
            return log_channels[event]
        else:
            return None
    
    async def get_all_log_channels(self, guild_id:int) -> dict:
        '''Return a dict of all log channels for a given guild. Returns None values if an event has no logging channel.'''

        records = await self.bot.caching.get(table="log_config", guild_id=guild_id)
        log_channels = json.loads(records[0]["log_channels"]) if records and records[0]["log_channels"] else {}
        for event in self.valid_log_events:
            if event not in log_channels.keys():
                log_channels[event] = None
        return log_channels

    async def set_log_channel(self, event:str, guild_id:int, channel_id:int=None):
        '''Sets logging channel for an event.'''

        if event not in self.valid_log_events: raise ValueError("Invalid event passed.")

        log_channels = await self.get_all_log_channels(guild_id)
        log_channels[event] = channel_id
        await self.bot.pool.execute('''
        INSERT INTO log_config (log_channels, guild_id) VALUES ($1, $2)
        ON CONFLICT (guild_id) DO
        UPDATE SET log_channels = $1''', json.dumps(log_channels), guild_id)
        await self.bot.caching.refresh(table="log_config", guild_id=guild_id)


    async def log(self, event:str, logcontent:Union[str, discord.Embed], guild_id:int, file:discord.File=None, bypass:bool=False):
        '''Log an event to the designated logging channel.'''

        if guild_id not in self.frozen_guilds or bypass:
            logging_channel_id = await self.get_log_channel(event, guild_id)
            if logging_channel_id:
                guild = self.bot.get_guild(guild_id)
                logging_channel = guild.get_channel(logging_channel_id)
                if logging_channel is None: return
                try:
                    if isinstance(logcontent, discord.Embed):
                        logcontent.timestamp = discord.utils.utcnow()
                        await logging_channel.send(embed=logcontent, file=file)
                    elif isinstance(logcontent, str):
                        await logging_channel.send(content=logcontent, file=file)
                except (discord.Forbidden, discord.HTTPException):
                    return
    
    async def freeze_logging(self, guild_id):
        '''Call to suspend logging temporarily in the given guild. Useful if a log-spammy command is being executed.'''
        if guild_id not in self.frozen_guilds:
            self.frozen_guilds.append(guild_id)
    
    async def unfreeze_logging(self, guild_id):
        '''Call to stop suspending the logging in a given guild.'''
        if guild_id in self.frozen_guilds:
            self.frozen_guilds.remove(guild_id)


    #Message deletion logging

    #First, if the message was cached, provide detailed info
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        #Guild-only, self ignored
        if message.guild is None or message.author.bot:
            return
        #Then do info collection & dump
        moderator = None
        try:
            async for entry in message.guild.audit_logs():
                if entry.action == discord.AuditLogAction.message_delete and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    if entry.target == message.author :
                        moderator = entry.user
                    break
                else :
                    break
        except discord.Forbidden:
            pass
        contentfield = message.content
        if contentfield == "":
            contentfield = "//The message did not contain text."
        if message.attachments:
            contentfield = f"{message.content}\n//The message contained an attachment."
        if message.embeds:
            contentfield = contentfield + "\n//The message contained an embed."

        if moderator != None: #If this was deleted by a mod
            embed = discord.Embed(title=f"🗑️ Message deleted by Moderator", description=f"**Message author:** `{message.author} ({message.author.id})`\n**Moderator:** `{moderator} ({moderator.id})`\n**Channel:** {message.channel.mention}\n**Message content:** ```{contentfield}```", color=self.bot.errorColor)
            await self.log("message_delete_mod", embed, message.guild.id)
        else:
            #Logging channel
            embed = discord.Embed(title=f"🗑️ Message deleted", description=f"**Message author:** `{message.author} ({message.author.id})`\n**Channel:** {message.channel.mention}\n**Message content:** ```{contentfield}```", color=self.bot.errorColor)
            await self.log("message_delete", embed, message.guild.id)

    #Message editing logging

    #First, if the message was cached, provide detailed info
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.guild is None or before.content == after.content:
            return
        #Add it to the recently deleted so on_raw_message_edit will ignore this
        self.recently_edited.append(after.id)
        #Then do info collection & dump
        before_content = before.content if len(before.content) < 1800 else before.content[:1800] + "..."
        after_content = after.content if len(after.content) < 1800 else after.content[:1800] + "..."
        if not after.author.bot:
            embed = discord.Embed(title=f"🖊️ Message edited", description=f"**Message author:** `{after.author} ({after.author.id})`\n**Channel:** {after.channel.mention}\n**Before:** ```{before_content}``` \n**After:** ```{after_content}```\n[Jump!]({after.jump_url})", color=self.bot.embedBlue)
            await self.log("message_edit", embed, after.guild.id)


    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        if payload.guild_id == None:
            return
    #Produce bulk msg generic log
        try:
            moderator = "Discord" 
            guild = self.bot.get_guild(payload.guild_id)
            async for entry in guild.audit_logs(): #Get the bot that did it
                if entry.action == discord.AuditLogAction.message_bulk_delete and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    moderator = entry.user
                    break
                else :
                    break
        except discord.Forbidden:
            pass
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id)
        embed = discord.Embed(title=f"🗑️ Bulk message deletion", description=f"**Channel:** {channel.mention if channel else 'Unknown'}\n**Moderator:** `{moderator}`\n```Multiple messages have been purged.```", color=self.bot.errorColor)
        await self.log("bulk_delete", embed, payload.guild_id)
    #Does not work, idk why but this event is never called
    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        embed = discord.Embed(title=f"🗑️ Invite deleted", description=f"**Invite:** `{invite}`", color=self.bot.errorColor)
        await self.log("invites", embed, invite.guild.id)
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        try:
            moderator = "Undefined"
            async for entry in role.guild.audit_logs():
                if entry.action == discord.AuditLogAction.role_delete:
                    if entry.target == role or entry.target.id == role.id and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                        moderator = entry.user
                    break
                else :
                    break
        except discord.Forbidden:
            return
        embed = discord.Embed(title=f"🗑️ Role deleted", description=f"**Role:** `{role}`\n**Moderator:** `{moderator}`", color=self.bot.errorColor)
        await self.log("roles", embed, role.guild.id)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        try:
            moderator = "Undefined"
            async for entry in channel.guild.audit_logs():
                if entry.action == discord.AuditLogAction.channel_delete:
                    if (entry.target == channel or entry.target.id == channel.id) and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                        moderator = entry.user
                    break
                else :
                    break
        except discord.Forbidden:
            return
        embed = discord.Embed(title=f"#️⃣ Channel deleted", description=f"**Channel:** `{channel.name}` ({channel.type})\n**Moderator:** `{moderator} ({moderator})`", color=self.bot.errorColor)
        await self.log("channels", embed, channel.guild.id)
    
    #Creation

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        try:
            moderator = "Undefined"
            async for entry in channel.guild.audit_logs():
                if entry.action == discord.AuditLogAction.channel_create and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    if entry.target == channel or entry.target.id == channel.id :
                        moderator = entry.user
                    break
                else :
                    break
        except discord.Forbidden:
            return
        embed = discord.Embed(title=f"#️⃣ Channel created", description=f"**Channel:** {channel.mention} `({channel.type})`\n**Moderator:** `{moderator}`", color=self.bot.embedGreen)
        await self.log("channels", embed, channel.guild.id)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        try:
            moderator = "Undefined"
            async for entry in role.guild.audit_logs():
                if entry.action == discord.AuditLogAction.role_create and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    if entry.target == role or entry.target.id == role.id :
                        moderator = entry.user
                    break
                else :
                    break
        except discord.Forbidden:
            return
        embed = discord.Embed(title=f"❇️ Role created", description=f"**Role:** `{role}`\n**Moderator:** `{moderator}`", color=self.bot.embedGreen)
        await self.log("roles", embed, role.guild.id)
    
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        try:
            moderator = None
            async for entry in after.guild.audit_logs():
                if entry.action == discord.AuditLogAction.role_update and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    if entry.target == after or entry.target.id == after.id :
                        moderator = entry.user
                    break
                else :
                    break
        except discord.Forbidden:
            return
        if moderator:
            embed = discord.Embed(title=f"🖊️ Role updated", description=f"**Role:** `{after.name}` \n**Moderator:** `{moderator}`\n**Before:**```Name: {before.name}\nColor: {before.color}\nHoisted: {before.hoist}\nManaged: {before.managed}\nMentionable: {before.mentionable}\nPosition: {before.position}\nPermissions: {before.permissions}```\n**After:**\n```Name: {after.name}\nColor: {after.color}\nHoisted: {after.hoist}\nManaged: {after.managed}\nMentionable: {after.mentionable}\nPosition:{after.position}\nPermissions: {after.permissions}```", color=self.bot.embedBlue)
            await self.log("roles", embed, after.guild.id)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        try:
            moderator = "Undefined"
            async for entry in after.audit_logs():
                if entry.action == discord.AuditLogAction.guild_update and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    moderator = entry.user
                    break
                else :
                    break
        except discord.Forbidden:
            return
        if moderator != "Undefined": #Necessary as e.g. Nitro boosts trigger guild update
            embed = discord.Embed(title=f"🖊️ Guild updated", description=f"Guild settings have been updated by `{moderator}`.", color=self.bot.embedBlue)
            await self.log("guild_settings", embed, after.id)

    
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        try:
            moderator = "Undefined"
            reason = "No reason provided"
            async for entry in guild.audit_logs():
                if entry.target == user and entry.action == discord.AuditLogAction.unban and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    moderator = entry.user
                    if entry.reason:
                        reason = entry.reason
                    break
                else:
                    break
        except discord.Forbidden:
            return
        embed = discord.Embed(title=f"🔨 User unbanned", description=f"**Offender:** `{user} ({user.id})`\n**Moderator:**`{moderator}`\n**Reason:** ```{reason}```", color=self.bot.embedGreen)
        await self.log("ban", embed, guild.id)


    @commands.Cog.listener()
    async def on_member_remove(self, member):

        await asyncio.sleep(1) #Wait for audit log to be present

        is_kick = False
        moderator = "Unknown"
        reason = "Error retrieving data from audit logs! Ensure the bot has permissions to view them!"
        try:
            async for entry in member.guild.audit_logs():
                if entry.action == discord.AuditLogAction.kick and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    if entry.target == member :
                        moderator = entry.user
                        reason = entry.reason
                        is_kick = True; break
                else :
                    break
        except discord.Forbidden:
            pass

        if is_kick:
            embed = discord.Embed(title=f"🚪👈 User was kicked", description=f"**Offender:** `{member} ({member.id})`\n**Moderator:**`{moderator}`\n**Reason:**```{reason}```", color=self.bot.errorColor)
            await self.log("kick", embed, member.guild.id)

        else:
            embed = discord.Embed(title=f"🚪 User left", description=f"**User:** `{member} ({member.id})`\n**User count:** `{member.guild.member_count}`", color=self.bot.errorColor)
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            await self.log("member_leave", embed, member.guild.id)
    

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):

        await asyncio.sleep(1) #Wait for audit log to be present
        moderator = "Unknown"
        reason = "Error retrieving data from audit logs! Ensure the bot has permissions to view them!"
        try:
            async for entry in guild.audit_logs():
                if entry.action == discord.AuditLogAction.ban and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                    if entry.target == user:
                        moderator = entry.user
                        reason = entry.reason; break
        except discord.Forbidden:
            pass
        embed = discord.Embed(title=f"🔨 User banned", description=f"**Offender:** `{user} ({user.id})`\n**Moderator:**`{moderator}`\n**Reason:**```{reason}```", color=self.bot.errorColor)
        await self.log("ban", embed, guild.id)


    @commands.Cog.listener()
    async def on_member_join(self, member):
        embed = discord.Embed(title=f"🚪 User joined", description=f"**User:** `{member} ({member.id})`\n**User count:** `{member.guild.member_count}`", color=self.bot.embedGreen)
        embed.add_field(name="Account created", value=f"{discord.utils.format_dt(member.created_at)} ({discord.utils.format_dt(member.created_at, style='R')})", inline=False)
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        await self.log("member_join", embed, member.guild.id)
    
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick:
            embed = discord.Embed(title=f"🖊️ Nickname changed", description=f"**User:** `{after.name} ({after.id})`\nNickname before: `{before.nick}`\nNickname after: `{after.nick}`", color=self.bot.embedBlue)
            await self.log("nickname", embed, after.guild.id)
        elif before.roles != after.roles:
            #Contains role that was added to user if any
            add_diff = list(set(after.roles)-set(before.roles))
            #Contains role that was removed from user if any
            rem_diff = list(set(before.roles)-set(after.roles))
            #Checking Auditlog for moderator who did it, if applicable
            try:
                moderator = "Undefined"
                async for entry in after.guild.audit_logs():
                    if entry.action == discord.AuditLogAction.member_role_update and (datetime.datetime.now(datetime.timezone.utc) - entry.created_at).total_seconds() < 15:
                        if entry.target == after :
                            moderator = entry.user
                        break
                    else :
                        break
            except discord.Forbidden:
                return
            if len(add_diff) != 0 :
                embed = discord.Embed(title=f"🖊️ Member roles updated", description=f"**User:** `{after.name}#{after.discriminator} ({after.id})`\n**Moderator:** `{moderator}`\n**Role added:** `{add_diff[0]}`", color=self.bot.embedBlue)
            elif len(rem_diff) != 0 :
                embed = discord.Embed(title=f"🖊️ Member roles updated", description=f"**User:** `{after.name}#{after.discriminator} ({after.id})`\n**Moderator:** `{moderator}`\n**Role removed:** `{rem_diff[0]}`", color=self.bot.embedBlue)
            #Role updates are considered elevated due to importance
            if isinstance(moderator, discord.User) or isinstance(moderator, discord.Member) and moderator.bot:
                pass
            else:
                await self.log("roles", embed, after.guild.id)

def setup(bot):
    logger.info("Adding cog: Logging...")
    bot.add_cog(Logging(bot))
