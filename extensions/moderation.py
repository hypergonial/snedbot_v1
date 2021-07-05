import argparse
import datetime
import gettext
import logging
import shlex
import re
from dataclasses import dataclass
import functools
import unicodedata

import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)
async def has_mod_perms(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, "mod_permitted")
async def is_automod_excluded(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, "automod_excluded")

async def can_mute(ctx):
    '''A check performed to see if the configuration is correct for muting to be done.'''
    async with ctx.bot.pool.acquire() as con:
        result = await con.fetch('''SELECT mute_role_id FROM mod_config WHERE guild_id = $1''', ctx.guild.id)
        if len(result) != 0 and result[0]:
            mute_role_id = result[0].get('mute_role_id')
            mute_role = ctx.guild.get_role(mute_role_id)
            if mute_role:
                return True
            else:
                return False
        else:
            return False

@dataclass
class ModerationSettings():
    dm_users_on_punish:bool
    clean_up_mod_commands:bool


class AlreadyMutedException(Exception):
    '''Raised when trying to mute an already muted user'''
    pass

class NotMutedException(Exception):
    '''Raised when trying to unmute a user who is not muted'''
    pass

class Moderation(commands.Cog):
    def __init__(self, bot):
        
        self.bot = bot
        self._ = self.bot.get_localization('moderation', self.bot.lang)

        self.spam_cd_mapping = commands.CooldownMapping.from_cooldown(10, 12, commands.BucketType.member)
        self.attach_spam_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.link_spam_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.escalate_prewarn_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.escalate_cd_mapping = commands.CooldownMapping.from_cooldown(2, 30, commands.BucketType.member)

        self.bot.loop.create_task(self.startup())
    
    async def cog_check(self, ctx):
        return await self.bot.custom_checks.module_is_enabled(ctx, "moderation")


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

    async def get_settings(self, guild_id:int) -> ModerationSettings:
        '''
        Checks for and returns the moderation settings for a given guild.
        '''
        async with self.bot.pool.acquire() as con:
            result = await con.fetch('SELECT * FROM mod_config WHERE guild_id = $1', guild_id)
            if result and len(result) > 0:
                mod_settings = ModerationSettings(
                    dm_users_on_punish=result[0].get("dm_users_on_punish"),
                    clean_up_mod_commands=result[0].get("clean_up_mod_commands")
                )
            else:
                mod_settings = ModerationSettings(
                    dm_users_on_punish=True,
                    clean_up_mod_commands=False

                )
            return mod_settings

    async def get_policies(self, guild_id:int) -> dict:
        '''
        Checks for and returns the auto-moderation policies for the given guild.
        '''
        async with self.bot.pool.acquire() as con:
            result = await con.fetch('SELECT * FROM mod_config WHERE guild_id = $1', guild_id)

            policies = {
                "invites": result[0].get("policies_invites") if result and len(result) > 0 else "disabled",
                "spam": result[0].get("policies_spam") if result and len(result) > 0 else "disabled",
                "mass_mentions": result[0].get("policies_zalgo") if result and len(result) > 0 else "disabled",
                "attach_spam": result[0].get("policies_attach_spam") if result and len(result) > 0 else "disabled",
                "link_spam": result[0].get("policies_link_spam") if result and len(result) > 0 else "disabled",
                "escalate": result[0].get("policies_escalate") if result and len(result) > 0 else "disabled"
            }

            return policies


    def mod_punish(func):
        '''
        Decorates commands that are supposed to punish a user.
        '''

        @functools.wraps(func)
        async def inner(*args, **kwargs):
            self = args[0]
            ctx = args[1]
            member = args[2]
            reason = kwargs["reason"]

            if ctx.author.id == member.id:
                embed=discord.Embed(title="❌ " + self._("You cannot {pwn} yourself.").format(pwn=ctx.command.name), description=self._("You cannot {pwn} your own account.").format(pwn=ctx.command.name), color=self.bot.errorColor)
                await ctx.send(embed=embed)
                return
            
            if member.bot:
                embed=discord.Embed(title="❌ " + self._("Cannot execute on bots."), description=self._("This command cannot be executed on bots."), color=self.bot.errorColor)
                await ctx.send(embed=embed)
                return
            
            settings = await self.get_settings(ctx.guild.id)
            types_conj = {
            "warn": "warned in",
            "mute": "muted in",
            "kick": "kicked from",
            "ban": "banned from",
            "softban": "soft-banned from",
            "tempban": "temp-banned from",
            }

            #This is a weird one, but it has to do this before actually
            #punishing the user, because if the user leaves the guild,
            #you can no longer DM them
            if settings.dm_users_on_punish:
                embed = discord.Embed(title="❗ " + "You have been {pwned} {guild}".format(pwned=types_conj[ctx.command.name], guild=ctx.guild.name), description=self._("You have been {pwned} **{guild}**.\n**Reason:** ```{reason}```").format(pwned=types_conj[ctx.command.name], guild=ctx.guild.name, reason=reason),color=self.bot.errorColor)
                try:
                    await member.send(embed=embed)
                except discord.Forbidden:
                    pass

            if settings.clean_up_mod_commands:
                print("Cleaning up mod commands...")
                try:
                    await ctx.message.delete()
                except (discord.Forbidden, discord.HTTPException):
                    pass
            
            return await func(*args, **kwargs)

        return inner


    def mod_command(func):
        '''
        Decorates general purpose mod-commands
        '''

        @functools.wraps(func)
        async def inner(*args, **kwargs):
            self = args[0]
            ctx = args[1]
            
            settings = await self.get_settings(ctx.guild.id)

            if settings.clean_up_mod_commands:
                try:
                    await ctx.message.delete()
                except (discord.Forbidden, discord.HTTPException):
                    pass

            return await func(*args, **kwargs)
        return inner


    async def warn(self, ctx, member:discord.Member, moderator:discord.Member, reason:str=None):
        '''
        Warn a member, increasing their warning count and logging it.
        Requires userlog extension for full functionality.
        '''
        db_user = await self.bot.global_config.get_user(member.id, ctx.guild.id)
        db_user.warns += 1
        await self.bot.global_config.update_user(db_user) #Update warns for user by incrementing it
        if reason is None :
            embed=discord.Embed(title="⚠️" + self._("Warning issued"), description=self._("**{offender}** has been warned by **{moderator}**.").format(offender=member, moderator=moderator), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{member.mention} has been warned by {moderator.mention}.\n**Warns:** {db_user.warns}\n\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        else :
            embed=discord.Embed(title="⚠️" + self._("Warning issued"), description=self._("**{offender}** has been warned by **{moderator}**.\n**Reason:** ```{reason}```").format(offender=member, moderator=moderator, reason=reason), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{member.mention} has been warned by {moderator.mention}.\n**Warns:** {db_user.warns}\n**Reason:** ```{reason}```\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        try:
            await self.bot.get_cog("Logging").log_elevated(warnembed, ctx.guild.id)
            await ctx.send(embed=embed)
        except AttributeError:
            pass

    async def mute(self, ctx, member:discord.Member, moderator:discord.Member, duration:str=None, reason:str=None):
        '''
        Handles muting a user. If logging is set up, it will log it. Time is converted via the timers extension.
        If duration is provided, it is a tempmute, otherwise permanent. Updates database. Returns converted duration, 
        if any.
        '''
        db_user = await self.bot.global_config.get_user(member.id, ctx.guild.id)
        if db_user.is_muted:
            raise AlreadyMutedException('This member is already muted.')
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
            raise NotMutedException('This member is not muted.')
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

    async def ban(self, ctx, member:discord.Member, moderator:discord.Member, duration:str=None, soft:bool=False, reason:str=None):
        '''
        Handles the banning of a user, can optionally accept a duration to make it a tempban.
        '''
        if duration and soft:
            raise RuntimeError("Ban type cannot be soft when a duration is specified.")

        if duration:
            try:
                dur = await self.bot.get_cog("Timers").converttime(duration)
                dur = dur[0]
                reason = f"{reason}\nBanned until: {dur}"

            except ValueError:
                embed=discord.Embed(title="❌ " + self.bot.errorDataTitle, description=self._("Your entered timeformat is invalid. Type `{prefix}help tempban` for more information.").format(prefix=ctx.prefix), color=self.bot.errorColor)
                return await ctx.send(embed=embed)
                
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{moderator} ({moderator.id}): \n{reason}"
        else:
            raw_reason = reason
            reason = f"{moderator} ({moderator.id}): \nNo reason provided"

        if soft:
            raw_reason = f"[SOFTBAN] {raw_reason}"
        elif duration:
            raw_reason = f"[TEMPBAN] {raw_reason}"

        try:
            await ctx.guild.ban(member, reason=reason, delete_message_days=1)
            if raw_reason:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.\n**Reason:** ```{raw_reason}```").format(offender=member, raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.").format(offender=member),color=self.bot.errorColor)
                await ctx.send(embed=embed)

            if soft:
                await ctx.guild.unban(member, reason="Automatic unban by softban")
            elif dur:
                try:
                    await self.bot.get_cog("Timers").create_timer(expires=dur, event="tempban", guild_id=ctx.guild.id, user_id=member.id, channel_id=ctx.channel.id)
                except AttributeError as error:
                    embed=discord.Embed(title="❌ " + self._("Tempbanning failed."), description=self._("This function requires an extension that is not enabled.\n**Error:** ```{error}```").format(error=error), color=self.bot.errorColor)
                    return await ctx.send(embed=embed)

        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Ban failed"), description=self._("Ban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return

    async def kick(self, ctx, member:discord.Member, moderator:discord.Member, reason:str=None):
        '''
        Handles the kicking of a user.
        '''
       
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{moderator} ({moderator.id}): \n{reason}"
        else:
            raw_reason = reason
            reason = f"{moderator} ({moderator.id}): \nNo reason provided"


        try:
            await ctx.guild.ban(member, reason=reason, delete_message_days=1)
            if raw_reason:
                embed = discord.Embed(title="🔨 " + self._("User kicked"), description=self._("**{offender}** has been kicked.\n**Reason:** ```{raw_reason}```").format(offender=member, raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="🔨 " + self._("User kicked"), description=self._("**{offender}** has been kicked.").format(offender=member),color=self.bot.errorColor)
                await ctx.send(embed=embed)

        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Kick failed"), description=self._("Ban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return



    #Warn a user & print it to logs, needs logs to be set up
    @commands.group(name="warn", help="Warns a user. Subcommands allow you to clear warnings.", aliases=["bonk"], description="Warns the user and logs it.", usage="warn <user> [reason]", invoke_without_command=True, case_insensitive=True)
    @commands.check(has_mod_perms)
    @commands.guild_only()
    @mod_punish
    async def warn_cmd(self, ctx, member:discord.Member, *, reason:str=None):
        '''
        Warn command. Person warning must be in permitted roles.
        '''
        await self.warn(ctx, member=member, moderator=ctx.author, reason=reason)
    

    @warn_cmd.command(name="clear", help="Clears all warnings from the specified user.", aliases=["clr"])
    @commands.check(has_mod_perms)
    @commands.guild_only()
    @mod_command
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
    @commands.check(has_mod_perms)
    @commands.check(can_mute)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    @mod_punish
    async def mute_cmd(self, ctx, member:discord.Member, *, reason:str=None):
        '''
        Mutes a member, by assigning the Mute role defined in settings.
        Muter must be priviliged.
        '''
        await ctx.channel.trigger_typing()
        try:
            await self.mute(ctx, member, ctx.author, None, reason)
        except AlreadyMutedException:
            embed=discord.Embed(title="❌ " + self._("Already muted"), description=self._("**{offender}** is already muted.").format(offender=member), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        except (AttributeError, discord.Forbidden):
            embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._("Unable to mute user. Check if you have a mute role configured, and if the bot has permissions to add said role.").format(offender=member.mention), color=self.bot.errorColor)
            await ctx.send(embed=embed)              
        else:
            if not reason: reason = "No reason specified"
            embed=discord.Embed(title="🔇 " + self._("User muted"), description=self._("**{offender}** has been muted.\n**Reason:** ```{reason}```").format(offender=member, reason=reason), color=self.bot.embedGreen)
            await ctx.send(embed=embed)


    @commands.command(name="unmute", help="Unmutes a user.", description="Unmutes a user. Logs the event if logging is set up.", usage="unmute <user> [reason]")
    @commands.check(has_mod_perms)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    @mod_command
    async def unmute_cmd(self, ctx, offender:discord.Member, *, reason:str=None):
        await ctx.channel.trigger_typing()
        try:
            await self.unmute(ctx, offender, moderator=ctx.author, reason=reason)
        except NotMutedException:
            embed=discord.Embed(title="❌ " + self._("Not muted"), description=self._("**{offender}** is not muted.").format(offender=offender), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        except (AttributeError, discord.Forbidden):
            embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._("Unable to unmute user. Check if you have a mute role configured, and if the bot has permissions to remove said role.").format(offender=offender.mention), color=self.bot.errorColor)
            await ctx.send(embed=embed)              
        else:
            if not reason: reason = "No reason specified"
            embed=discord.Embed(title="🔉 " + self._("User unmuted"), description=self._("**{offender}** has unbeen unmuted.\n**Reason:** ```{reason}```").format(offender=offender, reason=reason), color=self.bot.embedGreen)
            await ctx.send(embed=embed)
    

    @commands.command(help="Temporarily mutes a user.", description="Mutes a user for a specified duration. Logs the event if logging is set up.\n\n**Time formatting:**\n`s` or `second(s)`\n`m` or `minute(s)`\n`h` or `hour(s)`\n`d` or `day(s)`\n`w` or `week(s)`\n`M` or `month(s)`\n`Y` or `year(s)`\n\n**Example:** `tempmute @User -d 5minutes -r 'Being naughty'` or `tempmute @User 5d`\n**Note:** If your arguments contain spaces, you must wrap them in quotation marks.", usage="tempmute <user> -d <duration> -r [reason] OR tempmute <user> <duration>")
    @commands.check(has_mod_perms)
    @commands.check(can_mute)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    @mod_punish
    async def tempmute(self, ctx, member:discord.Member, *, args):
        '''
        Temporarily mutes a memeber, assigning them a Muted role defined in the settings
        Uses userlog extension to log the event and timers to count the time & unmute on schedule.
        '''
        await ctx.channel.trigger_typing()
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
            muted_until = await self.mute(ctx, member, ctx.author, dur, reason)
        except AlreadyMutedException as error:
            embed=discord.Embed(title="❌ " + self._("Already muted"), description=self._("**{offender}** is already muted.").format(offender=member), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        except ValueError:
            embed=discord.Embed(title="❌ " + self.bot.errorDataTitle, description=self._("Your entered timeformat is invalid. Type `{prefix}help tempmute` for more information.").format(prefix=ctx.prefix), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        except (AttributeError, discord.Forbidden):
            embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._("Unable to mute user. Check if you have a mute role configured, and if the bot has permissions to add said role.").format(offender=member.mention), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        except ModuleNotFoundError as error:
            embed=discord.Embed(title="❌ " + self._("Muting failed"), description=self._("This function requires an extension that is not enabled.\n**Error:** ```{error}```").format(error=error), color=self.bot.errorColor)
            await ctx.send(embed=embed)    
        else:
            embed=discord.Embed(title="🔇 " + self._("User muted"), description=self._("**{offender}** has been muted until `{duration} (UTC)`.\n**Reason:** ```{reason}```").format(offender=member, duration=muted_until, reason=reason), color=self.bot.embedGreen)
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
    

    @commands.command(name="ban", help="Bans a user.", description="Bans a user with an optional reason. Deletes the last 7 days worth of messages from the user.", usage="ban <user> [reason]")
    @commands.check(has_mod_perms)
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    @mod_punish
    async def ban_cmd(self, ctx, member:discord.Member, *, reason:str=None):
        '''
        Bans a member from the server.
        Banner must be priviliged and have ban_members perms.
        '''
        await ctx.channel.trigger_typing()

        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{ctx.author} ({ctx.author.id}): \nReason: {reason}"
        else:
            raw_reason = reason
            reason = f"{ctx.author} ({ctx.author.id}): \nNo reason provided"

        try:
            await ctx.guild.ban(member, reason=reason, delete_message_days=1)
            if raw_reason:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.\n**Reason:** ```{raw_reason}```").format(offender=member, raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** User has been banned.").format(offender=member),color=self.bot.errorColor)
                await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("This user cannot be banned."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Ban failed"), description=self._("Ban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return


    @commands.command(name="unban", help="Unbans a user.", description="Unbans a user with an optional reason. Deletes the last 7 days worth of messages from the user.", usage="unban <user> [reason]")
    @commands.check(has_mod_perms)
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    @mod_command
    async def unban_cmd(self, ctx, offender:discord.User, *, reason:str=None):
        '''
        Unbans a member from the server.
        Unbanner must be priviliged and have ban_members perms.
        '''
        await ctx.channel.trigger_typing()
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{ctx.author} ({ctx.author.id}): \n{reason}"
        else:
            raw_reason = reason
            reason = f"{ctx.author} ({ctx.author.id}): \nNo reason provided"
        try:
            await ctx.guild.unban(offender, reason=reason)
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User unbanned"), description=self._("**{offender}** has been unbanned.\n**Reason:** ```{raw_reason}```").format(offender=offender, raw_reason=raw_reason),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User unbanned"), description=self._("**{offender}** has been unbanned.").format(offender=offender),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Unban failed"), description=self._("Unban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
    

    @commands.command(name="tempban", help="Temporarily bans a user.", description="Temporarily bans a user for the duration specified. Deletes the last 7 days worth of messages from the user.\n\n**Time formatting:**\n`s` or `second(s)`\n`m` or `minute(s)`\n`h` or `hour(s)`\n`d` or `day(s)`\n`w` or `week(s)`\n`M` or `month(s)`\n`Y` or `year(s)`\n\n**Example:** `tempban @User -d 5minutes -r 'Being naughty'` or `tempban @User 5d`\n**Note:** If your arguments contain spaces, you must wrap them in quotation marks.", usage="tempban <user> -d <duration> -r [reason] OR tempban <user> <duration>")
    @commands.check(has_mod_perms)
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    @mod_punish
    async def tempban_cmd(self, ctx, member:discord.Member, *, args):
        '''
        Temporarily bans a member from the server.
        Requires timers extension to work.
        Banner must be priviliged and have ban_members perms.
        '''
        await ctx.channel.trigger_typing()
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

        raw_reason = reason #Shown to the public
        if reason:
            reason = f"{ctx.author} ({ctx.author.id}): \n{reason}"
        else:
            reason = f"{ctx.author} ({ctx.author.id}): \nNo reason provided"
        
        try:

            await self.ban(ctx, member, ctx.author, dur, reason)
            if raw_reason:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.\n**Reason:** ```{raw_reason}```").format(offender=member, raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.").format(offender=member),color=self.bot.errorColor)
                await ctx.send(embed=embed)

        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the ban, or this user cannot be banned."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Tempban failed"), description=self._("Tempban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return

    @commands.command(help="Mass-bans a list of IDs specified.", description="Mass-bans a list of userIDs specified. Reason goes first, then a list of user IDs seperated by spaces.", usage="massban <reason> <userIDs>")
    @commands.check(has_mod_perms)
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    @commands.cooldown(1, 60, type=commands.BucketType.guild)
    @mod_command #Does not follow punish formula
    async def massban(self, ctx, reason:str, *, user_ids:str):
        '''
        Mass-ban takes a list of IDs seperated by spaces,
        and then attempts to ban each user with the specified reason,
        then communicates the results to the invoker.
        '''

        failed = 0
        errors = [] #Contains error messages in case of any

        user_ids = user_ids.strip().split(" ")
        user_ids_conv = []
        for userid in user_ids:
            try:
                user_ids_conv.append(int(userid))
            except ValueError:
                failed += 1
                if " - An invalid, non-numerical userID was provided." not in errors:
                    errors.append(" - An invalid, non-numerical userID was provided.")

        await ctx.channel.trigger_typing() #Long operation, so typing is triggered
        
        for i, userid in enumerate(user_ids_conv):

            if i < 100:
                try:
                    member = ctx.guild.get_member(userid)
                    await ctx.guild.ban(member, reason=f"Mass-banned by {ctx.author} ({ctx.author.id}): \n{reason}")
                except:
                    failed += 1
                    if " - Error banning a user, userID is invalid or user is no longer member of the server." not in errors:
                        errors.append(" - Error banning a user, userID is invalid or user is no longer member of the server.")
            else:
                failed += 1
                if " - Exceeded maximum amount (100) of users bannable by this command." not in errors:
                    errors.append(" - Exceeded maximum amount (100) of users bannable by this command.")
        
        if failed == 0:
            embed = discord.Embed(title="🔨 " + self._("Massban successful"), description=self._("Successfully banned **{amount}** users.\n**Reason:** ```{reason}```").format(amount=len(user_ids_conv), reason=reason),color=self.bot.embedGreen)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="🔨 " + self._("Massban concluded with failures"), description=self._("Banned **{amount}/{total}** users.\n**Reason:** ```{reason}```").format(amount=len(user_ids)-failed, total=len(user_ids), reason=reason),color=self.bot.warnColor)
            await ctx.send(embed=embed)
            embed = discord.Embed(title="🔨 " + self._("Failures encountered:"), description=self._("Some errors were encountered during the mass-ban: \n```{errors}```").format(errors="\n".join(errors)),color=self.bot.warnColor)
            await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_tempban_timer_complete(self, timer):
        guild = self.bot.get_guild(timer.guild_id)
        if guild:
            try:
                offender = await self.bot.fetch_user(timer.user_id)
                await guild.unban(offender, reason="User unbanned: Tempban expired")
            except:
                return

    @commands.command(help="Softbans a user.", description="Bans a user then immediately unbans them, which means it will erase all messages from the user in the specified range.", usage="softban <user> [days-to-delete] [reason]")
    @commands.check(has_mod_perms)
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    @mod_punish
    async def softban(self, ctx, member:discord.Member, deldays:int=1, *, reason:str=None):
        '''
        Soft-bans a user, by banning and un-banning them.
        Removes messages from the last x days.
        Banner must be priviliged and have kick_members permissions.
        Bot must have ban_members permissions.
        '''
        raw_reason = reason #Shown to the public
        await ctx.channel.trigger_typing()
        if reason:
            reason = f"[SOFTBAN] {ctx.author} ({ctx.author.id}): \n{reason}"
        else:
            reason = f"[SOFTBAN] {ctx.author} ({ctx.author.id}): \nNo reason provided"

        try:
            deldays = int(deldays)
            await ctx.guild.ban(member, reason=reason, days_to_delete=deldays)
            await ctx.guild.unban(member, reason="Automatic unban by softban command")
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User soft-banned"), description=self._("**{offender}** has been soft-banned.\n**Reason:** {raw_reason}").format(offender=member, raw_reason=raw_reason),color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User soft-banned"), description=self._("**{offender}** has been soft-banned.").format(offender=member),color=self.bot.errorColor)
                await ctx.send(embed=embed)
        except ValueError:
            embed = discord.Embed(title=self.bot.errorDataTitle, description=self._("Invalid data for argument `days-to-delete` See `{prefix}help softban` for command usage.").format(prefix=ctx.prefix),color=self.bot.errorColor)
            return await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the ban, or this user cannot be banned."),color=self.bot.errorColor)
            return await ctx.send(embed=embed)
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Ban failed"), description=self._("Ban failed, please try again later."),color=self.bot.errorColor)
            return await ctx.send(embed=embed)

    
    @commands.command(help="Kicks a user.", description="Kicks a user with an optional reason. Deletes the last 7 days worth of messages from the user.", usage="kick <user> [reason]")
    @commands.check(has_mod_perms)
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    @mod_punish
    async def kick(self, ctx, member:discord.Member, *, reason:str=None):
        await ctx.channel.trigger_typing()
        if reason != None:
            raw_reason = reason #Shown to the public
            reason = f"{ctx.author} ({ctx.author.id}): \n{reason}"
        else:
            raw_reason = reason
            reason = f"{ctx.author} ({ctx.author.id}): \nNo reason provided"
        
        try:
            await ctx.guild.kick(member, reason=reason)
            if raw_reason:
                embed = discord.Embed(title="✅ " + self._("User kicked"), description=self._("**{offender}** has been kicked.\n**Reason:** ```{raw_reason}```").format(offender=member, raw_reason=raw_reason),color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(title="✅ " + self._("User kicked"), description=self._("**{offender}** has been kicked.").format(offender=member),color=self.bot.embedGreen)
                await ctx.send(embed=embed)

        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Kick failed"), description=self._("Kick failed, please try again later."),color=self.bot.errorColor)
            return await ctx.send(embed=embed)
    
    @commands.command(aliases=["bulkdelete", "bulkdel"], help="Deletes multiple messages at once.", description="Deletes up to 100 messages at once. Defaults to 5 messages. You can optionally specify a user whose messages will be purged.", usage="purge [limit] [user]")
    @commands.check(has_mod_perms)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    @mod_command
    async def purge(self, ctx, limit=5, member:discord.Member=None):
        if limit > 100:
            embed = discord.Embed(title="❌ " + self._("Limit too high"), description=self._("You cannot remove more than **100** messages."),color=self.bot.errorColor)
            await ctx.send(embed=embed, delete_after=20.0)
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
    @commands.check(has_mod_perms)
    @commands.bot_has_permissions(manage_messages=True)
    @mod_command
    async def clear(self, ctx, limit=5):
        if limit > 50:
            embed = discord.Embed(title="❌ " + self._("Limit too high"), description=self._("You cannot clear more than **50** messages."),color=self.bot.errorColor)
            await ctx.send(embed=embed, delete_after=20.0)
            return

        await ctx.channel.trigger_typing()
        def check(message):
            return message.author.id == self.bot.user.id

        cleared = await ctx.channel.purge(limit=limit, check=check)
        embed = discord.Embed(title="🗑️ " + self._("Messages cleared"), description=self._("**{count}** bot messages have been removed.").format(count=len(cleared)), color=self.bot.errorColor)
        await ctx.send(embed=embed, delete_after=20.0)


    async def automod_punish(self, ctx, offender:discord.Member, offense:str, reason:str):
        '''
        Decides and does the punishment set for the specified offense in the dashboard.
        '''

        valid_offenses = ["invites", "spam", "mass_mentions", "zalgo", "attach_spam", "link_spam", "escalate"]
        if offense not in valid_offenses:
            raise ValueError(f"{offense} is not a valid offense-type. Valid types are: {', '.join(valid_offenses)}")

        bot_perms = ctx.channel.permissions_for(ctx.guild.me)
        if not bot_perms.ban_members or not bot_perms.manage_roles or not bot_perms.manage_messages or not bot_perms.kick_members:
            return

        if await is_automod_excluded(ctx) or await has_mod_perms(ctx):
            return

        policies = await self.get_policies(ctx.guild.id)
        policy = policies[offense] #This will decide the type of punishment

        if policy.startswith("temp") or policy not in ["delete", "warn", "warn+delete", "escalate"]: #Get temporary punishment duration in minutes
            async with self.bot.pool.acquire() as con:
                result = await con.fetch('''SELECT * FROM mod_config WHERE guild_id = $1''', ctx.guild.id)
                temp_dur = result[0].get("temp_dur") if result and len(result) > 0 else 15
                dm_users_on_punish = result[0].get("dm_users_on_punish") if result and len(result) > 0 else False

        if policy == "disabled":
            return

        elif  policy == "delete":
            await ctx.message.delete()

        elif policy == "warn":
            await self.warn(ctx, offender, ctx.guild.me, reason=f"Warned by auto-moderator for {reason}.")

        elif policy == "warn+delete":
            await ctx.message.delete()
            await self.warn(ctx, offender, ctx.guild.me, reason=f"Warned by auto-moderator for {reason}.")
        
        elif policy == "escalate":
            await ctx.message.delete()
            bucket = self.escalate_cd_mapping.get_bucket(ctx.message)
            bucket_prewarn = self.escalate_prewarn_cd_mapping.get_bucket(ctx.message)

            if bucket.update_rate_limit():
                #If user continues ignoring warnings
                await self.automod_punish(ctx, offender, offense="escalate", reason="previous offenses")

            elif bucket_prewarn.update_rate_limit():
                #Issue warning after notice
                await self.warn(ctx, offender, ctx.guild.me, reason=f"Warned by auto-moderator for previous offenses.")
            else:
                #Issue a notice, not a formal warning first
                notices = {
                    "invites": "posting discord invites",
                    "mass_mentions": "mass mentioning users",
                    "zalgo": "using zalgo in your messages",
                    "attach_spam": "spamming attachments",
                    "link_spam": "spamming links",
                }

                embed=discord.Embed(title="💬 Auto-Moderation Notice", description=f"**{offender}**, please refrain from {notices[offense]}!", color=self.bot.warnColor)
                await ctx.send(content=offender.mention, embed=embed)


        elif policy == "tempmute":
            await self.mute(ctx, offender, ctx.guild.me, duration=f"{temp_dur} minutes", reason=f"Muted by auto-moderator for {reason}.")
            embed=discord.Embed(title="🔇 User muted", description="**{offender}** has been muted for **{temp_dur}** minutes.\n**Reason:**```Muted by auto-moderator for {reason}.```".format(offender=offender, temp_dur=temp_dur, reason=reason), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        
        elif policy == "kick":
            await self.kick(ctx, offender, ctx.guild.me, reason=f"Kicked by auto-moderator for {reason}.")
        
        elif policy == "softban":
            await self.ban(ctx, offender, ctx.guild.me, None, True, reason=f"Soft-banned by auto-moderator for {reason}.")
        
        elif policy == "tempban":
            await self.ban(ctx, offender, ctx.guild.me, f"{temp_dur} minutes", False, reason=f"Temp-banned by auto-moderator for {reason}.")

        elif policy == "permaban":
            await self.ban(ctx, offender, ctx.guild.me, None, False, reason=f"Permanently banned by auto-moderator for {reason}.")

                

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
        spam_exceeded = bucket.update_rate_limit()
        if spam_exceeded: #If user exceeded spam limits
            '''General Spam'''

            db_user = await self.bot.global_config.get_user(message.author.id, message.guild.id)
            ctx = await self.bot.get_context(message)

            if not db_user.is_muted and not message.author.bot:
                await self.automod_punish(ctx, offender=message.author, offense="spam", reason="spam")
        
        mentions = sum(member.id != message.author.id and not member.bot for member in message.mentions)
        if mentions > 7:
            '''Mention Spams'''
            await self.automod_punish(ctx, offender=message.author, offense="mass_mentions", reason=f"spamming {mentions} mentions in a single message")
  
        else: #If the obvious stuff didn't work
            '''Discord Invites, Links, Attachments & Zalgo'''
            invite_regex = re.compile(r"(?:https?://)?discord(?:app)?\.(?:com/invite|gg)/[a-zA-Z0-9]+/?")
            link_regex = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")
            invite_matches = invite_regex.findall(message.content)
            link_matches = link_regex.findall(message.content)
            ctx = await self.bot.get_context(message)
            if invite_matches:
                await self.automod_punish(ctx, offender=message.author, offense="invites", reason="posting Discord invites")
            elif link_matches:
                if len(link_matches) > 7:
                    await self.automod_punish(ctx, offender=message.author, offense="link_spam", reason="having too many links in a single message")
                else:
                    bucket = self.link_spam_cd_mapping.get_bucket(message)
                    if bucket.update_rate_limit():
                        await self.automod_punish(ctx, offender=message.author, offense="link_spam", reason="posting links too quickly")
            elif len(message.attachments) > 0:
                bucket = self.attach_spam_cd_mapping.get_bucket(message)
                if bucket.update_rate_limit():
                    await self.automod_punish(ctx, offender=message.author, offense="attach_spam", reason="posting images/attachments too quickly")
            else: #Check zalgo
                count = 0
                for char in message.content:
                    if unicodedata.combining(char):
                        count += 1
                        if count > 4:
                            await self.automod_punish(ctx, offender=message.author, offense="zalgo", reason="using zalgo text")
                            break
                    else:
                        count = 0




                            

    

def setup(bot):
    logging.info("Adding cog: Moderation...")
    bot.add_cog(Moderation(bot))
