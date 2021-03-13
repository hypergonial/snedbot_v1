import discord
import time
import threading
from discord.ext import commands
import logging
import asyncio
import os
import shutil
from dotenv import load_dotenv
import aiosqlite
from difflib import get_close_matches
import sys
import traceback
from itertools import chain
import datetime


#Loading token from .env file. If this file does not exist, nothing will work.
load_dotenv()
#Get token from .env
TOKEN = os.getenv("TOKEN")
#Database name/path
dbName = "database.db"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dbPath = os.path.join(BASE_DIR, dbName)
#Current version
currentVersion = "2.2.1"
#Is this build experimental?
experimentalBuild = False
#Bot commands prefix
prefix = '!'


#Determining the bot prefix & logging based on the build state.
if experimentalBuild == True : 
    prefix = '?'
    logging.basicConfig(level=logging.DEBUG)
else :
    prefix = '!'
    logging.basicConfig(level=logging.INFO)

#This is just my user ID, used for setting up who can & cant use priviliged commands along with a server owner.
creatorID = 163979124820541440
#Can modify command prefix & intents here (and probably a lot of other cool stuff I am not aware of)
bot = commands.Bot(command_prefix=prefix, intents= discord.Intents.all(), owner_id=creatorID, case_insensitive=True, help_command=None)

print("[INFO]: New Session Started.")

#Contains all the valid datatypes in settings. If you add a new one here, it will be automatically generated
#upon a new request to retrieve/modify that datatype.
datatypes = ["COMMANDSCHANNEL", "ANNOUNCECHANNEL", "ROLEREACTMSG", "LFGROLE", "LFGREACTIONEMOJI"]

#Overriding the default help command
#I actually have very little clue as to how this work, but it does, so it should be fine(tm)


#Executes when the bot starts & is ready.
@bot.event
async def on_ready():
    #Presence setup
    activity = discord.Activity(name='you', type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)
    print("[INFO]: Initialized as {0.user}".format(bot))
    if experimentalBuild == True :
        print("[WARN]: Experimental mode is enabled.")
#
#Error/warn messages
#
#Note: This contains strings for common error/warn msgs.

#Errors:
errorColor = 0xff0000
errorTimeoutTitle = "🕘 Error: Timed out."
errorTimeoutDesc = "Your request has expired. Execute the command again!"
errorDataTitle = "❌ Error: Invalid data entered."
errorDataDesc = "Operation cancelled."
errorEmojiTitle = "❌ Error: Invalid reaction entered."
errorEmojiDesc = "Operation cancelled."
errorFormatTitle = "❌ Error: Invalid format entered."
errorFormatDesc = "Operation cancelled."
errorCheckFailTitle = "❌ Error: Insufficient permissions."
errorCheckFailDesc = f"Type `{prefix}help` for a list of available commands."
errorCooldownTitle = "🕘 Error: This command is on cooldown."
#Warns:
warnColor = 0xffcc4d
warnDataTitle = "⚠️ Warning: Invalid data entered."
warnDataDesc = "Please check command usage."
warnEmojiTitle = "⚠️ Warning: Invalid reaction entered."
warnEmojiDesc = "Please enter a valid reaction."
warnFormatTitle = "⚠️ Warning: Invalid format entered."
warnFormatDesc = "Please try entering valid data."

#
#Normal commands
#
#Note: These commands can be used by everyone on the server.

#Custom help command, shows all commands a user can execute based on their priviliges.
#Also has an alternate mode where it shows information about a specific command, if specified as an argument.
@bot.command(brief="Displays this help message.", description="Displays all available commands you can execute, based on your permission level.", usage=f"{prefix}help [command]")
async def help(ctx, commandname : str=None):
    #Retrieve all commands except hidden, unless user is priviliged.
    
    #Direct copy of hasPriviliged()
    #If user is priviliged, get all commands, including hidden ones, otherwise just the not hidden ones.

    #Note: checkprivs() returns a list of tuples as roleIDs
    userRoles = [role.id for role in ctx.author.roles]
    privroles = [role[0] for role in await checkprivs(ctx.guild.id)]
    
    #Determine how many commands and associated details we need to retrieve, then retrieve them.
    if any(roleID in userRoles for roleID in privroles) or (ctx.author.id == creatorID or ctx.author.id == ctx.guild.owner_id) :
        cmds = [cmd.name for cmd in bot.commands]
        briefs = [cmd.brief for cmd in bot.commands]
        allAliases = [cmd.aliases for cmd in bot.commands]
    else :
        cmds = [cmd.name for cmd in bot.commands if not cmd.hidden]
        briefs = [cmd.brief for cmd in bot.commands if not cmd.hidden]
        allAliases = [cmd.aliases for cmd in bot.commands if not cmd.hidden]
    i = 0
    #Note: allAliases is a matrix of multiple lists, this will convert it into a singular list
    aliases = list(chain(*allAliases))
    helpFooter=f"Requested by {ctx.author.name}#{ctx.author.discriminator}"
    if commandname == None :
        formattedmsg = []
        i = 0
        formattedmsg.append(f"You can also use `{prefix}help <command>` to get more information about a specific command. \n \n")
        for i in range(len(cmds)) :
            if briefs[i] != None :
                formattedmsg.append(f"`{prefix}{cmds[i]}` - {briefs[i]} \n")
            else :
                formattedmsg.append(f"`{prefix}{cmds[i]}` \n")

        final = "".join(formattedmsg)
        embed=discord.Embed(title="⚙️ __Available commands:__", description=final, color=0x009dff)
        embed.set_footer(text=helpFooter, icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
        return
    else :
        #Oh no, you found me o_o
        if commandname == "Hyper" :
            embed=discord.Embed(title="❓ I can't...", description=f"I am sorry, but he can't be helped. He is beyond redemption.", color=0xbe1931)
            embed.set_footer(text="Requested by a stinky person.", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
            return
        #If our user is a dumbass and types ?help ?command instead of ?help command, we will remove the prefix from it first
        if commandname.startswith(prefix) :
            #Remove first character
            commandname = commandname[0 : 0 : ] + commandname[0 + 1 : :]
        #If found, we will try to retrieve detailed command information about it, and provide it to the user.
        if commandname in cmds or commandname in aliases :
            command = bot.get_command(commandname)
            if len(command.aliases) > 0 :
                #Add the prefix to the aliases before displaying
                commandaliases = ["`" + prefix + alias + "`" for alias in command.aliases]
                #Then join them together
                commandaliases = ", ".join(commandaliases)
                embed=discord.Embed(title=f"⚙️ Command: {prefix}{command.name}", description=f"{command.description} \n \n**Usage:** `{command.usage}` \n**Aliases:** {commandaliases}", color=0x009dff)
                embed.set_footer(text=helpFooter, icon_url=ctx.author.avatar_url)
                await ctx.send(embed=embed)
                return
            else :
                command = bot.get_command(commandname)
                embed=discord.Embed(title=f"⚙️ Command: {prefix}{command.name}", description=f"{command.description} \n \n**Usage:** `{command.usage}`", color=0x009dff)
                embed.set_footer(text=helpFooter, icon_url=ctx.author.avatar_url)
                await ctx.send(embed=embed)
                return
        else :
            embed=discord.Embed(title="❓ Unknown command!", description=f"Use `{prefix}help` for a list of available commands.", color=0xbe1931)
            embed.set_footer(text=helpFooter, icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
            return



#Gets the ping of the bot.
@bot.command(brief="Displays bot ping.", description="Displays the current ping of the bot in miliseconds. Takes no arguments.", usage=f"{prefix}ping")
async def ping(ctx):
    embed=discord.Embed(title="🏓 Pong!", description=f"Latency: `{round(bot.latency * 1000)}ms`", color=0xffffff)
    embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
    await ctx.channel.send(embed=embed)

#A more fun way to get the ping.
@bot.command(hidden = True, brief="A better way to get the ping.", description="Why? because yes. Displays the current ping of the bot in miliseconds. Takes no arguments.", usage=f"{prefix}LEROY")
async def leroy(ctx):
    embed=discord.Embed(title="JEEEEENKINS!", description=f"... Oh my god he just ran in. 👀 `{round(bot.latency * 1000)}ms`", color =0xffffff)
    embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
    await ctx.channel.send(embed=embed)

@bot.command(brief="Displays information about the bot.", description="Displays information about the bot. Takes no arguments.", usage=f"{prefix}about")
async def about(ctx):
    embed=discord.Embed(title=f"ℹ️ About {bot.user.name}", description=f"**Version:** {currentVersion} \n**Made by:** Hyper#0001 \n**GitHub:** https://github.com/HyperGH/AnnoSnedBot", color=0x009dff)
    embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
    embed.set_thumbnail(url=bot.user.avatar_url)
    await ctx.channel.send(embed=embed)

@bot.command(brief="Displays a user's avatar.", description="Displays a user's avatar for your viewing (or stealing) pleasure.", usage=f"{prefix}avatar <userID|userMention|userName>")
@commands.cooldown(1, 30, type=commands.BucketType.member)
async def avatar(ctx, member : discord.Member) :
    embed=discord.Embed(title=f"{member.name}'s avatar:")
    embed.set_image(url=member.avatar_url)
    embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
    await ctx.channel.send(embed=embed)

@avatar.error
async def avatar_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.MemberNotFound) :
        embed=discord.Embed(title="❌ Unable to find user.", description="Please check if you typed everything correctly, then try again.", color=errorColor)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)


#Command to initalize matchmaking.
#This is the main command of the bot, and is by far the most complicated one.
#The TL;DR version of this command is the following: It DMs the user, asks them some questions,
#evaluates the answers based on some criteria, then use those answers to construct a formatted
#multiplayer listing, which will then in turn go into a preconfigured channel. It will also ping a
#designated role if set. Can be limited as to which channels it can be run from via the COMMANDSCHANNEL setting.
@bot.command(brief="Start setting up a new multiplayer listing.", description="Start matchmaking! After command execution, you will receive a direct message to help you set up a multiplayer listing! Takes no arguments.", aliases=['multiplayer', 'init', 'match','multi','mp'], usage=f"{prefix}matchmaking")
@commands.guild_only()
@commands.max_concurrency(1, per=commands.BucketType.user,wait=False)
@commands.cooldown(1, 43200, type=commands.BucketType.member)
async def matchmaking(ctx):
    cmdchannel = await retrievesetting("COMMANDSCHANNEL", ctx.guild.id)
    #Performs check if the command is executed in the right channel, if this is 0, this feature is disabled.
    if cmdchannel != 0 :
        if cmdchannel != ctx.channel.id :
            print("[WARN]: Matchmaking initiated in disabled channel.")
            return
    mpsessiondata = []
    mpEmbedColor = 0xd76b00
    #This should be a list of all the names of the functions below
    #Note: The questions will be asked in this order specified here, change it here to change the order. confirmlisting must be last.
    #Scroll to the bottom of the command scope to see how & where this is used.
    qtypes = ["UbiName", "GameMode", "PlayerCount", "DLC", "Mods", "TimeZone", "Additional", "ConfirmListing"]
    #Messaging the channel to provide feedback
    #It sends these seperately to ideally grab the user's attention, but can be merged.
    embed=discord.Embed(title="**Starting matchmaking...**", description=f"Started matchmaking for **{ctx.author.name}#{ctx.author.discriminator}**. Please check your DMs!", color=mpEmbedColor)
    embed.set_footer(text="If you didn't receive a DM, make sure you have direct messages enabled from server members.")
    await ctx.channel.send(embed=embed)
    embed=discord.Embed(title="**Hello!**", description="I will help you set up a new multiplayer listing!  Follow the steps below! Note: You can edit your submission in case you made any errors!", color=mpEmbedColor)
    embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/203158031511453696/446da0b60a670b6866cd463fb5e87195.png?size=1024")
    await ctx.author.send(embed=embed)

    #Custom function to add or modify a value in the listing values.
    async def modifymatchmaking(qType, data, isModifying):
        #If we are modifying, we will get where we need to modify the value, and we make the correction.
        if isModifying == True :
            index = qtypes.index(qType)
            mpsessiondata[index] = data
        #Otherwise append
        elif isModifying == False :
            mpsessiondata.append(data)

    #The question function, specify a questionType, and if you are modifying or not.
    async def ask(qType, isModifying):
        if qType == "UbiName" :
            embed=discord.Embed(title="Ubisoft Connect username", description="Please type in your Ubisoft Connect username!", color=mpEmbedColor)
            embed.set_footer(text="Note: Maximum length is 32 characters")
            msg = await ctx.author.send(embed=embed)
            def usernamecheck(payload):
                return payload.author == ctx.author and payload.guild is None
            try:
                payload = await bot.wait_for('message', timeout=300.0, check=usernamecheck)
                #32char username limit
                if len(payload.content) > 32 :
                    await msg.delete()
                    embed=discord.Embed(title=warnDataTitle, description="Username too long. Maximum 32 characters", color=warnColor)
                    await ctx.author.send(embed=embed)
                    return -2
                else :
                    await modifymatchmaking(qType, payload.content, isModifying)
                    embed=discord.Embed(title="✅ Username set.", description=f"Your Ubisoft Connect username is: **{payload.content}**", color=mpEmbedColor)
                    await ctx.author.send(embed=embed)
                    return 0

            except:
                embed = discord.Embed(title=errorTimeoutTitle, description=errorTimeoutDesc, color=errorColor)
                await ctx.author.send(embed=embed)
                return -1
        if qType == "GameMode" :
            embed=discord.Embed(title="Should this match be a PvP or Co-Op match?", description="⚔️ - PvP (Player versus Player) \n 🛡️ - Co-Op (Cooperative)", color=mpEmbedColor)
            embed.set_footer(text="React below with your choice!")
            msg = await ctx.author.send(embed=embed)
            #Add two reactions to this message
            await msg.add_reaction("⚔️")
            await msg.add_reaction("🛡️")

            #We check if the message ID is the same, so this is not a different message.
            #We also check if the user who reacted was the user who sent the command.
            gameModeEmojies = ["🛡️", "⚔️"]
            def gamemodecheck(payload):
                return payload.message_id == msg.id and payload.user_id == ctx.author.id
            try:
                payload = await bot.wait_for('raw_reaction_add', timeout=300.0, check=gamemodecheck)

                #Check reaction emoji
                if str(payload.emoji) == "⚔️":
                    gamemode = "PvP"
                    
                elif str(payload.emoji) == "🛡️":
                    gamemode = "Co-Op"
                
                elif str(payload.emoji) not in gameModeEmojies:
                    await msg.delete()
                    embed = discord.Embed(title=warnEmojiTitle, description=warnEmojiDesc , color=warnColor)
                    await ctx.author.send(embed=embed)
                    return -2

                #Save it to list
                await modifymatchmaking(qType, gamemode, isModifying)
                
                embed=discord.Embed(title="✅ Gamemode set.", description=f"Your gamemode is set to:  **{gamemode}**.", color=mpEmbedColor)
                await ctx.author.send(embed=embed)
                return 0
            except asyncio.TimeoutError:
                embed = discord.Embed(title=errorTimeoutTitle
            , description=errorTimeoutDesc, color=errorColor)
                await ctx.author.send(embed=embed)
                return -1
        if qType == "PlayerCount" :
            embed=discord.Embed(title="How many players you want to play with?", description="2️⃣ - 2 players \n 3️⃣ - 3 players \n 4️⃣ - 4 players \n ♾️ - 5 or more players", color=mpEmbedColor)
            msg = await ctx.author.send(embed=embed)
            #Saving the ID of this message we just sent
            msgid = msg.id
            playersEmoji =["2️⃣", "3️⃣", "4️⃣", "♾️"]
            playersOptions =["2", "3", "4", "5 or more"]
            for emoji in playersEmoji :
                await msg.add_reaction(emoji)

            #We check if the message ID is the same, so this is not a different message.
            #We also check if the user who reacted was the user who sent the command.
            def playercountcheck(payload):
                return payload.message_id == msgid and payload.user_id == ctx.author.id
            try:
                payload = await bot.wait_for('raw_reaction_add', timeout=300.0, check=playercountcheck)
                i = 0
                playernum = "[DefaultCount] If you see this, something is very wrong..."
                #Check if emoj is invalid, otherwise check for match & break on match
                while i != len(playersOptions):
                    if str(payload.emoji) not in playersEmoji :
                        await msg.delete()
                        embed = discord.Embed(title=warnEmojiTitle, description=warnEmojiDesc, color=warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                    elif str(payload.emoji) == playersEmoji[i]:
                        playernum = playersOptions[i]
                        await msg.delete()
                        break
                    i += 1
                
                await modifymatchmaking(qType, playernum, isModifying)
                embed=discord.Embed(title="✅ Number of players set.", description=f"Number of players: **{playernum}**", color=mpEmbedColor)
                await ctx.author.send(embed=embed)
                return 0
            except asyncio.TimeoutError:
                embed = discord.Embed(title=errorTimeoutTitle, description=errorTimeoutDesc, color=errorColor)
                await ctx.author.send(embed=embed)
                return -1
        if qType == "DLC" :
            embed=discord.Embed(title="Now react with the symbol of **all** the DLCs you want to use! Click the green checkmark (✅) once done!", description=" 🔥 - The Anarchist \n 🤿 - Sunken Treasures \n 🌹 - Botanica \n ❄️ - The Passage \n 🏛️ - Seat of Power \n 🚜 - Bright Harvest \n 🦁 - Land of Lions \n ⚓ - Docklands", color=mpEmbedColor)
            embed.set_footer(text="Note: If you do not own any DLC, just simply press ✅ to continue.")
            msg = await ctx.author.send(embed=embed)
            #Add to the list of DLC here. Note: the emojies & DLC must be in the same order, & a green tick must be at the end of emojies. 
            DLCemojies = ["🔥", "🤿", "🌹", "❄️", "🏛️", "🚜", "🦁", "⚓", "✅"]
            allDLCs = ["The Anarchist", "Sunken Treasures", "Botanica", "The Passage", "Seat of Power", "Bright Harvest", "Land of Lions", "Docklands" ]
            for emoji in DLCemojies :
                await msg.add_reaction(emoji)
            DLC = []
            #We check if the message ID is the same, so this is not a different message.
            #We also check if the user who reacted was the user who sent the command.
            def confirmDLCcheck(payload):
                return payload.message_id == msg.id and payload.user_id == ctx.author.id and str(payload.emoji) == "✅"
            try:
                payload = await bot.wait_for('raw_reaction_add', timeout=300.0, check=confirmDLCcheck)
                #We have to fetch here otherwise reaction counting does not work for some reason..?
                msg = await ctx.author.fetch_message(msg.id)
                #Count all the emojies
                i = 0
                while i != len(allDLCs) :
                    #If emoji is invalid, we re-run question    
                    if str(msg.reactions[i]) not in DLCemojies :
                        await msg.delete()
                        embed = discord.Embed(title=warnEmojiTitle, description=warnEmojiDesc, color=warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                    #Otherwise we add to the list of DLC
                    elif msg.reactions[i].count == 2 :
                        DLC.append(allDLCs[i])
                    i += 1
                #We can override this field so it is easier to read
                if len(DLC) == 8:
                    DLC = "All"
                elif len(DLC) == 0:
                    DLC = "None"
                else :
                    DLC = ", ".join(DLC)
                await modifymatchmaking(qType, DLC, isModifying)
                await msg.delete()
                embed=discord.Embed(title="✅ DLC set.", description=f"Your DLC for this match: {DLC}", color=mpEmbedColor)
                await ctx.author.send(embed=embed)
                return 0

            except asyncio.TimeoutError:
                embed = discord.Embed(title=errorTimeoutTitle, description=errorTimeoutDesc, color=errorColor)
                await ctx.author.send(embed=embed)
                return -1

        if qType == "Mods" :
            #Add msg
            embed=discord.Embed(title="Are you going to use mods in this match?", description="React below with your response!", color=mpEmbedColor)
            embed.set_footer(text="Note: Mods are not officially supported. All participants must share the same mods to play together. Please share the mods you use at the end of the form. ")
            msg = await ctx.author.send(embed=embed)
            #Add emoji
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            modemojies = ["✅", "❌"]

            def modcheck(payload):
                return payload.message_id == msg.id and payload.user_id == ctx.author.id
            try:
                payload = await bot.wait_for('raw_reaction_add', timeout=300.0, check=modcheck)
                #Check reaction emoji
                if str(payload.emoji) == "✅":
                    modded = "Yes"
                elif str(payload.emoji) == "❌":
                    modded = "No"
                
                elif str(payload.emoji) not in modemojies :
                    await msg.delete()
                    embed = discord.Embed(title=warnEmojiTitle, description=warnEmojiDesc, color=warnColor)
                    await ctx.author.send(embed=embed)
                    return -2
                
                await modifymatchmaking(qType, modded, isModifying)
                await msg.delete()
                embed=discord.Embed(title="✅ Mods set.", description=f"Modded: **{modded}**", color=mpEmbedColor)
                await ctx.author.send(embed=embed)
                return 0

            except asyncio.TimeoutError:
                embed = discord.Embed(title=errorTimeoutTitle, description=errorTimeoutDesc, color=errorColor)
                await ctx.author.send(embed=embed)
                return -1
        
        if qType == "TimeZone" :
            embed=discord.Embed(title="Specify your timezone as an UTC offset!", description="For example: If your timezone is UTC+1, **type in 1!**", color=mpEmbedColor)
            embed.set_footer(text="If you are unsure what timezone you are in, check here: https://www.timeanddate.com/time/map")
            msg = await ctx.author.send(embed=embed)
            def timezonecheck(payload):
                return payload.author == ctx.author and payload.guild is None
            try:
                payload = await bot.wait_for('message', timeout=300.0, check=timezonecheck)
                try:
                    #We will check if it is an int
                    int(payload.content)
                    #Check if it is a valid value for a timezone
                    if int(payload.content) not in range(-12, 14) :
                        await msg.delete()
                        embed=discord.Embed(title="⚠️ Invalid timezone!", description="Please enter a valid timezone.", color=warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                    #If it is smaller than 0, we will make it UTC-
                    elif int(payload.content) < 0 :
                        timezone = int(payload.content)
                        await modifymatchmaking(qType, f"UTC{timezone}", isModifying)
                        await msg.delete()
                        embed=discord.Embed(title="✅ Timezone set.", description=f"Your timezone: UTC{timezone}", color=mpEmbedColor)
                        await ctx.author.send(embed=embed)
                        return 0
                    #Otherwise UTC+
                    else :
                        timezone = int(payload.content)
                        await modifymatchmaking(qType, f"UTC+{timezone}", isModifying)
                        await msg.delete()
                        embed=discord.Embed(title="✅ Timezone set.", description=f"Your timezone: UTC+{timezone}", color=mpEmbedColor)
                        await ctx.author.send(embed=embed)
                        return 0
                except ValueError:
                    await msg.delete()
                    embed=discord.Embed(title="⚠️ Invalid timezone!", description="Please enter a valid timezone.", color=warnColor)
                    await ctx.author.send(embed=embed)
                    return -2
            except asyncio.TimeoutError:
                embed = discord.Embed(title=errorTimeoutTitle, description=errorTimeoutDesc, color=errorColor)
                await ctx.author.send(embed=embed)
                return -1
        if qType == "Additional" :
            embed=discord.Embed(title="If you want to add additional notes to your listing, type it in now!", description="Examples of what to include (not mandatory): When you want to start, Duration of a match, Mods (if any)", color=mpEmbedColor)
            embed.set_footer(text="Type in 'skip' to skip this step! Max length: 256 characters")
            msg = await ctx.author.send(embed=embed)
            def additionalinfocheck(payload):
                return payload.author == ctx.author and payload.guild is None
            try:
                payload = await bot.wait_for('message', timeout=300.0, check=additionalinfocheck)
                if len(payload.content) > 256 :
                    await msg.delete()
                    embed = discord.Embed(title=warnDataTitle, description="Additional info exceeded character limit! Maximum length: 256 characters", color=warnColor)
                    await ctx.author.send(embed=embed)
                    return -2
                else :
                    if payload.content.lower() == "skip" :
                        await modifymatchmaking(qType, "-", isModifying)
                        await msg.delete()
                        embed=discord.Embed(title="✅ Additional info skipped.", description="You skipped this step.", color=mpEmbedColor)
                        await ctx.author.send(embed=embed)
                        return 0
                    else :
                        await modifymatchmaking(qType, payload.content, isModifying)
                        await msg.delete()
                        embed=discord.Embed(title="✅ Additional info set.", description=f"You typed: {payload.content} ", color=mpEmbedColor)
                        await ctx.author.send(embed=embed)
                        return 0
            except:
                embed = discord.Embed(title=errorTimeoutTitle, description=errorTimeoutDesc, color=errorColor)
                await ctx.author.send(embed=embed)
                return -1
        
        if qType == "ConfirmListing" :
            #Send listing preview
            embed=discord.Embed(title="**__Looking for Players: Anno 1800__**", description=f"**Ubisoft Connect Username: ** {mpsessiondata[0]} \n **Gamemode: ** {mpsessiondata[1]} \n **Players: ** {mpsessiondata[2]} \n **DLC: ** {mpsessiondata[3]} \n **Mods:** {mpsessiondata[4]} \n **Timezone:** {mpsessiondata[5]} \n **Additional info:** {mpsessiondata[6]} \n \n Contact {ctx.message.author.mention} in DMs if you are interested, or react with ⏫! This will notify the host when {mpsessiondata[2]} players have expressed interest! (including the host)", color=mpEmbedColor)
            embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/203158031511453696/446da0b60a670b6866cd463fb5e87195.png?size=1024")
            embed.set_footer(text="Note: This listing is valid for 7 days, after that, no more join interests can be submitted.")
            await ctx.author.send(embed=embed)
            embed=discord.Embed(title="Please review your listing!", description="If everything looks good, hit ✅ to submit! If you want to edit any information, hit 🖊️. If you want to cancel your submission, hit ❌.", color=mpEmbedColor)
            msg = await ctx.author.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("🖊️")
            await msg.add_reaction("❌")
            #Called to create a new multiplayer posting
            async def createposting(mpsessiondata):
                try:
                    channel = bot.get_channel(await retrievesetting("ANNOUNCECHANNEL", ctx.guild.id))
                    lfgrole = ctx.guild.get_role(await retrievesetting("LFGROLE", ctx.guild.id))
                    #If LFG role is not set up, we will not include a mention to it at the end.
                    if await retrievesetting("LFGROLE", ctx.guild.id) == 0 :
                        #yeah this is long lol
                        embed=discord.Embed(title="**__Looking for Players: Anno 1800__**", description=f"**Ubisoft Connect Username: ** {mpsessiondata[0]} \n **Gamemode: ** {mpsessiondata[1]} \n **Players: ** {mpsessiondata[2]} \n **DLC: ** {mpsessiondata[3]} \n **Mods:** {mpsessiondata[4]} \n **Timezone:** {mpsessiondata[5]} \n **Additional info:** {mpsessiondata[6]} \n \n Contact {ctx.message.author.mention} in DMs if you are interested, or react with ⏫! This will notify the host when {mpsessiondata[2]} players have expressed interest! (including the host)")
                        embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/203158031511453696/446da0b60a670b6866cd463fb5e87195.png?size=1024")
                        embed.set_footer(text="Note: This listing is valid for 7 days, after that, no more join interests can be submitted.")
                        posting = await channel.send(embed=embed)
                        await posting.add_reaction("⏫")
                        #await channel.send(f"**__Looking for Players: Anno 1800__** \n \n **Ubisoft Connect Username: ** {mpsessiondata[0]} \n **Gamemode: ** {mpsessiondata[1]} \n **Players: ** {mpsessiondata[2]} \n **DLC: ** {DLC} \n **Mods:** {mpsessiondata[3]} \n **Timezone:** {mpsessiondata[4]} \n **Additional info:** {mpsessiondata[5]} \n \n Contact {ctx.message.author.mention} in DMs if you are interested!")
                        print(f"[INFO]: {ctx.author} User created new multiplayer listing. Session: {mpsessiondata}")   
                    else :
                        embed=discord.Embed(title="**__Looking for Players: Anno 1800__**", description=f"**Ubisoft Connect Username: ** {mpsessiondata[0]} \n **Gamemode: ** {mpsessiondata[1]} \n **Players: ** {mpsessiondata[2]} \n **DLC: ** {mpsessiondata[3]} \n **Mods:** {mpsessiondata[4]} \n **Timezone:** {mpsessiondata[5]} \n **Additional info:** {mpsessiondata[6]} \n \n Contact {ctx.message.author.mention} in DMs if you are interested, or react with ⏫! This will notify the host when {mpsessiondata[2]} players have expressed interest! (including the host)")
                        embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/203158031511453696/446da0b60a670b6866cd463fb5e87195.png?size=1024")
                        embed.set_footer(text="Note: This listing is valid for 7 days, after that, no more join interests can be submitted.")
                        posting = await channel.send(embed=embed,content=lfgrole.mention)
                        await posting.add_reaction("⏫")
                        #await channel.send(f"**__Looking for Players: Anno 1800__** \n \n **Ubisoft Connect Username: ** {mpsessiondata[0]} \n **Gamemode: ** {mpsessiondata[1]} \n **Players: ** {mpsessiondata[2]} \n **DLC: ** {DLC} \n **Mods:** {mpsessiondata[3]} \n **Timezone:** {mpsessiondata[4]} \n **Additional info:** {mpsessiondata[5]} \n \n Contact {ctx.message.author.mention} in DMs if you are interested! \n \n {lfgrole.mention}")
                        print(f"[INFO]: {ctx.author} User created new multiplayer listing. Session: {mpsessiondata}") 
                except:
                #    #If for whatever reason the message cannot be made, we message the user about it.
                    print(f"[ERROR]: Could not create listing for {ctx.author}. Did you set up matchmaking?")
                    embed=discord.Embed(title="❌ Error: Exception encountered.", description="Failed to generated listing. Contact an administrator! Operation cancelled.", color=errorColor)
                    await ctx.author.send(embed=embed)
                    return -1

            #Returns -1 for fail, 0 for successful modification
            async def modifylisting():
                embed=discord.Embed(title="What do you want to change in your listing?", description="👤 - Ubisoft Username \n🕹️ - Gamemode \n🧮 - Player count \n💿 - DLC \n🏗️ - Mods\n🕘 - Timezone \n✉️ - Additional details", color=mpEmbedColor)
                msg = await ctx.author.send(embed=embed)
                #Questions you can modify
                #These should be in the SAME order as modifyquestions, otherwise it WILL break!!
                modifyEmojies =["👤", "🕹️", "🧮", "💿","🏗️","🕘","✉️"]
                for emoji in modifyEmojies :
                    await msg.add_reaction(emoji)
                def confirmModifyCheck(payload):
                    return payload.message_id == msg.id and payload.user_id == ctx.author.id
                try:
                    payload = await bot.wait_for('raw_reaction_add', timeout=300.0, check=confirmModifyCheck)

                    if str(payload.emoji) in modifyEmojies :
                        #We get the index, and now we know which question to re-run
                        index = modifyEmojies.index(str(payload.emoji))
                        warns = 0
                        #-2 means repeat until question is either failed (-1) or completed (0)
                        errcode=-2
                        #We will run until it finishes (aka errcode is 0)
                        while errcode != 0:
                            #Get the current question, evaluate it
                            errcode = await ask(qtypes[index], True)
                            #If it is fatal, return the whole command
                            if errcode == -1:
                                return -1
                            #Otherwise it is an invalid value, so we check if we reached warn limit
                            else :
                                if warns == 2:
                                    embed=discord.Embed(title="❌ Exceeded error limit.", description="You have made too many errors. Please retry your submission.", color=errorColor)
                                    await ctx.author.send(embed=embed)
                                    return -1
                                else:
                                    warns += 1
                        return 0
                        
                    else :
                        #We have to cancel the entire command here, as it would be way too difficult to implement looping here as well
                        embed = discord.Embed(title=errorEmojiTitle, description="Cancelled matchmaking.", color=errorColor)
                        await ctx.author.send(embed=embed)
                        return -1

                except asyncio.TimeoutError :
                    embed = discord.Embed(title=errorTimeoutTitle, description=errorTimeoutDesc, color=errorColor)
                    await ctx.author.send(embed=embed)
                    return -1
                
                
            #We create a function to check some properties of the payload
            #We check if the message ID is the same, so this is not a different message.
            #We also check if the user who reacted was the user who sent the command.
            def confirmcheck(payload):
                return payload.message_id == msg.id and payload.user_id == ctx.author.id
            #Now we will try to wait for a reaction add event for 60 seconds
            try:
                payload = await bot.wait_for('raw_reaction_add', timeout=300.0, check=confirmcheck)
                #Check reaction emoji
                if str(payload.emoji) == "✅":
                    if await createposting(mpsessiondata) == -1:
                        return -1
                    else :
                        embed=discord.Embed(title="✅ Listing submitted!", description="Thanks for using the service! If you have found a bug or want to give feedback, please contact `Hyper#0001`!", color=0x00ff2a)
                        await ctx.author.send(embed=embed)
                        return 1
                elif str(payload.emoji) == "🖊️":
                    if await modifylisting() == 0 :
                        #If modification is successful, repeat this step (confirmcheck)
                        return -3
                    else :
                        embed=discord.Embed(title="❌ Modification failed.", description="If you have found a bug or want to give feedback, please contact `Hyper#0001`!", color=errorColor)
                        await ctx.author.send(embed=embed)
                        print(f"[INFO]: {ctx.author} User failed modification.")
                        return -1


                elif str(payload.emoji) == "❌":
                    embed=discord.Embed(title="❌ Submission cancelled.", description="If you have found a bug or want to give feedback, please contact `Hyper#0001`!", color=errorColor)
                    await ctx.author.send(embed=embed)
                    print(f"[INFO]: {ctx.author} User cancelled matchmaking.")
                    return -1
                else :
                    await msg.delete()
                    embed = discord.Embed(title=warnEmojiTitle, description=warnEmojiDesc, color=warnColor)
                    await ctx.author.send(embed=embed)
                    return -2

            except asyncio.TimeoutError:
                embed = discord.Embed(title=errorTimeoutTitle, description=errorTimeoutDesc, color=errorColor)
                await ctx.author.send(embed=embed)
                return -1
    
    #Call all the functions defined earlier
    #Error codes:
    # 1 = finished
    # 0 = success, continue
    # -1 = Fatal error, cancel command
    # -2 = Invalid value, repeat question
    # -3 = Repeat question, no error, only triggered when editing
    #  
    #
    #This means that we keep looping until our error code is -2 or -3, stop loop when it is 0
    #And return the whole command if it is -1
    
    #I also count how many invalid values have been added, and how many edits have been made, and if it reaches a value, it will cancel the command.
    warns = 0
    edits = 0
    #Current question we are at
    question = 0
    #Every time a question is asked, a number is returned to this value
    errcode=-2
    #We will run until it finishes (aka errcode is 1)
    while errcode != 1:
        #Get the current question, evaluate the code
        errcode = await ask(qtypes[question], False)
        #If it is fatal, return the whole command
        if errcode == -1:
            matchmaking.reset_cooldown(ctx)
            return
        #If it succeeds, we move to the next question
        elif errcode == 0:
            question += 1
        #If editing, we will add one to the edits variable.
        elif errcode == -3:
            if edits == 6:
                embed=discord.Embed(title="❌ Exceeded edit limit.", description="You cannot make more edits to your submission. Please try executing the command again.",color=errorColor)
                await ctx.author.send(embed=embed)
                matchmaking.reset_cooldown(ctx)
                return
            else :
                edits += 1
        #If it is an invalid value, add a warn
        elif errcode == -2 :
            if warns == 4:
                embed=discord.Embed(title="❌ Exceeded error limit.", description="You have made too many errors. Please retry your submission.", color=errorColor)
                await ctx.author.send(embed=embed)
                matchmaking.reset_cooldown(ctx)
                return
            else:
                warns += 1
    print("[INFO]matchmaking command exited successfully.")


@matchmaking.error
async def matchmaking_error(ctx, error):
    #Due to it's performance requirements and complexity, this command is limited to 1 per user
    if isinstance(error, commands.MaxConcurrencyReached):
        embed = discord.Embed(title="❌ Error: Max concurrency reached!", description="You already have a matchmaking request in progress.", color=errorColor)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.channel.send(embed=embed)


#
#Event Handlers
#
#Note: This is where stuff that is not a command is handled


#Generic error handling. Will catch all errors with these types
@bot.event
async def on_command_error(ctx, error):
    #This gets sent whenever a user has insufficient permissions to execute a command.
    if isinstance(error, commands.CheckFailure):
        embed=discord.Embed(title=errorCheckFailTitle, description=errorCheckFailDesc, color=errorColor)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
    elif isinstance(error, commands.CommandNotFound):
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
            embed=discord.Embed(title="❓ Unknown command!", description=f"Did you mean `{prefix}{matches[0]}`?", color=0xbe1931)
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
        elif len(aliasmatches) > 0:
            embed=discord.Embed(title="❓ Unknown command!", description=f"Did you mean `{prefix}{aliasmatches[0]}`?", color=0xbe1931)
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
        else:
            embed=discord.Embed(title="❓ Unknown command!", description=f"Use `{prefix}help` for a list of available commands.", color=0xbe1931)
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
    elif isinstance(error, commands.CommandOnCooldown):
        embed=discord.Embed(title=errorCooldownTitle, description=f"Please retry in: `{datetime.timedelta(seconds=round(error.retry_after))}`", color=errorColor)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed=discord.Embed(title="❌ Missing argument.", description=f"One or more arguments are missing. \n__Hint:__ You can use `{prefix}help {ctx.command.name}` to view command usage.", color=errorColor)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)


    else :
        #If no known error has been passed, we will print the exception to console as usual
        #IMPORTANT!!! If you remove this, your command errors will not get output to console.
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

#Reaction roles for LFG
@bot.event
async def on_raw_reaction_add(payload):
    #Check if we are in a guild so we dont bombard the database with Null errors.
    if payload.guild_id != None : 
        guild = bot.get_guild(payload.guild_id)
        #Check if it is the message we set
        if await retrievesetting("ROLEREACTMSG", payload.guild_id) == payload.message_id :
            #Check the emoji
            if payload.emoji == bot.get_emoji(await retrievesetting("LFGREACTIONEMOJI", guild.id)) and payload.user_id != bot.user.id:
                member = guild.get_member(payload.user_id)
                try:
                    #Then set the role for the user
                    role = guild.get_role(await retrievesetting("LFGROLE", guild.id))
                    await member.add_roles(role)
                    print(f"[INFO]: Role {role} added to {member}")
                    #Also DM the user about the change, and let them know that the action was performed successfully.
                    embed=discord.Embed(title="💬 Notifications enabled.", description="You are now looking for games, and will be notified of any new multiplayer listing!", color=0x00ff2a)
                    await member.send(embed=embed)
                    return
                except:
                    #In case anything goes wrong, we will tell the user to bully admins who can then bully me :) /s
                    embed=discord.Embed(title="❌ Error: Exception encountered.", description="Failed to add role. Contact an administrator! Operation cancelled.", color=errorColor)
                    await member.send(embed=embed)
                    print(f"[ERROR]: Unable to modify roles for {member}. Possible permissions issue.")
                    return
        elif await retrievesetting("ANNOUNCECHANNEL", guild.id) == payload.channel_id:
            if str(payload.emoji) == "⏫" and payload.user_id != bot.user.id:
                #The listing message
                listing = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
                #If the message is older than 2 weeks, we ignore this request
                if (datetime.datetime.utcnow() - listing.created_at).days >= 7 :
                    return
                #The person who reacted
                member = guild.get_member(payload.user_id)
                #Get context for this message
                ctx = await bot.get_context(listing)
                #Get the content, then lines seperated into a list of the listing
                listingContent = listing.embeds
                listingLines = listingContent[0].description.splitlines()
                #The second line contains information about playercount
                playerCount = listingLines[2].split(": ** ")[1]
                #We get the mention that is in-between the words Contact... and ...in, and convert it to type of member.
                converter = commands.MemberConverter()
                host = await converter.convert(ctx, listingLines[len(listingLines)-1].split("Contact ")[1].split(" in")[0])
                #We get a list of users who reacted to this
                interestedPlayers = await listing.reactions[0].users().flatten()
                #Remove bot accounts from this list, and join them together in a new str.
                for player in interestedPlayers :
                    if player.bot == True or player == host :
                        interestedPlayers.remove(player)
                interestedMentions = ", ".join([member.mention for member in interestedPlayers])
                #Convert the playercount to int, subtract 1 as to not count the host itself
                try :
                    playerCount = int(playerCount)-1
                except ValueError :
                    playerCount = 4
                #Sending confirmation to user who signed up
                if member != host :
                    embed=discord.Embed(title=f"📝 You expressed intent to join {host.name}'s game!", description="They will receive a notification when their desired playercap has been reached.", color=0x00ff2a)
                    await member.send(embed=embed)
                    print(f"[INFO]: {member.name}#{member.discriminator} expressed interest to join {host.name}#{host.discriminator}'s game.")
                #If we have reached the desired playercount, we will message to the host. This message will get every time a new player reacts.
                if len(interestedPlayers) >= playerCount :
                    embed=discord.Embed(title="📝 Your listing reached your set playercap!", description=f"Hello! Just letting you know that your multiplayer listing on **{guild.name}** has reached {playerCount} or more interested players.\nPlayers who want to play with you in this match: {interestedMentions}", color=0x00ff2a)
                    embed.set_footer(text="If you believe that this feature was abused, contact a moderator immediately!")
                    await host.send(embed=embed)
                    print(f"[INFO]: {host.name}#{host.discriminator}'s listing reached cap. Host notified.")
                return



#Same thing but in reverse
@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id != None :
        setmsg = await retrievesetting("ROLEREACTMSG", payload.guild_id)
        if setmsg == payload.message_id :
            guild = bot.get_guild(payload.guild_id)
            if payload.emoji == bot.get_emoji(await retrievesetting("LFGREACTIONEMOJI", guild.id)) and payload.user_id != bot.user.id:
                member = guild.get_member(payload.user_id)
                try:
                    role = guild.get_role(await retrievesetting("LFGROLE", guild.id))
                    await member.remove_roles(role)
                    print(f"[INFO]: Role {role} removed from {member}")
                    embed=discord.Embed(title="💬 Notifications disabled.", description="You will no longer get notifications on multiplayer game listings.", color=errorColor)
                    await member.send(embed=embed)
                except:
                    embed=discord.Embed(title="❌ Error: Exception encountered.", description="Failed to remove role. Contact an administrator! Operation cancelled.", color=errorColor)
                    await member.send(embed=embed)
                    print(f"[ERROR]: Unable to modify roles for {member}. Possible permissions or hierarchy issue.")

#
#ADMIN/Config commands
#
#Note: These commands are intended to be only used by people authorized by the server owner.


#Check performed to see if the person is either the guild owner or the bot owner.
async def hasOwner(ctx):
    return ctx.author.id == creatorID or ctx.author.id == ctx.guild.owner_id

#Check performed to see if the user has priviliged access.
async def hasPriviliged(ctx):
    #Gets a list of all the roles the user has, then gets the ID from that.
    userRoles = [x.id for x in ctx.author.roles]
    #Also get privliged roles, then compare
    privroles = [role[0] for role in await checkprivs(ctx.guild.id)]
    #Check if any of the roles in user's roles are contained in the priviliged roles.
    return any(role in userRoles for role in privroles) or (ctx.author.id == creatorID or ctx.author.id == ctx.guild.owner_id)

#Fun command, because yes. (Needs mod privilege as it can be abused for spamming)
@bot.command(hidden = True, brief = "Deploys the duck army.", description="🦆 I am surprised you even need help for this...", usage=f"{prefix}quack")
@commands.check(hasPriviliged)
@commands.guild_only()
async def quack(ctx):
    await ctx.channel.send("🦆")
    await ctx.message.delete()

#Commands used to add and/or remove other roles from executing potentially unwanted things
@bot.command(hidden=True, aliases=['addprivrole', 'addbotadminrole'], brief="Add role to priviliged roles", description="Adds a role to the list of priviliged roles, allowing them to execute admin commands.", usage=f"{prefix}addpriviligedrole <rolename>")
@commands.check(hasOwner)
@commands.guild_only()
async def addpriviligedrole(ctx, rolename):
    try :
        role = discord.utils.get(ctx.guild.roles, name=rolename)
    except :
        await ctx.channel.send("**Error:** Unable to locate role.")
    async with aiosqlite.connect(dbPath) as db:

        cursor = await db.execute("SELECT priviliged_role_id FROM priviliged WHERE guild_id = ? AND priviliged_role_id = ?", [ctx.guild.id, role.id])
        reply = await cursor.fetchone()
        if reply != None :
            await ctx.channel.send("**Error:** Role already added.")
        else :
            await db.execute("INSERT INTO priviliged (guild_id, priviliged_role_id) VALUES (?, ?)", [ctx.guild.id, role.id])
            await db.commit()
            await ctx.channel.send(f"**{role.name}** has been granted bot admin priviliges.")


@bot.command(hidden=True, aliases=['remprivrole', 'removeprivrole', 'removebotadminrole', 'rembotadminrole'], brief="Remove role from priviliged roles.", description="Removes a role to the list of priviliged roles, revoking their permission to execute admin commands.", usage=f"{prefix}removepriviligedrole <rolename>")
@commands.check(hasOwner)
@commands.guild_only()
async def removepriviligedrole(ctx,rolename):
    try :
        role = discord.utils.get(ctx.guild.roles, name=rolename)
    except :
        await ctx.channel.send("**Error:** Unable to locate role.")
    async with aiosqlite.connect(dbPath) as db:
        cursor = await db.execute("SELECT priviliged_role_id FROM priviliged WHERE guild_id = ? AND priviliged_role_id = ?", [ctx.guild.id, role.id])
        reply = await cursor.fetchone()
        if reply == None :
            await ctx.channel.send("**Error:** Role not priviliged.")
        else :
            await db.execute("DELETE FROM priviliged WHERE guild_id = ? AND priviliged_role_id = ?", [ctx.guild.id, role.id])
            await db.commit()
            await ctx.channel.send(f"**{role}** has had it's bot admin priviliges revoked.")


@bot.command(hidden=True, aliases=['privroles', 'botadminroles'],brief="List all priviliged roles.", description="Returns all priviliged roles on this server.", usage=f"{prefix}priviligedroles")
@commands.check(hasOwner)
@commands.guild_only()
async def priviligedroles(ctx) :
    async with aiosqlite.connect(dbPath) as db :
        cursor = await db.execute("SELECT priviliged_role_id FROM priviliged WHERE guild_id = ?", [ctx.guild.id])
        roleIDs = await cursor.fetchall()
        if len(roleIDs) == 0 :
            await ctx.channel.send("**Error:** No priviliged roles set.")
            return
        else :
            roles = []
            roleNames = []
            for item in roleIDs :
                roles.append(ctx.guild.get_role(item[0]))
            for item in roles :
                roleNames.append(item.name)
            await ctx.channel.send(f"Priviliged roles for this guild: `{roleNames}`")

#Returns basically all information we know about a given member of this guild.
@bot.command(hidden=True, brief="Get information about a user.", description="Provides information about a specified user in the guild.", usage=f"{prefix}whois <userID|userMention|userName>")
@commands.check(hasPriviliged)
@commands.guild_only()
async def whois(ctx, member : discord.Member) :
    rolelist = [role.name for role in member.roles]
    roleformatted = ", ".join(rolelist)
    embed=discord.Embed(title=f"User information: {member.name}", description=f"Username: `{member.name}` \nNickname: `{member.display_name}` \nUser ID: `{member.id}` \nStatus: `{member.raw_status}` \nBot: `{member.bot}` \nAccount creation date: `{member.created_at}` \nJoin date: `{member.joined_at}` \nRoles: `{roleformatted}`", color=0x009dff)
    embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
    embed.set_thumbnail(url=member.avatar_url)
    await ctx.channel.send(embed=embed)
@whois.error
async def whois_error(ctx, error):
    if isinstance(error, discord.ext.commands.errors.MemberNotFound) :
        embed=discord.Embed(title="❌ Unable to find user.", description="Please check if you typed everything correctly, then try again.", color=errorColor)
        await ctx.send(embed=embed)


#Ahh yes, the setup command... *instant PTSD*
#It basically just collects a bunch of values from the user, in this case an admin, and then changes the settings
#based on that, instead of the admin having to use !modify for every single value
#TL;DR: fancy setup thing
@bot.command(hidden=True,brief="Starts bot configuration setups.", description = "Used to set up and configure different parts of the bot. Valid setup-types: `matchmaking, LFG` Only usable by priviliged users.", usage=f"{prefix}setup <setuptype>")
@commands.check(hasPriviliged)
@commands.guild_only()
@commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
async def setup (ctx, setuptype):
    #This is the LFG setup variant, it will set up role reactions on either an existing message or a new one.
    #More setup variants may be added in the future
    if setuptype == "LFG":
        msg = await ctx.channel.send("Initializing LFG role setup... \n Do you already have an existing message for rolereact?")
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        #The various values that will be collected by the setup process and executed in configurevalues()
        #Declared here for easier visibility

        def confirmcheck(payload):
            return payload.message_id == msg.id and payload.user_id == ctx.author.id
        def idcheck(payload):
            return payload.author == ctx.author and payload.channel.id == ctx.channel.id

        #Where the values actually get changed
        async def configurevalues(createmsg, reactmsg, msgcontent, reactchannel, reactemoji, rolename):
            if createmsg == True :
                #Create message
                msg = await reactchannel.send(str(msgcontent))
                #Add reaction
                await msg.add_reaction(reactemoji)

            elif createmsg == False :
                #Get message
                msg = reactmsg
                #Add reaction
                await msg.add_reaction(reactemoji)

            #Get role
            role = discord.utils.get(ctx.guild.roles, name = rolename)
            #Saving all the values
            #These are the values other code listens to, at this point this means that the function is live.
            await modifysettings("LFGREACTIONEMOJI", reactemoji.id, ctx.guild.id)
            await modifysettings("LFGROLE", role.id, ctx.guild.id)
            await modifysettings("ROLEREACTMSG", msg.id, ctx.guild.id)
            print(f"[INFO]: Setup for {setuptype} concluded successfully.")
            await ctx.channel.send("✅ Setup completed. Role reactions set up!")

        #The common part of the LFG setup
        async def continueprocess(reactchannel, msgcontent, reactmsg, createmsg):
            try:
                def confirmemoji(payload):
                    return payload.message_id == msg.id and payload.user_id == ctx.author.id
                #Get emoji
                msg = await ctx.channel.send("React **to this message** with the emoji you want to use!")
                payload = await bot.wait_for('raw_reaction_add', timeout=60.0,check=confirmemoji)
                reactemoji = payload.emoji
                await ctx.channel.send(f"Emoji to be used will be {reactemoji}")
                #Get the name of the role, then pass it on
                await ctx.channel.send("Name the role that will be handed out!")
                payload = await bot.wait_for('message', timeout=60.0, check=idcheck)
                rolename = payload.content
                await ctx.channel.send(f"Role set to **{rolename}**")
                #Pass all values to configurator
                await configurevalues(createmsg, reactmsg, msgcontent, reactchannel, reactemoji, rolename)
            except asyncio.TimeoutError:
                await ctx.channel.send("**Error: **Timed out. Setup process cancelled.")
                return
        try:
            payload = await bot.wait_for('raw_reaction_add', timeout=60.0, check=confirmcheck)
            if str(payload.emoji) == ("✅") :

                try:
                    #Defining these to be None, because they need to be passed to continueprocess
                    reactchannel = None
                    msgcontent = None
                    await ctx.channel.send("Send a channel mention of the channel where the message is located!")
                    payload = await bot.wait_for('message', timeout =60.0, check=idcheck)
                    #We will attempt to convert this from a channel mention
                    reactchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                    createmsg = True
                    await ctx.channel.send(f"Channel set to **{reactchannel.mention}**")
                    #Since the message already exists, we will try to get it's ID from the user
                    await ctx.channel.send("Please specify the ID of the message.")
                    payload = await bot.wait_for('message', timeout=60.0, check=idcheck)
                    #We will attempt to convert this to an int to check if it is one
                    int(payload.content)
                    reactmsg = await reactchannel.fetch_message(int(payload.content))
                    createmsg = False
                    await ctx.channel.send(f"Reaction message set to the following: \n*{reactmsg.content}* **in** {reactchannel.mention}")
                    #Pass all collected values to continue
                    await continueprocess(reactchannel, msgcontent, reactmsg, createmsg)
                    return
                except asyncio.TimeoutError:
                    await ctx.channel.send("**Error: **Timed out. Setup process cancelled.")
                    return
                except ValueError:
                    await ctx.channel.send("**Error: **Invalid value. Setup process cancelled.")
                    return
                except commands.ChannelNotFound:
                    await ctx.channel.send("**Error: ** Unable to locate channel. Setup process cancelled.")
                    return

            elif str(payload.emoji) == ("❌"):
                await ctx.channel.send("Please specify the channel where you want the message to be sent via mentioning the channel.")
                try:
                    reactmsg = None
                    payload = await bot.wait_for('message', timeout =60.0, check=idcheck)
                    #We will attempt to convert this from a channel mention
                    reactchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                    createmsg = True
                    await ctx.channel.send(f"Channel set to **{reactchannel.mention}**")

                    await ctx.channel.send("What should the content of the message be?")
                    payload = await bot.wait_for('message', timeout = 60.0, check=idcheck)
                    msgcontent = payload.content
                    await ctx.channel.send(f"Message content will be set to the following: \n*{msgcontent}*")

                    #Pass all collected values to continue
                    await continueprocess(reactchannel, msgcontent, reactmsg, createmsg)
                    return
                except asyncio.TimeoutError:
                    await ctx.channel.send("**Error: **Timed out. Setup process cancelled.")
                    return
                except commands.ChannelNotFound:
                    await ctx.channel.send("**Error: ** Unable to locate channel. Setup process cancelled.")
                    return
            else :
                await ctx.channel.send("**Error:** Invalid reaction. Setup process cancelled.")
                return
        except asyncio.TimeoutError:
            await ctx.channel.send("**Error: **Timed out. Setup process cancelled.")
            return
    #This setup will set up the !matchmaking command to work properly.
    if setuptype == "matchmaking" or "Matchmaking" or "MATCHMAKING":
        await ctx.channel.send("Initializing matchmaking setup...\nPlease mention a channel where users should send the command to start matchmaking! Type `disable` to disable this feature.")
        try:
            #Gathering info
            def check(payload):
                return payload.author == ctx.author and payload.channel.id == ctx.channel.id
            payload = await bot.wait_for('message', timeout =60.0, check=check)
            if payload.content == "disable":
                cmdchannel = 0
                await ctx.channel.send("Commands channel **disabled.**")
            else :
                cmdchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                await ctx.channel.send(f"Commands channel set to {cmdchannel.mention}")

            await ctx.channel.send("Now please mention the channel where the multiplayer listings should go. If you already have LFG reaction roles set up, they will also be pinged once a listing goes live.")
            payload = await bot.wait_for('message', timeout=60.0, check=check)
            announcechannel = await commands.TextChannelConverter().convert(ctx, payload.content)
            await ctx.channel.send(f"Multiplayer listings channel set to {announcechannel.mention}")

            #Executing based on info

            if cmdchannel == 0 :
                await modifysettings("COMMANDSCHANNEL", 0, ctx.guild.id)
            else :
                await modifysettings("COMMANDSCHANNEL", cmdchannel.id, ctx.guild.id)
            await modifysettings("ANNOUNCECHANNEL", announcechannel.id, ctx.guild.id)
            await ctx.channel.send("✅ Setup completed. Matchmaking set up!")
            return

        except commands.ChannelNotFound:
            await ctx.channel.send("**Error:** Unable to locate channel. Setup process cancelled.")
            return
        except asyncio.TimeoutError:
            await ctx.channel.send("**Error: **Timed out. Setup process cancelled.")
            return

    else:
        await ctx.channel.send("**Error:** Unable to find requested setup process. Valid setups: `LFG, matchmaking`.")
        return

@setup.error
async def setup_error(ctx, error):
    if isinstance(error, commands.MaxConcurrencyReached):
        embed = discord.Embed(title="❌ Error: Max concurrency reached!", description="You already have a setup process running.", color=errorColor)
        await ctx.channel.send(embed=embed)


#Command used for deleting a guild settings file
@bot.command(hidden=True, brief="Resets all settings for this guild.", description = "Resets all settings for this guild. Irreversible.", usage=f"{prefix}resetsettings")
@commands.check(hasPriviliged)
@commands.guild_only()
async def resetsettings(ctx):
    msg = await ctx.channel.send("**Are you sure you want to reset all settings? This action is irreversible, and may break things!**")
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    def check(payload):
        return payload.message_id == msg.id and payload.user_id == ctx.author.id
    try:
        payload = await bot.wait_for('raw_reaction_add', timeout=10.0,check=check)
        if str(payload.emoji) == "✅":
            await deletesettings(ctx.guild.id)
            await ctx.channel.send("Settings reset. \n \n *Goodbye cruel world!* 😢")
        elif str(payload.emoji) == "❌" :
            await ctx.channel.send("Settings reset cancelled by user.")
        else :
            await ctx.channel.send("**Error:** Invalid reaction. Settings preserved.")
    except asyncio.TimeoutError:
        await ctx.channel.send("**Error:** Timed out. Settings preserved.")


#Display the current settings for this guild.
@bot.command(hidden=True, brief="Displays settings.", description="Displays the settings for the current guild.", usage=f"{prefix}settings")
@commands.check(hasPriviliged)
@commands.guild_only()
async def settings(ctx):
    settingsdata = await displaysettings(ctx.guild.id)
    if settingsdata == -1 :
        await ctx.channel.send("**Error:** No settings for this guild.")
    else :
        formatteddata = "".join(settingsdata)
        await ctx.channel.send(f"```Settings for guild {ctx.guild.id}: \n \n{formatteddata}```")


#Modify a value in the settings, use with care or it will break things
@bot.command(hidden=True, brief=f"Modifies a setting value. Recommended to use `{prefix}setup` instead.", description=f"Modifies a single value in the settings, improper use can and will break things! Use `{prefix}setup` instead.", usage=f"{prefix}modify <datatype> <value>")
@commands.check(hasPriviliged)
@commands.guild_only()
async def modify(ctx, datatype, value) :
    if datatype not in datatypes :
        await ctx.channel.send("**Error: ** Invalid datatype.")
        return
    try:
        int(value)
        await modifysettings(datatype, int(value), ctx.guild.id)
        await ctx.channel.send(f"**{datatype}** is now set to **{value}** for guild **{ctx.guild.id}**!")
    except ValueError:
        await ctx.channel.send("**Error: **Invalid value.")
    except:
        await ctx.channel.send("**Error: ** Unknown error encountered!")


#
#   SETTINGS HANDLER
#
# ALERT: Under major rewrite to support SQLite

#Deletes a guild specific settings file.
async def deletesettings(guildID):
    #Delete all data relating to this guild.
    async with aiosqlite.connect(dbPath) as db:
        await db.execute("DELETE FROM settings WHERE guild_id = ?", [guildID])
        await db.execute("DELETE FROM priviliged WHERE guild_id = ?", [guildID])
        await db.commit()
        #os.remove(f"{guildID}_settings.cfg")
        print(f"[WARN]: Settings have been reset for guild {guildID}.")

#Returns the priviliged roles for a specific guild as a list.
async def checkprivs(guildID):
    async with aiosqlite.connect(dbPath) as db:
        cursor = await db.execute("SELECT priviliged_role_id FROM priviliged WHERE guild_id = ?", [guildID])
        return await cursor.fetchall()

async def modifysettings(datatype, value, guildID):
    if datatype in datatypes :
        #Check if we have values for this guild
        print("Check")
        async with aiosqlite.connect(dbPath) as db:
            cursor = await db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", [guildID])
            result = await cursor.fetchone()
            if result != None :
                print("Guild Exists")
                #Looking for the datatype
                cursor = await db.execute("SELECT datatype FROM settings WHERE guild_id = ? AND datatype = ?", [guildID, datatype])
                result = await cursor.fetchone()
                #If the datatype does exist, we return the value
                if result != None :
                    print("Data exists")
                    #We update the matching record with our new value
                    await db.execute("UPDATE settings SET guild_id = ?, datatype = ?, value = ? WHERE guild_id = ? AND datatype = ?", [guildID, datatype, value, guildID, datatype])
                    await db.commit()
                    return
                #If it does not, for example if a new valid datatype is added to the code, we will create it, and assign it the value.
                else :
                    print("New data added")
                    await db.execute("INSERT INTO settings (guild_id, datatype, value) VALUES (?, ?, ?)", [guildID, datatype, value])
                    await db.commit()
                    return
            #If no data relating to the guild can be found, we will create every datatype for the guild, and return their value.
            #Theoretically not necessary, but it outputs better into displaysettings()
            else :
                for item in datatypes :
                    print("Guild data missing... creating..")
                    #We insert every datatype into the table for this guild.
                    await db.execute("INSERT INTO settings (guild_id, datatype, value) VALUES (?, ?, 0)", [guildID, item])
                await db.commit()
                #And then we update the value we wanted to change in the first place.
                await db.execute("UPDATE settings SET guild_id = ?, datatype = ?, value = ? WHERE guild_id = ? AND datatype = ?", [guildID, datatype, value, guildID, datatype])
                await db.commit()
                return


#Retrieves a setting for a specified guild.
async def retrievesetting(datatype, guildID) :
    if datatype in datatypes :
        #Check if we have values for this guild
        async with aiosqlite.connect(dbPath) as db:
            cursor = await db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", [guildID])
            result = await cursor.fetchone()
            #If we do, we check if the datatype exists
            if result != None :
                #Looking for the datatype
                cursor = await db.execute("SELECT datatype FROM settings WHERE guild_id = ? AND datatype = ?", [guildID, datatype])
                result = await cursor.fetchone()
                #If the datatype does exist, we return the value
                if result != None :
                    cursor = await db.execute("SELECT value FROM settings WHERE guild_id = ? AND datatype = ?", [guildID, datatype])
                    #This is necessary as fetchone() returns it as a tuple of one element.
                    value = await cursor.fetchone()
                    return value[0]
                #If it does not, for example if a new valid datatype is added to the code, we will create it, then return it's value.
                else :
                    await db.execute("INSERT INTO settings (guild_id, datatype, value) VALUES ?, ?, 0", [guildID, datatype])
                    cursor = await db.execute("SELECT value FROM settings WHERE guild_id = ? AND datatype = ?", [guildID, datatype])
                    value = await cursor.fetchone()
                    return value[0]
            #If no data relating to the guild can be found, we will create every datatype for the guild, and return their value.
            #Theoretically not necessary, but it outputs better into displaysettings()
            else :
                for item in datatypes :
                    #We insert every datatype into the table for this guild.
                    await db.execute("INSERT INTO settings (guild_id, datatype, value) VALUES (?, ?, 0)", [guildID, item])
                await db.commit()
                #And then we essentially return 0
                cursor = await db.execute("SELECT value IN settings WHERE guild_id = ? AND datatype = ?", [guildID, datatype])
                value = await cursor.fetchone()
                return value[0]
    else :
        print(f"[INTERNAL ERROR]: Invalid datatype called in retrievesetting() (Called datatype: {datatype})")

async def displaysettings(guildID) :
    #Check if there are any values stored related to the guild.
    #If this is true, guild settings exist.
    async with aiosqlite.connect(dbPath) as db:
        cursor = await db.execute("SELECT guild_id FROM settings WHERE guild_id = ?", [guildID])
        result = await cursor.fetchone()
        #If we find something, we gather it, return it.
        if result != None :
            #This gets datapairs in a tuple, print it below if you want to see how it looks
            cursor = await db.execute("SELECT datatype, value FROM settings WHERE guild_id = ?", [guildID])
            dbSettings = await cursor.fetchall()
            #print(dbSettings)
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

#Run bot with token from .env
bot.run(TOKEN)
