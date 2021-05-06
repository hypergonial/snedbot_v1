import asyncio
import datetime
import gettext
import json
import logging
import os
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from difflib import get_close_matches
from itertools import chain
from pathlib import Path

import asyncpg
import discord
from discord.ext import commands, menus
from dotenv import load_dotenv

#Language
lang = "en"
#Is this build experimental? Enable for additional debugging. Also writes to a different database to prevent conflict issues.
EXPERIMENTAL = False
#Version of the bot
current_version = "4.2.1"
#Loading token from .env file. If this file does not exist, nothing will work.
load_dotenv()
TOKEN = os.getenv("TOKEN")
DBPASS = os.getenv("DBPASS")

#Determines bot prefix & logging based on build state.
default_prefix = '!'
if EXPERIMENTAL == True :
    default_prefix = '?'
    logging.basicConfig(level=logging.INFO)
    db_name = "sned_exp"
else :
    default_prefix = '!'
    logging.basicConfig(level=logging.INFO)
    db_name="sned"


#Block bot from ever pinging @everyone
allowed_mentions = discord.AllowedMentions(everyone=False, users=True, roles=True, replied_user=True)
#This is just my user ID, used for setting up who can & cant use priviliged commands along with a server owner.
creatorID = 163979124820541440

async def get_prefix(bot, message):
    if message.guild is None:
        return default_prefix
    elif message.guild.id in bot.cache['prefix']: #If prefix is cached
        return bot.cache['prefix'][message.guild.id] #Get from cache
    else:
        async with bot.pool.acquire() as con: #Else try to find in db
            results = await con.fetch('''SELECT prefix FROM global_config WHERE guild_id = $1''', message.guild.id)
            if len(results) !=0 and results[0] and results[0].get('prefix'):
                prefixes = results[0].get('prefix')
                bot.cache['prefix'][message.guild.id] = prefixes
                return prefixes
            else: #Fallback to default prefix if there is none found
                bot.cache['prefix'][message.guild.id] = default_prefix #Cache it
                return default_prefix

#Disabled: presences, typing, integrations
activity = discord.Activity(name='@Sned', type=discord.ActivityType.listening)
intents=discord.Intents(guilds=True, members=True, bans=True, emojis=True, webhooks=True, invites=True, voice_states=True, messages=True, reactions=True)
bot = commands.Bot(command_prefix=get_prefix, intents=intents, owner_id=creatorID, case_insensitive=True, help_command=None, activity=activity, max_messages=20000, allowed_mentions=allowed_mentions)

#Global bot settings


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
bot.localePath = Path(BASE_DIR, 'locale')
bot.pool = bot.loop.run_until_complete(asyncpg.create_pool(dsn="postgres://postgres:{DBPASS}@192.168.1.101:5432/{db_name}".format(DBPASS=DBPASS, db_name=db_name)))

bot.whitelisted_guilds = [372128553031958529, 627876365223591976, 818223666143690783, 836248845268680785] #Guilds whitelisted for certain commands
bot.anno_guilds = [372128553031958529, 627876365223591976, 818223666143690783] #Guilds whitelisted for Anno-related commands

if lang == "de":
    de = gettext.translation('main', localedir=bot.localePath, languages=['de'])
    de.install()
    _ = de.gettext
elif lang == "en":
    _ = gettext.gettext
#Fallback to english
else :
    logging.error("Invalid language, fallback to English.")
    lang = "en"
    _ = gettext.gettext


#No touch, handled in runtime by extensions
bot.BASE_DIR = BASE_DIR
bot.current_version = current_version
bot.lang = lang
bot.default_prefix = default_prefix
bot.EXPERIMENTAL = EXPERIMENTAL
bot.recentlyDeleted = []
bot.recentlyEdited = []
bot.cache = {}
bot.cache['prefix'] = {}
bot.cache['rr'] = {}
bot.cd_mapping = commands.CooldownMapping.from_cooldown(10, 10, commands.BucketType.channel)


#All extensions that are loaded on boot-up, change these to alter what modules you want (Note: These refer to filenames NOT cognames)
#Note: Without the extension admin_commands, most things will break, so I consider this a must-have. Remove at your own peril.
#Jishaku is a bot-owner only debug extension, requires 'pip install jishaku'.
initial_extensions = [
'extensions.admin_commands', 'extensions.moderation','extensions.reaction_roles', 'extensions.ktp', 'extensions.matchmaking', 'extensions.tags', 'extensions.setup', 
'extensions.userlog', 'extensions.timers', 'extensions.fun', 'extensions.annoverse','extensions.misc_commands', 'jishaku'
]

'''
#Error/warn messages

This contains strings for common error/warn msgs.
'''
#Errors:
bot.errorColor = 0xff0000
bot.errorTimeoutTitle = "🕘 " + _("Error: Timed out.")
bot.errorTimeoutDesc = _("Your session has expired. Execute the command again!")
bot.errorDataTitle = "❌ " + _("Error: Invalid data entered.")
bot.errorDataDesc = _("Operation cancelled.")
bot.errorEmojiTitle = "❌ " + _("Error: Invalid reaction entered.")
bot.errorEmojiDesc = _("Operation cancelled.")
bot.errorFormatTitle = "❌ " + _("Error: Invalid format entered.")
bot.errorFormatDesc = _("Operation cancelled.")
bot.errorCheckFailTitle = "❌ " + _("Error: Insufficient permissions.")
bot.errorCheckFailDesc = _("You did not meet the checks to execute this command. This could also be caused by incorrect configuration. \nType `{prefix}help` for a list of available commands.")
bot.errorCooldownTitle = "🕘 " + _("Error: This command is on cooldown.")
bot.errorMissingModuleTitle = "❌ " + _("Error: Missing module.")
bot.errorMissingModuleDesc = _("This operation is missing a module.")
bot.errorMaxConcurrencyReachedTitle = "❌ " + _("Error: Max concurrency reached!")
bot.errorMaxConcurrencyReachedDesc= _("You have reached the maximum amount of instances for this command.")
#Warns:
bot.warnColor = 0xffcc4d
bot.warnDataTitle = "⚠️ " + _("Warning: Invalid data entered.")
bot.warnDataDesc = _("Please check command usage.")
bot.warnEmojiTitle = "⚠️ " + _("Warning: Invalid reaction entered.")
bot.warnEmojiDesc = _("Please enter a valid reaction.")
bot.warnFormatTitle = "⚠️ " + _("Warning: Invalid format entered.")
bot.warnFormatDesc = _("Please try entering valid data.")
bot.requestFooter = _("Requested by {user_name}#{discrim}")
bot.unknownCMDstr = "❓ " + _("Unknown command!")
#Misc:
bot.embedBlue = 0x009dff
bot.embedGreen = 0x77b255
bot.unknownColor = 0xbe1931
bot.miscColor = 0xc2c2c2

logging.info("New Session Started.")
logging.info(f"Language: {lang}")




async def startup():
    '''
    Gets executed on first start of the bot
    '''
    await bot.wait_until_ready()

    logging.info("Initialized as {0.user}".format(bot))
    if bot.EXPERIMENTAL == True :
        logging.warning("Experimental mode is enabled.")
        logging.info(f"Extensions loaded: {bot.checkExtensions}")
    #Insert all guilds the bot is member of into the db on startup
    async with bot.pool.acquire() as con:
        for guild in bot.guilds:
            await con.execute('''
            INSERT INTO global_config (guild_id) VALUES ($1)
            ON CONFLICT (guild_id) DO NOTHING''', guild.id)
        results = await con.fetch('''SELECT * FROM global_config''')
        logging.info("Initializing cache...")
        for result in results:
            if result.get('prefix'):
                bot.cache['prefix'][result.get('guild_id')] = result.get('prefix')
            else:
                bot.cache['prefix'][result.get('guild_id')] = bot.default_prefix
        logging.info("Cache ready!")

bot.loop.create_task(startup())

#Executes when the bot starts/reconnects & is ready.
@bot.event
async def on_ready():
    logging.info("Connected to Discord!")


class GlobalConfig():
    '''
    Class that handles the global configuration & users within the database
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
        logging.warning(f"Settings have been reset and tags erased for guild {guild_id}.")
    

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


def checkExtensions():
    '''
    Simple function that just gets all currently loaded cog/extension names
    '''
    extensions = []
    for cogName,cogClass in bot.cogs.items():
        extensions.append(cogName)
    return extensions
        
bot.checkExtensions = checkExtensions()

class CommandChecks():

    '''
    Custom checks for commands across the bot
    '''
    #Has bot or guild owner
    async def hasOwner(self, ctx):
        return ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id

    #Check performed to see if the user has priviliged access.
    async def hasPriviliged(self, ctx):
        userRoles = [x.id for x in ctx.author.roles]
        async with bot.pool.acquire() as con:
            results = await con.fetch('''SELECT priviliged_role_id FROM priviliged WHERE guild_id = $1''', ctx.guild.id)
            privroles = [result.get('priviliged_role_id') for result in results]
            #Check if any of the roles in user's roles are contained in the priviliged roles.
            return any(role in userRoles for role in privroles) or (ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.administrator)


bot.CommandChecks = CommandChecks()

#The custom help command subclassing the dpy one. See the docs or this guide (https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96) on how this was made.
class SnedHelp(commands.HelpCommand):
    #Method to get information about a command to display in send_bot_help
    def get_command_signature(self, command):
        return '**`{prefix}{parent}{command}`** - {commandbrief}'.format(prefix=self.clean_prefix, parent=command.full_parent_name, command=command.name, commandbrief=command.short_doc) #short_doc goes to brief first, otherwise gets first line of help
    
    def get_subcommand_signature(self, group, command): #Essentially the same as get_command_signature but appends the group name in front of the command
        return '**`{prefix}{group} {command}`** - {commandbrief}'.format(prefix=self.clean_prefix, group=group.name, command=command.name, commandbrief=command.short_doc)
    
    #Send generic help message with all commands included
    async def send_bot_help(self, mapping):

        class HelpPages(menus.MenuPages):
            '''
            Subclassing MenuPages to add an offset for the homepage (so it does not swallow the first page)
            '''
            def __init__(self, initial_message, source, **kwargs):
                self.initial_message = initial_message
                super().__init__(source, **kwargs)
            
            async def send_initial_message(self, _, channel):
                self.current_page = -1
                return await channel.send(embed=self.initial_message)

        #Menu pagination
        class HelpSource(menus.ListPageSource):
            '''
            Takes a list, and puts it into an embed menu, 2 items per page
            '''
            def __init__(self, data):
                super().__init__(data, per_page=2)

            async def format_page(self, menu, entries):
                #offset = (menu.current_page-999) * self.per_page --> This also works and changes nothing c:
                offset = menu.current_page * self.per_page
                embed=discord.Embed(title="⚙️ " + _("__Available commands:__"), description=_("**Tip:** You can also type **`{prefix}help [command]`** to get more information about a specific command and see any subcommands a command may have.\nStill lost? [Join our Discord server!](https://discord.gg/kQVNf68W2a)\n\n").format(prefix=ctx.prefix) + ''.join(f'{v}' for i, v in enumerate(entries, start=offset)), color=bot.embedBlue)
                embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator) + f"  |  Page {menu.current_page + 1}/{self.get_max_pages()}", icon_url=ctx.author.avatar_url)
                return embed

        ctx = self.context   #Obtaining ctx
        cmdslist = []
        #We retrieve all the commands from the mapping of cog,commands
        for cog, commands in mapping.items(): 
            filtered = await self.filter_commands(commands, sort=True)   #This will filter commands to those the user can actually execute
            command_signatures = [self.get_command_signature(command) for command in filtered]   #Get command signature in format as specified above
            #If we have any, put them in categories according to cogs, fallback is "Other"
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "Other") #Append items into a list of str, one item per cog
                cmdslist.append("**{cn}**\n{cs}\n".format(cn=cog_name, cs='\n'.join(command_signatures)))
        
        help_home_embed=discord.Embed(title="🏠 " + _("__Help Home__"), color=bot.embedBlue, description='''**How to navigate this help dialogue**

        Navigate via the ◀️ ▶️ reactions, or skip to the end via the ⏮️ ⏭️ reactions.
        You can stop this help session by reacting with ⏹️.

        **Command Usage & Syntax**

        `<argument>` is a __required__ parameter
        `[argument]` is an __optional__ parameter
        `<foo|bar>` means foo __OR__ bar

        *Do not include the brackets in your commands!*        

        React with ▶️ to see the next page and what commands are available to you!
        ''')
        help_home_embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)

        pages = HelpPages(help_home_embed, source=HelpSource(cmdslist), clear_reactions_after=True) #Feed the list of commands into the menu system
        await pages.start(ctx)

    async def send_command_help(self, command):
        ctx = self.context   #Obtaining ctx
        if command.parents:
            detail_embed=discord.Embed(title="⚙️ " + _("Command: {prefix}{parent} {command}").format(prefix=self.clean_prefix, parent=command.full_parent_name, command=command.name), color=bot.embedBlue)
        else:
            detail_embed=discord.Embed(title="⚙️ " + _("Command: {prefix}{command}").format(prefix=self.clean_prefix, command=command.name), color=bot.embedBlue)
        if command.description:
            detail_embed.add_field(name=_("Description:"), value=command.description)  #Getting command description
        elif command.help:
            detail_embed.add_field(name=_("Description:"), value=command.help)  #Fallback to help attribute if description does not exist
        if command.usage:
            detail_embed.add_field(name=_("Usage:"), value=f"**`{self.clean_prefix}{command.usage}`**", inline=False) #Getting command usage & formatting it
        aliases = []
        for alias in command.aliases:
            if command.parents:
                aliases.append(f"**`{self.clean_prefix}{command.full_parent_name} {alias}`**")
            else:
                aliases.append(f"**`{self.clean_prefix}{alias}`**")  #Adding some custom formatting to each alias
        if aliases:
            detail_embed.add_field(name=_("Aliases:"), value=", ".join(aliases), inline=False)   #If any aliases exist, we add those to the embed in new field
        detail_embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        channel = self.get_destination()   #Send it to destination
        await channel.send(embed=detail_embed)

    async def send_cog_help(self, cog):
        #I chose not to implement help for cogs, but if you want to do something, do it here
        ctx = self.context
        embed=discord.Embed(title=bot.unknownCMDstr, description=_("Use `{prefix}help` for a list of available commands.").format(prefix=ctx.prefix), color=bot.unknownColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_group_help(self, group):
        ctx = self.context
        group_embed = discord.Embed(title="⚙️ " + _("Group: {prefix}{group}").format(prefix=ctx.prefix, group=group.name), description=_("**Note:**\nTo see detailed information about one of the subcommands, type **`{prefix}help {group} [subcommand]`**").format(prefix=ctx.prefix, group=group.name), color=bot.embedBlue)
        if group.description:
            group_embed.add_field(name=_("Description:"), value=group.description)  #Getting command description
        elif group.help:
            group_embed.add_field(name=_("Description:"), value=group.help)  #Fallback to help attribute if description does not exist
        if group.usage:
            group_embed.add_field(name=_("Usage:"), value=f"**`{self.clean_prefix}{group.usage}`**", inline=False) #Getting command usage & formatting it
        aliases = []
        for alias in group.aliases:
            aliases.append(f"**`{self.clean_prefix}{alias}`**")  #Adding some custom formatting to each alias
        if aliases:
            group_embed.add_field(name=_("Aliases:"), value=", ".join(aliases), inline=False)   #If any aliases exist, we add those to the embed in new field
        sub_cmds = []
        filtered = await self.filter_commands(group.walk_commands(), sort=True)
        for command in filtered:
            sub_cmds.append(self.get_subcommand_signature(group, command))
        if sub_cmds:
            sub_cmds = "\n".join(sub_cmds)
            group_embed.add_field(name=_("Sub-commands:"), value=f"{sub_cmds}")
        channel = self.get_destination()
        await channel.send(embed=group_embed)

    async def send_error_message(self, error):   #Overriding the default help error message
        ctx = self.context
        embed=discord.Embed(title=bot.unknownCMDstr, description=_("Use `{prefix}help` for a list of available commands.").format(prefix=ctx.prefix), color=bot.unknownColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        channel = self.get_destination()
        await channel.send(embed=embed)

#Assign custom help command to bot
bot.help_command = SnedHelp()


@bot.event
async def on_command_error(ctx, error):
    '''
    Global Error Handler

    Generic error handling. Will catch all otherwise not handled errors
    '''

    if isinstance(error, commands.CheckFailure):
        logging.info(f"{ctx.author} tried calling a command but did not meet checks.")
        if isinstance(error, commands.BotMissingPermissions):
            embed=discord.Embed(title="❌ " + _("Bot missing permissions"), description=_("The bot requires additional permissions to execute this command.\n**Error:**```{error}```").format(error=error), color=bot.errorColor)
            return await ctx.send(embed=embed)

    if isinstance(error, commands.CommandInvokeError):
        if isinstance(error.original, asyncio.exceptions.TimeoutError):
            embed=discord.Embed(title=bot.errorTimeoutTitle, description=bot.errorTimeoutDesc, color=bot.errorColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed)
        else:
            raise error

    elif isinstance(error, commands.CommandNotFound):
        logging.info(f"{ctx.author} tried calling a command in but the command was not found. ({ctx.message.content})")
        #This is a fancy suggestion thing that will suggest commands that are similar in case of typos.
        #Get original cmd, and convert it into lowercase as to make it case-insensitive
        cmd = ctx.invoked_with.lower()
        #Gets all cmds and aliases
        cmds = [cmd.name for cmd in bot.commands if not cmd.hidden]
        allAliases = [cmd.aliases for cmd in bot.commands if not cmd.hidden]
        aliases = list(chain(*allAliases))
        #Get close matches
        matches = get_close_matches(cmd, cmds)
        aliasmatches = get_close_matches(cmd, aliases)
        #Check if there are any matches, then suggest if yes.
        if len(matches) > 0:
            embed=discord.Embed(title=bot.unknownCMDstr, description=_("Did you mean `{prefix}{match}`?").format(prefix=ctx.prefix, match=matches[0]), color=bot.unknownColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed)
        elif len(aliasmatches) > 0:
            embed=discord.Embed(title=bot.unknownCMDstr, description=_("Did you mean `{prefix}{match}`?").format(prefix=ctx.prefix, match=aliasmatches[0]), color=bot.unknownColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            return await ctx.send(embed=embed)
        '''else:
            embed=discord.Embed(title=bot.unknownCMDstr, description=_("Use `{prefix}help` for a list of available commands.").format(prefix=ctx.prefix), color=bot.unknownColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)'''

    elif isinstance(error, commands.CommandOnCooldown):
        embed=discord.Embed(title=bot.errorCooldownTitle, description=_("Please retry in: `{cooldown}`").format(cooldown=datetime.timedelta(seconds=round(error.retry_after))), color=bot.errorColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        return await ctx.send(embed=embed)

    elif isinstance(error, commands.MissingRequiredArgument):
        embed=discord.Embed(title="❌" + _("Missing argument."), description=_("One or more arguments are missing. \n__Hint:__ You can use `{prefix}help {command_name}` to view command usage.").format(prefix=ctx.prefix, command_name=ctx.command.name), color=bot.errorColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        logging.info(f"{ctx.author} tried calling a command ({ctx.message.content}) but did not supply sufficient arguments.")
        return await ctx.send(embed=embed)


    elif isinstance(error, commands.MaxConcurrencyReached):
        embed = discord.Embed(title=bot.errorMaxConcurrencyReachedTitle, description=bot.errorMaxConcurrencyReachedDesc, color=bot.errorColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        return await ctx.channel.send(embed=embed)

    elif isinstance(error, commands.MemberNotFound):
        embed=discord.Embed(title="❌ " + _("Cannot find user by that name"), description=_("Please check if you typed everything correctly, then try again.\n**Error:**```{error}```").format(error=str(error)), color=bot.errorColor)
        return await ctx.send(embed=embed)

    elif isinstance(error, commands.errors.BadArgument):
        embed=discord.Embed(title="❌ " + _("Bad argument"), description=_("Invalid data entered! Check `{prefix}help {command_name}` for more information.\n**Error:**```{error}```").format(prefix=ctx.prefix, command_name=ctx.command.name, error=error), color=bot.errorColor)
        return await ctx.send(embed=embed)

    elif isinstance(error, commands.TooManyArguments):
        embed=discord.Embed(title="❌ " + _("Too many arguments"), description=_("You have provided more arguments than what `{prefix}{command_name}` can take. Check `{prefix}help {command_name}` for more information.").format(prefix=ctx.prefix, command_name=ctx.command.name), color=bot.errorColor)
        return await ctx.send(embed=embed)

    else :
        #If no known error has been passed, we will print the exception to console as usual
        #IMPORTANT!!! If you remove this, your command errors will not get output to console.
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

#Executed on any command attempt
@bot.event
async def on_command(ctx):
    logging.info(f"{ctx.author} called command {ctx.message.content} in guild {ctx.guild.id}")

'''
Guild Join/Leave behaviours
'''
@bot.event
async def on_guild_join(guild):
    if guild.id == 336642139381301249: #Discord.py specific join behaviour
        async with bot.pool.acquire() as con:
            await con.execute('INSERT INTO global_config (guild_id) VALUES ($1)', guild.id)
            await con.execute('''UPDATE global_config SET prefix = array_append(prefix,$1) WHERE guild_id = $2''', "sned ", guild.id)
            logging.info("Joined discord.py! :verycool:")
            return
    #Generate guild entry for DB
    async with bot.pool.acquire() as con:
        await con.execute('INSERT INTO global_config (guild_id) VALUES ($1)', guild.id)
    if guild.system_channel != None :
        try:
            embed=discord.Embed(title=_("Beep Boop!"), description=_("I have been summoned to this server. Use `{prefix}help` to see what I can do!").format(prefix=default_prefix), color=0xfec01d)
            embed.set_thumbnail(url=bot.user.avatar_url)
            await guild.system_channel.send(embed=embed)
        except discord.Forbidden:
            pass
    logging.info(f"Bot has been added to new guild {guild.id}.")

#Triggered when bot leaves guild, or gets kicked/banned, or guild gets deleted.
@bot.event
async def on_guild_remove(guild):
    #Erase all settings for this guild on removal to keep the db tidy.
    #The reason this does not use GlobalConfig.deletedata() is to not recreate the entry for the guild
    async with bot.pool.acquire() as con:
            await con.execute('''DELETE FROM global_config WHERE guild_id = $1''', guild.id)
    logging.info(f"Bot has been removed from guild {guild.id}, correlating data erased.")

@bot.event
async def on_message(message):
    bucket = bot.cd_mapping.get_bucket(message)
    retry_after = bucket.update_rate_limit()
    if not retry_after: #If not ratelimited
        mentions = [f"<@{bot.user.id}>", f"<@!{bot.user.id}>"]
        if mentions[0] == message.content or mentions[1] == message.content:
            async with bot.pool.acquire() as con:
                results = await con.fetch('''SELECT prefix FROM global_config WHERE guild_id = $1''', message.guild.id)
            if results[0].get('prefix'):
                prefix = results[0].get('prefix')
            else:
                prefix = [default_prefix]
            embed=discord.Embed(title=_("Beep Boop!"), description=_("My prefixes on this server are the following: `{prefix}`").format(prefix=", ".join(prefix)), color=0xfec01d)
            embed.set_thumbnail(url=bot.user.avatar_url)
            await message.reply(embed=embed)

        await bot.process_commands(message)
    else:
        pass #Ignore requests that would exceed rate-limits


#Run bot with token from .env
try :
    bot.run(TOKEN)
except KeyboardInterrupt :
    bot.loop.run_until_complete(bot.pool.close())
    bot.close()
