import argparse
import datetime
import gettext
import logging
import shlex
import re

import discord
from discord.ext import commands

async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)

class Moderation(commands.Cog):
    def __init__(self, bot):
        
        self.bot = bot
        self._ = self.bot.get_localization('moderation', self.bot.lang)
        self.spam_cd_mapping = commands.CooldownMapping.from_cooldown(8, 10, commands.BucketType.member)
        self.invite_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.invite_mute_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.bot.loop.create_task(self.startup())
    
    async def startup(self):
        '''
        Runs after on_ready has fired, used to initialize the cache for the bot
        '''
        await self.bot.wait_until_ready()
        #self.bot.cache['moderation'] = {}
        #async with self.bot.pool.acquire() as con:
        #    results = await con.fetch('''SELECT * FROM mod_config''')
        #    for result in results:
        #        self.bot.cache['moderation'][result.get('guild_id')] = {}
        #        self.bot.cache['moderation'][result.get('guild_id')]['mute_role_id'] = result.get('mute_role_id')
        #        self.bot.cache['moderation'][result.get('guild_id')]['automod_level'] = result.get('automod_level')
        #        self.bot.cache['moderation'][result.get('guild_id')]['is_raidmode'] = result.get('is_raidmode')
                #P.S.: I know this is bad, but I am too dumb to figure out a better solution c:


    async def warn(self, ctx, member:discord.Member, moderator:discord.Member, reason:str=None):
        '''
        Warn a member, increasing their warning count and logging it.
        Requires userlog extension for full functionality.
        '''
        db_user = await self.bot.global_config.get_user(member.id, ctx.guild.id)
        warns = db_user.warns + 1
        new_user = self.bot.global_config.User(user_id = db_user.user_id, guild_id = db_user.guild_id, flags=db_user.flags, warns=warns, is_muted=db_user.is_muted, notes=db_user.notes)
        await self.bot.global_config.update_user(new_user) #Update warns for user by incrementing it
        if reason is None :
            embed=discord.Embed(title="⚠️" + self._("Warning issued"), description=self._("**{offender}** has been warned by **{moderator}**.").format(offender=member, moderator=moderator), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{member.mention} has been warned by {moderator.mention}.\n**Warns:** {warns}\n\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        else :
            embed=discord.Embed(title="⚠️" + self._("Warning issued"), description=self._("**{offender}** has been warned by **{moderator}**.\n**Reason:** ```{reason}```").format(offender=member, moderator=moderator, reason=reason), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{member.mention} has been warned by {moderator.mention}.\n**Warns:** {warns}\n**Reason:** ```{reason}```\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        try:
            await self.bot.get_cog("Logging").log_elevated(warnembed, ctx.guild.id)
            await ctx.send(embed=embed)
        except AttributeError:
            pass


    #Warn a user & print it to logs, needs logs to be set up
    @commands.group(name="warn", help="Warns a user. Subcommands allow you to clear warnings.", aliases=["bonk"], description="Warns the user and logs it.", usage="warn <user> [reason]", invoke_without_command=True, case_insensitive=True)
    @commands.check(has_priviliged)
    @commands.guild_only()
    async def warn_cmd(self, ctx, offender:discord.Member, *, reason:str=None):
        '''
        Warn command. Person warning must be priviliged.
        '''
        await self.warn(ctx, member=offender, moderator=ctx.author, reason=reason)
    

    @warn_cmd.command(name="clear", help="Clears all warnings from the specified user.", aliases=["clr"])
    @commands.check(has_priviliged)
    @commands.guild_only()
    async def warn_clr(self, ctx, offender:discord.Member, *, reason:str=None):
        '''
        Clears all stored warnings for a specified user.
        '''
        db_user = await self.bot.global_config.get_user(offender.id, ctx.guild.id)
        new_user = self.bot.global_config.User(user_id = db_user.user_id, guild_id = db_user.guild_id, flags=db_user.flags, warns=0, is_muted=db_user.is_muted, notes=db_user.notes)
        await self.bot.global_config.update_user(new_user) #Update warns for user by incrementing it
        if reason is None :
            embed=discord.Embed(title="✅ " + self._("Warnings cleared"), description=self._("**{offender}**'s warnings have been cleared.").format(offender=offender), color=self.bot.embedGreen)
            warnembed=discord.Embed(title="⚠️ Warnings cleared.", description=f"{offender.mention}'s warnings have been cleared by {ctx.author.mention}.\n\n[Jump!]({ctx.message.jump_url})", color=self.bot.embedGreen)
        else :
            embed=discord.Embed(title="✅ " + self._("Warnings cleared"), description=self._("**{offender}**'s warnings have been cleared.\n**Reason:** ```{reason}```").format(offender=offender, reason=reason), color=self.bot.embedGreen)
            warnembed=discord.Embed(title="⚠️ Warnings cleared.", description=f"{offender.mention}'s warnings have been cleared by {ctx.author.mention}.\n**Reason:** ```{reason}```\n[Jump!]({ctx.message.jump_url})", color=self.bot.embedGreen)
        try:
            await self.bot.get_cog("Logging").log_elevated(warnembed, ctx.guild.id)
            await ctx.send(embed=embed)
        except AttributeError:
            pass


    async def mute(self, ctx, member:discord.Member, moderator:discord.Member, duration:str=None, reason:str=None):
        '''
        Handles muting a user. If logging is set up, it will log it. Time is converted via the timers extension.
        If duration is provided, it is a tempmute, otherwise permanent. Updates database. Returns converted duration, if any.
        '''
        db_user = await self.bot.global_config.get_user(member.id, ctx.guild.id)
        if db_user.is_muted:
            raise ValueError('This member is already muted.')
        else:
            mute_role_id = 0
            async with self.bot.pool.acquire() as con:
                result = await con.fetch('''SELECT mute_role_id FROM mod_config WHERE guild_id = $1''', ctx.guild.id)
                if len(result) != 0 and result[0]:
                    mute_role_id = result[0].get('mute_role_id')
            mute_role = ctx.guild.get_role(mute_role_id)
            try:
                await member.add_roles(mute_role, reason=reason)
            except:
                raise
            else:
                new_user = self.bot.global_config.User(user_id = db_user.user_id, guild_id = db_user.guild_id, flags=db_user.flags, warns=db_user.warns, is_muted=True, notes=db_user.notes)
                await self.bot.global_config.update_user(new_user)
                dur = None
                if duration:
                    try:                   
                        dur = await self.bot.get_cog("Timers").converttime(duration)
                        await self.bot.get_cog("Timers").create_timer(expires=dur[0], event="tempmute", guild_id=ctx.guild.id, user_id=member.id, channel_id=ctx.channel.id)
                    except AttributeError:
                        raise ModuleNotFoundError('timers extension not found')
                try:
                    if not duration: duration = "Infinite"
                    else: duration = f"{dur[0]} (UTC)"
                    muteembed=discord.Embed(title="🔇 User muted", description=F"**User:** `{member} ({member.id})`\n**Moderator:** `{moderator} ({moderator.id})`\n**Until:** `{duration}`\n**Reason:** ```{reason}```", color=self.bot.errorColor)
                    await self.bot.get_cog("Logging").log_elevated(muteembed, ctx.guild.id)
                except:
                    pass
                if dur:
                    return dur[0] #Return it if needed to display
    

    async def unmute(self, ctx, member:discord.Member, moderator:discord.Member, reason:str=None):
        '''
        Handles unmuting a user, if logging is set up, it will log it. Updates database.
        '''
        db_user = await self.bot.global_config.get_user(member.id, ctx.guild.id)
        if not db_user.is_muted:
            raise ValueError('This member is not muted.')
        else:
            mute_role_id = 0
            async with self.bot.pool.acquire() as con:
                result = await con.fetch('''SELECT mute_role_id FROM mod_config WHERE guild_id = $1''', ctx.guild.id)
                if len(result) != 0 and result[0]:
                    mute_role_id = result[0].get('mute_role_id')
            mute_role = ctx.guild.get_role(mute_role_id)
            try:
                await member.remove_roles(mute_role)
            except:
                raise
            else:
                new_user = self.bot.global_config.User(user_id = db_user.user_id, guild_id = db_user.guild_id, flags=db_user.flags, warns=db_user.warns, is_muted=False, notes=db_user.notes)
                await self.bot.global_config.update_user(new_user)
                try:
                    muteembed=discord.Embed(title="🔉 User unmuted", description=F"**User:** `{member} ({member.id})`\n**Moderator:** `{moderator} ({moderator.id})`\n**Reason:** ```{reason}```", color=self.bot.embedGreen)
                    await self.bot.get_cog("Logging").log_elevated(muteembed, ctx.guild.id)
                except:
                    pass
                

    @commands.Cog.listener()
    async def on_member_join(self, member):
        '''
        If the user was muted previously, we apply
        the mute again.
        TL;DR: Mute-persistence
        '''
        db_user = await self.bot.global_config.get_user(member.id, member.guild.id)
        if db_user.is_muted == True:
            try:
                mute_role_id = 0
                async with self.bot.pool.acquire() as con:
                    result = await con.fetch('''SELECT mute_role_id FROM mod_config WHERE guild_id = $1''', member.guild.id)
                    if len(result) != 0 and result[0]:
                        mute_role_id = result[0].get('mute_role_id')
                mute_role = member.guild.get_role(mute_role_id)
                await member.add_roles(mute_role, reason="User was muted previously.")
            except AttributeError:
                return       


    @commands.command(name="mute", help="Mutes a user.", description="Mutes a user permanently (until unmuted). Logs the event if logging is set up.", usage="mute <user> [reason]")
    @commands.check(has_priviliged)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def mute_cmd(self, ctx, offender:discord.Member, *, reason:str=None):
        '''
        Mutes a member, by assigning the Mute role defined in settings.
        Muter must be priviliged.
        '''
        await ctx.channel.trigger_typing()
        if offender.id == ctx.author.id:
            embed=discord.Embed(title="❌ " + self._("You cannot mute yourself"), description=self._("You cannot mute your own account."), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        else:
            try:
                await self.mute(ctx, offender, moderator=ctx.author, reason=reason)
            except ValueError as error:
                if str(error) == 'This member is already muted.':
                    embed=discord.Embed(title="❌ " + self._("Already muted"), description=self._("**{offender}** is already muted.").format(offender=offender), color=self.bot.errorColor)
                    await ctx.send(embed=embed)
            except (AttributeError, discord.Forbidden):
                embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._("Unable to mute user. Check if you have a mute role configured, and if the bot has permissions to add said role.").format(offender=offender.mention), color=self.bot.errorColor)
                await ctx.send(embed=embed)              
            else:
                if not reason: reason = "No reason specified"
                embed=discord.Embed(title="🔇 " + self._("User muted"), description=self._("**{offender}** has been muted.\n**Reason:** ```{reason}```").format(offender=offender, reason=reason), color=self.bot.embedGreen)
                await ctx.send(embed=embed)


    @commands.command(name="unmute", help="Unmutes a user.", description="Unmutes a user. Logs the event if logging is set up.", usage="unmute <user> [reason]")
    @commands.check(has_priviliged)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def unmute_cmd(self, ctx, offender:discord.Member, *, reason:str=None):
        await ctx.channel.trigger_typing()
        try:
            await self.unmute(ctx, offender, moderator=ctx.author, reason=reason)
        except ValueError as error:
            if str(error) == 'This member is not muted.':
                embed=discord.Embed(title="❌ " + self._("Not muted"), description=self._("**{offender} is not muted.").format(offender=offender), color=self.bot.errorColor)
                await ctx.send(embed=embed)
        except (AttributeError, discord.Forbidden):
            embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._("Unable to unmute user. Check if you have a mute role configured, and if the bot has permissions to remove said role.").format(offender=offender.mention), color=self.bot.errorColor)
            await ctx.send(embed=embed)              
        else:
            if not reason: reason = "No reason specified"
            embed=discord.Embed(title="🔉 " + self._("User unmuted"), description=self._("**{offender}** has unbeen unmuted.\n**Reason:** ```{reason}```").format(offender=offender, reason=reason), color=self.bot.embedGreen)
            await ctx.send(embed=embed)
    

    @commands.command(help="Temporarily mutes a user.", description="Mutes a user for a specified duration. Logs the event if logging is set up.\n\n**Time formatting:**\n`s` or `second(s)`\n`m` or `minute(s)`\n`h` or `hour(s)`\n`d` or `day(s)`\n`w` or `week(s)`\n`M` or `month(s)`\n`Y` or `year(s)`\n\n**Example:** `tempmute @User -d 5minutes -r 'Being naughty'` or `tempmute @User 5d`\n**Note:** If your arguments contain spaces, you must wrap them in quotation marks.", usage="tempmute <user> -d <duration> -r [reason] OR tempmute <user> <duration>")
    @commands.check(has_priviliged)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def tempmute(self, ctx, offender:discord.Member, *, args):
        '''
        Temporarily mutes a memeber, assigning them a Muted role defined in the settings
        Uses userlog extension to log the event and timers to count the time & unmute on schedule.
        '''
        await ctx.channel.trigger_typing()
        if offender.id == ctx.author.id:
            embed=discord.Embed(title="❌ " + self._("You cannot mute yourself."), description=self._("You cannot mute your own account."), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        parser.add_argument('--duration', '-d')
        parser.add_argument('--reason', '-r')
        try: 
            args = parser.parse_args(shlex.split(str(args)))
            dur = args.duration
            reason = args.reason
        except:
            dur = args
            reason = "No reason provided"

        try:
            muted_until = await self.mute(ctx, offender, moderator=ctx.author, duration=dur, reason=reason)
        except ValueError as error:
            if str(error) == 'This member is already muted.':
                embed=discord.Embed(title="❌ " + self._("Already muted"), description=self._("**{offender}** is already muted.").format(offender=offender), color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed=discord.Embed(title="❌ " + self.bot.errorDataTitle, description=self._("Your entered timeformat is invalid. Type `{prefix}help tempmute` for more information.").format(prefix=ctx.prefix), color=self.bot.errorColor)
                await ctx.send(embed=embed)
        except (AttributeError, discord.Forbidden):
            embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._("Unable to mute user. Check if you have a mute role configured, and if the bot has permissions to add said role.").format(offender=offender.mention), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        except ModuleNotFoundError as error:
            embed=discord.Embed(title="❌ " + self._("Muting failed"), description=self._("This function requires an extension that is not enabled.\n**Error:** ```{error}```").format(error=error), color=self.bot.errorColor)
            await ctx.send(embed=embed)    
        else:
            embed=discord.Embed(title="🔇 " + self._("User muted"), description=self._("**{offender}** has been muted until `{duration} (UTC)`.\n**Reason:** ```{reason}```").format(offender=offender, duration=muted_until, reason=reason), color=self.bot.embedGreen)
            await ctx.send(embed=embed)
    

    @commands.Cog.listener()
    async def on_tempmute_timer_complete(self, timer):
        guild = self.bot.get_guild(timer.guild_id)
        db_user = await self.bot.global_config.get_user(timer.user_id, timer.guild_id)
        is_muted = db_user.is_muted
        if not is_muted:
            return
        new_user = self.bot.global_config.User(user_id = db_user.user_id, guild_id = db_user.guild_id, flags=db_user.flags, warns=db_user.warns, is_muted=False, notes=db_user.notes)
        await self.bot.global_config.update_user(new_user) #Update this here so if the user comes back, they are not perma-muted :pepeLaugh:
        if guild.get_member(timer.user_id) is not None: #Check if the user is still in the guild
            mute_role_id = 0
            async with self.bot.pool.acquire() as con:
                result = await con.fetch('SELECT mute_role_id FROM mod_config WHERE guild_id = $1', timer.guild_id)
                if len(result) != 0 and result[0]:
                    mute_role_id = result[0].get('mute_role_id')
            mute_role = guild.get_role(mute_role_id)
            try:
                offender = guild.get_member(timer.user_id)
                await offender.remove_roles(mute_role,  reason="Temporary mute expired.")
                embed=discord.Embed(title="🔉 User unmuted.", description=f"**{offender}** `({offender.id})` has been unmuted because their temporary mute expired.", color=self.bot.embedGreen)
                await self.bot.get_cog("Logging").log_elevated(embed, timer.guild_id)
            except (AttributeError, discord.Forbidden):
                return
    

    @commands.command(help="Bans a user.", description="Bans a user with an optional reason. Deletes the last 7 days worth of messages from the user.", usage="ban <user> [reason]")
    @commands.check(has_priviliged)
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(self, ctx, offender:discord.Member, *, reason:str=None):
        '''
        Bans a member from the server.
        Banner must be priviliged and have ban_members perms.
        '''
        await ctx.channel.trigger_typing()
        if offender.id == ctx.author.id:
            embed=discord.Embed(title="❌ " + self._("You cannot ban yourself"), description=self._("You cannot ban your own account."), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{ctx.author} ({ctx.author.id}):\nReason: {reason}"
        else:
            raw_reason = reason
            reason = f"{ctx.author} ({ctx.author.id}):\nNo reason provided"

        try:
            embed = discord.Embed(title="🔨 " + self._("You have been banned"), description=self._("You have been banned from **{guild}**.\n**Reason:** ```{raw_reason}```").format(guild=ctx.guild.name, raw_reason=raw_reason),color=self.bot.errorColor)
            await offender.send(embed=embed)
        except:
            logging.info('Failed to notify user about punishment.')

        try:
            await ctx.guild.ban(offender, reason=reason, delete_message_days=7)
            if raw_reason:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.\n**Reason:** ```{raw_reason}```").format(offender=offender, raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** User has been banned.").format(offender=offender),color=self.bot.errorColor)
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
    @commands.check(has_priviliged)
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(self, ctx, offender:discord.User, *, reason:str=None):
        '''
        Unbans a member from the server.
        Unbanner must be priviliged and have ban_members perms.
        '''
        await ctx.channel.trigger_typing()
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{ctx.author} ({ctx.author.id}):\n{reason}"
        else:
            raw_reason = reason
            reason = f"{ctx.author} ({ctx.author.id}):\nNo reason provided"
        try:
            await ctx.guild.unban(offender, reason=reason)
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User unbanned"), description=self._("**{offender}** has been unbanned.\n**Reason:** ```{raw_reason}```").format(offender=offender, raw_reason=raw_reason),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User unbanned"), description=self._("**{offender}** has been unbanned.").format(offender=offender),color=self.bot.embedGreen)
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
    @commands.check(has_priviliged)
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def tempban(self, ctx, offender:discord.Member, *, args):
        '''
        Temporarily bans a member from the server.
        Requires timers extension to work.
        Banner must be priviliged and have ban_members perms.
        '''
        await ctx.channel.trigger_typing()
        if offender.id == ctx.author.id:
            embed=discord.Embed(title="❌ " + self._("You cannot ban yourself."), description=self._("You cannot ban your own account."), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        parser.add_argument('--duration', '-d')
        parser.add_argument('--reason', '-r')
        try: #If args are provided, we use those, otherwise whole arg is converted to time
            args = parser.parse_args(shlex.split(str(args)))
            dur = args.duration
            reason = args.reason
        except:
            dur = args
            reason = "No reason provided"
        try:
            dur = await self.bot.get_cog("Timers").converttime(dur)
            dur = dur[0]
            reason = f"[TEMPBAN] {reason}\nBanned until: {dur}"
        except ValueError:
            embed=discord.Embed(title="❌ " + self.bot.errorDataTitle, description=self._("Your entered timeformat is invalid. Type `{prefix}help tempban` for more information.").format(prefix=ctx.prefix), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            await ctx.message.delete()
        except AttributeError as error:
            embed=discord.Embed(title="❌ " + self._("Tempbanning failed."), description=self._("This function requires an extension that is not enabled.\n**Error:** ```{error}```").format(error=error), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{ctx.author} ({ctx.author.id}):\n{reason}"
        else:
            raw_reason = reason
            reason = f"{ctx.author} ({ctx.author.id}):\nNo reason provided"
        
        try:
            embed = discord.Embed(title="🔨 " + self._("You have been banned"), description=self._("You have been banned from **{guild}**.\n**Reason:** ```{raw_reason}```").format(guild=ctx.guild.name, raw_reason=raw_reason),color=self.bot.errorColor)
            await offender.send(embed=embed)
        except:
            logging.info('Failed to notify user about punishment.')

        try:
            await self.bot.get_cog("Timers").create_timer(expires=dur, event="tempban", guild_id=ctx.guild.id, user_id=offender.id, channel_id=ctx.channel.id)
            await ctx.guild.ban(offender, reason=reason, delete_message_days=7)
            if raw_reason:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.\n**Reason:** ```{raw_reason}```").format(offender=offender, raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.").format(offender=offender),color=self.bot.errorColor)
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
        except:
            return

    @commands.command(help="Softbans a user.", description="Bans a user then immediately unbans them, which means it will erase all messages from the user in the specified range.", usage="softban <user> [days-to-delete] [reason]")
    @commands.check(has_priviliged)
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def softban(self, ctx, offender:discord.Member, deldays:int=1, *, reason:str=None):
        '''
        Soft-bans a user, by banning and un-banning them.
        Removes messages from the last x days.
        Banner must be priviliged and have kick_members permissions.
        Bot must have ban_members permissions.
        '''
        await ctx.channel.trigger_typing()
        if offender.id == ctx.author.id:
            embed=discord.Embed(title="❌ " + self._("You cannot soft-ban yourself."), description=self._("You cannot soft-ban your own account."), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"[SOFTBAN] {ctx.author} ({ctx.author.id}):\n{reason}"
        else:
            raw_reason = reason
            reason = f"[SOFTBAN] {ctx.author} ({ctx.author.id}):\nNo reason provided"
            try:
                embed = discord.Embed(title="🔨 " + self._("You have been soft-banned"), description=self._("You have been soft-banned from **{guild}**. You may rejoin.\n**Reason:** ```{raw_reason}```").format(guild=ctx.guild.name, raw_reason=raw_reason),color=self.bot.errorColor)
                await offender.send(embed=embed)
            except:
                logging.info('Failed to notify user about punishment.')

        try:
            deldays = int(deldays)
            await ctx.guild.ban(offender, reason=reason, delete_message_days=7)
            await ctx.guild.unban(offender, reason="Automatic unban by softban command")
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User soft-banned"), description=self._("**{offender}** has been soft-banned.\n**Reason:** {raw_reason}").format(offender=offender, raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User soft-banned"), description=self._("**{offender}** has been soft-banned.").format(offender=offender),color=self.bot.errorColor)
                await ctx.send(embed=embed)
        except ValueError:
            embed = discord.Embed(title=self.bot.errorDataTitle, description=self._("Invalid format for argument `days-to-delete` See `{prefix}help softban` for command usage.").format(prefix=ctx.prefix),color=self.bot.errorColor)
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
    @commands.check(has_priviliged)
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(self, ctx, offender:discord.Member, *, reason:str=None):
        await ctx.channel.trigger_typing()
        if offender.id == ctx.author.id:
            embed=discord.Embed(title="❌ " + self._("You cannot kick yourself."), description=self._("You cannot kick your own account."), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        if reason != None:
            raw_reason = reason #Shown to the public
            reason = f"{ctx.author} ({ctx.author.id}):\n{reason}"
        else:
            raw_reason = reason
            reason = f"{ctx.author} ({ctx.author.id}):\nNo reason provided"
        
        try:
            embed = discord.Embed(title="🚪👈 " + self._("You have been kicked"), description=self._("You have been kicked from **{guild}**.\n**Reason:** ```{raw_reason}```").format(guild=ctx.guild.name, raw_reason=raw_reason),color=self.bot.errorColor)
            await offender.send(embed=embed)
        except:
            logging.info('Failed to notify user about punishment.')

        try:
            await ctx.guild.kick(offender, reason=reason)
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User kicked"), description=self._("**{offender}** has been kicked.\n**Reason:** ```{raw_reason}```").format(offender=offender, raw_reason=raw_reason),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User kicked"), description=self._("**{offender}** has been kicked.").format(offender=offender),color=self.bot.embedGreen)
                await ctx.send(embed=embed)

        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the kick, or this user cannot be kicked."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Kick failed"), description=self._("Kick failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
    
    @commands.command(aliases=["bulkdelete", "bulkdel"], help="Deletes multiple messages at once.", description="Deletes up to 100 messages at once. Defaults to 5 messages. You can optionally specify a user whose messages will be purged.", usage="purge [limit] [user]")
    @commands.check(has_priviliged)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def purge(self, ctx, limit=5, member:discord.Member=None):
        if limit > 100:
            embed = discord.Embed(title="❌ " + self._("Limit too high"), description=self._("You cannot remove more than **100** messages."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        await ctx.channel.trigger_typing()

        if member:
            def check(message):
                return message.author.id == member.id   
            purged = await ctx.channel.purge(limit=limit, check=check)

        else:
            purged = await ctx.channel.purge(limit=limit)
        
        embed = discord.Embed(title="🗑️ " + self._("Messages purged"), description=self._("**{count}** messages have been deleted.").format(count=len(purged)), color=self.bot.errorColor)
        await ctx.send(embed=embed, delete_after=20.0)
    
    @commands.command(aliases=['clr'], help="Cleans up the bot's messages.", description="Delete up to 50 of the bot's own responses in this channel. Defaults to 5.", usage="clear [limit]")
    @commands.check(has_priviliged)
    @commands.bot_has_permissions(manage_messages=True)
    async def clear(self, ctx, limit=5):
        if limit > 50:
            embed = discord.Embed(title="❌ " + self._("Limit too high"), description=self._("You cannot clear more than **50** messages."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return

        await ctx.channel.trigger_typing()
        def check(message):
            return message.author.id == self.bot.user.id

        cleared = await ctx.channel.purge(limit=limit, check=check)
        embed = discord.Embed(title="🗑️ " + self._("Messages cleared"), description=self._("**{count}** bot messages have been removed.").format(count=len(cleared)), color=self.bot.errorColor)
        await ctx.send(embed=embed, delete_after=20.0)

    @commands.group(help="Controls raidmode for this server.", description="Controls raidmode for this server. Enabling raidmode will set auto-moderation to the highest level, and also sets the server verification level to `High`. Disabling sets it back to `Medium`.\n\n**Requires the following permissions for the bot:**\n`Manage Roles, Manage Messages, Manage Server, Kick Members, Ban Members`\n\nPlease ensure that the bot has all of those permissions, otherwise this command will not work properly.", usage="raidmode [on/off]", invoke_without_command=True, case_insensitive=True)
    @commands.check(has_priviliged)
    @commands.bot_has_permissions(manage_roles=True, manage_messages=True, ban_members=True, kick_members=True)
    async def raidmode(self, ctx):
        await ctx.send_help(ctx.command)

    @raidmode.command(name="on", aliases=["enable"], help="Enables raidmode.", description="Enables raidmode, setting auto-moderation to the highest setting, and server verification to `High`.")
    @commands.check(has_priviliged)
    @commands.bot_has_permissions(manage_roles=True, manage_messages=True, ban_members=True, kick_members=True, manage_guild=True)
    @commands.has_permissions(ban_members=True, manage_messages=True)
    async def raidmode_on(self, ctx):
        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO mod_config (guild_id, is_raidmode) 
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO
            UPDATE SET is_raidmode = $2''', ctx.guild.id, True)
        await ctx.guild.edit(verification_level=discord.VerificationLevel.table_flip)
        embed=discord.Embed(title="🚨 Raidmode enabled", color=self.bot.errorColor, description="""The following changes have been made:
        - Server verification has been set to `High`
        - Auto-Moderation has been set to **(╯°□°）╯︵ ┻━┻**
          - **All** auto-moderation actions will now result in a **permanent ban**
        
        You can disable raidmode via the **`{prefix}raidmode off`** command.""".format(prefix=ctx.prefix))
        await ctx.send(embed=embed)

    @raidmode.command(name="off", aliases=["disable"], help="Disables raidmode.", description="Disables raidmode, setting auto-moderation to the previous setting, and server verification to `Medium`.")
    @commands.check(has_priviliged)
    @commands.bot_has_permissions(manage_roles=True, manage_messages=True, ban_members=True, kick_members=True, manage_guild=True)
    async def raidmode_off(self, ctx):
        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO mod_config (guild_id, is_raidmode) 
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO
            UPDATE SET is_raidmode = $2''', ctx.guild.id, False)
        await ctx.guild.edit(verification_level=discord.VerificationLevel.medium)
        embed=discord.Embed(title="🚨 Raidmode disabled", color=self.bot.errorColor, description="""The following changes have been made:
        - Server verification has been set to `Medium`
        - Auto-Moderation has been reset to it's previous value.
          - You can also modify the auto-moderation level now.""")
        await ctx.send(embed=embed)

        

    async def automod_punish(self, ctx, offender:discord.Member, severity:int, delete_original:bool=False, reason:str=None):
        '''
        Handles automatic punishment for certain actions depending on the current automoderator level & raidmode.
        Severity is defined as such:
        0 - Delete the message if delete_original, otherwise does nothing. Warns user on high & up
        1 - Warn the user, 
        2 - Instant temporary punishment depending on automod level
        3 - Permaban

        Severity is automatically switched to 2 in the case of raidmode.
        '''

        bot_perms = ctx.channel.permissions_for(ctx.guild.me)
        if not bot_perms.ban_members or not bot_perms.manage_roles or not bot_perms.manage_messages or not bot_perms.kick_members:
            return

        if await has_priviliged(ctx):
            return

        async with self.bot.pool.acquire() as con:
            result = await con.fetch('''SELECT * FROM mod_config WHERE guild_id = $1''', ctx.guild.id)
        if len(result) > 0 and result[0]:
            automod_level = result[0].get('automod_level')
            is_raidmode = result[0].get('is_raidmode')

        if is_raidmode:
            automod_level = 4
            severity = 3
            reason = f"[RAID MODE] {reason}"


        if automod_level == 0 or automod_level == 1 and len(ctx.author.roles) > 1:
            return #Automod level 1 ignores people with roles

        if delete_original == True:
            try:
                await ctx.message.delete()
            except:
                logging.info('Auto-moderator failed to delete a message.')
                return

        if severity == 0:

            if automod_level in [3, 4]:
                try:
                    await self.mute(ctx, offender, ctx.guild.me, "15min", reason=f"Muted by auto-moderator\nReason:{reason}")
                except:
                    pass
                else:
                    embed=discord.Embed(title="🔇 " + self._("User muted"), description=self._("**{offender}** has been auto-muted for **15** minutes.\n**Reason:**```{reason}```").format(offender=offender, reason=reason), color=self.bot.errorColor)
                    embed.set_footer(text=self._("If you believe this was a mistake, contact a moderator."))
                    await ctx.send(embed=embed)

        if severity == 1:

            if automod_level in [1, 2]:
                await self.warn(ctx, offender, ctx.guild.me, reason)
            else:
                try:
                    await self.mute(ctx, offender, ctx.guild.me, "15min", reason=f"Muted by auto-moderator\nReason:{reason}")
                except:
                    logging.info(f'Auto-mute failed in guild {ctx.guild.id}')
                else:
                    embed=discord.Embed(title="🔇 " + self._("User muted"), description=self._("**{offender}** has been auto-muted for **15** minutes.\n**Reason:**```{reason}```").format(offender=offender, reason=reason), color=self.bot.errorColor)
                    embed.set_footer(text=self._("If you believe this was a mistake, contact a moderator."))
                    await ctx.send(embed=embed)

        elif severity == 2:

            if automod_level in [1, 2]:
                try:
                    await self.mute(ctx, offender, ctx.guild.me, "15min", reason=f"Muted by auto-moderator\nReason:{reason}")
                except:
                    logging.info(f'Auto-mute failed in guild {ctx.guild.id}')
                else:
                    embed=discord.Embed(title="🔇 " + self._("User muted"), description=self._("**{offender}** has been auto-muted for **15** minutes.\n**Reason:**```{reason}```").format(offender=offender, reason=reason), color=self.bot.errorColor)
                    embed.set_footer(text=self._("If you believe this was a mistake, contact a moderator."))
                    await ctx.send(embed=embed)

            elif automod_level == 3:
                try:
                    embed = discord.Embed(title="🔨 " + self._("You have been soft-banned"), description=self._("You have been soft-banned from **{guild}**. You may rejoin.\n**Reason:** ```{reason}```").format(guild=ctx.guild.name, reason=reason),color=self.bot.errorColor)
                    await offender.send(embed=embed)
                except:
                    pass
                await offender.ban(reason=f"Softbanned by auto-moderator\nReason:{reason}", delete_message_days=1)
                await offender.unban(reason="Automatic unban by softban")
                embed = discord.Embed(title="🔨 " + self._("User softbanned"), description=self._("**{offender}** has been auto-softbanned.\n**Reason:** ```{reason}```").format(offender=offender, reason=reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)

            elif automod_level == 4:
                try:
                    embed = discord.Embed(title="🔨 " + self._("You have been banned"), description=self._("You have been banned from **{guild}**.\n**Reason:** ```{reason}```").format(guild=ctx.guild.name, reason=reason),color=self.bot.errorColor)
                    await offender.send(embed=embed)
                except:
                    pass
                await offender.ban(reason=f"Permabanned by auto-moderator\nReason:{reason}", delete_message_days=1)
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been auto-banned.\n**Reason:** ```{reason}```").format(offender=offender, reason=reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)

        elif severity == 3:

            try:
                embed = discord.Embed(title="🔨 " + self._("You have been banned"), description=self._("You have been banned from **{guild}**.\n**Reason:** ```{reason}```").format(guild=ctx.guild.name, reason=reason),color=self.bot.errorColor)
                await offender.send(embed=embed)
            except:
                pass
            await offender.ban(reason=f"Permabanned by auto-moderator\nReason:{reason}", delete_message_days=7)
            embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been auto-banned.\n**Reason:** ```{reason}```").format(offender=offender, reason=reason),color=self.bot.errorColor)
            await ctx.send(embed=embed)
                

    @commands.Cog.listener()
    async def on_message(self, message):
        '''
        Auto-Moderation
        '''

        if message.guild is None:
            return

        if not isinstance(message.author, discord.Member):
            return

        bucket = self.spam_cd_mapping.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after: #If user exceeded spam limits

            db_user = await self.bot.global_config.get_user(message.author.id, message.guild.id)
            ctx = await self.bot.get_context(message)

            if not db_user.is_muted and not await has_priviliged(ctx) and not message.author.bot:
                await self.automod_punish(ctx, offender=message.author, severity=2, reason="Spam")
        

        mentions = sum(member.id != message.author.id and not member.bot for member in message.mentions)
        if mentions > 7:
            await self.automod_punish(ctx, offender=message.author, severity=3, delete_original=True, reason=f"Spamming {mentions} mentions")
            
        else: #If user posted a discord invite
            invite_regex = re.compile(r"(?:https?://)?discord(?:app)?\.(?:com/invite|gg)/[a-zA-Z0-9]+/?")
            matches = invite_regex.findall(message.content)
            ctx = await self.bot.get_context(message)
            if matches:
                #Delete the invite link, and if automod level is high enough, mute the user
                await self.automod_punish(ctx, offender=message.author, severity=0, delete_original=True, reason="Trying to post Discord Invite links")
                bucket = self.invite_cd_mapping.get_bucket(message)
                invite_rt = bucket.update_rate_limit()
                if invite_rt: #If invite ratelimited
                    mute_bucket = self.invite_mute_cd_mapping.get_bucket(message)
                    invite_mute_rt = mute_bucket.update_rate_limit()
                    if invite_mute_rt: #If user has been warned previously
                        await self.automod_punish(ctx, offender=message.author, severity=2, reason="Trying to post Discord Invite links")
                    else: #Warn user for repeat offenses
                        await self.automod_punish(ctx, offender=message.author, severity=1, reason="Trying to post Discord Invite links")
                            

    

def setup(bot):
    logging.info("Adding cog: Moderation...")
    bot.add_cog(Moderation(bot))
