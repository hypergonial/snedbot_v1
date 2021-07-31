import asyncio
import datetime
import gettext
import logging
import os
import sys
import traceback
from dataclasses import dataclass
from difflib import get_close_matches
from itertools import chain
from pathlib import Path

import asyncpg
import discord
from discord.ext import commands, ipc, tasks

from extensions.utils import cache, context

try:
    from config import config
except ImportError:
    logging.error("Failed loading configuration. Please make sure 'config.py' exists in the root directory of the project and contains valid data.")
    exit()

#Language
lang = "en"
#Version of the bot
current_version = "5.0.0m"

TOKEN = config["token"]

'''
All extensions that are loaded on boot-up, change these to alter what modules you want (Note: These refer to filenames NOT cognames)
Please note that the bot was not built for modularity and the absence of any of the extensions may cause fatal errors.
Jishaku is a bot-owner only debug extension, requires 'pip install jishaku'.
'''
initial_extensions = (
    'extensions.permissions',
    'extensions.admin_commands',
    'extensions.help', 
    'extensions.homeguild',
    'extensions.moderation',
    'extensions.role_buttons', 
    'extensions.events',
    'extensions.ktp', 
    'extensions.matchmaking', 
    'extensions.tags', 
    'extensions.setup', 
    'extensions.userlog', 
    'extensions.timers', 
    'extensions.fun', 
    'extensions.annoverse',
    'extensions.giveaway',
    'extensions.ipc',
    'extensions.misc_commands',
    'jishaku'
)


async def get_prefix(bot, message):
    '''
    Gets custom prefix for the current guild
    '''
    if message.guild is None:
        return bot.DEFAULT_PREFIX
    else:
        records = await bot.caching.get(table="global_config", guild_id=message.guild.id)
        if records:
            prefixes = records["prefix"][0]
            if prefixes and len(prefixes) > 0: return prefixes
            else: return bot.DEFAULT_PREFIX
        else:
            return bot.DEFAULT_PREFIX


class SnedBot(commands.Bot):
    '''The bot class'''

    def __init__(self):
        allowed_mentions = discord.AllowedMentions(everyone=False, users=True, roles=True, replied_user=True)
        activity = discord.Activity(name='@Sned', type=discord.ActivityType.listening)
        #Disabled: presences, typing, integrations, webhooks, voice_states
        intents = discord.Intents(
            guilds = True,
            members = True,
            bans = True,
            emojis = True,
            messages = True,
            invites = True,
            reactions = True
        )
        super().__init__(command_prefix=get_prefix, allowed_mentions=allowed_mentions, 
        intents=intents, case_insensitive=True, activity=activity, max_messages=10000)

        if config["ipc_secret"] and config["ipc_secret"] != "":
            self.ipc = ipc.Server(self, host="0.0.0.0", port=8765, secret_key=config["ipc_secret"], do_multicast=False)

        self.caching = cache.Caching(self)
        self.config = config

        self.EXPERIMENTAL = config["experimental"]
        self.DEFAULT_PREFIX = 'sn '
        if self.EXPERIMENTAL == True :
            self.DEFAULT_PREFIX = 'snx '
            logging.basicConfig(level=logging.INFO)
            DB_NAME = "sned_exp"
        else :
            logging.basicConfig(level=logging.INFO)
            DB_NAME = "sned"

        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        self.lang = lang
        self.pool = self.loop.run_until_complete(asyncpg.create_pool(dsn=config["postgres_dsn"].format(db_name=DB_NAME)))
        self.whitelisted_guilds = [372128553031958529, 627876365223591976, 818223666143690783, 836248845268680785]
        self.anno_guilds = (372128553031958529, 627876365223591976, 818223666143690783) #Guilds whitelisted for Anno-related commands
        self.cmd_cd_mapping = commands.CooldownMapping.from_cooldown(10, 10, commands.BucketType.channel)
        self.current_version = current_version

        self.loop.create_task(self.startup())

    
    async def on_ready(self):
        logging.info("Connected to Discord!")
        if not hasattr(self, "uptime"):
            self.uptime = datetime.datetime.utcnow()

    """ async def on_ipc_ready(self):
        logging.info("IPC is connected and ready.") """ #Borked in 2.0

    async def on_ipc_error(self, endpoint, error):
        logging.error(f"{endpoint} raised {error}")


    async def startup(self):
        '''
        Gets executed on first start of the bot, sets up the prefix cache
        '''
        await self.wait_until_ready()

        logging.info("Initialized as {0.user}".format(self))
        if self.EXPERIMENTAL == True :
            logging.warning("\n--------------\nExperimental mode is enabled!\n--------------")
            cogs = await self.current_cogs()
            logging.info(f"Cogs loaded: {', '.join(cogs)}")
        #Insert all guilds the bot is member of into the db global config on startup
        async with self.pool.acquire() as con:
            for guild in self.guilds:
                await con.execute('''
                INSERT INTO global_config (guild_id) VALUES ($1)
                ON CONFLICT (guild_id) DO NOTHING''', guild.id)

    def get_localization(self, extension_name:str, lang:str):
        '''
        Installs the proper localization for a given extension
        '''
        LOCALE_PATH = Path(self.BASE_DIR, 'locale')

        if lang == "de":
            de = gettext.translation('main', localedir=LOCALE_PATH, languages=['de'])
            de.install()
            _ = de.gettext
            return _
        #Fallback to English
        else :
            lang = "en"
            _ = gettext.gettext
            return _

    
    async def current_cogs(self):
        '''
        Simple function that just gets all currently loaded cog/extension names
        '''
        cogs = []
        for cogName,cogClass in bot.cogs.items(): # pylint: disable=<unused-variable>
            cogs.append(cogName)
        return cogs

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=context.Context)

        if ctx.command is None:
            return

        if message.author.bot:
            return

        await self.invoke(ctx)


    async def on_message(self, message):
        if self.is_ready() and self.caching.is_ready:
            bucket = self.cmd_cd_mapping.get_bucket(message)
            retry_after = bucket.update_rate_limit()
            if not retry_after and len(message.content) < 1500: #If not ratelimited
                #Also limits message length to prevent errors originating from insane message
                #length (Thanks Nitro :) )
                mentions = [f"<@{bot.user.id}>", f"<@!{bot.user.id}>"]
                if message.content in mentions:
                    record = await self.caching.get(table="global_config", guild_id=message.guild.id)
                    if not record or len(record["prefix"][0]) == 0:
                        prefix = [self.DEFAULT_PREFIX]
                    else:
                        prefix = record["prefix"][0]
                    embed=discord.Embed(title=_("Beep Boop!"), description=_("My prefixes on this server are the following: `{prefix}` \nUse the command `{prefix_0}help` to see what I can do!").format(prefix="`, `".join(prefix), prefix_0=prefix[0]), color=0xfec01d)
                    embed.set_thumbnail(url=self.user.avatar.url)
                    await message.reply(embed=embed)

                await self.process_commands(message)
            else:
                pass #Ignore requests that would exceed rate-limits

    async def on_command(self, ctx):
        logging.info(f"{ctx.author} called command {ctx.message.content} in guild {ctx.guild.id}")


    async def on_guild_join(self, guild):
        #Generate guild entry for DB
        async with bot.pool.acquire() as con:
            await con.execute('INSERT INTO global_config (guild_id) VALUES ($1)', guild.id)
        if guild.system_channel != None :
            try:
                embed=discord.Embed(title=_("Beep Boop!"), description=_("I have been summoned to this server. Use `{prefix}help` to see what I can do!").format(prefix=bot.DEFAULT_PREFIX), color=0xfec01d)
                embed.set_thumbnail(url=self.user.avatar.url)
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                pass
        logging.info(f"Bot has been added to new guild {guild.id}.")


    async def on_guild_remove(self, guild):
        '''
        Erase all settings for this guild on removal to keep the db tidy.
        The reason this does not use GlobalConfig.deletedata() is to not recreate the entry for the guild
        '''
        async with bot.pool.acquire() as con:
            await con.execute('''DELETE FROM global_config WHERE guild_id = $1''', guild.id)
        await self.caching.wipe(guild.id)
        logging.info(f"Bot has been removed from guild {guild.id}, correlating data erased.")

    async def on_error(self, event_method:str, *args, **kwargs):
        '''
        Global Error Handler

        Prints all exceptions and also tries to sends them to the specified error channel, if any.
        '''
        print(f'Ignoring exception in {event_method}', file=sys.stderr)
        error_str = traceback.format_exc()
        print(error_str)
        await self.bot.get_cog("HomeGuild").log_error(error_str, event_method=event_method)


    async def on_command_error(self, ctx, error):
        '''
        Global Command Error Handler

        Generic error handling. Will catch all otherwise not handled errors
        '''
        if isinstance(error, commands.CheckFailure):
            logging.info(f"{ctx.author} tried calling a command but did not meet checks.")
            if isinstance(error, commands.BotMissingPermissions):
                embed=discord.Embed(title="❌ " + _("Bot missing permissions"), description=_("The bot requires additional permissions to execute this command.\n**Error:**```{error}```").format(error=error), color=self.errorColor)
                return await ctx.send(embed=embed)
            return

        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, asyncio.exceptions.TimeoutError):
            embed=discord.Embed(title=self.errorTimeoutTitle, description=self.errorTimeoutDesc, color=self.errorColor)
            embed.set_footer(text=self.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandNotFound):
            '''
            This is a fancy suggestion thing that will suggest commands that are similar in case of typos.
            '''
            logging.info(f"{ctx.author} tried calling a command in {ctx.guild.id} but the command was not found. ({ctx.message.content})")
            
            cmd = ctx.invoked_with.lower()

            cmds = [cmd.name for cmd in bot.commands if not cmd.hidden]
            allAliases = [cmd.aliases for cmd in bot.commands if not cmd.hidden]
            aliases = list(chain(*allAliases))

            matches = get_close_matches(cmd, cmds)
            aliasmatches = get_close_matches(cmd, aliases)

            if len(matches) > 0:
                embed=discord.Embed(title=self.unknownCMDstr, description=_("Did you mean `{prefix}{match}`?").format(prefix=ctx.prefix, match=matches[0]), color=self.unknownColor)
                embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
                return await ctx.send(embed=embed)
            elif len(aliasmatches) > 0:
                embed=discord.Embed(title=self.unknownCMDstr, description=_("Did you mean `{prefix}{match}`?").format(prefix=ctx.prefix, match=aliasmatches[0]), color=self.unknownColor)
                embed.set_footer(text=self.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
                return await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandOnCooldown):
            embed=discord.Embed(title=self.errorCooldownTitle, description=_("Please retry in: `{cooldown}`").format(cooldown=datetime.timedelta(seconds=round(error.retry_after))), color=self.errorColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.MissingRequiredArgument):
            embed=discord.Embed(title="❌" + _("Missing argument."), description=_("One or more arguments are missing. \n__Hint:__ You can use `{prefix}help {command_name}` to view command usage.").format(prefix=ctx.prefix, command_name=ctx.command.name), color=self.errorColor)
            embed.set_footer(text=self.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
            logging.info(f"{ctx.author} tried calling a command ({ctx.message.content}) but did not supply sufficient arguments.")
            return await ctx.send(embed=embed)


        elif isinstance(error, commands.MaxConcurrencyReached):
            embed = discord.Embed(title=self.errorMaxConcurrencyReachedTitle, description=self.errorMaxConcurrencyReachedDesc, color=self.errorColor)
            embed.set_footer(text=self.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
            return await ctx.channel.send(embed=embed)

        elif isinstance(error, commands.MemberNotFound):
            embed=discord.Embed(title="❌ " + _("Cannot find user by that name"), description=_("Please check if you typed everything correctly, then try again.\n**Error:**```{error}```").format(error=str(error)), color=self.errorColor)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.errors.BadArgument):
            embed=discord.Embed(title="❌ " + _("Bad argument"), description=_("Invalid data entered! Check `{prefix}help {command_name}` for more information.\n**Error:**```{error}```").format(prefix=ctx.prefix, command_name=ctx.command.name, error=error), color=self.errorColor)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.TooManyArguments):
            embed=discord.Embed(title="❌ " + _("Too many arguments"), description=_("You have provided more arguments than what `{prefix}{command_name}` can take. Check `{prefix}help {command_name}` for more information.").format(prefix=ctx.prefix, command_name=ctx.command.name), color=self.errorColor)
            return await ctx.send(embed=embed)

        else :
            #If no known error has been passed, we will print the exception to console as usual
            #IMPORTANT!!! If you remove this, your command errors will not get output to console.
            #logging.error('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            exception_msg = "\n".join(traceback.format_exception(type(error), error, error.__traceback__))
            try:
                await self.get_cog("HomeGuild").log_error(exception_msg, ctx)
            except Exception as error:
                logging.error(f"Failed to log to server: {error}")
            logging.error(exception_msg)
            #traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


bot = SnedBot()
_ = bot.get_localization('main', lang)


'''
#Error/warn messages

This contains strings for common error/warn msgs.
'''
#Errors:
bot.errorColor = 0xff0000
bot.errorTimeoutTitle = "🕘 " + _("Error: Timed out")
bot.errorTimeoutDesc = _("Your session has expired. Execute the command again!")
bot.errorDataTitle = "❌ " + _("Error: Invalid data entered")
bot.errorDataDesc = _("Operation cancelled.")
bot.errorEmojiTitle = "❌ " + _("Error: Invalid reaction entered")
bot.errorEmojiDesc = _("Operation cancelled.")
bot.errorFormatTitle = "❌ " + _("Error: Invalid format entered")
bot.errorFormatDesc = _("Operation cancelled.")
bot.errorCheckFailTitle = "❌ " + _("Error: Insufficient permissions")
bot.errorCheckFailDesc = _("You did not meet the checks to execute this command. This could also be caused by incorrect configuration. \nType `{prefix}help` for a list of available commands.")
bot.errorCooldownTitle = "🕘 " + _("Error: This command is on cooldown")
bot.errorMissingModuleTitle = "❌ " + _("Error: Missing module")
bot.errorMissingModuleDesc = _("This operation is missing a module")
bot.errorMaxConcurrencyReachedTitle = "❌ " + _("Error: Max concurrency reached!")
bot.errorMaxConcurrencyReachedDesc= _("You have reached the maximum amount of instances for this command.")
#Warns:
bot.warnColor = 0xffcc4d
bot.warnDataTitle = "⚠️ " + _("Warning: Invalid data entered")
bot.warnDataDesc = _("Please check command usage.")
bot.warnEmojiTitle = "⚠️ " + _("Warning: Invalid reaction entered")
bot.warnEmojiDesc = _("Please enter a valid reaction.")
bot.warnFormatTitle = "⚠️ " + _("Warning: Invalid format entered")
bot.warnFormatDesc = _("Please try entering valid data.")
bot.requestFooter = _("Requested by {user_name}#{discrim}")
bot.unknownCMDstr = "❓ " + _("Unknown command!")
#Misc:
bot.embedBlue = 0x009dff
bot.embedGreen = 0x77b255
bot.unknownColor = 0xbe1931
bot.miscColor = 0xc2c2c2


class GlobalConfig():
    '''
    Class that handles the global configuration & users within the database
    These tables are created automatically as they must exist
    '''

    @dataclass
    class User:
        '''
        Represents a user stored inside the database
        '''
        user_id:int
        guild_id:int
        flags:list=None
        warns:int=0
        is_muted:bool=False
        notes:str=None

    def __init__(self, bot):
        async def init_table():
            self.bot = bot
            async with bot.pool.acquire() as con:
                await con.execute('''
                CREATE TABLE IF NOT EXISTS public.global_config
                (
                    guild_id bigint NOT NULL,
                    prefix text[],
                    PRIMARY KEY (guild_id)
                )''')
                await con.execute('''
                CREATE TABLE IF NOT EXISTS public.users
                (
                    user_id bigint NOT NULL,
                    guild_id bigint NOT NULL,
                    flags text[],
                    warns integer NOT NULL DEFAULT 0,
                    is_muted bool NOT NULL DEFAULT false,
                    notes text,
                    PRIMARY KEY (user_id, guild_id),
                    FOREIGN KEY (guild_id)
                        REFERENCES global_config (guild_id)
                        ON DELETE CASCADE
                )''')
        bot.loop.run_until_complete(init_table())
        self.cleanup_userdata.start()

    @tasks.loop(seconds=3600.0)
    async def cleanup_userdata(self):
        '''Clean up garbage userdata from db'''
        await bot.wait_until_ready()
        async with self.bot.pool.acquire() as con:
            await con.execute('''
                DELETE FROM users WHERE flags IS NULL and warns = 0 AND is_muted = false AND notes IS NULL 
                ''')

    async def deletedata(self, guild_id):
        '''
        Deletes all data related to a specific guild, including but not limited to: all settings, priviliged roles, stored tags, stored multiplayer listings etc...
        Warning! This also erases any stored warnings & other moderation actions for the guild!
        '''
        #The nuclear option c:
        async with self.bot.pool.acquire() as con:
            await con.execute('''DELETE FROM global_config WHERE guild_id = $1''', guild_id)
            #This one is necessary so that the list of guilds the bot is in stays accurate
            await con.execute('''INSERT INTO global_config (guild_id) VALUES ($1)''', guild_id)

        await self.caching.wipe(guild_id)
        logging.warning(f"Config reset and cache wiped for guild {guild_id}.")
    

    async def update_user(self, user):
        '''
        Takes an instance of GlobalConfig.User and tries to either update or create a new user entry if one does not exist already
        '''
        async with bot.pool.acquire() as con:
            try:
                await con.execute('''
                INSERT INTO users (user_id, guild_id, flags, warns, is_muted, notes) 
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id, guild_id) DO
                UPDATE SET flags = $3, warns = $4, is_muted = $5, notes = $6''', user.user_id, user.guild_id, user.flags, user.warns, user.is_muted, user.notes)
            except asyncpg.exceptions.ForeignKeyViolationError:
                logging.warn('Trying to update a guild db_user whose guild no longer exists. This could be due to pending timers.')

    async def get_user(self, user_id, guild_id): 
        '''
        Gets an instance of GlobalConfig.User that contains basic information about the user in relation to a guild
        Returns None if not found
        '''
        async with bot.pool.acquire() as con:
            result = await con.fetch('''SELECT * FROM users WHERE user_id = $1 AND guild_id = $2''', user_id, guild_id)
        if result:
            user = self.User(user_id = result[0].get('user_id'), guild_id=result[0].get('guild_id'), flags=result[0].get('flags'), 
            warns=result[0].get('warns'), is_muted=result[0].get('is_muted'), notes=result[0].get('notes'))
            return user
        else:
            user = self.User(user_id = user_id, guild_id = guild_id) #Generate a new db user if none exists
            await self.update_user(user) 
            return user

    
    async def get_all_guild_users(self, guild_id):
        '''
        Returns all users related to a specific guild as a list of GlobalConfig.User
        Return None if no users are contained in the database
        '''
        async with bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM users WHERE guild_id = $1''', guild_id)
        if results:
            users = []
            for result in results:
                user = self.User(user_id = result.get('user_id'), guild_id=result.get('guild_id'), flags=result.get('flags'), 
                warns=result.get('warns'), is_muted=result.get('is_muted'), notes=result.get('notes'))
                users.append(user)
            return users

bot.global_config = GlobalConfig(bot)

'''
Loading extensions, has to be AFTER global_config is initialized so global_config already exists
'''

if __name__ == '__main__':
    '''
    Loading extensions from the list of extensions defined in initial_extensions
    '''
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            logging.error(f'Failed to load extension {extension}.', file=sys.stderr)
            traceback.print_exc()


class CustomChecks():
    '''
    Custom checks for commands and cogs across the bot
    Some of these checks are not intended to be implemented directly, as they take arguments,
    instead, you should wrap them into other functions that give them said arguments.
    '''

    async def has_owner(self, ctx):
        '''
        True if the invoker is either bot or guild owner
        '''
        if ctx.guild:
            return ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id
        else:
            return ctx.author.id == ctx.bot.owner_id

    async def module_is_enabled(self, ctx, module_name:str):
        '''
        True if module is enabled, false otherwise. module_name is the extension filename.
        '''
        record = await bot.caching.get(table="modules", guild_id=ctx.guild.id, module_name=module_name)
        if record and record["is_enabled"][0]:
            return record["is_enabled"][0]
        else:
            return True

    async def has_permissions(self, ctx, perm_node:str):
        '''
        Returns True if a user is in the specified permission node, 
        or in the administrator node, or is a Discord administrator, or is the owner.
        '''
        if ctx.guild:
            user_role_ids = [x.id for x in ctx.author.roles]
            role_ids = await ctx.bot.get_cog("Permissions").get_perms(ctx.guild, perm_node)
            admin_role_ids = await ctx.bot.get_cog("Permissions").get_perms(ctx.guild, "admin_permitted")
            return any(role in user_role_ids for role in admin_role_ids) or any(role in user_role_ids for role in role_ids) or ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.administrator

bot.custom_checks = CustomChecks()

#Run bot with token from .env
try :
    if hasattr(bot, 'ipc'):
        bot.ipc.start()
    else:
        logging.warn('IPC secret was not found!')
    bot.run(TOKEN)
except KeyboardInterrupt :
    bot.loop.run_until_complete(bot.pool.close())
    bot.close()
