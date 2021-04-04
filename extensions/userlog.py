import discord
from discord.ext import commands
import logging
import asyncio
import datetime

#Main user-facing logging
class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    #Message deletion logging

    #First, if the message was cached, provide detailed info
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        #Guild-only, self ignored
        if message.guild == None or message.author == self.bot.user :
            return
        #Add it to the recently deleted so on_raw_message_delete will ignore this
        self.bot.recentlyDeleted.append(message.id)
        #Then do info collection & dump
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", message.guild.id)
        if loggingchannelID == 0:
            return
        if message.channel.id != loggingchannelID :
            #Logging channel
            loggingchannel = message.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🗑️ Message deleted", description=f"**Message author:** {message.author} ({message.author.id})\n**Channel:** {message.channel.mention}\n**Message content:** ```{message.content}```", color=self.bot.errorColor)
            await loggingchannel.send(embed=embed)

    #Message editing logging

    #First, if the message was cached, provide detailed info
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.guild == None :
            return
        #Do this check to avoid embed edits triggering log
        if before.content == after.content:
            self.bot.recentlyEdited.append(after.id)
            return
        #Add it to the recently deleted so on_raw_message_edit will ignore this
        self.bot.recentlyEdited.append(after.id)
        #Then do info collection & dump
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", after.guild.id)
        if loggingchannelID == 0:
            return
        if after.channel.id != loggingchannelID and after.author != self.bot.user :
            #Logging channel
            loggingchannel = after.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🖊️ Message edited", description=f"**Message author:** {after.author} ({after.author.id})\n**Channel:** {after.channel.mention}\n**Before:** ```{before.content}``` \n**After:** ```{after.content}```\n[Jump!]({after.jump_url})", color=self.bot.embedBlue)
            await loggingchannel.send(embed=embed)

    #This will get called on every message edit regardless of cached state
    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):
        if payload.guild_id == None :
            return
        #Wait for on_message_edit to complete
        await asyncio.sleep(1)
        #If it is in the list, we remove it and stop
        if payload.message_id in self.bot.recentlyDeleted :
            self.bot.recentlyEdited.remove(payload.message_id)
            return
        #Else it is not cached, so we run the logic related to producing a generic edit message.
        else :
            loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", payload.guild_id)
            if payload.channel_id != loggingchannelID :
                if loggingchannelID == 0:
                    return
                else :
                    guild = self.bot.get_guild(payload.guild_id)
                    channel = guild.get_channel(payload.channel_id)
                    message = await channel.fetch_message(payload.message_id)
                    loggingchannel = guild.get_channel(loggingchannelID)
                    embed = discord.Embed(title=f"🖊️ Message edited", description=f"**Channel:** {channel.mention}\n**Message author:** {message.author} ({message.author.id})\n\n**Message contents were not cached.**\n\n**Current content**: ```{message.content}```\n[Jump!]({message.jump_url})", color=self.bot.embedBlue)
                    await loggingchannel.send(embed=embed)


    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        if payload.guild_id == None:
            return
    #Produce bulk msg generic log
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", payload.guild_id)
        if payload.channel_id != loggingchannelID :
            if loggingchannelID == 0:

                return
            else :
                guild = self.bot.get_guild(payload.guild_id)
                channel = guild.get_channel(payload.channel_id)
                loggingchannel = guild.get_channel(loggingchannelID)
                embed = discord.Embed(title=f"🗑️ Bulk message deletion", description=f"**Channel:** {channel.mention}\n**Multiple messages have been purged.**", color=self.bot.errorColor)
                await loggingchannel.send(embed=embed)
    #Does not work, idk why but this event is never called
    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", invite.guild.id)
        if loggingchannelID == 0:
            return
        else :
            loggingchannel = invite.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🗑️ Invite deleted", description=f"**Invite:** {invite}", color=self.bot.errorColor)
            await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", role.guild.id)
        if loggingchannelID == 0:
            return
        else :
            embed = discord.Embed(title=f"🗑️ Role deleted", description=f"**Role:** `{role}`", color=self.bot.errorColor)
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", role.guild.id)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = role.guild.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else :
                loggingchannel = role.guild.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", channel.guild.id)
        if loggingchannelID == 0:
            return
        else :
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", channel.guild.id)
            embed = discord.Embed(title=f"#️⃣ Channel deleted", description=f"**Channel:** `{channel.name}`", color=self.bot.errorColor)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = channel.guild.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else :
                loggingchannel = channel.guild.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)
    
    #Creation

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", channel.guild.id)
        if loggingchannelID == 0:
            return
        else :
            if isinstance(channel, discord.TextChannel):
                embed = discord.Embed(title=f"#️⃣ Channel created", description=f"Channel: {channel.mention}", color=self.bot.embedGreen)
            else :
                embed = discord.Embed(title=f"#️⃣ Channel created", description=f"Channel: `{channel.name}`", color=self.bot.embedGreen)
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", channel.guild.id)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = channel.guild.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else :
                loggingchannel = channel.guild.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", role.guild.id)
        if loggingchannelID == 0:
            return
        else :
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", role.guild.id)
            embed = discord.Embed(title=f"❇️ Role created", description=f"**Role:** `{role}`", color=self.bot.embedGreen)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = role.guild.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else :
                loggingchannel = role.guild.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", after.guild.id)
        if loggingchannelID == 0:
            return
        else :
            embed = discord.Embed(title=f"🖊️ Role updated", description=f"**Role:** `{after.name}` \n**Before:**```Name: {before.name}\nColor: {before.color}\nManaged: {before.managed}\nMentionable: {before.mentionable}\nPosition: {before.position}\nPermissions: {before.permissions}```\n**After:**\n```Name: {after.name}\nColor: {after.color}\nManaged: {after.managed}\nMentionable: {after.mentionable}\nPosition:{after.position}\nPermissions: {after.permissions}```", color=self.bot.embedBlue)
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", after.guild.id)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = after.guild.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else :
                loggingchannel = after.guild.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", after.id)
        if loggingchannelID == 0:
            return
        else :
            embed = discord.Embed(title=f"🖊️ Guild updated", description=f"Guild settings have been updated.", color=self.bot.embedBlue)
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", after.id)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = after.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else:
                loggingchannel = after.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", guild.id)
        if loggingchannelID == 0:
            return
        else :
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", guild.id)
            embed = discord.Embed(title=f"🖊️ Guild integrations updated", description=f"Guild integrations have been updated.", color=self.bot.embedBlue)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = guild.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else :
                loggingchannel = guild.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", guild.id)
        if loggingchannelID == 0:
            return
        else :
            moderator = "Undefined"
            reason = "Not specified"
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                if entry.target == user :
                    moderator = entry.user
                    reason = entry.reason
                    break
            if entry.reason != None:
                embed = discord.Embed(title=f"🔨 User banned", description=f"**Offender:** `{user} ({user.id})`\n**Moderator:**`{moderator}`\n**Reason:**```{reason}```", color=self.bot.errorColor)
            else :
                embed = discord.Embed(title=f"🔨 User banned", description=f"**Offender:** `{user} ({user.id})`\n**Moderator:**`{moderator}`\n**Reason:**```Not specified```", color=self.bot.errorColor)
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", guild.id)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = guild.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else :
                loggingchannel = guild.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)

    
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", guild.id)
        if loggingchannelID == 0:
            return
        else :
            loggingchannel = guild.get_channel(loggingchannelID)
            moderator = "Undefined"
            async for entry in guild.audit_logs(action=discord.AuditLogAction.unban):
                if entry.target == user :
                    moderator = entry.user
                    break
            embed = discord.Embed(title=f"🔨 User unbanned", description=f"**Offender:** `{user} ({user.id})`\n**Moderator:**`{moderator}`", color=self.bot.embedGreen)
            elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", guild.id)
            if elevated_loggingchannelID != 0:
                elevated_loggingchannel = guild.get_channel(elevated_loggingchannelID)
                await elevated_loggingchannel.send(embed=embed)
            else :
                loggingchannel = guild.get_channel(loggingchannelID)
                await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", member.guild.id)
        if loggingchannelID == 0:
            return
        else :
            loggingchannel = member.guild.get_channel(loggingchannelID)
            moderator = "Undefined"
            reason = "Not specified"
            async for entry in member.guild.audit_logs():
                if entry.action == discord.AuditLogAction.kick:
                    if entry.target == member :
                        moderator = entry.user
                        reason = entry.reason
                        break
                else :
                    break
            #If we have not found a kick auditlog
            if moderator == "Undefined":
                embed = discord.Embed(title=f"🚪 User left", description=f"**User:** `{member} ({member.id})`", color=self.bot.errorColor)
                await loggingchannel.send(embed=embed)
            #If we did
            else :
                if entry.reason != None :
                    embed = discord.Embed(title=f"🚪👈 User was kicked", description=f"**Offender:** `{member} ({member.id})`\n**Moderator:**`{moderator}`\n**Reason:**```{reason}```", color=self.bot.errorColor)
                else :
                    embed = discord.Embed(title=f"🚪👈 User was kicked", description=f"**Offender:** `{member} ({member.id})`\n**Moderator:**`{moderator}`\n**Reason:**```Not specified```", color=self.bot.errorColor)
                elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", member.guild.id)
                if elevated_loggingchannelID != 0:
                    elevated_loggingchannel = member.guild.get_channel(elevated_loggingchannelID)
                    await elevated_loggingchannel.send(embed=embed)
                else :
                    loggingchannel = member.guild.get_channel(loggingchannelID)
                    await loggingchannel.send(embed=embed)
                

    @commands.Cog.listener()
    async def on_member_join(self, member):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", member.guild.id)
        if loggingchannelID == 0:
            return
        else :
            loggingchannel = member.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🚪 User joined", description=f"**User:** `{member} ({member.id})`", color=self.bot.embedGreen)
            await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_command(self, ctx):
        if ctx.guild == None:
            return
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", ctx.guild.id)
        if loggingchannelID == 0:
            return
        else :
            loggingchannel = ctx.author.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"☎️ Command called", description=f"**User:** `{ctx.author} ({ctx.author.id})`\n**Channel:** {ctx.channel.mention}\n**Command:** `{ctx.message.content}`\n\n[Jump!]({ctx.message.jump_url})", color=self.bot.embedBlue)
            await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        #Check this before we go on & do a db call as this listener will get spammed A LOT
        if before.nick != after.nick or before.roles != after.roles or before.pending != after.pending:
            loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", after.guild.id)
            if loggingchannelID == 0:
                return
            else :
                loggingchannel = after.guild.get_channel(loggingchannelID)
                if before.nick != after.nick:
                    embed = discord.Embed(title=f"🖊️ Nickname changed", description=f"**User:** `{after.name} ({after.id})`\nNickname before: `{before.nick}`\nNickname after: `{after.nick}`", color=self.bot.embedBlue)
                    await loggingchannel.send(embed=embed)
                if before.roles != after.roles:
                    #Contains role that was added to user if any
                    add_diff = list(set(after.roles)-set(before.roles))
                    #Contains role that was removed from user if any
                    rem_diff = list(set(before.roles)-set(after.roles))
                    if len(add_diff) != 0 :
                        embed = discord.Embed(title=f"🖊️ Member roles updated", description=f"**User:** `{after.name} ({after.id})`\nRole added: `{add_diff[0]}`", color=self.bot.embedBlue)
                    elif len(rem_diff) != 0 :
                        embed = discord.Embed(title=f"🖊️ Member roles updated", description=f"**User:** `{after.name} ({after.id})`\nRole removed: `{rem_diff[0]}`", color=self.bot.embedBlue)
                    #Role updates are considered elevated due to importance
                    elevated_loggingchannelID = await self.bot.DBHandler.retrievesetting("ELEVATED_LOGSCHANNEL", after.guild.id)
                    if elevated_loggingchannelID != 0:
                        elevated_loggingchannel = after.guild.get_channel(elevated_loggingchannelID)
                        await elevated_loggingchannel.send(embed=embed)
                    else :
                        loggingchannel = after.guild.get_channel(loggingchannelID)
                        await loggingchannel.send(embed=embed)
                if before.pending != after.pending:
                    embed = discord.Embed(title=f"🖊️ Member state changed", description=f"**User:** `{after.name} ({after.id})`\n`Pending: {before.pending}` ---> `Pending: {after.pending}`", color=self.bot.embedBlue)

def setup(bot):
    logging.info("Adding cog: Logging...")
    bot.add_cog(Logging(bot))