import argparse
import asyncio
import functools
import json
import logging
import re
import shlex
from dataclasses import dataclass
from typing import TypeVar, Union

import discord
from discord.ext import commands

from extensions.utils import components

logger = logging.getLogger(__name__)

async def has_owner(ctx) -> bool:
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_mod_perms(ctx) -> bool:
    return await ctx.bot.custom_checks.has_permissions(ctx, "mod_permitted")

async def can_mute(ctx) -> bool:
    '''A check performed to see if the configuration is correct for muting to be done.'''
    records = await ctx.bot.caching.get(table="mod_config", guild_id=ctx.guild.id)
    if records and records[0]["mute_role_id"]:
        mute_role = ctx.guild.get_role(records[0]["mute_role_id"])
        if mute_role:
            return True
        return False

@dataclass
class ModerationSettings():
    dm_users_on_punish:bool
    clean_up_mod_commands:bool
    mute_role_id:int

def default_mod_settings() -> ModerationSettings:
    return ModerationSettings(
        dm_users_on_punish=True,
        clean_up_mod_commands=False,
        mute_role_id=None
    )

mod_settings_strings = {
    "dm_users_on_punish": "DM users after punishment",
    "clean_up_mod_commands": "Clean up mod commands",
    "mute_role_id": "Mute role"
}


class AlreadyMutedException(Exception):
    '''Raised when trying to mute an already muted user'''
    pass

class NotMutedException(Exception):
    '''Raised when trying to unmute a user who is not muted'''
    pass

class ModConfMainView(components.AuthorOnlyView):
    def __init__(self, ctx, options:dict, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.value = None
        self.options = options
        self.ctx = ctx

        for option in options:
            self.add_item(self.MenuSelectButton(option=option, label=options[option], style=discord.ButtonStyle.blurple))
        self.add_item(self.MenuSelectButton(option="quit", label="Quit", style=discord.ButtonStyle.red))

    class MenuSelectButton(discord.ui.Button):
        def __init__(self, option:str, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.option = option

        async def callback(self, interaction: discord.Interaction):
            self.view.value = self.option
            self.view.stop()

class Moderation(commands.Cog):
    '''All Moderation & Auto-Moderation related functionality'''
    
    def __init__(self, bot):
        
        self.bot = bot
        self._ = self.bot.get_localization('moderation', self.bot.lang)
        self.can_mute = can_mute

    
    async def cog_check(self, ctx) -> bool:
        return await self.bot.custom_checks.module_is_enabled(ctx, "moderation")

    async def get_settings(self, guild_id:int) -> ModerationSettings:
        '''
        Checks for and returns the moderation settings for a given guild.
        '''
        records = await self.bot.caching.get(table="mod_config", guild_id=guild_id)
        if records:
            mod_settings = ModerationSettings(
                dm_users_on_punish=records[0]["dm_users_on_punish"],
                clean_up_mod_commands=records[0]["clean_up_mod_commands"],
                mute_role_id=records[0]["mute_role_id"]
            )
        else:
            mod_settings = default_mod_settings()
        return mod_settings


    def mod_punish(func):
        '''
        Decorates commands that are supposed to punish a user.
        '''

        @functools.wraps(func)
        async def inner(*args, **kwargs):
            self = args[0]
            ctx = args[1]
            user = args[2]
            reason = kwargs["reason"] if "reason" in kwargs.keys() else "No reason provided"

            if ctx.author.id == user.id:
                embed=discord.Embed(title="❌ " + self._("You cannot {pwn} yourself.").format(pwn=ctx.command.name), description=self._("You cannot {pwn} your own account.").format(pwn=ctx.command.name), color=self.bot.errorColor)
                await ctx.send(embed=embed)
                return
            
            if user.bot:
                embed=discord.Embed(title="❌ " + self._("Cannot execute on bots."), description=self._("This command cannot be executed on bots."), color=self.bot.errorColor)
                await ctx.send(embed=embed)
                return
            
            settings = await self.get_settings(ctx.guild.id)
            types_conj = {
            "warn": "warned in",
            "mute": "muted in",
            "tempmute": "muted in",
            "kick": "kicked from",
            "ban": "banned from",
            "softban": "soft-banned from",
            "tempban": "temp-banned from",
            }

            #This is a weird one, but it has to do this before actually
            #punishing the user, because if the user leaves the guild,
            #you can no longer DM them
            if settings.dm_users_on_punish and isinstance(user, discord.Member):
                embed = discord.Embed(title="❗ " + "You have been {pwned} {guild}".format(pwned=types_conj[ctx.command.name], guild=ctx.guild.name), description=self._("You have been {pwned} **{guild}**.\n**Reason:** ```{reason}```").format(pwned=types_conj[ctx.command.name], guild=ctx.guild.name, reason=reason),color=self.bot.errorColor)
                try:
                    await user.send(embed=embed)
                except discord.Forbidden:
                    pass

            if settings.clean_up_mod_commands:
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
            embed=discord.Embed(title="⚠️ " + self._("Warning issued"), description=self._("**{offender}** has been warned by **{moderator}**.").format(offender=member, moderator=moderator), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{member.mention} has been warned by {moderator.mention}.\n**Warns:** {db_user.warns}\n\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        else :
            embed=discord.Embed(title="⚠️ " + self._("Warning issued"), description=self._("**{offender}** has been warned by **{moderator}**.\n**Reason:** ```{reason}```").format(offender=member, moderator=moderator, reason=reason), color=self.bot.warnColor)
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
        if can_mute(ctx):
            db_user = await self.bot.global_config.get_user(member.id, ctx.guild.id)
            if db_user.is_muted:
                raise AlreadyMutedException('This member is already muted.')
            else:
                mute_role_id = 0
                records = await self.bot.caching.get(table="mod_config", guild_id=ctx.guild.id)
                if records and records[0]["mute_role_id"]:
                    mute_role_id = records[0]["mute_role_id"]
                mute_role = ctx.guild.get_role(mute_role_id)
                try:
                    await member.add_roles(mute_role, reason=reason)
                except:
                    raise
                else:
                    db_user.is_muted = True
                    await self.bot.global_config.update_user(db_user)
                    dur = None
                    if duration:
                        try:                   
                            dur = await self.bot.get_cog("Timers").converttime(duration)
                            await self.bot.get_cog("Timers").create_timer(expires=dur[0], event="tempmute", guild_id=ctx.guild.id, user_id=member.id, channel_id=ctx.channel.id)
                        except AttributeError:
                            raise ModuleNotFoundError('timers extension not found')
                    try:
                        if not duration: duration = "Infinite"
                        else: duration = discord.utils.format_dt(dur[0])
                        muteembed=discord.Embed(title="🔇 User muted", description=F"**User:** `{member} ({member.id})`\n**Moderator:** `{moderator} ({moderator.id})`\n**Until:** {duration}\n**Reason:** ```{reason}```", color=self.bot.errorColor)
                        await self.bot.get_cog("Logging").log_elevated(muteembed, ctx.guild.id)
                    except:
                        pass
                    if dur:
                        return dur[0] #Return it if needed to display
        else:
            raise AttributeError("No mute role set.")

    async def unmute(self, ctx, member:discord.Member, moderator:discord.Member, reason:str=None):
        '''
        Handles unmuting a user, if logging is set up, it will log it. Updates database.
        '''
        db_user = await self.bot.global_config.get_user(member.id, ctx.guild.id)
        if not db_user.is_muted:
            raise NotMutedException('This member is not muted.')
        else:
            mute_role_id = 0
            records = await self.bot.caching.get(table="mod_config", guild_id=ctx.guild.id)
            if records and records[0]["mute_role_id"]:
                mute_role_id = records[0]["mute_role_id"]
            mute_role = ctx.guild.get_role(mute_role_id)
            try:
                await member.remove_roles(mute_role)
            except:
                raise
            else:
                db_user.is_muted = False
                await self.bot.global_config.update_user(db_user)
                try:
                    muteembed=discord.Embed(title="🔉 User unmuted", description=F"**User:** `{member} ({member.id})`\n**Moderator:** `{moderator} ({moderator.id})`\n**Reason:** ```{reason}```", color=self.bot.embedGreen)
                    await self.bot.get_cog("Logging").log_elevated(muteembed, ctx.guild.id)
                except:
                    pass

    async def ban(self, ctx, user:Union[discord.User, discord.Member], moderator:discord.Member, duration:str=None, soft:bool=False, days_to_delete:int=1, reason:str=None):
        '''
        Handles the banning of a user, can optionally accept a duration to make it a tempban.
        '''
        if duration and soft:
            raise RuntimeError("Ban type cannot be soft when a duration is specified.")

        if duration:
            try:
                dur = await self.bot.get_cog("Timers").converttime(duration)
                dur = dur[0]
                reason = f"{reason}\nBanned until: {dur} (UTC)"

            except ValueError:
                embed=discord.Embed(title="❌ " + self.bot.errorDataTitle, description=self._("Your entered timeformat is invalid. Type `{prefix}help tempban` for more information.").format(prefix=ctx.prefix), color=self.bot.errorColor)
                return await ctx.send(embed=embed)
                
        if reason:
            raw_reason = reason #Shown to the public
            reason = f"{moderator} ({moderator.id}): \n{reason}"
        else:
            raw_reason = "No reason provided"
            reason = f"{moderator} ({moderator.id}): \nNo reason provided"

        if soft:
            raw_reason = f"[SOFTBAN] {raw_reason}"
        elif duration:
            raw_reason = f"[TEMPBAN] {raw_reason}"

        try:
            await ctx.guild.ban(user, reason=reason, delete_message_days=days_to_delete)
            embed = discord.Embed(title="🔨 " + self._("User banned"), description=self._("**{offender}** has been banned.\n**Reason:** ```{raw_reason}```").format(offender=user, raw_reason=raw_reason),color=self.bot.errorColor)
            await ctx.send(embed=embed)

            if soft:
                await ctx.guild.unban(user, reason="Automatic unban by softban")
            elif duration and dur:
                try:
                    await self.bot.get_cog("Timers").create_timer(expires=dur, event="tempban", guild_id=ctx.guild.id, user_id=user.id, channel_id=ctx.channel.id)
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


    @commands.command(name="moderation", aliases=["mod"], help="Configures moderation.", description="Configures various moderation settings via an interactive menu.")
    @commands.check(has_mod_perms)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
    async def mod_conf_cmd(self, ctx):

        async def show_main_menu(self, message:discord.Message=None):

            options = await self.get_settings(ctx.guild.id)
            options_dict = {}
            embed = discord.Embed(title="Moderation Settings", description="Below you can see the current moderation settings, to change any of them, press the corresponding button!", color=self.bot.embedBlue)
            if not await can_mute(ctx):
                embed.add_field(name="⚠️ Warning!", value="There is **no mute role** set! Without a mute role, muting and tempmuting is unavailable! Please configure one here!", inline=False)

            for field in options.__dataclass_fields__:
                value = getattr(options, field)
                if field == "mute_role_id":
                    mute_role = ctx.guild.get_role(value)
                    if mute_role:
                        value = mute_role.mention
                    else:
                        value = "Not set"

                embed.add_field(name=f"{mod_settings_strings[field]}", value=value, inline=True)
                options_dict[field] = mod_settings_strings[field]

            view = ModConfMainView(ctx, options_dict)
            if not message:
                message = await ctx.send(embed=embed, view=view)
            else:
                await self.bot.maybe_edit(message, embed=embed, view=view)
            
            def check(message):
                return message.author.id == ctx.author.id and  ctx.channel.id == message.channel.id

            await view.wait()
            if view.value == "quit" or not view.value:
                await self.bot.maybe_delete(message)
            elif view.value == "dm_users_on_punish":
                await self.bot.pool.execute('''
                INSERT INTO mod_config (guild_id, dm_users_on_punish)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO
                UPDATE SET dm_users_on_punish = $2''', ctx.guild.id, not options.dm_users_on_punish)
                await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                await show_main_menu(self, message)
            elif view.value == "clean_up_mod_commands":
                await self.bot.pool.execute('''
                INSERT INTO mod_config (guild_id, clean_up_mod_commands)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO
                UPDATE SET clean_up_mod_commands = $2''', ctx.guild.id, not options.clean_up_mod_commands)
                await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                await show_main_menu(self, message)
            elif view.value == "mute_role_id":
                embed = discord.Embed(title=f"Configuring mute role", description="Please enter a mention, ID, or name of the role you want to use as a mute role! This role should **not be able** to send messages or add reactions in any channels for muting to work correctly!", color=self.bot.embedBlue)
                await self.bot.maybe_edit(message, embed=embed, view=None)

                try:
                    input = await self.bot.wait_for('message', check=check, timeout=180)
                except asyncio.TimeoutError:
                    await self.bot.maybe_delete(message)
                else:
                    try:
                        mute_role = await commands.RoleConverter().convert(ctx, input.content)

                        await self.bot.pool.execute('''
                        INSERT INTO mod_config (guild_id, mute_role_id)
                        VALUES ($1, $2)
                        ON CONFLICT (guild_id) DO
                        UPDATE SET mute_role_id = $2''', ctx.guild.id, mute_role.id)
                        await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)

                        await self.bot.maybe_delete(message)
                        await show_main_menu(self, message)

                    except commands.RoleNotFound:
                        view = components.BackButtonView(ctx)
                        embed = discord.Embed(title="❌ Role not found", description="Unable to find role! Please make sure what you entered is correct.", color=self.bot.errorColor)
                        await self.bot.maybe_edit(message, view=view, embed=embed)
                        await self.bot.maybe_delete(input)

                        await view.wait()
                        if view.value == "back":
                            await show_main_menu(self, message)
                        else:
                            await self.bot.maybe_delete(message)

        await show_main_menu(self)


    #Warn a user & print it to logs, needs logs to be set up
    @commands.group(name="warn", help="Warns a user. Subcommands allow you to clear warnings.", aliases=["bonk"], description="Warns the user and logs it.", usage="warn <user> [reason]", invoke_without_command=True, case_insensitive=True)
    @commands.check(has_mod_perms)
    @commands.guild_only()
    @mod_punish
    async def warn_cmd(self, ctx, member:discord.Member, *, reason:str=None):
        '''
        Warn command. Person warning must be in permitted roles.
        '''
        await ctx.channel.trigger_typing()
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
        db_user.warns = 0
        await self.bot.global_config.update_user(db_user)
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
        db_user = await self.bot.global_config.get_user(member.id, member.guild.id) #Ouch
        if db_user.is_muted == True:
            try:
                mute_role_id = 0
                record = await self.bot.caching.get(table="mod_config", guild_id=member.guild.id)
                if record and record[0]["mute_role_id"]:
                    mute_role = member.guild.get_role(record[0]["mute_role_id"])
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
            embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._(f"Unable to mute user. Check if you have a mute role configured, and if the bot has permissions to add said role. Use `{ctx.prefix}moderation` to configure this.").format(offender=member.mention), color=self.bot.errorColor)
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
            embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._(f"Unable to unmute user. Check if you have a mute role configured, and if the bot has permissions to add said role. Use `{ctx.prefix}moderation` to configure this.").format(offender=offender.mention), color=self.bot.errorColor)
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
            embed=discord.Embed(title="❌ " + self._("Mute role error"), description=self._(f"Unable to mute user. Check if you have a mute role configured, and if the bot has permissions to add said role. Use `{ctx.prefix}moderation` to configure this.").format(offender=member.mention), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        except ModuleNotFoundError as error:
            embed=discord.Embed(title="❌ " + self._("Muting failed"), description=self._("This function requires an extension that is not enabled.\n**Error:** ```{error}```").format(error=error), color=self.bot.errorColor)
            await ctx.send(embed=embed)    
        else:
            embed=discord.Embed(title="🔇 " + self._("User muted"), description=self._("**{offender}** has been muted until {duration}.\n**Reason:** ```{reason}```").format(offender=member, duration=discord.utils.format_dt(muted_until), reason=reason), color=self.bot.embedGreen)
            await ctx.send(embed=embed)
    

    @commands.Cog.listener()
    async def on_tempmute_timer_complete(self, timer):
        guild = self.bot.get_guild(timer.guild_id)
        db_user = await self.bot.global_config.get_user(timer.user_id, timer.guild_id)
        is_muted = db_user.is_muted
        if not is_muted:
            return
        db_user.is_muted = False
        await self.bot.global_config.update_user(db_user) #Update this here so if the user comes back, they are not perma-muted :pepeLaugh:
        if guild.get_member(timer.user_id) is not None: #Check if the user is still in the guild
            mute_role_id = 0
            records = await self.bot.caching.get(table="mod_config", guild_id=timer.guild_id)
            if records and records[0]["mute_role_id"]:
                mute_role_id = records[0]["mute_role_id"]
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
    async def ban_cmd(self, ctx, user:discord.User, *, reason:str=None):
        '''
        Bans a member from the server.
        Banner must be priviliged and have ban_members perms.
        '''
        await ctx.channel.trigger_typing()

        try:
            await self.ban(ctx, user, ctx.author, duration=None, soft=False, reason=reason)
        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("This user cannot be banned."),color=self.bot.errorColor)
            await ctx.send(embed=embed); return

        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Ban failed"), description=self._("Ban failed, please try again later."),color=self.bot.errorColor)
            await ctx.send(embed=embed); return


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
        
        try:
            await self.ban(ctx, member, ctx.author, duration=dur, reason=reason)

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
    async def softban(self, ctx, member:discord.Member, days_to_delete:int=1, *, reason:str=None):
        '''
        Soft-bans a user, by banning and un-banning them.
        Removes messages from the last x days.
        Banner must be priviliged and have kick_members permissions.
        Bot must have ban_members permissions.
        '''
        raw_reason = reason #Shown to the public
        await ctx.channel.trigger_typing()

        try:
            days_to_delete = int(days_to_delete)
            await self.ban(ctx, member, ctx.author, reason=reason, soft=True, days_to_delete=days_to_delete)

        except discord.Forbidden:
            embed = discord.Embed(title="❌ " + self._("Bot has insufficient permissions"), description=self._("The bot has insufficient permissions to perform the ban, or this user cannot be banned."),color=self.bot.errorColor)
            return await ctx.send(embed=embed)
        except discord.HTTPException:
            embed = discord.Embed(title="❌ " + self._("Ban failed"), description=self._("Ban failed, please try again later."),color=self.bot.errorColor)
            return await ctx.send(embed=embed)

    
    @commands.command(help="Kicks a user.", description="Kicks a user from the server with an optional reason.", usage="kick <user> [reason]")
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
    
    @commands.command(aliases=['clr', 'cleanup'], help="Cleans up the bot's messages.", description="Delete up to 50 of the bot's own responses in this channel. Defaults to 5.", usage="clear [limit]")
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

    #Returns basically all information we know about a given member of this guild.
    @commands.command(help="Get information about a user.", description="Provides information about a specified user. If they are in the server, more detailed information will be provided.\n\n__Note:__ To receive information about users outside this server, you must use their ID.", usage=f"whois <userID|userMention|userName>")
    @commands.check(has_mod_perms)
    @commands.guild_only()
    async def whois(self, ctx, *, user : discord.User) :


        if user in ctx.guild.members:
            db_user = await self.bot.global_config.get_user(user.id, ctx.guild.id)
            member = ctx.guild.get_member(user.id)
            rolelist = [role.mention for role in member.roles]
            rolelist.pop(0)
            roleformatted = ", ".join(rolelist) if len(rolelist) > 0 else "`-`"
            embed=discord.Embed(title=f"User information: {member.name}", description=f"""Username: `{member.name}`
            Nickname: `{member.display_name if member.display_name != member.name else "-"}`
            User ID: `{member.id}`
            Bot: `{member.bot}`
            Account creation date: {discord.utils.format_dt(member.created_at)} ({discord.utils.format_dt(member.created_at, style='R')})
            Join date: {discord.utils.format_dt(member.joined_at)} ({discord.utils.format_dt(member.joined_at, style='R')})
            Warns: `{db_user.warns}`
            Muted: `{db_user.is_muted}`
            Flags: `{db_user.flags}`
            Notes: `{db_user.notes}`
            Roles: {roleformatted}""", color=member.colour)
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)

        else: #Retrieve limited information about the user if they are not in the guild
            embed=discord.Embed(title=f"User information: {user.name}", description=f"""Username: `{user}`
            Nickname: `-` 
            User ID: `{user.id}` 
            Status: `-` 
            Bot: `{user.bot}` 
            Account creation date: {discord.utils.format_dt(user.created_at)} ({discord.utils.format_dt(user.created_at, style='R')})
            Join date: `-`
            Roles: `-`
            *Note: This user is not a member of this server*""", color=self.bot.embedBlue)
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)

        if await self.bot.is_owner(ctx.author):
            records = await self.bot.caching.get(table="blacklist", guild_id=0, user_id=user.id)
            is_blacklisted = True if records and records[0]["user_id"] == user.id else False
            embed.description = f"{embed.description}\nBlacklisted: `{is_blacklisted}`"

        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar.url)
        await ctx.channel.send(embed=embed)




def setup(bot):
    logger.info("Adding cog: Moderation...")
    bot.add_cog(Moderation(bot))
