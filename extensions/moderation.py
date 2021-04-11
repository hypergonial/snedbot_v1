import argparse
import datetime
import gettext
import logging
import shlex

import aiosqlite
import discord
from discord.ext import commands


async def hasOwner(ctx):
    return ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id

#Check performed to see if the user has priviliged access.
async def hasPriviliged(ctx):
    #Gets a list of all the roles the user has, then gets the ID from that.
    userRoles = [x.id for x in ctx.author.roles]
    #Also get privliged roles, then compare
    privroles = await ctx.bot.DBHandler.checkprivs(ctx.guild.id)
    #Check if any of the roles in user's roles are contained in the priviliged roles.
    return any(role in userRoles for role in privroles) or (ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.lang == "de":
            de = gettext.translation('moderation', localedir=self.bot.localePath, languages=['de'])
            de.install()
            self._ = de.gettext
        elif self.bot.lang == "en":
            self._ = gettext.gettext
        #Fallback to english
        else :
            logging.error("Invalid language, fallback to English.")
            self._ = gettext.gettext
    
    #Warn a user & print it to logs, needs logs to be set up
    @commands.command(help="Warns a user.", description="Warns the user and logs it.", usage="warn <user> [reason]")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def warn(self, ctx, offender:discord.Member, *, reason:str=None):
        '''
        Warn a member, increasing their warning count and logging it.
        Requires userlog extension to work. Person warning must be priviliged.
        '''
        db_user = await self.bot.DBHandler.getUser(offender.id, ctx.guild.id)
        warns = db_user["warns"]
        warns +=1
        await self.bot.DBHandler.updateUser(offender.id, "warns", warns, ctx.guild.id) #Update warns for user by incrementing it
        if reason == None :
            embed=discord.Embed(title="⚠️" + self._("Warning issued."), description=self._("{offender} has been warned.").format(offender=offender.mention), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{offender.mention} has been warned by {ctx.author.mention}.\n**Warns:** {warns}\n\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        else :
            embed=discord.Embed(title="⚠️" + self._("Warning issued."), description=self._("{offender} has been warned.\n**Reason:** {reason}").format(offender=offender.mention, reason=reason), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{offender.mention} has been warned by {ctx.author.mention}.\n**Warns:** {warns}\n**Reason:** ```{reason}```\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        try:
            await self.bot.get_cog("Logging").log_elevated(warnembed, ctx.guild.id)
            await ctx.send(embed=embed)
        except AttributeError:
            embed=discord.Embed(title="❌ " + self._("Warning failed."), description=self._("Logging is not set up properly."), color=self.bot.errorColor)
            await ctx.send(embed=embed, delete_after=20)
            await ctx.message.delete()
        
    @commands.command(help="Mutes a user.", description="Mutes a user permanently (until unmuted). Logs the event if logging is set up.", usage="mute <user> [reason]")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def mute(self, ctx, offender:discord.Member, *, reason:str=None):
        '''
        Mutes a member, by assigning the Mute role defined in settings.
        Muter must be priviliged.
        '''
        db_user = await self.bot.DBHandler.getUser(offender.id, ctx.guild.id)
        is_muted = db_user["is_muted"]
        if is_muted == 1:
            embed=discord.Embed(title="❌ " + self._("Already muted."), description=self._("{offender} is already muted.").format(offender=offender.mention), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        else:
            mute_role_id = await self.bot.DBHandler.retrievesetting("MOD_MUTEROLE", ctx.guild.id)
            mute_role = ctx.guild.get_role(mute_role_id)
            try:
                await offender.add_roles(mute_role)
            except AttributeError:
                embed=discord.Embed(title="❌ " + self._("Mute role not set."), description=self._("Unable to mute user.").format(offender=offender.mention), color=self.bot.errorColor)
                await ctx.send(embed=embed)
                return
            await self.bot.DBHandler.updateUser(offender.id, "is_muted", 1, ctx.guild.id)
            embed=discord.Embed(title="✅ " + self._("User muted."), description=self._("**{offender}** has been muted.").format(offender=offender.mention), color=self.bot.embedGreen)
            await ctx.send(embed=embed)
            muteembed=discord.Embed(title="🔇 User muted", description=F"**User:** `{offender} ({offender.id})`\n**Moderator:** `{ctx.author} ({ctx.author.id})` via {self.bot.user.mention}\n**Reason:** ```{reason}```", color=self.bot.errorColor)
            try:
                await self.bot.get_cog("Logging").log_elevated(muteembed, ctx.guild.id)
            except AttributeError:
                pass
    
    @commands.command(help="Unmutes a user.", description="Unmutes a user. Logs the event if logging is set up.", usage="unmute <user> [reason]")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def unmute(self, ctx, offender:discord.Member, *, reason:str=None):
        db_user = await self.bot.DBHandler.getUser(offender.id, ctx.guild.id)
        is_muted = db_user["is_muted"]
        if is_muted == 0:
            embed=discord.Embed(title="❌ " + self._("Not muted."), description=self._("{offender} is not muted.").format(offender=offender.mention), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        else:
            mute_role_id = await self.bot.DBHandler.retrievesetting("MOD_MUTEROLE", ctx.guild.id)
            mute_role = ctx.guild.get_role(mute_role_id)
            try:
                await offender.remove_roles(mute_role)
            except AttributeError:
                embed=discord.Embed(title="❌ " + self._("Mute role not set."), description=self._("Unable to unmute user.").format(offender=offender.mention), color=self.bot.errorColor)
                await ctx.send(embed=embed)
                return
            await self.bot.DBHandler.updateUser(offender.id, "is_muted", 0, ctx.guild.id)
            embed=discord.Embed(title="✅ " + self._("User unmuted."), description=self._("**{offender}** has been unmuted.").format(offender=offender.mention), color=self.bot.embedGreen)
            await ctx.send(embed=embed)
            muteembed=discord.Embed(title="🔉 User unmuted", description=F"**User:** `{offender} ({offender.id})`\n**Moderator:** `{ctx.author} ({ctx.author.id})` via {self.bot.user.mention}\n**Reason:** ```{reason}```", color=self.bot.embedGreen)
            await self.bot.get_cog("Logging").log_elevated(muteembed, ctx.guild.id)
    
    @commands.command(help="Temporarily mutes a user.", description="Mutes a user for a specified duration. Logs the event if logging is set up.\n\n**Time formatting:**\n`s` or `second(s)`\n`m` or `minute(s)`\n`h` or `hour(s)`\n`d` or `day(s)`\n`w` or `week(s)`\n`M` or `month(s)`\n`Y` or `year(s)`\n\n**Example:** `tempmute @User -d 5minutes -r 'Being naughty'` or `tempmute @User 5d`\n**Note:** If your arguments contain spaces, you must wrap them in quotation marks.", usage="tempmute <user> -d <duration> -r [reason] OR tempmute <user> <duration>")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def tempmute(self, ctx, offender:discord.Member, *, args):
        '''
        Temporarily mutes a memeber, assigning them a Muted role defined in the settings
        Uses userlog extension to log the event and timers to count the time & unmute on schedule.
        '''
        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        parser.add_argument('--duration', '-d')
        parser.add_argument('--reason', '-r')
        try: 
            args = parser.parse_args(shlex.split(str(args)))
            dur = args.duration
            reason = args.reason
        except Exception:
            dur = args
            reason = "No reason provided"
        except SystemExit:
            dur = args
            reason = "No reason provided"
        try:
            dur = await self.bot.get_cog("Timers").converttime(dur)
            dur = dur[0]
            db_user = await self.bot.DBHandler.getUser(offender.id, ctx.guild.id)
            is_muted = db_user["is_muted"]
            if is_muted == 1:
                embed=discord.Embed(title="❌ " + self._("Already muted."), description=self._("{offender} is already muted.").format(offender=offender.mention), color=self.bot.errorColor)
                await ctx.send(embed=embed)
                return
            else:
                await self.bot.get_cog("Timers").create_timer(expiry=dur, event="tempmute", guild_id=ctx.guild.id, user_id=offender.id, channel_id=ctx.channel.id)
                mute_role_id = await self.bot.DBHandler.retrievesetting("MOD_MUTEROLE", ctx.guild.id)
                mute_role = ctx.guild.get_role(mute_role_id)
                try:
                    await offender.add_roles(mute_role)
                except AttributeError:
                    embed=discord.Embed(title="❌ " + self._("Mute role not set."), description=self._("Unable to mute user.").format(offender=offender.mention), color=self.bot.errorColor)
                    await ctx.send(embed=embed)
                    return
                await self.bot.DBHandler.updateUser(offender.id, "is_muted", 1, ctx.guild.id)
                embed=discord.Embed(title="✅ " + self._("User muted."), description=self._("**{offender}** has been muted until `{time}`.").format(offender=offender.mention, time=dur), color=self.bot.embedGreen)
                await ctx.send(embed=embed)
                muteembed=discord.Embed(title="🔇 User muted", description=F"**User:** `{offender} ({offender.id})`\n**Moderator:** `{ctx.author} ({ctx.author.id})` via {self.bot.user.mention}\n**Until:** `{dur} (UTC)`\n**Reason:** ```{reason}```", color=self.bot.errorColor)
                await self.bot.get_cog("Logging").log_elevated(muteembed, ctx.guild.id)
        except ValueError:
            embed=discord.Embed(title="❌ " + self.bot.errorDataTitle, description=self._("Your entered timeformat is invalid. Type `{prefix}help tempmute` for more information.").format(prefix=self.bot.prefix), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            await ctx.message.delete()
        except AttributeError as error:
            embed=discord.Embed(title="❌ " + self._("Muting failed."), description=self._("This function requires an extension that is not enabled.\n**Error:** ```{error}```").format(error=error), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
    
    @commands.Cog.listener()
    async def on_tempmute_timer_complete(self, timer):
        guild = self.bot.get_guild(timer.guild_id)
        if guild is None:
            return
        db_user = await self.bot.DBHandler.getUser(timer.user_id, timer.guild_id)
        is_muted = db_user["is_muted"]
        if is_muted == 0:
            return
        elif guild.get_member(timer.user_id) != None: #Check if the user is still in the guild
            mute_role_id = await self.bot.DBHandler.retrievesetting("MOD_MUTEROLE", timer.guild_id)
            mute_role = guild.get_role(mute_role_id)
            try:
                offender = guild.get_member(timer.user_id)
                await offender.remove_roles(mute_role)
            except AttributeError:
                return
            await self.bot.DBHandler.updateUser(offender.id, "is_muted", 0, timer.guild_id)
            embed=discord.Embed(title="🔉 User unmuted.", description=f"**{offender}** `({offender.id})` has been unmuted because their temporary mute expired.".format(offender=offender.mention), color=self.bot.embedGreen)
            await self.bot.get_cog("Logging").log_elevated(embed, timer.guild_id)
    
    @commands.command(help="Bans a user.", description="Bans a user with an optional reason. Deletes the last 7 days worth of messages from the user.", usage="ban <user> [reason]")
    @commands.check(hasPriviliged)
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx, offender:discord.Member, *, reason:str=None):
        '''
        Bans a member from the server.
        Banner must be priviliged and have ban_members perms.
        '''
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"Reason: {reason}\n\nExecuted by {ctx.author} ({ctx.author.id})"
        else:
            reason = f"No reason provided - Executed by {ctx.author} ({ctx.author.id})"
        try:
            await ctx.guild.ban(offender, reason=reason, delete_message_days=7)
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User banned"), description=self._("User has been banned.\n**Reason:** {raw_reason}").format(raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User banned"), description=self._("User has been banned."),color=self.bot.errorColor)
                await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the ban, or this user cannot be banned."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Ban failed"), description=self._("Ban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return

    @commands.command(help="Unbans a user.", description="Unbans a user with an optional reason. Deletes the last 7 days worth of messages from the user.", usage="unban <user> [reason]")
    @commands.check(hasPriviliged)
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(self, ctx, offender:discord.User, *, reason:str=None):
        '''
        Unbans a member from the server.
        Unbanner must be priviliged and have ban_members perms.
        '''
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"Reason: {reason}\n\nExecuted by {ctx.author} ({ctx.author.id})"
        else:
            reason = f"No reason provided - Executed by {ctx.author} ({ctx.author.id})"
        try:
            await ctx.guild.unban(offender, reason=reason)
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User unbanned"), description=self._("User has been unbanned.\n**Reason:** {raw_reason}").format(raw_reason=raw_reason),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User unbanned"), description=self._("User has been unbanned."),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the unban, or this user cannot be unbanned."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Unban failed"), description=self._("Unban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
    
    @commands.command(help="Temporarily bans a user.", description="Temporarily bans a user for the duration specified. Deletes the last 7 days worth of messages from the user.\n\n**Time formatting:**\n`s` or `second(s)`\n`m` or `minute(s)`\n`h` or `hour(s)`\n`d` or `day(s)`\n`w` or `week(s)`\n`M` or `month(s)`\n`Y` or `year(s)`\n\n**Example:** `tempban @User -d 5minutes -r 'Being naughty'` or `tempban @User 5d`\n**Note:** If your arguments contain spaces, you must wrap them in quotation marks.", usage="tempban <user> -d <duration> -r [reason] OR tempban <user> <duration>")
    @commands.check(hasPriviliged)
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def tempban(self, ctx, offender:discord.Member, *, args):
        '''
        Temporarily bans a member from the server.
        Requires timers extension to work.
        Banner must be priviliged and have ban_members perms.
        '''
        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        parser.add_argument('--duration', '-d')
        parser.add_argument('--reason', '-r')
        try: 
            args = parser.parse_args(shlex.split(str(args)))
            dur = args.duration
            reason = args.reason
        except Exception:
            dur = args
            reason = "No reason provided"
        except SystemExit:
            dur = args
            reason = "No reason provided"
        try:
            dur = await self.bot.get_cog("Timers").converttime(dur)
            dur = dur[0]
            reason = f"[TEMPBAN] {reason}\nBanned until: {dur}"
        except ValueError:
            embed=discord.Embed(title="❌ " + self.bot.errorDataTitle, description=self._("Your entered timeformat is invalid. Type `{prefix}help tempban` for more information.").format(prefix=self.bot.prefix), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            await ctx.message.delete()
        except AttributeError as error:
            embed=discord.Embed(title="❌ " + self._("Tempbanning failed."), description=self._("This function requires an extension that is not enabled.\n**Error:** ```{error}```").format(error=error), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{reason}\n\nExecuted by {ctx.author} ({ctx.author.id})"
        else:
            reason = f"No reason provided - Executed by {ctx.author} ({ctx.author.id})"
        try:
            await self.bot.get_cog("Timers").create_timer(expiry=dur, event="tempban", guild_id=ctx.guild.id, user_id=offender.id, channel_id=ctx.channel.id)
            await ctx.guild.ban(offender, reason=reason, delete_message_days=7)
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User banned"), description=self._("User has been banned.\n**Reason:** {raw_reason}").format(raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User banned"), description=self._("User has been banned."),color=self.bot.errorColor)
                await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the ban, or this user cannot be banned."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Tempban failed"), description=self._("Tempban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return

    @commands.Cog.listener()
    async def on_tempban_timer_complete(self, timer):
        guild = self.bot.get_guild(timer.guild_id)
        if guild is None:
            return
        try:
            offender = await self.bot.fetch_user(timer.user_id)
            await guild.unban(offender, reason="User unbanned: Tempban expired")
        except AttributeError:
            return
        await self.bot.DBHandler.updateUser(offender.id, "is_muted", 0, timer.guild_id)


    @commands.command(help="Softbans a user.", description="Bans a user then immediately unbans them, which means it will erase all messages from the user in the specified range.", usage="softban <user> [days-to-delete] [reason]")
    @commands.check(hasPriviliged)
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def softban(self, ctx, offender:discord.Member, deldays:int=1, *, reason:str=None):
        '''
        Soft-bans a user, by banning and un-banning them.
        Removes messages from the last x days.
        Banner must be priviliged and have kick_members permissions.
        Bot must have ban_members permissions.
        '''
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"[SOFTBAN] {reason}\n\nExecuted by {ctx.author} ({ctx.author.id})"
        else:
            reason = f"[SOFTBAN] No reason provided - Executed by {ctx.author} ({ctx.author.id})"
        try:
            deldays = int(deldays)
            await ctx.guild.ban(offender, reason=reason, delete_message_days=7)
            await ctx.guild.unban(offender, reason="Automatic unban by softban command")
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User soft-banned"), description=self._("User has been soft-banned.\n**Reason:** {raw_reason}").format(raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User soft-banned"), description=self._("User has been soft-banned."),color=self.bot.errorColor)
                await ctx.send(embed=embed)
        except ValueError:
            embed = discord.Embed(title=self.bot.errorDataTitle, description=self._("Invalid format for argument `days-to-delete` See `{prefix}help softban` for command usage.").format(prefix=self.bot.prefix),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the ban, or this user cannot be banned."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Ban failed"), description=self._("Ban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
    
    @commands.command(help="Kicks a user.", description="Kicks a user with an optional reason. Deletes the last 7 days worth of messages from the user.", usage="kick <user> [reason]")
    @commands.check(hasPriviliged)
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx, offender:discord.Member, *, reason:str=None):
        if reason != None:
            raw_reason = reason #Shown to the public
            reason = f"Reason: {reason}\n\nExecuted by {ctx.author} ({ctx.author.id})"
        else:
            reason = f"No reason provided - Executed by {ctx.author} ({ctx.author.id})"
        try:
            await ctx.guild.kick(offender, reason=reason)
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User kicked"), description=self._("User has been kicked.\n**Reason:** ```{raw_reason}```").format(raw_reason=raw_reason),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User kicked"), description=self._("User has been kicked."),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the kick, or this user cannot be kicked."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Kick failed"), description=self._("Kick failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return

def setup(bot):
    logging.info("Adding cog: Moderation...")
    bot.add_cog(Moderation(bot))
