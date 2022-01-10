import asyncio
import datetime
import gettext
import logging
import os
import sys
import traceback
from difflib import get_close_matches
from itertools import chain

import asyncpg
import db_backup
import discord
from discord.ext import commands, ipc, tasks
from extensions.utils import cache, context

from classes.checks import CustomChecks
from classes.config_handler import ConfigHandler


async def get_prefix(bot, message):
    """
    Gets custom prefix for the current guild
    """
    if message.guild is None:
        return bot.DEFAULT_PREFIX
    else:
        records = await bot.caching.get(table="global_config", guild_id=message.guild.id)
        if records:
            prefixes = records[0]["prefix"]
            if prefixes and len(prefixes) > 0:
                return prefixes
            else:
                return bot.DEFAULT_PREFIX
        else:
            return bot.DEFAULT_PREFIX


class SnedBot(commands.Bot):
    def __init__(self, config):

        # Invoking super
        allowed_mentions = discord.AllowedMentions(everyone=False, users=True, roles=True, replied_user=True)
        activity = discord.Activity(name="@Sned", type=discord.ActivityType.listening)
        # Disabled intents: presences, typing, integrations, webhooks, voice_states
        intents = discord.Intents(
            guilds=True,
            members=True,
            bans=True,
            emojis=True,
            messages=True,
            invites=True,
            reactions=True,
        )
        super().__init__(
            command_prefix=get_prefix,
            allowed_mentions=allowed_mentions,
            intents=intents,
            case_insensitive=True,
            activity=activity,
            max_messages=10000,
        )

        # Bot vars
        self.config = config
        self.caching = cache.Caching(self)
        self.BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        self.DEFAULT_PREFIX = "sn "
        self.current_version = "Deprecated"
        self.lang = "en"  # DEPRECATED
        self.skip_db_backup = True  # Set to True to skip the next daily db backup

        self.config.pop("token")

        # IPC Server
        if self.config["ipc_secret"] and self.config["ipc_secret"] != "":
            self.ipc = ipc.Server(
                self,
                host="0.0.0.0",
                port=8765,
                secret_key=config["ipc_secret"],
                do_multicast=False,
            )

        # Experimental Debug mode
        self.EXPERIMENTAL = self.config["experimental"]
        if self.EXPERIMENTAL == True:
            self.DEFAULT_PREFIX = "snx "
            self.debug_guilds = [self.config["home_guild"] if isinstance(self.config["home_guild"], int) else None]
            logging.basicConfig(level=logging.INFO)
            DB_NAME = "sned_exp"
        else:
            logging.basicConfig(level=logging.INFO)
            DB_NAME = "sned"

        # Database
        self.dsn = self.config["postgres_dsn"].format(db_name=DB_NAME)
        self.pool = self.loop.run_until_complete(asyncpg.create_pool(dsn=self.dsn))

        # Whitelists
        self.whitelisted_guilds = [
            372128553031958529,
            627876365223591976,
            818223666143690783,
            836248845268680785,
        ]

        # Command invoke cooldown mapping
        self.cmd_cd_mapping = commands.CooldownMapping.from_cooldown(10, 10, commands.BucketType.channel)

        # Additional modules
        self.global_config = ConfigHandler(self)
        self.custom_checks = CustomChecks(self)

        # Color scheme
        self.error_color = 0xFF0000
        self.warn_color = 0xFFCC4D
        self.embed_blue = 0x009DFF
        self.embed_green = 0x77B255
        self.unknown_color = 0xBE1931
        self.misc_color = 0xC2C2C2

        self.loop.create_task(self.startup())

    async def on_ready(self):
        logging.info("Connected to Discord!")

    async def on_ipc_error(self, endpoint, error):
        logging.error(f"{endpoint} raised {error}")

    async def startup(self):
        """
        Gets executed on first start of the bot, sets up the prefix cache
        """
        await self.wait_until_ready()
        self.uptime = discord.utils.utcnow()

        logging.info(f"Initialized as {self.user}")

        if self.EXPERIMENTAL == True:
            logging.warning("\n--------------\nExperimental mode is enabled!\n--------------")
            cogs = await self.current_cogs()
            logging.info(f"Cogs loaded: {', '.join(cogs)}")

        # Insert all guilds the bot is member of into the db global config on startup
        async with self.pool.acquire() as con:
            for guild in self.guilds:
                await con.execute(
                    """
                INSERT INTO global_config (guild_id) VALUES ($1)
                ON CONFLICT (guild_id) DO NOTHING""",
                    guild.id,
                )
        # Start daily database backup task
        await self.backup_bot_db.start()

    def get_localization(self, extension_name: str, lang: str):
        """
        DEPRECATED
        Installs the proper localization for a given extension
        """
        lang = "en"
        _ = gettext.gettext
        return _

    async def current_cogs(self):
        """
        Simple function that gets all currently loaded cog/extension names
        """
        cogs = []
        for cog_name, cog_cls in self.cogs.items():  # pylint: disable=<unused-variable>
            cogs.append(cog_name)
        return cogs

    async def process_commands(self, message):
        """Inject custom context"""

        ctx = await self.get_context(message, cls=context.Context)

        if message.author.bot:
            return

        records = await self.caching.get(table="blacklist", guild_id=0, user_id=ctx.author.id)
        is_blacklisted = True if records and records[0]["user_id"] == ctx.author.id else False

        if is_blacklisted:
            return

        await self.invoke(ctx)

    async def on_message(self, message):
        """Catch bot mentions & implement limts"""

        if self.is_ready() and self.caching.is_ready:
            bucket = self.cmd_cd_mapping.get_bucket(message)
            retry_after = bucket.update_rate_limit()
            if not retry_after and len(message.content) < 1500:  # If not ratelimited
                # Also limits message length to prevent errors originating from insane message
                # length (Thanks Nitro :) )
                mentions = [f"<@{self.user.id}>", f"<@!{self.user.id}>"]
                if message.content in mentions:
                    records = await self.caching.get(table="global_config", guild_id=message.guild.id)
                    if not records:
                        prefix = [self.DEFAULT_PREFIX]
                    else:
                        prefix = (
                            records[0]["prefix"]
                            if records[0]["prefix"] and len(records[0]["prefix"]) > 0
                            else [self.DEFAULT_PREFIX]
                        )
                    embed = discord.Embed(
                        title="Beep Boop!",
                        description="My prefixes on this server are the following: `{prefix}` \nUse the command `{prefix_0}help` to see what I can do!".format(
                            prefix="`, `".join(prefix), prefix_0=prefix[0]
                        ),
                        color=0xFEC01D,
                    )
                    embed.set_thumbnail(url=self.user.avatar.url)
                    await message.reply(embed=embed)

                await self.process_commands(message)
            else:
                pass  # Ignore requests that would exceed rate-limits

    async def on_message_edit(self, before, after):
        """Register message edits as possible command source"""
        if self.is_ready() and self.caching.is_ready:
            if before.content != after.content:
                await self.process_commands(after)

    async def on_command(self, ctx):
        logging.info(f"{ctx.author} called command {ctx.message.content} in guild {ctx.guild.id}")

    async def on_guild_join(self, guild):
        """Generate guild entry for DB"""

        await self.pool.execute("INSERT INTO global_config (guild_id) VALUES ($1)", guild.id)
        if guild.system_channel is not None:
            try:
                embed = discord.Embed(
                    title="Beep Boop!",
                    description="I have been summoned to this server. Use `{prefix}help` to see what I can do!".format(
                        prefix=self.DEFAULT_PREFIX
                    ),
                    color=0xFEC01D,
                )
                embed.set_thumbnail(url=self.user.avatar.url)
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                pass
        logging.info(f"Bot has been added to new guild {guild.id}.")

    async def on_guild_remove(self, guild):
        """
        Erase all settings for this guild on removal to keep the db tidy.
        The reason this does not use GlobalConfig.deletedata() is to not recreate the entry for the guild
        """

        await self.pool.execute("""DELETE FROM global_config WHERE guild_id = $1""", guild.id)
        await self.caching.wipe(guild.id)
        logging.info(f"Bot has been removed from guild {guild.id}, correlating data erased.")

    async def on_error(self, event_method: str, *args, **kwargs):
        """
        Global Error Handler

        Prints all exceptions and also tries to sends them to the specified error channel, if any.
        """

        print(f"Ignoring exception in {event_method}", file=sys.stderr)
        error_str = traceback.format_exc()
        print(error_str)
        await self.get_cog("HomeGuild").log_error(error_str, event_method=event_method)

    async def on_command_error(self, ctx, error):
        """
        Global Command Error Handler

        Generic error handling. Will catch all otherwise not handled errors
        """

        if isinstance(error, commands.CheckFailure):
            logging.info(f"{ctx.author} tried calling a command but did not meet checks.")
            if isinstance(error, commands.BotMissingPermissions):
                embed = discord.Embed(
                    title="❌ Bot missing permissions",
                    description="The bot requires additional permissions to execute this command.\n**Error:**```{error}```".format(
                        error=error
                    ),
                    color=self.error_color,
                )
                embed = self.add_embed_footer(ctx, embed)
                return await ctx.send(embed=embed)
            return

        elif isinstance(error, commands.CommandInvokeError) and isinstance(
            error.original, asyncio.exceptions.TimeoutError
        ):
            embed = discord.Embed(
                title=self.errorTimeoutTitle,
                description=self.errorTimeoutDesc,
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandNotFound):
            """
            Command name suggestions
            """

            logging.info(
                f"{ctx.author} tried calling a command in {ctx.guild.id} but the command was not found. ({ctx.message.content})"
            )

            cmd = ctx.invoked_with.lower()

            cmds = [cmd.qualified_name for cmd in self.commands if not cmd.hidden]
            allAliases = [cmd.aliases for cmd in self.commands if not cmd.hidden]
            aliases = list(chain(*allAliases))

            matches = get_close_matches(cmd, cmds)
            aliasmatches = get_close_matches(cmd, aliases)

            if len(matches) > 0:
                embed = discord.Embed(
                    title="❓ Unknown command!",
                    description=f"Did you mean `{ctx.prefix}{matches[0]}`?",
                    color=self.unknown_color,
                )
                embed = self.add_embed_footer(ctx, embed)
                return await ctx.send(embed=embed)
            elif len(aliasmatches) > 0:
                embed = discord.Embed(
                    title="❓ Unknown command!",
                    description=f"Did you mean `{ctx.prefix}{matches[0]}`?",
                    color=self.unknown_color,
                )
                embed = self.add_embed_footer(ctx, embed)
                return await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="🕘 Command under cooldown",
                description=f"Please retry in: `{datetime.timedelta(seconds=round(error.retry_after))}`",
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ Missing argument",
                description=f"One or more arguments are missing.\n**Command usage:** `{ctx.prefix}{ctx.command.usage}`\n\n__Hint:__ You can use `{ctx.prefix}help {ctx.command.qualified_name}` to view more information about this command.",
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            logging.info(
                f"{ctx.author} tried calling a command ({ctx.message.content}) but did not supply sufficient arguments."
            )
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.MaxConcurrencyReached):
            embed = discord.Embed(
                title="❌ Max concurrency reached",
                description="You have reached the maximum amount of instances for this command.",
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            return await ctx.channel.send(embed=embed)

        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                title="❌ Cannot find user by that name",
                description="Please check if you typed everything correctly, then try again.\n**Error:**```{error}```".format(
                    error=str(error)
                ),
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.errors.BadArgument):
            embed = discord.Embed(
                title="❌ Bad argument",
                description="Invalid data entered! Check `{prefix}help {command_name}` for more information.\n**Error:**```{error}```".format(
                    prefix=ctx.prefix,
                    command_name=ctx.command.qualified_name,
                    error=error,
                ),
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.TooManyArguments):
            embed = discord.Embed(
                title="❌ Too many arguments",
                description="You have provided more arguments than what `{prefix}{command_name}` can take. Check `{prefix}help {command_name}` for more information.".format(
                    prefix=ctx.prefix, command_name=ctx.command.qualified_name
                ),
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            return await ctx.send(embed=embed)

        elif isinstance(error, discord.Forbidden):
            embed = discord.Embed(
                title="❌ Permissions error",
                description="This action has failed due to a lack of permissions.\n**Error:** {error}".format(
                    error=error
                ),
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            return await ctx.send(embed=embed)

        elif isinstance(error, discord.DiscordServerError):
            embed = discord.Embed(
                title="❌ Discord Server Error",
                description="This action has failed due to an issue with Discord's servers. Please try again in a few moments.".format(
                    error=error
                ),
                color=self.error_color,
            )
            embed = self.add_embed_footer(ctx, embed)
            return await ctx.send(embed=embed)

        else:
            """If no known error has been passed, we will print the exception to console as usual
            IMPORTANT!!! If removed, command errors will not get output to stderr."""

            logging.error("Ignoring exception in command {}:".format(ctx.command))
            exception_msg = "\n".join(traceback.format_exception(type(error), error, error.__traceback__))

            try:
                await self.get_cog("HomeGuild").log_error(exception_msg, ctx)
            except Exception as error:
                logging.error(f"Failed to log to server: {error}")
            logging.error(exception_msg)

            embed = discord.Embed(
                title="❌ Unhandled exception",
                description="An error happened that should not have happened. Please [contact us](https://discord.gg/KNKr8FPmJa) with a screenshot of this message!\n**Error:** ```{error}```".format(
                    error=error
                ),
                color=self.error_color,
            )
            embed.set_footer(text=f"Guild: {ctx.guild.id}")
            return await ctx.send(embed=embed)

    async def maybe_send(self, channel, **kwargs):
        """Try and send a message in the given channel, and silently swallow the error if it fails."""
        try:
            await channel.send(**kwargs)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    async def maybe_edit(self, message, **kwargs):
        """Try and edit the given message, and silently swallow the error if it fails."""
        try:
            await message.edit(**kwargs)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    async def maybe_delete(self, message):
        """Try and delete the message, and silently swallow the error if it fails."""
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    def add_embed_footer(self, ctx, embed: discord.Embed):
        """Add the 'Requested by xyz' standard footer to an embed."""
        if ctx.author.display_avatar:
            embed.set_footer(
                text=f"Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )
        else:
            embed.set_footer(text=f"Requested by {ctx.author}")
        return embed

    @tasks.loop(hours=24.0)
    async def backup_bot_db(self):
        if self.skip_db_backup == False:  # Prevent quick bot restarts from triggering the system
            file = await db_backup.backup_database(self.dsn)
            await self.wait_until_ready()
            if self.config["home_guild"] and self.config["db_backup_channel"] and self.is_ready():
                guild = self.get_guild(self.config["home_guild"])
                backup_channel = guild.get_channel(self.config["db_backup_channel"])
                if guild and backup_channel:
                    await backup_channel.send(
                        f"Database Backup: {discord.utils.format_dt(discord.utils.utcnow())}",
                        file=file,
                    )
                    logging.info("Database backed up to specified Discord channel.")
        else:
            logging.info("Skipping database backup for this day...")
            self.skip_db_backup = False
