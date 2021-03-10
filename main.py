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
creatorID = 163979124820541440
bot = commands.Bot(command_prefix='!', intents= discord.Intents.all(), owner_id=creatorID)
#This is just my user ID, used for setting up who can & cant use priviliged commands along with a server owner.


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
    #Populate datatypes[] with all valid datatypes
    initsettings()

#
#Normal commands
#
#Note: These commands can be used by everyone on the server.

#Gets the ping of the bot.
@bot.command(description="Displays bot ping.")
async def ping(ctx):
    await ctx.send(f"Pong! ({round(bot.latency * 1000)}ms)")

#A more fun way to get the ping.
@bot.command(hidden = True)
async def LEROY(ctx):
    await ctx.send(f"JEEEEEEENKINS! ({round(bot.latency * 1000)}ms) \n \n Oh my god he just ran in. 👀")


#Command to initalize matchmaking.
#This is the main command of the bot, and is by far the most complicated one.
#The TL;DR version of this command is the following: It DMs the user, asks them some questions,
#evaluates the answers based on some criteria, then use those answers to construct a formatted
#multiplayer listing, which will then in turn go into a preconfigured channel. It will also ping a
#designated role if set. Can be limited as to which channels it can be run from via the COMMANDSCHANNEL setting.
@bot.command(description="Start matchmaking! Takes no arguments.", aliases=['multiplayer', 'init'])
@commands.guild_only()
@commands.max_concurrency(1, per=commands.BucketType.member,wait=False)
async def matchmaking(ctx):
    cmdchannel = retrievesetting("COMMANDSCHANNEL", ctx.guild.id)
    #Performs check if the command is executed in the right channel, if this is 0, this feature is disabled.
    if cmdchannel != "0" :
        if int(cmdchannel) != ctx.channel.id :
            print("[WARN]: Matchmaking initiated in disabled channel.")
            return
    mpsessiondata = []
    #Messaging the channel to provide feedback
    #It sends these seperately to ideally grab the user's attention, but can be merged.
    await ctx.channel.send(f"Starting matchmaking for **{ctx.author.name}**. Check your DMs!")
    await ctx.author.send("**Hello! I will help you set up a multiplayer listing!**")
    #Sending initial DM
    msg = await ctx.author.send("Please type in your Ubisoft Connect username!")
    def usernamecheck(payload):
        return payload.author == ctx.author and payload.guild is None
    try:
        payload = await bot.wait_for('message', timeout=90.0, check=usernamecheck)
        #32char username limit
        if len(payload.content) > 32 :
            await ctx.author.send("**Error:** Invalid username. (Too long) Matchmaking cancelled.")
            return
        else :
            mpsessiondata.append(payload.content)
            await msg.delete()
            await ctx.author.send(f"Ubisoft Connect Username set to:** {payload.content}**")

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
            await msg.delete()
            await ctx.author.send("Gamemode set to **PvP**")
            mpsessiondata.append("PvP")
        elif str(payload.emoji) == "🛡️":
            await msg.delete()
            await ctx.author.send("Gamemode set to **Co-op**")
            mpsessiondata.append("Co-op")
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
            await msg.delete()
            await ctx.author.send("Player count set to: **2**")
            mpsessiondata.append("2")
        elif str(payload.emoji) == "3️⃣":
            await msg.delete()
            await ctx.author.send("Player count set to: **3**")
            mpsessiondata.append("3")
        elif str(payload.emoji) == "4️⃣":
            await msg.delete()
            await ctx.author.send("Player count set to: **4**")
            mpsessiondata.append("4")
        elif str(payload.emoji) == "♾️":
            await msg.delete()
            await ctx.author.send("Player count set to: **5 or more**")
            mpsessiondata.append("5 or more")
        else :
            await ctx.author.send("**Error:** Invalid reaction entered. Matchmaking cancelled.")
            return
    #If we dont get a response within 60 seconds it times out.
    except asyncio.TimeoutError:
        await ctx.author.send("**Error:**Timed out. Matchmaking cancelled.")
        return

    msg = await ctx.author.send("Now react with the symbol of **all** the DLCs you want to use! Click the green checkmark (✅) once done! \n 🔥 - The Anarchist \n 🤿 - Sunkean Treasures \n 🌹 - Botanica \n ❄️ - The Passage \n 🏛️ - Seat of Power \n 🚜 - Bright Harvest \n 🦁 - Land of Lions \n ⚓ - Docklands \n*Note: If you do not own any DLC, just simply press ✅ to continue.*")
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
            await msg.delete()
            await ctx.author.send(f"DLCs selected:**All**")
            DLC = "All"
        elif len(DLC) == 0:
            await msg.delete()
            await ctx.author.send(f"DLCs selected:**None**")
            DLC = "None"
        else:
            await msg.delete()
            await ctx.author.send(f"DLCs selected:**{DLC}**")
        
    except asyncio.TimeoutError:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return
    #Add msg
    msg = await ctx.author.send("Are you going to use mods?")
    msgid = msg.id
    #Add emoji
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    def modcheck(payload):
        return payload.message_id == msgid and payload.user_id == ctx.author.id
    try:
        payload = await bot.wait_for('raw_reaction_add', timeout=60.0, check=modcheck)
        #Check reaction emoji
        if str(payload.emoji) == "✅":
            await msg.delete()
            mpsessiondata.append("Yes")
            await ctx.author.send("Modded: **Yes**")
        elif str(payload.emoji) == "❌":
            await msg.delete()
            mpsessiondata.append("No")
            await ctx.author.send("Modded: **No**")
        else :
            await ctx.author.send("**Error:** Invalid reaction entered. Matchmaking cancelled.")
            return

    except asyncio.TimeoutError:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return
    
    msg = await ctx.author.send("Specify your timezone as an UTC offset! *For example: If your timezone is UTC+1,* ***type in 1!*** \n*If you are unsure what timezone you are in, check here:* <https://www.timeanddate.com/time/map>")
    def timezonecheck(payload):
        return payload.author == ctx.author and payload.guild is None
    try:
        payload = await bot.wait_for('message', timeout=60.0, check=timezonecheck)
        try:
            #We will check if it is an int
            int(payload.content)
            #Check if it is a valid value for a timezone
            if int(payload.content) not in range(-11, 14) :
                await ctx.author.send("**Error:** Invalid timezone. Matchmaking cancelled.")
                return
            #If it is smaller than 0, we will make it UTC-
            elif int(payload.content) < 0 :
                timezone = int(payload.content)
                mpsessiondata.append(f"UTC{timezone}")
                await msg.delete()
                await ctx.author.send(f"Timezone set to:** UTC{timezone}**")
            #Otherwise UTC+
            else :
                timezone = int(payload.content)
                mpsessiondata.append(f"UTC+{timezone}")
                await msg.delete()
                await ctx.author.send(f"Timezone set to:** UTC+{timezone}**")
        except ValueError:
            await ctx.author.send("**Error:** Invalid timezone. Matchmaking cancelled.")
            return
    except asyncio.TimeoutError:
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
                await msg.delete()
                await ctx.author.send(f"Additional info: *Not specified*")
            else :
                mpsessiondata.append(payload.content)
                await msg.delete()
                await ctx.author.send(f"Additional info: {payload.content}")
    except:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return
    
    await ctx.author.send(f"```Looking for Players: Anno 1800 \n \n Ubisoft Connect Username: {mpsessiondata[0]} \n Gamemode: {mpsessiondata[1]} \n Players: {mpsessiondata[2]} \n DLC: {DLC} \n Mods: {mpsessiondata[3]} \n Timezone: {mpsessiondata[4]} \n Additional info: {mpsessiondata[5]} \n \n Contact {ctx.message.author} in DMs if you are interested!```")
    msg = await ctx.author.send("Please review your listing! If everything looks good, hit ✅ to submit!")
    #Saving the ID of this message we just sent
    msgid = msg.id
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    #Called to create a new multiplayer posting
    async def createposting(mpsessiondata, DLC):
        try:
            channel = bot.get_channel(int(retrievesetting("ANNOUNCECHANNEL", ctx.guild.id)))
            lfgrole = ctx.guild.get_role(int(retrievesetting("LFGROLE", ctx.guild.id)))
            #If LFG role is not set up, we will not include a mention to it at the end.
            if retrievesetting("LFGROLE", ctx.guild.id) == "-1" :
                #yeah this is long lol
                await channel.send(f"**__Looking for Players: Anno 1800__** \n \n **Ubisoft Connect Username: ** {mpsessiondata[0]} \n **Gamemode: ** {mpsessiondata[1]} \n **Players: ** {mpsessiondata[2]} \n **DLC: ** {DLC} \n **Mods:** {mpsessiondata[3]} \n **Timezone:** {mpsessiondata[4]} \n **Additional info:** {mpsessiondata[5]} \n \n Contact {ctx.message.author.mention} in DMs if you are interested!")
                await ctx.author.send("Matchmaking post made! Thanks for using my service! If you have found a bug or experienced issues, please contact `Hyper#0001`!")
                print(f"[INFO]: {ctx.author} User created new multiplayer listing. Session: {mpsessiondata} DLC: {DLC}")   
            else :
                await channel.send(f"**__Looking for Players: Anno 1800__** \n \n **Ubisoft Connect Username: ** {mpsessiondata[0]} \n **Gamemode: ** {mpsessiondata[1]} \n **Players: ** {mpsessiondata[2]} \n **DLC: ** {DLC} \n **Mods:** {mpsessiondata[3]} \n **Timezone:** {mpsessiondata[4]} \n **Additional info:** {mpsessiondata[5]} \n \n Contact {ctx.message.author.mention} in DMs if you are interested! \n \n {lfgrole.mention}")
                await ctx.author.send("Matchmaking post made! Thanks for using my service! If you have found a bug or experienced issues, please contact `Hyper#0001`!")
                print(f"[INFO]: {ctx.author} User created new multiplayer listing. Session: {mpsessiondata} DLC: {DLC}")
        except:
        #    #If for whatever reason the message cannot be made, we message the user about it.
            print(f"[ERROR]: Could not create listing for {ctx.author}. Did you set up matchmaking?")
            await ctx.author.send("**Error: **Exception encountered when trying to generate listing. Contact an administrator! Matchmaking cancelled!")
            return  
        
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
            await createposting(mpsessiondata, DLC)
        elif str(payload.emoji) == "❌":
            await ctx.author.send("Cancelled matchmaking. If you have found a bug or experienced issues, please contact `Hyper#0001`!")
            print(f"[INFO]: {ctx.author} User cancelled matchmaking.")
            return
        else :
            await ctx.author.send("**Error:** Invalid reaction entered. Matchmaking cancelled.")
            return

    #If we dont get a response within 60 seconds it times out.
    except asyncio.TimeoutError:
        await ctx.author.send("**Error: **Timed out. Matchmaking cancelled.")
        return

@matchmaking.error
async def matchmaking_error(ctx, error):
    if isinstance(error, commands.MaxConcurrencyReached):
        await ctx.channel.send("**Error: ** You already have a matchmaking process in progress.")

#Reaction roles for LFG
@bot.event
async def on_raw_reaction_add(payload):
    setmsg = retrievesetting("ROLEREACTMSG", payload.guild_id)
    #Check if it is the message we set
    if int(setmsg) == payload.message_id and payload.user_id != bot.user.id :
        guild = bot.get_guild(payload.guild_id)
        emoji = bot.get_emoji(int(retrievesetting("LFGREACTEMOJI", guild.id)))
        #Check the emoji
        if payload.emoji == emoji:
            member = guild.get_member(payload.user_id)
            try:
                #Then set the role for the user
                role = guild.get_role(int(retrievesetting("LFGROLE", guild.id)))
                await member.add_roles(role)
                print(f"[INFO]: Role {role} added to {member}")
                #Also DM the user about the change, and let them know that the action was performed successfully.
                await member.send("You are now looking for games, and will be notified of any new multiplayer listing!")
            except:
                #In case anything goes wrong, we will tell the user to bully admins who can then bully me :) /s
                await member.send("**Error:** Server configuration error, contact an administrator! Unable to add role.")
                print(f"[ERROR]: Unable to modify roles for {member}. Possible permissions issue.")

#Same thing but in reverse
@bot.event
async def on_raw_reaction_remove(payload):
    setmsg = retrievesetting("ROLEREACTMSG", payload.guild_id)
    if int(setmsg) == payload.message_id :
        guild = bot.get_guild(payload.guild_id)
        emoji = bot.get_emoji(int(retrievesetting("LFGREACTEMOJI", guild.id)))
        if payload.emoji == emoji and payload.user_id != bot.user.id:
            member = guild.get_member(payload.user_id)
            try:
                role = guild.get_role(int(retrievesetting("LFGROLE", guild.id)))
                await member.remove_roles(role)
                print(f"[INFO]: Role {role} removed from {member}")
                await member.send("You will no longer get notifications on multiplayer game listings.")
            except:
                await member.send("**Error:** Server configuration error, contact an administrator! Unable to remove role.")
                print(f"[ERROR]: Unable to modify roles for {member}. Possible permissions or hierarchy issue.")

#
#ADMIN/Config commands
#
#Note: These commands are intended to be only used by people authorized by the server owner.


#Check performed to see if the person is either the guild owner or the bot owner.
def hasOwner(ctx):
    return ctx.author.id == creatorID or ctx.author.id == ctx.guild.owner_id

#Check performed to see if the user has priviliged access.
def hasPriviliged(ctx):
    #Gets a list of all the roles the user has, then gets the name from that.
    userRoles = [x.name for x in ctx.author.roles]
    #Check if any of the roles in user's roles are contained in the priviliged roles.
    return any(role in userRoles for role in checkprivs(ctx.guild.id)) or (ctx.author.id == creatorID or ctx.author.id == ctx.guild.owner_id)

#Fun command, because yes. (Needs mod privilege as it can be abused for spamming)
@bot.command(hidden = True, description = "Deploys the duck army.")
@commands.check(hasPriviliged)
@commands.guild_only()
async def quack(ctx):
    await ctx.channel.send("🦆")
    await ctx.message.delete()

#Commands used to add and/or remove other roles from executing potentially unwanted things
@bot.command(hidden=True, aliases=['addprivrole', 'addbotadminrole'], description="Adds a role to the list of priviliged roles, allowing them to execute admin commands.")
@commands.check(hasOwner)
@commands.guild_only()
async def addpriviligedrole(ctx, role):
    rolesRaw = retrievesetting("PRIVROLES", ctx.guild.id)
    roles = rolesRaw.split(",")
    if role not in roles :
        roles.append(role)
        rolesRaw = ",".join(roles)
        modifysettings("PRIVROLES", rolesRaw, ctx.guild.id)
        await ctx.channel.send(f"**{role}** has been granted bot admin priviliges.")
    else :
        await ctx.channel.send("**Error:** Role already added.")

@addpriviligedrole.error
async def addprivilegedrole_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.channel.send("**Error: ** Insufficient permissions.")

@bot.command(hidden=True, aliases=['remprivrole', 'removeprivrole', 'removebotadminrole', 'rembotadminrole'], description="Removes a role to the list of priviliged roles, revoking their permission to execute admin commands.")
@commands.check(hasOwner)
@commands.guild_only()
async def removepriviligedrole(ctx,role):
    rolesRaw = retrievesetting("PRIVROLES", ctx.guild.id)
    roles = rolesRaw.split(",")
    if role in roles :
        roles.remove(role)
        rolesRaw = ",".join(roles)
        modifysettings("PRIVROLES", rolesRaw, ctx.guild.id)
        await ctx.channel.send(f"**{role}** had it's bot admin priviliges revoked.")
    else :
        await ctx.channel.send("**Error:** Role not found.")

@removepriviligedrole.error
async def removeprivilegedrole_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.channel.send("**Error: ** Insufficient permissions.")


#Ahh yes, the setup command... *instant PTSD*
#It basically just collects a bunch of values from the user, in this case an admin, and then changes the settings
#based on that, instead of the admin having to use !modify for every single value
#TL;DR: fancy setup thing
@bot.command(hidden=True, description = "Used to set up and configurate different parts of the bot. Only usable by priviliged users.")
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
            modifysettings("LFGREACTEMOJI", str(reactemoji.id), ctx.guild.id)
            modifysettings("LFGROLE", str(role.id), ctx.guild.id)
            modifysettings("ROLEREACTMSG", str(msg.id), ctx.guild.id)
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
                cmdchannel = "0"
                await ctx.channel.send("Commands channel **disabled.**")
            else :
                cmdchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                await ctx.channel.send(f"Commands channel set to {cmdchannel.mention}")

            await ctx.channel.send("Now please mention the channel where the multiplayer listings should go. If you already have LFG reaction roles set up, they will also be pinged once a listing goes live.")
            payload = await bot.wait_for('message', timeout=60.0, check=check)
            announcechannel = await commands.TextChannelConverter().convert(ctx, payload.content)
            await ctx.channel.send(f"Multiplayer listings channel set to {announcechannel.mention}")

            #Executing based on info

            if cmdchannel == "0" :
                modifysettings("COMMANDSCHANNEL", "0", ctx.guild.id)
            else :
                modifysettings("COMMANDSCHANNEL", str(cmdchannel.id), ctx.guild.id)
            modifysettings("ANNOUNCECHANNEL", str(announcechannel.id), ctx.guild.id)
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
    if isinstance(error, commands.CheckFailure):
        await ctx.channel.send("**Error: ** Insufficient permissions.")
    elif isinstance(error, commands.MaxConcurrencyReached):
        await ctx.channel.send("**Error: ** Setup is already running.")

#Command used for deleting a guild settings file
@bot.command(hidden=True, description = "Resets all settings. Irreversible.")
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
            deletesettings(ctx.guild.id)
            await ctx.channel.send("Settings reset. \n \n *Goodbye cruel world!* 😢")
        elif str(payload.emoji) == "❌" :
            await ctx.channel.send("Settings reset cancelled by user.")
        else :
            await ctx.channel.send("**Error:** Invalid reaction. Settings preserved.")
    except asyncio.TimeoutError:
        await ctx.channel.send("**Error:** Timed out. Settings preserved.")

@resetsettings.error
async def resetsettings_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.channel.send("**Error: ** Insufficient permissions.")

#Display the current settings for this guild.
@bot.command(hidden=True, description="Displays the settings for the current guild.")
@commands.check(hasPriviliged)
@commands.guild_only()
async def settings(ctx):
    settingsdata = displaysettings(ctx.guild.id)
    if settingsdata == -1 :
        await ctx.channel.send("**Error:** No settings for this guild.")
    else :
        formatteddata = "".join(settingsdata)
        await ctx.channel.send(f"```Settings for guild {ctx.guild.id}: \n \n{formatteddata}```")

@settings.error
async def settings_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.channel.send("**Error: ** Insufficient permissions.")

#Modify a value in the settings, use with care or it will break things
@bot.command(hidden=True, description="Modifies a single value in the settings, can break things! Use !setup instead.")
@commands.check(hasPriviliged)
@commands.guild_only()
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

@modify.error
async def modify_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.channel.send("**Error: ** Insufficient permissions.")


#
#   SETTINGS HANDLER
#
#It is basic and inefficient, but it works :P

#Deletes a guild specific settings file.
def deletesettings(guildID):
    os.remove(f"{guildID}_settings.cfg")
    print(f"[WARN]: Settings have been reset for guild {guildID}.")

#Returns the priviliged roles for a specific guild as a list.
def checkprivs(guildID):
    rolesRaw = retrievesetting("PRIVROLES", guildID)
    roles = rolesRaw.split(",")
    return roles

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
