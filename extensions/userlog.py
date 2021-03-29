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

    #This will get called on every message removal regardless of cached state
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        #Wait for on_message_delete to complete
        await asyncio.sleep(1)
        #If it is in the list, we remove it and stop
        if payload.message_id in self.bot.recentlyDeleted :
            self.bot.recentlyDeleted.remove(payload.message_id)
            return
        #Else it is not cached, so we run the logic related to producing a generic deletion message.
        else :
            loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", payload.guild_id)
            if payload.channel_id != loggingchannelID :
                if loggingchannelID == 0:
                    logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
                    return
                else :
                    guild = self.bot.get_guild(payload.guild_id)
                    channel = guild.get_channel(payload.channel_id)
                    loggingchannel = guild.get_channel(loggingchannelID)
                    embed = discord.Embed(title=f"🗑️ Message deleted", description=f"**Channel:** {channel.mention}\n**Message content and author was not cached.**", color=self.bot.errorColor)
                    await loggingchannel.send(embed=embed)

    #Message editing logging

    #First, if the message was cached, provide detailed info
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        #Do this check to avoid embed edits triggering log
        if before.content == after.content:
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
        #Wait for on_message_edit to complete
        await asyncio.sleep(1)
        #If it is in the list, we remove it and stop
        if payload.message_id in self.bot.recentlyDeleted :
            self.bot.recentlyEdited.remove(payload.message_id)
            return
    #Currently removed due to this implementation needing discord.py 1.7.0
    '''
        #Else it is not cached, so we run the logic related to producing a generic edit message.
        else :
            loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", payload.guild_id)
            if payload.channel_id != loggingchannelID :
                if loggingchannelID == 0:
                    logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
                    return
                else :
                    guild = self.bot.get_guild(payload.guild_id)
                    channel = guild.get_channel(payload.channel_id)
                    message = await channel.fetch_message(payload.message_id)
                    loggingchannel = guild.get_channel(loggingchannelID)
                    embed = discord.Embed(title=f"🖊️ Message edited", description=f"**Channel:** {channel.mention}\n**Message author:** {message.author} ({message.author.id})\n\n**Message contents were not cached.**\n\n**Current content**: {message.content}", color=self.bot.embedBlue)
                    await loggingchannel.send(embed=embed)
    '''


    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
    #Produce bulk msg generic log
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", payload.guild_id)
        if payload.channel_id != loggingchannelID :
            if loggingchannelID == 0:
                logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
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
        print("Boop")
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", invite.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = invite.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🗑️ Invite deleted", description=f"**Invite:** {invite}", color=self.bot.errorColor)
            await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", role.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = role.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🗑️ Role deleted", description=f"**Role:** `{role}`", color=self.bot.errorColor)
            await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", channel.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = channel.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🗑️ Channel deleted", description=f"**Channel:** `{channel}`", color=self.bot.errorColor)
            await loggingchannel.send(embed=embed)
    
    #Creation

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", channel.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = channel.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"❇️ Channel created", description=f"**Channel:** `{channel}`", color=self.bot.embedGreen)
            await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", role.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = role.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"❇️ Role created", description=f"**Role:** `{role}`", color=self.bot.embedGreen)
            await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", after.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = after.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🖊️ Role updated", description=f"**Role:** `{after.name}` \n**Before:**```Name: {before.name}\nColor: {before.color}\nManaged: {before.managed}\nMentionable: {before.mentionable}\nPosition: {before.position}\nPermissions: {before.permissions}```\n**After:**\n```Name: {after.name}\nColor: {after.color}\nManaged: {after.managed}\nMentionable: {after.mentionable}\nPosition:{after.position}\nPermissions: {after.permissions}```", color=self.bot.embedBlue)
            await loggingchannel.send(embed=embed)
    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", after.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = after.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🖊️ Guild updated", description=f"Guild settings have been updated.", color=self.bot.embedBlue)
            await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🖊️ Guild integrations updated", description=f"Guild integrations have been updated.", color=self.bot.embedBlue)
            await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = guild.get_channel(loggingchannelID)
            moderator = "Undefined"
            reason = "Not specified"
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                if entry.target == user :
                    moderator = entry.user
                    reason = entry.reason
                    break
            if entry.reason != None:
                embed = discord.Embed(title=f"🔨 Member banned", description=f"**Offender:** `{user} ({user.id})`\n**Moderator:**`{moderator}`\n**Reason:**```{reason}```", color=self.bot.errorColor)
                await loggingchannel.send(embed=embed)
            else :
                embed = discord.Embed(title=f"🔨 Member banned", description=f"**Offender:** `{user} ({user.id})`\n**Moderator:**`{moderator}`\n**Reason:**```Not specified```", color=self.bot.errorColor)
                await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = guild.get_channel(loggingchannelID)
            moderator = "Undefined"
            async for entry in guild.audit_logs(action=discord.AuditLogAction.unban):
                if entry.target == user :
                    moderator = entry.user
                    break
            embed = discord.Embed(title=f"🔨 Member unbanned", description=f"**Offender:** `{user} ({user.id})`\n**Moderator:**`{moderator}`", color=self.bot.embedGreen)
            await loggingchannel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        print("Left, but why?")
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", member.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            print("Finding evidence")
            loggingchannel = member.guild.get_channel(loggingchannelID)
            moderator = "Undefined"
            reason = "Not specified"
            async for entry in member.guild.audit_logs():
                if entry.action == discord.AuditLogAction.kick:
                    if entry.target == member :
                        print("Found in loop")
                        moderator = entry.user
                        reason = entry.reason
                        break
                else :
                    print("Loop broke without evidence")
                    break
            #If we have not found a kick auditlog
            if moderator == "Undefined":
                print("None found")
                embed = discord.Embed(title=f"🚪 Member left", description=f"**User:** `{member} ({member.id})`", color=self.bot.errorColor)
                await loggingchannel.send(embed=embed)
            #If we did
            else :
                print("Found")
                if entry.reason != None :
                    print("Reason found")
                    embed = discord.Embed(title=f"🚪👈 Member kicked", description=f"**Offender:** `{member} ({member.id})`\n**Moderator:**`{moderator}`\n**Reason:**```{reason}```", color=self.bot.errorColor)
                    await loggingchannel.send(embed=embed)
                else :
                    print("No reason")
                    embed = discord.Embed(title=f"🚪👈 Member kicked", description=f"**Offender:** `{member} ({member.id})`\n**Moderator:**`{moderator}`\n**Reason:**```Not specified```", color=self.bot.errorColor)
                    await loggingchannel.send(embed=embed)
                

    @commands.Cog.listener()
    async def on_member_join(self, member):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", member.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = member.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"🚪 Member joined", description=f"**User:** `{member} ({member.id})`", color=self.bot.embedGreen)
            await loggingchannel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_command(self, ctx):
        loggingchannelID = await self.bot.DBHandler.retrievesetting("LOGCHANNEL", ctx.guild.id)
        if loggingchannelID == 0:
            logging.warn("Logging extension is loaded but not set up. Unable to log user events!")
            return
        else :
            loggingchannel = ctx.author.guild.get_channel(loggingchannelID)
            embed = discord.Embed(title=f"☎️ Command called", description=f"**User:** `{ctx.author} ({ctx.author.id})`\n**Channel:** {ctx.channel.mention}\n**Command:** `{ctx.message.content}`\n\n[Jump!]({ctx.message.jump_url})", color=self.bot.embedBlue)
            await loggingchannel.send(embed=embed)
def setup(bot):
    logging.info("Adding cog: Logging...")
    bot.add_cog(Logging(bot))