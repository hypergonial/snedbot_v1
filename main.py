import discord
import time
import threading
from discord.ext import commands
import logging
import asyncio
import os
import shutil
from dotenv import load_dotenv

#Loading token from .env file. If this file does not exist, nothing will work.
load_dotenv()
TOKEN = os.getenv("TOKEN")
#Enabling logging
logging.basicConfig(level=logging.INFO)
#Can modify command prefix & intents here (and probably a lot of other cool stuff I am not aware of)
bot = commands.Bot(command_prefix='!', intents= discord.Intents.all())

print("[INFO]: New Session Started.")

#Contains all the valid datatypes in settings. Gets populated by initsettings()
datatypes = []

#Executes when the bot starts & is ready.
@bot.event
async def on_ready():
    print("[INFO]: Initialized as {0.user}".format(bot))
    #Presence setup
    activity = discord.Activity(name='you', type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)
    #Populate initsettings()
    initsettings()

#Gets the ping of the bot.
@bot.command(description="Displays bot ping.")
async def ping(ctx):
    await ctx.send(f"Pong! ({round(bot.latency * 1000)}ms)")

#A more fun to get the ping.
@bot.command(hidden = True)
async def LEROY(ctx):
    await ctx.send(f"JEEEEEEENKINS! ({round(bot.latency * 1000)}ms) \n \n Oh my god he just ran in. 👀")

#Fun command, because yes. (Needs mod privilege as it can be abused for spamming)
@bot.command(hidden = True, description = "Deploys the duck army.")
@commands.has_any_role("Moderator","Admin")
async def quack(ctx):
    await ctx.channel.send("🦆")
    await ctx.message.delete()

#Command to initalize matchmaking.
@bot.command(description="Start matchmaking! Takes no arguments.")
async def init(ctx):
    #Defining the emojies that will be used.
    mpsessiondata = []
    #Messaging the channel to provide feedback
    await ctx.channel.send(f"Starting matchmaking for **{ctx.author.name}**. Check your DMs!")

    await ctx.author.send("**Hello! I will help you set up a multiplayer listing!**")
    #Sending initial DM
    msg = await ctx.author.send("Please type in your Ubisoft Connect username!")
    def usernamecheck(payload):
        return payload.author == ctx.author and payload.guild is None
    try:
        payload = await bot.wait_for('message', timeout=60.0, check=usernamecheck)
        if len(payload.content) > 32 :
            await ctx.author.send("**Error:** Invalid username. (Too long) Matchmaking cancelled.")
            return
        else :
            mpsessiondata.append(payload.content)
            await ctx.author.send(f"Ubisoft Connect Username set to:** {payload.content}**")
            await msg.delete()

    except:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return

    msg = await ctx.author.send("Should the game be a PvP or a Co-op match? \n ⚔️ PvP (Player versus Player) \n 🛡️ Co-op (Cooperative)")
    #Saving the ID of this message we just sent
    msgid = msg.id
    #Add two reactions to this message
    await msg.add_reaction("⚔️")
    await msg.add_reaction("🛡️")

    #We create a function to check some properties of the payload
    #We check if the message ID is the same, so this is not a different message.
    #We also check if the user who reacted was the user who sent the command.
    def gamemodecheck(payload):
        return payload.message_id == msgid and payload.user_id == ctx.author.id
    #Now we will try to wait for a reaction add event for 60 seconds
    try:
        payload = await bot.wait_for('raw_reaction_add', timeout=60.0, check=gamemodecheck)
        #Check reaction emoji
        if str(payload.emoji) == "⚔️":
            await ctx.author.send("Gamemode set to **PvP**")
            mpsessiondata.append("PvP")
            await msg.delete()
        elif str(payload.emoji) == "🛡️":
            await ctx.author.send("Gamemode set to **Co-op**")
            mpsessiondata.append("Co-op")
            await msg.delete()
        #In the event that the emoji is not any of the above, we can eliminate an edge-case here
        else :
            await ctx.author.send("**Error:** Invalid reaction entered. Matchmaking cancelled.")
            return
    #If we dont get a response within 60 seconds it times out.
    except asyncio.TimeoutError:
        await ctx.author.send("**Error:**Timed out. Matchmaking cancelled.")
        return

    msg = await ctx.author.send("Good! Now specify how many players you want to play with!\n 2️⃣ - 2 players \n 3️⃣ - 3 players \n 4️⃣ - 4 players \n ♾️ - 5 or more players")
    #Saving the ID of this message we just sent
    msgid = msg.id
    await msg.add_reaction("2️⃣")
    await msg.add_reaction("3️⃣")
    await msg.add_reaction("4️⃣")
    await msg.add_reaction("♾️")

    #We create a function to check some properties of the payload
    #We check if the message ID is the same, so this is not a different message.
    #We also check if the user who reacted was the user who sent the command.
    def playercountcheck(payload):
        return payload.message_id == msgid and payload.user_id == ctx.author.id
    #Now we will try to wait for a reaction add event for 60 seconds
    try:
        payload = await bot.wait_for('raw_reaction_add', timeout=60.0, check=playercountcheck)
        #Check reaction emoji
        if str(payload.emoji) == "2️⃣":
            await ctx.author.send("Player count set to: **2**")
            mpsessiondata.append("2")
            await msg.delete()
        elif str(payload.emoji) == "3️⃣":
            await ctx.author.send("Player count set to: **3**")
            mpsessiondata.append("3")
            await msg.delete()
        elif str(payload.emoji) == "4️⃣":
            await ctx.author.send("Player count set to: **4**")
            mpsessiondata.append("4")
            await msg.delete()
        elif str(payload.emoji) == "♾️":
            await ctx.author.send("Player count set to: **5 or more**")
            mpsessiondata.append("5 or more")
            await msg.delete()
        #In the event that the emoji is not any of the above, we can eliminate an edge-case here
        else :
            await ctx.author.send("**Error:** Invalid reaction entered. Matchmaking cancelled.")
            return
    #If we dont get a response within 60 seconds it times out.
    except asyncio.TimeoutError:
        await ctx.author.send("**Error:**Timed out. Matchmaking cancelled.")
        return

    msg = await ctx.author.send("Now react with the symbol of **all** the DLCs you own! Click the green checkmark (✅) once done! \n 🔥 - The Anarchist \n 🤿 - Sunkean Treasures \n 🌹 - Botanica \n ❄️ - The Passage \n 🏛️ - Seat of Power \n 🚜 - Bright Harvest \n 🦁 - Land of Lions \n ⚓ - Docklands")
    #Saving the ID of this message we just sent
    msgid = msg.id

    await msg.add_reaction("🔥")
    await msg.add_reaction("🤿")
    await msg.add_reaction("🌹")
    await msg.add_reaction("❄️")
    await msg.add_reaction("🏛️")
    await msg.add_reaction("🚜")
    await msg.add_reaction("🦁")
    await msg.add_reaction("⚓")
    await msg.add_reaction("✅")

    #We create a function to check some properties of the payload
    #We check if the message ID is the same, so this is not a different message.
    #We also check if the user who reacted was the user who sent the command.
    def confirmDLCcheck(payload):
        return payload.message_id == msgid and payload.user_id == ctx.author.id and str(payload.emoji) == "✅"
    #Now we will try to wait for a reaction add event for 60 seconds
    try:
        payload = await bot.wait_for('raw_reaction_add', timeout=60.0, check=confirmDLCcheck)
        #Check reaction emoji
        DLC = []
        #DMC = ctx.author.DMChannel
        msg = await ctx.author.fetch_message(msgid)
        if msg.reactions[0].count == 2:
            DLC.append("The Anarchist")
        if msg.reactions[1].count == 2:
            DLC.append("Sunken Treasures")
        if msg.reactions[2].count == 2:
            DLC.append("Botanica")
        if msg.reactions[3].count == 2:
            DLC.append("The Passage")
        if msg.reactions[4].count == 2:
            DLC.append("Seat of Power")
        if msg.reactions[5].count == 2:
            DLC.append("Bright Harvest")
        if msg.reactions[6].count == 2:
            DLC.append("Land of Lions")
        if msg.reactions[7].count == 2:
            DLC.append("Docklands")

        if len(DLC) == 8:
            await ctx.author.send(f"DLCs selected:**All**")
            await msg.delete()
        elif len(DLC) == 0:
            await ctx.author.send(f"DLCs selected:**None**")
            await msg.delete()
        else:
            await ctx.author.send(f"DLCs selected:**{DLC}**")
            await msg.delete()
        #In the event that the emoji is not any of the above, we can eliminate an edge-case here
    #If we dont get a response within 60 seconds it times out.
    except asyncio.TimeoutError:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return

    msg = await ctx.author.send("Are you going to use mods?")
    #Saving the ID of this message we just sent
    msgid = msg.id

    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    #We create a function to check some properties of the payload
    #We check if the message ID is the same, so this is not a different message.
    #We also check if the user who reacted was the user who sent the command.
    def modcheck(payload):
        return payload.message_id == msgid and payload.user_id == ctx.author.id
    #Now we will try to wait for a reaction add event for 60 seconds
    try:
        payload = await bot.wait_for('raw_reaction_add', timeout=60.0, check=modcheck)
        #Check reaction emoji
        if str(payload.emoji) == "✅":
            mpsessiondata.append("Modded")
            await ctx.author.send("Modded: **Yes**")
            await msg.delete()
        elif str(payload.emoji) == "❌":
            mpsessiondata.append("Vanilla")
            await ctx.author.send("Modded: **No**")
            await msg.delete()

        #In the event that the emoji is not any of the above, we can eliminate an edge-case here
    #If we dont get a response within 60 seconds it times out.
    except asyncio.TimeoutError:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return
    
    msg = await ctx.author.send("Specify your timezone as an UTC offset! *For example: If your timezone is UTC+1, type in 1!*")
    def timezonecheck(payload):
        return payload.author == ctx.author and payload.guild is None
    try:
        payload = await bot.wait_for('message', timeout=60.0, check=timezonecheck)
        if len(payload.content) > 2 :
            await ctx.author.send("**Error:** Invalid timezone. Matchmaking cancelled.")
            return
        else :
            try :
                timezone = int(payload.content)
                mpsessiondata.append(f"UTC+{timezone}")
                await ctx.author.send(f"Timezone set to:** UTC+{timezone}**")
                await msg.delete()
            except:
                await ctx.author.send("**Error:** Invalid timezone. Matchmaking cancelled.")
    except:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return

    msg = await ctx.author.send("If you want to add additional notes to your listing, type it in now! Type in 'skip' to skip this step! Max length: 256 characters  \n *Examples of what to include (not mandatory): When you want to start, Duration of a match*")
    def additionalinfocheck(payload):
        return payload.author == ctx.author and payload.guild is None
    try:
        payload = await bot.wait_for('message', timeout=60.0, check=additionalinfocheck)
        if len(payload.content) > 256 :
            await ctx.author.send("**Error:** Message exceeded character limit. Matchmaking cancelled.")
            return
        else :
            if payload.content == "skip" :
                mpsessiondata.append("-")
                await ctx.author.send(f"Additional info: *Not specified*")
                await msg.delete()
            else :
                mpsessiondata.append(payload.content)
                await ctx.author.send(f"Additional info: {payload.content}")
                await msg.delete()
    except:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return
    
    msg = await ctx.author.send("Please review your listing! If everything looks good, hit ✅ to submit!")
    #Saving the ID of this message we just sent
    msgid = msg.id

    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    #Called to create a new multiplayer posting
    async def createposting(mpsessiondata, DLC):
        channel = bot.get_channel(int(retrievesetting("ANNOUNCECHANNEL", ctx.guild.id)))
        #yeah this is long lol
        await channel.send(f"**__Looking for Players: Anno 1800__** \n \n **Ubisoft Connect Username: ** {mpsessiondata[0]} \n **Gamemode: ** {mpsessiondata[1]} \n **Players: ** {mpsessiondata[2]} \n **DLC: ** {DLC} \n **Mods:** {mpsessiondata[3]} \n **Timezone:** {mpsessiondata[4]} \n **Additional info:** {mpsessiondata[5]} \n \n Contact {ctx.message.author.mention} in DMs if you are interested!")
    #We create a function to check some properties of the payload
    #We check if the message ID is the same, so this is not a different message.
    #We also check if the user who reacted was the user who sent the command.
    def confirmcheck(payload):
        return payload.message_id == msgid and payload.user_id == ctx.author.id
    #Now we will try to wait for a reaction add event for 60 seconds
    try:
        payload = await bot.wait_for('raw_reaction_add', timeout=60.0, check=confirmcheck)
        #Check reaction emoji
        if str(payload.emoji) == "✅":
            await ctx.author.send("[WIP] Matchmaking post made! Thanks for using my service! If you have found a bug or experienced issues, please contact `Hyper#0001`!")
            await createposting(mpsessiondata, DLC)
        elif str(payload.emoji) == "❌":
            await ctx.author.send("Cancelled matchmaking. If you have found a bug or experienced issues, please contact `Hyper#0001`!")
            return

        #In the event that the emoji is not any of the above, we can eliminate an edge-case here
    #If we dont get a response within 60 seconds it times out.
    except asyncio.TimeoutError:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return

#Reaction roles
@bot.event
async def on_raw_reaction_add(payload):
    setmsg = retrievesetting("ROLEREACTMSG", payload.guild_id)
    if int(setmsg) == payload.message_id :
        guild = bot.get_guild(payload.guild_id)
        emoji = discord.utils.get(guild.emojis, name=retrievesetting("LFGREACTEMOJI", payload.guild_id))
        if payload.emoji == emoji:
            member = guild.get_member(payload.user_id)
            try:
                role = discord.utils.get(guild.roles, name = retrievesetting("LFGROLENAME", payload.guild_id))
                await member.add_roles(role)
                print(f"[INFO]: Role {role} added to {member}")
                await member.send("You are now looking for games, and will be notified of any new multiplayer listing!")
            except:
                await member.send("**Error:** Server configuration error, contact an administrator! Unable to add role.")
                print(f"[ERROR]: Unable to modify roles for {member}. Possible permissions issue.")
@bot.event
async def on_raw_reaction_remove(payload):
    setmsg = retrievesetting("ROLEREACTMSG", payload.guild_id)
    if int(setmsg) == payload.message_id :
        guild = bot.get_guild(payload.guild_id)
        emoji = discord.utils.get(guild.emojis, name=retrievesetting("LFGREACTEMOJI", payload.guild_id))
        if payload.emoji == emoji:
            member = guild.get_member(payload.user_id)
            try:
                role = discord.utils.get(guild.roles, name = retrievesetting("LFGROLENAME", payload.guild_id))
                await member.remove_roles(role)
                print(f"[INFO]: Role {role} removed from {member}")
                await member.send("You will no longer get notifications on multiplayer game listings.")
            except:
                await member.send("**Error:** Server configuration error, contact an administrator! Unable to remove role.")
                print(f"[ERROR]: Unable to modify roles for {member}. Possible permissions issue.")

#Notes: TODO: add a command to actually create a message and correctly set it up


#Display the current settings for this guild.
@bot.command(hidden=True)
@commands.has_any_role("Moderator", "Admin")
async def settings(ctx):
    settingsdata = displaysettings(ctx.guild.id)
    if settingsdata == -1 :
        await ctx.channel.send("**Error:** No settings for this guild.")
    else :
        formatteddata = "".join(settingsdata)
        await ctx.channel.send(f"```Settings for guild {ctx.guild.id}: \n{formatteddata}```")

#Modify a value in the settings, use with care or it will break things
@bot.command(hidden=True)
@commands.has_any_role("Moderator","Admin")
async def modify(ctx, datatype, value) :
    if datatype not in datatypes :
        await ctx.channel.send("**Error: ** Invalid datatype.")
        return
    try:
        #int(value)
        modifysettings(datatype, value, ctx.guild.id)
        await ctx.channel.send(f"**{datatype}** is now set to **{value}** for guild **{ctx.guild.id}**!")
    except ValueError:
        await ctx.channel.send("**Error: **Invalid value!")
    except:
        await ctx.channel.send("**Error: ** Unknown error encountered!")


#
#   SETTINGS HANDLER
#
#It is basic and inefficient, but it works :P

def modifysettings(datatype, value, guildID):
    #Get all data from settings file if it exists
    if os.path.isfile(f"{guildID}_settings.cfg") :
        settings = open(f"{guildID}_settings.cfg","r")
        settingslines = settings.readlines()
        settings.close()
    #If not, we copy it from a template, then open it up
    else :
        shutil.copyfile("settingsdefault.cfg", f"{guildID}_settings.cfg")
        settings = open(f"{guildID}_settings.cfg","r")
        settingslines = settings.readlines()
        settings.close()

    linetomodify = 0
    i = 0
    #Find the datatype we want to modify
    while i != len(settingslines):
        if settingslines[i].split("=")[0] == datatype :
            linetomodify = i
            break
        i += 1
    print("Data modification info \n")
    print("Initial data:")
    print(settingslines)
    #Modify the entire line to be of new datatype and value
    settingslines[linetomodify] = datatype+"="+value+"\n"
    print("Modified data:")
    print(settingslines)
    #Open up the file, and write back the modified data.
    settings = open(f"{guildID}_settings.cfg", "a")
    settings.truncate(0)
    i = 0
    while i != len(settingslines) :
        settings.write(settingslines[i])
        i += 1
    settings.close()

def retrievesetting(datatype, guildID) :
    if datatype in datatypes :
        #Check if file exists, get all data
        if os.path.isfile(f"{guildID}_settings.cfg") :
            settings = open(f"{guildID}_settings.cfg","r")
            settingslines = settings.readlines()
            settings.close()
        #If not, we copy it from a template, then open it up
        else :
            shutil.copyfile("settingsdefault.cfg", f"{guildID}_settings.cfg")
            settings = open(f"{guildID}_settings.cfg","r")
            settingslines = settings.readlines()
            settings.close()
        #Search for the datatype, then get the value.
        i = 0
        while i != len(settingslines):
            if settingslines[i].split("=")[0] == datatype :
                linetoreturn = i
                break
            i += 1
        #Return the part after the "=" aka the value, stripped of \n
        #print("Returned this: " + settingslines[linetoreturn].split("=")[1].strip())
        return settingslines[linetoreturn].split("=")[1].strip()
    else :
        print(f"[INTERNAL ERROR]: Invalid datatype called in retrievesetting() (Called datatype: {datatype})")

def displaysettings(guildID) :
        #Check if file exists, get all data
    if os.path.isfile(f"{guildID}_settings.cfg") :
        settings = open(f"{guildID}_settings.cfg","r")
        settingslines = settings.readlines()
        settings.close()
        return settingslines

    #If not, then return -1, indicating the fact that there are no settings for this guild.
    else :
        return -1
#Gathers all valid datatypes from the default settings
#Notice: If there is a missing datatype in the specific guild settings files, stuff will break
#TODO: Settings versioning
def initsettings() :

    settingsdefault = open("settingsdefault.cfg", "r")
    defaultlines = settingsdefault.readlines()
    settingsdefault.close()
    for line in defaultlines :
        datatypes.append(line.split("=")[0])

#Run bot with token from .env
bot.run(TOKEN)
