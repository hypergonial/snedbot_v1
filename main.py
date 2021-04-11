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
from difflib import get_close_matches
from itertools import chain
from pathlib import Path

import aiosqlite
import discord
from discord.ext import commands
from dotenv import load_dotenv

#Language
lang = "en"
#Is this build experimental?
experimentalBuild = True
#Version of the bot
currentVersion = "3.4.0c"
#Loading token from .env file. If this file does not exist, nothing will work.
load_dotenv()
#Get token from .env
TOKEN = os.getenv("TOKEN")
#Activity
activity = discord.Activity(name='Anno 9', type=discord.ActivityType.playing)
#Determines bot prefix & logging based on build state.
prefix = '!'
if experimentalBuild == True : 
    prefix = '?'
    logging.basicConfig(level=logging.INFO)
else :
    prefix = '!'
    logging.basicConfig(level=logging.INFO)

#This is just my user ID, used for setting up who can & cant use priviliged commands along with a server owner.
creatorID = 163979124820541440
#Can modify command prefix & intents here (and probably a lot of other cool stuff I am not aware of)
bot = commands.Bot(command_prefix=prefix, intents= discord.Intents.all(), owner_id=creatorID, case_insensitive=True, help_command=None, activity=activity, max_messages=20000)

#General global bot settings

#Database filename
dbName = "database.db"
#Database filepath
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
bot.dbPath = Path(BASE_DIR, dbName)
bot.localePath = Path(BASE_DIR, 'locale')
loop = asyncio.get_event_loop()
bot.db = loop.run_until_complete(aiosqlite.connect(bot.dbPath))
#bot.db = await aiosqlite.connect(bot.dbPath)
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
bot.currentVersion = currentVersion
bot.prefix = prefix
bot.lang = lang
bot.experimentalBuild = experimentalBuild
bot.recentlyDeleted = []
bot.recentlyEdited = []


#All extensions that are loaded on boot-up, change these to alter what modules you want (Note: These refer to filenames NOT cognames)
#Note: Without the extension admin_commands, most things will break, so I consider this a must-have. Remove at your own peril.
#Jishaku is a bot-owner only debug extension, requires 'pip install jishaku'.
initial_extensions = ['extensions.admin_commands', 'extensions.misc_commands', 'extensions.matchmaking', 'extensions.tags', 'extensions.setup', 'extensions.userlog', 'extensions.moderation', 'extensions.timers', 'jishaku']
#Contains all the valid datatypes in settings. If you add a new one here, it will be automatically generated
#upon a new request to retrieve/modify that datatype.
bot.datatypes = ["LOGCHANNEL", "ELEVATED_LOGCHANNEL",   #Used in module userlog
"COMMANDSCHANNEL", "ANNOUNCECHANNEL", "ROLEREACTMSG", "LFGROLE", "LFGREACTIONEMOJI",   #Used in module matchmaking
"KEEP_ON_TOP_CHANNEL", "KEEP_ON_TOP_MSG", #Used in module matchmaking & in main
"MOD_MUTEROLE"]  #Moderation & automod
#These text names are reserved and used for internal functions, other ones may get created by users for tags.
bot.reservedTextNames = ["KEEP_ON_TOP_CONTENT"]
#
#Error/warn messages
#
#Note: This contains strings for common error/warn msgs.

#Errors:
bot.errorColor = 0xff0000
bot.errorTimeoutTitle = "🕘 " + _("Error: Timed out.")
bot.errorTimeoutDesc = _("Your request has expired. Execute the command again!")
bot.errorDataTitle = "❌ " + _("Error: Invalid data entered.")
bot.errorDataDesc = _("Operation cancelled.")
bot.errorEmojiTitle = "❌ " + _("Error: Invalid reaction entered.")
bot.errorEmojiDesc = _("Operation cancelled.")
bot.errorFormatTitle = "❌ " + _("Error: Invalid format entered.")
bot.errorFormatDesc = _("Operation cancelled.")
bot.errorCheckFailTitle = "❌ " + _("Error: Insufficient permissions.")
bot.errorCheckFailDesc = _("Type `{prefix}help` for a list of available commands.").format(prefix=bot.prefix)
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


#Loading extensions from the list of extensions defined above
if __name__ == '__main__':
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            logging.error(f'Failed to load extension {extension}.', file=sys.stderr)
            traceback.print_exc()

#Simple function that just gets all currently loaded cog/extension names
def checkExtensions():
    extensions = []
    for cogName,cogClass in bot.cogs.items():
        extensions.append(cogName)
    return extensions
        
bot.checkExtensions = checkExtensions()

#Executes when the bot starts & is ready.
@bot.event
async def on_ready():
    logging.info("Initialized as {0.user}".format(bot))
    if bot.experimentalBuild == True :
        logging.warning("Experimental mode is enabled.")
        logging.info(f"Extensions loaded: {bot.checkExtensions}")


#
#DBHandler
#
#All helper functions relating to adding, updating, inserting, or removing from any table in the database
class DBhandler():
    #Deletes all data related to a specific guild, including but not limited to: all settings, priviliged roles, stored tags, stored multiplayer listings etc...
    #Warning! This also erases any stored warnings & other moderation actions for the guild
    async def deletedata(self, guildID):
        #The nuclear option
        await bot.db.execute("DELETE FROM settings WHERE guild_id = ?", [guildID])
        await bot.db.execute("DELETE FROM priviliged WHERE guild_id = ?", [guildID])
        await bot.db.execute("DELETE FROM stored_text WHERE guild_id = ?", [guildID])
        await bot.db.execute("DELETE FROM match_listings WHERE guild_id = ?", [guildID])
        await bot.db.execute("DELETE FROM users WHERE guild_id = ?", [guildID])
        await bot.db.commit()
        logging.warning(f"Settings have been reset and tags erased for guild {guildID}.")

    #Returns the priviliged roles for a specific guild as a list.
    async def checkprivs(self, guildID):
        cursor = await bot.db.execute("SELECT priviliged_role_id FROM priviliged WHERE guild_id = ?", [guildID])
        roleIDs = await cursor.fetchall()
        #Abstracting away the conversion from tuples
        roleIDs = [role[0] for role in roleIDs]
        return roleIDs
    #Inserts a priviliged role
    async def setpriv(self, roleID, guildID):
        await bot.db.execute("INSERT INTO priviliged (guild_id, priviliged_role_id) VALUES (?, ?)", [guildID, roleID])
        await bot.db.commit()
    #Deletes a priviliged role
    async def delpriv(self, roleID, guildID):
        await bot.db.execute("DELETE FROM priviliged WHERE guild_id = ? AND priviliged_role_id = ? ", [guildID, roleID])
        await bot.db.commit()
    #Modifies a value in settings relating to a guild
    async def modifysettings(self, datatype, value, guildID):
        if datatype in bot.datatypes :
        #Check if we have values for this guild
            cursor = await bot.db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", [guildID])
            result = await cursor.fetchone()
            if result != None :
                #Looking for the datatype
                cursor = await bot.db.execute("SELECT datatype FROM settings WHERE guild_id = ? AND datatype = ?", [guildID, datatype])
                result = await cursor.fetchone()
                #If the datatype does exist, we return the value
                if result != None :
                    #We update the matching record with our new value
                    await bot.db.execute("UPDATE settings SET guild_id = ?, datatype = ?, value = ? WHERE guild_id = ? AND datatype = ?", [guildID, datatype, value, guildID, datatype])
                    await bot.db.commit()
                    return
                #If it does not, for example if a new valid datatype is added to the code, we will create it, and assign it the value.
                else :
                    await bot.db.execute("INSERT INTO settings (guild_id, datatype, value) VALUES (?, ?, ?)", [guildID, datatype, value])
                    await bot.db.commit()
                    return
            #If no data relating to the guild can be found, we will create every datatype for the guild
            #Theoretically not necessary, but it outputs better into displaysettings()
            else :
                for item in bot.datatypes :
                    #We insert every datatype into the table for this guild.
                    await bot.db.execute("INSERT INTO settings (guild_id, datatype, value) VALUES (?, ?, 0)", [guildID, item])
                await bot.db.commit()
                #And then we update the value we wanted to change in the first place.
                await bot.db.execute("UPDATE settings SET guild_id = ?, datatype = ?, value = ? WHERE guild_id = ? AND datatype = ?", [guildID, datatype, value, guildID, datatype])
                await bot.db.commit()
                return
        else :
            #This is an internal error and indicates a coding error
            logging.critical(f"Invalid datatype called in DBHandler.modifysetting() (Called datatype: {datatype})")


    #Retrieves a setting for a specified guild.
    async def retrievesetting(self, datatype, guildID) :
        if datatype in bot.datatypes :
        #Check if we have values for this guild
            cursor = await bot.db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", [guildID])
            result = await cursor.fetchone()
            #If we do, we check if the datatype exists
            if result != None :
                #Looking for the datatype
                cursor = await bot.db.execute("SELECT datatype FROM settings WHERE guild_id = ? AND datatype = ?", [guildID, datatype])
                result = await cursor.fetchone()
                #If the datatype does exist, we return the value
                if result != None :
                    cursor = await bot.db.execute("SELECT value FROM settings WHERE guild_id = ? AND datatype = ?", [guildID, datatype])
                    #This is necessary as fetchone() returns it as a tuple of one element.
                    value = await cursor.fetchone()
                    return value[0]
                #If it does not, for example if a new valid datatype is added to the code, we will create it, then return 0.
                else :
                    await bot.db.execute("INSERT INTO settings (guild_id, datatype, value) VALUES (?, ?, 0)", [guildID, datatype])
                    await bot.db.commit()
                    return 0
            #If no data relating to the guild can be found, we will create every datatype for the guild, and return their value.
            #Theoretically not necessary, but it outputs better into displaysettings()
            else :
                for item in bot.datatypes :
                    #We insert every datatype into the table for this guild.
                    await bot.db.execute("INSERT INTO settings (guild_id, datatype, value) VALUES (?, ?, 0)", [guildID, item])
                await bot.db.commit()
                #And then we return error -1 to signal that there are no settings
                return -1
        else :
            #This is an internal error and indicates a coding error
            logging.critical(f"Invalid datatype called in DBHandler.retrievesetting() (Called datatype: {datatype})")

    #Should really be retrieveallsettings() but it is only used in !settings to display them to the users
    async def displaysettings(self, guildID) :
    #Check if there are any values stored related to the guild.
    #If this is true, guild settings exist.
        result = None
        cursor = await bot.db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", [guildID])
        result = await cursor.fetchone()
        #If we find something, we gather it, return it.
        if result != None :
            #This gets datapairs in a tuple, print it below if you want to see how it looks
            cursor = await bot.db.execute("SELECT datatype, value FROM settings WHERE guild_id = ?", [guildID])
            dbSettings = await cursor.fetchall()
            #The array we will return to send in the message
            settings = []
            #Now we just combine them.
            i = 0
            for i in range(len(dbSettings)) :
                settings.append(f"{dbSettings[i][0]} = {dbSettings[i][1]} \n")
                i += 1
            return settings
        #If not, we return error code -1, corresponding to no settings.
        else:
            return -1
    #Retrieves a piece of stored text inside table stored_text (Mostly used for tags)
    async def retrievetext(self, textname, guildID) :
        
        #Check if we have values for this guild
        #Check for the desired text
        cursor = await bot.db.execute("SELECT text_name FROM stored_text WHERE guild_id = ? AND text_name = ?", [guildID, textname])
        result = await cursor.fetchone()
        #If the datatype does exist, we return the value
        if result != None :
            cursor = await bot.db.execute("SELECT text_content FROM stored_text WHERE guild_id = ? AND text_name = ?", [guildID, textname])
            result = await cursor.fetchone()
            #This is necessary as fetchone() returns it as a tuple of one element.
            return result[0]
        #If it does not exist, return None
        else :
            return None
    #Stores a piece of text inside table stored_text for later use
    async def storetext(self, textname, textcontent, guildID):
        #Check if we have values for this guild
        #Check for the desired text
        cursor = await bot.db.execute("SELECT text_name FROM stored_text WHERE guild_id = ? AND text_name = ?", [guildID, textname])
        result = await cursor.fetchone()
        #Updating value if it exists
        if result != None :
            await bot.db.execute("UPDATE stored_text SET guild_id = ?, text_name = ?, text_content = ? WHERE guild_id = ? AND text_name = ?", [guildID, textname, textcontent, guildID, textname])
            await bot.db.commit()
        #If it does not exist, insert it
        else :
            await bot.db.execute("INSERT INTO stored_text (guild_id, text_name, text_content) VALUES (?, ?, ?)", [guildID, textname, textcontent])
            await bot.db.commit()
    #Deletes a single text entry
    async def deltext(self, textname, guildID):
        await bot.db.execute("DELETE FROM stored_text WHERE text_name = ? AND guild_id = ?", [textname, guildID])
        await bot.db.commit()
        return
    #Get all tags for a guild (Get all text that is not reserved)
    async def getTags(self, guildID):
        cursor = await bot.db.execute("SELECT text_name FROM stored_text WHERE guild_id = ?", [guildID])
        results = await cursor.fetchall()
        #Fix for tuples
        results = [result[0] for result in results]
        #Remove reserved stuff
        for result in results :
            if result in bot.reservedTextNames :
                results.remove(result)
        return results
    #Handling the match_listings table - specific to matchmaking extension
    async def addListing(self, ID, ubiname, hostID, gamemode, playercount, DLC, mods, timezone, additional_info, timestamp, guildID):
            await bot.db.execute("INSERT INTO match_listings (ID, ubiname, hostID, gamemode, playercount, DLC, mods, timezone, additional_info, timestamp, guild_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [ID, ubiname, hostID, gamemode, playercount, DLC, mods, timezone, additional_info, timestamp, guildID])
            await bot.db.commit()
            return
    async def delListing(self, ID, guildID):
        await bot.db.execute("DELETE FROM match_listings WHERE ID = ? AND guild_id = ?", [ID, guildID])
        await bot.db.commit()
        return
    #Retrieve every information about a single listing
    async def retrieveListing(self, ID, guildID):
        cursor = await bot.db.execute("SELECT * FROM match_listings WHERE ID = ? AND guild_id = ?", [ID, guildID])
        listing = await cursor.fetchone()
        if listing == None :
            return
        listingDict = {
            "ID": listing[0],
            "ubiname": listing[1],
            "hostID": listing[2],
            "gamemode": listing[3],
            "playercount": listing[4],
            "DLC": listing[5],
            "mods": listing[6],
            "timezone": listing[7],
            "additional_info": listing[8],
            "timestamp": listing[9],
            "guild_id": listing[10]
        }
        return listingDict
    #Retrieve every information about every listing stored
    async def retrieveAllListings(self):
        cursor = await bot.db.execute("SELECT * FROM match_listings")
        results = await cursor.fetchall()
        ID, ubiname, hostID, gamemode, playercount, DLC, mods, timezone, additional_info, timestamp, guild_id = ([] for i in range(11))
        for listing in results :
            ID.append(listing[0])
            ubiname.append(listing[1])
            hostID.append(listing[2])
            gamemode.append(listing[3])
            playercount.append(listing[4])
            DLC.append(listing[5])
            mods.append(listing[6])
            timezone.append(listing[7])
            additional_info.append(listing[8])
            timestamp.append(listing[9])
            guild_id.append(listing[10])
        listings = {
            "ID": ID,
            "ubiname": ubiname,
            "hostID": hostID,
            "gamemode": gamemode,
            "playercount": playercount,
            "DLC": DLC,
            "mods": mods,
            "timezone": timezone,
            "additional_info": additional_info,
            "timestamp": timestamp,
            "guild_id": guild_id
        }
        return listings
    
    async def createUser(self, userID, guildID, flags=None, warns=0, is_muted=0, notes=None): #Creates an empty user, or you can specify attributes (but you should not)
        await bot.db.execute("INSERT INTO users (user_id, flags, warns, is_muted, notes, guild_id) VALUES (?, ?, ?, ?, ?, ?)", [userID, flags, warns, is_muted, notes, guildID])
        await bot.db.commit()


    async def getUser(self, userID, guildID): #Gets a single user from the db
        cursor = await bot.db.execute("SELECT * FROM users WHERE user_id = ? AND guild_id = ?", [userID, guildID])
        result = await cursor.fetchone()
        if result:
            user = {
                "user_id": result[0],
                "flags": result[1],
                "warns": result[2],
                "is_muted": result[3],
                "notes": result[4],
                "guild_id": result[5]
            }
            return user
        else:
            await self.createUser(userID, guildID) #If the user does not exist, we create an empty entry for them, then repeat the get request
            return await self.getUser(userID, guildID) #Recursion yay (I am immature)
    
    async def getAllGuildUsers(self, guildID):
        cursor = await bot.db.execute("SELECT * FROM users WHERE guild_id = ?", [guildID])
        results = await cursor.fetchall()
        if results:
            userID, flags, warns, is_muted, notes, guild_id = ([] for i in range(6))
            for result in results:
                userID.append(result[0])
                flags.append(result[1])
                warns.append(result[2])
                is_muted.append(result[3])
                notes.append(result[4])
                guild_id.append(result[5])
            users = {
                "user_id": userID,
                "flags": flags,
                "warns": warns,
                "is_muted": is_muted,
                "notes": notes,
                "guild_id": guild_id
            }
            return users
    
    async def updateUser(self, userID, field, value, guildID): #Update a user's specific attribute
        valid_fields=["flags", "warns", "is_muted", "notes"] #This should prevent SQL Injection, and accidental data writes/errors
        if field not in valid_fields:
            logging.critical(f"DBHandler.updateUser referenced invalid field: {field}")
            return
        if await self.getUser(userID, guildID):
            await bot.db.execute(f"UPDATE users SET {field} = ? WHERE user_id = ? AND guild_id = ?", [value, userID, guildID])
            #Printing the same thing in console
            await bot.db.commit()
        else:
            print("User not found, creating")
            self.createUser(userID, guildID) #Create the user
            await bot.db.execute(f"UPDATE users SET {field} = ? WHERE user_id = ? AND guild_id = ?", [value, userID, guildID])
            await bot.db.commit()



#The main instance of DBHandler
bot.DBHandler = DBhandler()

#The custom help command subclassing the dpy one. See the docs or this guide (https://gist.github.com/InterStella0/b78488fb28cadf279dfd3164b9f0cf96) on how this was made.
class SnedHelp(commands.HelpCommand):
    #Method to get information about a command to display in send_bot_help
    def get_command_signature(self, command):
        return '`{prefix}{command}` - {commandbrief}'.format(prefix=self.clean_prefix, command=command.name, commandbrief=command.short_doc) #short_doc goes to brief first, otherwise gets first line of help
    
    #Send generic help message with all commands included
    async def send_bot_help(self, mapping):
        ctx = self.context   #Obtaining ctx
        help_embed = discord.Embed(title="⚙️ " + _("__Available commands:__"), description=_("You can also use `{prefix}help <command>` to get more information about a specific command.").format(prefix=self.clean_prefix), color=bot.embedBlue)
        #We retrieve all the commands from the mapping of cog,commands
        for cog, commands in mapping.items(): 
            filtered = await self.filter_commands(commands, sort=True)   #This will filter commands to those the user can actually execute
            command_signatures = [self.get_command_signature(command) for command in filtered]   #Get command signature in format as specified above
            #If we have any, put them in categories according to cogs, fallback is "Other"
            if command_signatures:
                cog_name = getattr(cog, "qualified_name", "Other")
                help_embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)
            #Put fancy footer on it
            help_embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        channel=self.get_destination() #Print it out
        await channel.send(embed=help_embed)

    async def send_command_help(self, command):
        ctx = self.context   #Obtaining ctx
        detail_embed=discord.Embed(title="⚙️ " + _("Command: {prefix}{command}").format(prefix=self.clean_prefix, command=command.name), color=bot.embedBlue)
        if command.description:
            detail_embed.add_field(name=_("Description:"), value=command.description)  #Getting command description
        elif command.help:
            detail_embed.add_field(name=_("Description:"), value=command.help)  #Fallback to help attribute if description does not exist
        if command.usage:
            detail_embed.add_field(name=_("Usage:"), value=f"`{self.clean_prefix}{command.usage}`", inline=False) #Getting command usage & formatting it
        aliases = []
        for alias in command.aliases:
            aliases.append(f"`{self.clean_prefix}{alias}`")  #Adding some custom formatting to each alias
        if aliases:
            detail_embed.add_field(name=_("Aliases:"), value=", ".join(aliases), inline=False)   #If any aliases exist, we add those to the embed in new field
        detail_embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        channel = self.get_destination()   #Send it to destination
        await channel.send(embed=detail_embed)

    async def send_cog_help(self, cog):
        #I chose not to implement help for cogs, but if you want to do something, do it here
        ctx = self.context
        embed=discord.Embed(title=bot.unknownCMDstr, description=_("Use `{prefix}help` for a list of available commands.").format(prefix=prefix), color=bot.unknownColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_group_help(self, group):
        await self.send_command_help(group) #I chose not to implement any custom features for groups, they just get command help retrieved

    async def send_error_message(self, error):   #Overriding the default help error message
        ctx = self.context
        embed=discord.Embed(title=bot.unknownCMDstr, description=_("Use `{prefix}help` for a list of available commands.").format(prefix=prefix), color=bot.unknownColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        channel = self.get_destination()
        await channel.send(embed=embed)

#Assign custom help command to bot
bot.help_command = SnedHelp()

#
#
#Error handler
#
#
#Generic error handling. Will catch all otherwise not handled errors
@bot.event
async def on_command_error(ctx, error):
    #This gets sent whenever a user has insufficient permissions to execute a command.
    if isinstance(error, commands.CheckFailure):
        logging.info(f"{ctx.author} tried calling a command but did not meet checks.")
        embed=discord.Embed(title=bot.errorCheckFailTitle, description=bot.errorCheckFailDesc, color=bot.errorColor)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
    elif isinstance(error, commands.CommandNotFound):
        logging.info(f"{ctx.author} tried calling a command but the command was not found. ({ctx.message.content})")
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
            embed=discord.Embed(title=bot.unknownCMDstr, description=_("Did you mean `{prefix}{match}`?").format(prefix=prefix, match=matches[0]), color=bot.unknownColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
        elif len(aliasmatches) > 0:
            embed=discord.Embed(title=bot.unknownCMDstr, description=_("Did you mean `{prefix}{match}`?").format(prefix=prefix, match=aliasmatches[0]), color=bot.unknownColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
        else:
            embed=discord.Embed(title=bot.unknownCMDstr, description=_("Use `{prefix}help` for a list of available commands.").format(prefix=prefix), color=bot.unknownColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
    #Cooldown error
    elif isinstance(error, commands.CommandOnCooldown):
        embed=discord.Embed(title=bot.errorCooldownTitle, description=_("Please retry in: `{cooldown}`").format(cooldown=datetime.timedelta(seconds=round(error.retry_after))), color=bot.errorColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
    #MissingArg error
    elif isinstance(error, commands.MissingRequiredArgument):
        embed=discord.Embed(title="❌" + _("Missing argument."), description=_("One or more arguments are missing. \n__Hint:__ You can use `{prefix}help {command_name}` to view command usage.").format(prefix=prefix, command_name=ctx.command.name), color=bot.errorColor)
        embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
        logging.info(f"{ctx.author} tried calling a command ({ctx.message.content}) but did not supply sufficient arguments.")
    #MaxConcurrencyReached error
    elif isinstance(error, commands.MaxConcurrencyReached):
            embed = discord.Embed(title=bot.errorMaxConcurrencyReachedTitle, description=bot.errorMaxConcurrencyReachedDesc, color=bot.errorColor)
            embed.set_footer(text=bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            await ctx.channel.send(embed=embed)

    else :
        #If no known error has been passed, we will print the exception to console as usual
        #IMPORTANT!!! If you remove this, your command errors will not get output to console.
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

#Executed on any command attempt
@bot.event
async def on_command(ctx):
    logging.info(f"{ctx.author} called command {ctx.message.content}")
#
# Guild Join/Leave behaviours
#
#Triggered when bot joins a new guild
@bot.event
async def on_guild_join(guild):
    #This forces settings to generate for this guild.
    await bot.DBHandler.retrievesetting("COMMANDSCHANNEL", guild.id)
    if guild.system_channel != None :
        embed=discord.Embed(title=_("Beep Boop!"), description=_("I have been summoned to this server. Use `{prefix}help` to see what I can do!").format(prefix=prefix), color=0xfec01d)
        embed.set_thumbnail(url=bot.user.avatar_url)
        await guild.system_channel.send(embed=embed)
    logging.info(f"Bot has been added to new guild {guild.id}.")

#Triggered when bot leaves guild, or gets kicked/banned, or guild gets deleted.
@bot.event
async def on_guild_remove(guild):
    #Erase all settings for this guild on removal to keep the db tidy.
    await bot.DBHandler.deletedata(guild.id)
    logging.info(f"Bot has been removed from guild {guild.id}, correlating data erased.")

#Keep-On-Top message functionality (Requires setup extension to be properly set up)
@bot.event
async def on_message(message):
    #Check if we are in a guild to avoid exceptions
    if message.guild != None:
        topChannelID = await bot.DBHandler.retrievesetting("KEEP_ON_TOP_CHANNEL", message.guild.id)
        if message.channel.id == topChannelID:
            keepOnTopContent = await bot.DBHandler.retrievetext("KEEP_ON_TOP_CONTENT", message.guild.id)
            if keepOnTopContent != message.content :
                #Get rid of previous message
                previousTop = await message.channel.fetch_message(await bot.DBHandler.retrievesetting("KEEP_ON_TOP_MSG", message.guild.id))
                await previousTop.delete()
                #Send new message
                newTop = await message.channel.send(keepOnTopContent)
                #Set the id to keep the ball rolling
                await bot.DBHandler.modifysettings("KEEP_ON_TOP_MSG", newTop.id, newTop.guild.id)
        elif topChannelID == None :
            logging.warning("Settings not found.")
        #This is necessary, otherwise bot commands will break because on_message would override them
    await bot.process_commands(message)


#Run bot with token from .env
try :
    bot.run(TOKEN)
except KeyboardInterrupt :
    pass
