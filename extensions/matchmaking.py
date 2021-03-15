import discord
from discord.ext import commands
import asyncio
import datetime

#Disclaimer: This extension is proprietary to Annoverse, and should not be used elsewhere without heavy modifications

class Matchmaking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Command to initalize matchmaking.
    #This is the main command of the bot, and is by far the most complicated one.
    #The TL;DR version of this command is the following: It DMs the user, asks them some questions,
    #evaluates the answers based on some criteria, then use those answers to construct a formatted
    #multiplayer listing, which will then in turn go into a preconfigured channel. It will also ping a
    #designated role if set. Can be limited as to which channels it can be run from via the COMMANDSCHANNEL setting.
    @commands.command(brief="Start setting up a new multiplayer listing.", description="Start matchmaking! After command execution, you will receive a direct message to help you set up a multiplayer listing! Takes no arguments.", aliases=['multiplayer', 'init', 'match','multi','mp'], usage=f"matchmaking")
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.user,wait=False)
    @commands.cooldown(1, 43200, type=commands.BucketType.member)
    async def matchmaking(self, ctx):
        cmdchannel = await self.bot.DBHandler.retrievesetting("COMMANDSCHANNEL", ctx.guild.id)
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
                    payload = await self.bot.wait_for('message', timeout=300.0, check=usernamecheck)
                    #32char username limit
                    if len(payload.content) > 32 :
                        await msg.delete()
                        embed=discord.Embed(title=self.bot.warnDataTitle, description="Username too long. Maximum 32 characters", color=self.bot.warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                    else :
                        await modifymatchmaking(qType, payload.content, isModifying)
                        embed=discord.Embed(title="✅ Username set.", description=f"Your Ubisoft Connect username is: **{payload.content}**", color=mpEmbedColor)
                        await ctx.author.send(embed=embed)
                        return 0

                except:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
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
                    payload = await self.bot.wait_for('raw_reaction_add', timeout=300.0, check=gamemodecheck)

                    #Check reaction emoji
                    if str(payload.emoji) == "⚔️":
                        gamemode = "PvP"
                        
                    elif str(payload.emoji) == "🛡️":
                        gamemode = "Co-Op"
                    
                    elif str(payload.emoji) not in gameModeEmojies:
                        await msg.delete()
                        embed = discord.Embed(title=self.bot.warnEmojiTitle, description=self.bot.warnEmojiDesc , color=self.bot.warnColor)
                        await ctx.author.send(embed=embed)
                        return -2

                    #Save it to list
                    await modifymatchmaking(qType, gamemode, isModifying)
                    
                    embed=discord.Embed(title="✅ Gamemode set.", description=f"Your gamemode is set to:  **{gamemode}**.", color=mpEmbedColor)
                    await ctx.author.send(embed=embed)
                    return 0
                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
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
                    payload = await self.bot.wait_for('raw_reaction_add', timeout=300.0, check=playercountcheck)
                    i = 0
                    playernum = "[DefaultCount] If you see this, something is very wrong..."
                    #Check if emoj is invalid, otherwise check for match & break on match
                    while i != len(playersOptions):
                        if str(payload.emoji) not in playersEmoji :
                            await msg.delete()
                            embed = discord.Embed(title=self.bot.warnEmojiTitle, description=self.bot.warnEmojiDesc, color=self.bot.warnColor)
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
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
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
                    payload = await self.bot.wait_for('raw_reaction_add', timeout=300.0, check=confirmDLCcheck)
                    #We have to fetch here otherwise reaction counting does not work for some reason..?
                    msg = await ctx.author.fetch_message(msg.id)
                    #Count all the emojies
                    i = 0
                    while i != len(allDLCs) :
                        #If emoji is invalid, we re-run question    
                        if str(msg.reactions[i]) not in DLCemojies :
                            await msg.delete()
                            embed = discord.Embed(title=self.bot.warnEmojiTitle, description=self.bot.warnEmojiDesc, color=self.bot.warnColor)
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
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
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
                    payload = await self.bot.wait_for('raw_reaction_add', timeout=300.0, check=modcheck)
                    #Check reaction emoji
                    if str(payload.emoji) == "✅":
                        modded = "Yes"
                    elif str(payload.emoji) == "❌":
                        modded = "No"
                    
                    elif str(payload.emoji) not in modemojies :
                        await msg.delete()
                        embed = discord.Embed(title=self.bot.warnEmojiTitle, description=self.bot.warnEmojiDesc, color=self.bot.warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                    
                    await modifymatchmaking(qType, modded, isModifying)
                    await msg.delete()
                    embed=discord.Embed(title="✅ Mods set.", description=f"Modded: **{modded}**", color=mpEmbedColor)
                    await ctx.author.send(embed=embed)
                    return 0

                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1
            
            if qType == "TimeZone" :
                embed=discord.Embed(title="Specify your timezone as an UTC offset!", description="For example: If your timezone is UTC+1, **type in 1!**", color=mpEmbedColor)
                embed.set_footer(text="If you are unsure what timezone you are in, check here: https://www.timeanddate.com/time/map")
                msg = await ctx.author.send(embed=embed)
                def timezonecheck(payload):
                    return payload.author == ctx.author and payload.guild is None
                try:
                    payload = await self.bot.wait_for('message', timeout=300.0, check=timezonecheck)
                    try:
                        #We will check if it is an int
                        int(payload.content)
                        #Check if it is a valid value for a timezone
                        if int(payload.content) not in range(-12, 14) :
                            await msg.delete()
                            embed=discord.Embed(title="⚠️ Invalid timezone!", description="Please enter a valid timezone.", color=self.bot.warnColor)
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
                        embed=discord.Embed(title="⚠️ Invalid timezone!", description="Please enter a valid timezone.", color=self.bot.warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1
            if qType == "Additional" :
                embed=discord.Embed(title="If you want to add additional notes to your listing, type it in now!", description="Examples of what to include (not mandatory): When you want to start, Duration of a match, Mods (if any)", color=mpEmbedColor)
                embed.set_footer(text="Type in 'skip' to skip this step! Max length: 256 characters")
                msg = await ctx.author.send(embed=embed)
                def additionalinfocheck(payload):
                    return payload.author == ctx.author and payload.guild is None
                try:
                    payload = await self.bot.wait_for('message', timeout=300.0, check=additionalinfocheck)
                    if len(payload.content) > 256 :
                        await msg.delete()
                        embed = discord.Embed(title=self.bot.warnDataTitle, description="Additional info exceeded character limit! Maximum length: 256 characters", color=self.bot.warnColor)
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
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
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
                        channel = self.bot.get_channel(await self.bot.DBHandler.retrievesetting("ANNOUNCECHANNEL", ctx.guild.id))
                        lfgrole = ctx.guild.get_role(await self.bot.DBHandler.retrievesetting("LFGROLE", ctx.guild.id))
                        #If LFG role is not set up, we will not include a mention to it at the end.
                        if await self.bot.DBHandler.retrievesetting("LFGROLE", ctx.guild.id) == 0 :
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
                        #If for whatever reason the message cannot be made, we message the user about it.
                        print(f"[ERROR]: Could not create listing for {ctx.author}. Did you set up matchmaking?")
                        embed=discord.Embed(title="❌ Error: Exception encountered.", description="Failed to generated listing. Contact an administrator! Operation cancelled.", color=self.bot.errorColor)
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
                        payload = await self.bot.wait_for('raw_reaction_add', timeout=300.0, check=confirmModifyCheck)

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
                                        embed=discord.Embed(title="❌ Exceeded error limit.", description="You have made too many errors. Please retry your submission.", color=self.bot.errorColor)
                                        await ctx.author.send(embed=embed)
                                        return -1
                                    else:
                                        warns += 1
                            return 0
                            
                        else :
                            #We have to cancel the entire command here, as it would be way too difficult to implement looping here as well
                            embed = discord.Embed(title=self.bot.errorEmojiTitle, description="Cancelled matchmaking.", color=self.bot.errorColor)
                            await ctx.author.send(embed=embed)
                            return -1

                    except asyncio.TimeoutError :
                        embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                        await ctx.author.send(embed=embed)
                        return -1
                    
                    
                #We create a function to check some properties of the payload
                #We check if the message ID is the same, so this is not a different message.
                #We also check if the user who reacted was the user who sent the command.
                def confirmcheck(payload):
                    return payload.message_id == msg.id and payload.user_id == ctx.author.id
                #Now we will try to wait for a reaction add event for 60 seconds
                try:
                    payload = await self.bot.wait_for('raw_reaction_add', timeout=300.0, check=confirmcheck)
                    #Check reaction emoji
                    if str(payload.emoji) == "✅":
                        if await createposting(mpsessiondata) == -1:
                            return -1
                        else :
                            embed=discord.Embed(title="✅ Listing submitted!", description="Thanks for using the service! If you have found a bug or want to give feedback, please contact `Hyper#0001`!", color=self.bot.embedGreen)
                            await ctx.author.send(embed=embed)
                            return 1
                    elif str(payload.emoji) == "🖊️":
                        if await modifylisting() == 0 :
                            #If modification is successful, repeat this step (confirmcheck)
                            return -3
                        else :
                            embed=discord.Embed(title="❌ Modification failed.", description="If you have found a bug or want to give feedback, please contact `Hyper#0001`!", color=self.bot.errorColor)
                            await ctx.author.send(embed=embed)
                            print(f"[INFO]: {ctx.author} User failed modification.")
                            return -1


                    elif str(payload.emoji) == "❌":
                        embed=discord.Embed(title="❌ Submission cancelled.", description="If you have found a bug or want to give feedback, please contact `Hyper#0001`!", color=self.bot.errorColor)
                        await ctx.author.send(embed=embed)
                        print(f"[INFO]: {ctx.author} User cancelled matchmaking.")
                        return -1
                    else :
                        await msg.delete()
                        embed = discord.Embed(title=self.bot.warnEmojiTitle, description=self.bot.warnEmojiDesc, color=self.bot.warnColor)
                        await ctx.author.send(embed=embed)
                        return -2

                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
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
                self.matchmaking.reset_cooldown(ctx)
                return
            #If it succeeds, we move to the next question
            elif errcode == 0:
                question += 1
            #If editing, we will add one to the edits variable.
            elif errcode == -3:
                if edits == 6:
                    embed=discord.Embed(title="❌ Exceeded edit limit.", description="You cannot make more edits to your submission. Please try executing the command again.",color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    self.matchmaking.reset_cooldown(ctx)
                    return
                else :
                    edits += 1
            #If it is an invalid value, add a warn
            elif errcode == -2 :
                if warns == 4:
                    embed=discord.Embed(title="❌ Exceeded error limit.", description="You have made too many errors. Please retry your submission.", color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    self.matchmaking.reset_cooldown(ctx)
                    return
                else:
                    warns += 1
        print("[INFO]matchmaking command exited successfully.")


    @matchmaking.error
    async def matchmaking_error(self, ctx, error):
        #Due to it's performance requirements and complexity, this command is limited to 1 per user
        if isinstance(error, commands.MaxConcurrencyReached):
            embed = discord.Embed(title="❌ Error: Max concurrency reached!", description="You already have a matchmaking request in progress.", color=self.bot.errorColor)
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
            await ctx.channel.send(embed=embed)

    

    #Reaction roles for LFG, and subscribing to listings
    #Directly related to matchmaking functionality
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        #Check if we are in a guild so we dont bombard the database with Null errors.
        if payload.guild_id != None : 
            guild = self.bot.get_guild(payload.guild_id)
            #Check if it is the message we set
            if await self.bot.DBHandler.retrievesetting("ROLEREACTMSG", payload.guild_id) == payload.message_id :
                #Check the emoji
                if payload.emoji == self.bot.get_emoji(await self.bot.DBHandler.retrievesetting("LFGREACTIONEMOJI", guild.id)) and payload.user_id != self.bot.user.id:
                    member = guild.get_member(payload.user_id)
                    try:
                        #Then set the role for the user
                        role = guild.get_role(await self.bot.DBHandler.retrievesetting("LFGROLE", guild.id))
                        await member.add_roles(role)
                        print(f"[INFO]: Role {role} added to {member}")
                        #Also DM the user about the change, and let them know that the action was performed successfully.
                        embed=discord.Embed(title="💬 Notifications enabled.", description="You are now looking for games, and will be notified of any new multiplayer listing!", color=self.bot.embedGreen)
                        await member.send(embed=embed)
                        return
                    except:
                        #In case anything goes wrong, we will tell the user to bully admins who can then bully me :) /s
                        embed=discord.Embed(title="❌ Error: Exception encountered.", description="Failed to add role. Contact an administrator! Operation cancelled.", color=self.bot.errorColor)
                        await member.send(embed=embed)
                        print(f"[ERROR]: Unable to modify roles for {member}. Possible permissions issue.")
                        return
            elif await self.bot.DBHandler.retrievesetting("ANNOUNCECHANNEL", guild.id) == payload.channel_id:
                #I put a fair number of logging in here to track abuse of this feature
                if str(payload.emoji) == "⏫" and payload.user_id != self.bot.user.id:
                    #The listing message
                    listing = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
                    #The person who reacted
                    member = guild.get_member(payload.user_id)
                    #If the message is older than a week, we ignore this request
                    if (datetime.datetime.utcnow() - listing.created_at).days >= 7 :
                        print(f"[INFO]: {member.name}#{member.discriminator} tried to join an expired listing.")
                        return
                    #Get context for this message
                    ctx = await self.bot.get_context(listing)
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
                        embed=discord.Embed(title=f"📝 You subscribed to {host.name}'s game!", description="They will receive a notification when their desired playercap has been reached.", color=self.bot.embedGreen)
                        await member.send(embed=embed)
                        print(f"[INFO]: {member.name}#{member.discriminator} expressed interest to join {host.name}#{host.discriminator}'s game.")
                    #If we have reached the desired playercount, we will message to the host. This message will get every time a new player reacts.
                    if len(interestedPlayers) >= playerCount :
                        embed=discord.Embed(title="📝 Your listing reached your set playercap!", description=f"Hello! Just letting you know that your multiplayer listing on **{guild.name}** has reached {playerCount} or more interested players.\nPlayers who want to play with you in this match: {interestedMentions}", color=self.bot.embedGreen)
                        embed.set_footer(text="If you believe that this feature was abused, contact a moderator immediately!")
                        await host.send(embed=embed)
                        print(f"[INFO]: {host.name}#{host.discriminator}'s listing reached cap. Host notified.")
                    return



    #Same thing but in reverse
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id != None :
            setmsg = await self.bot.DBHandler.retrievesetting("ROLEREACTMSG", payload.guild_id)
            guild = self.bot.get_guild(payload.guild_id)
            if setmsg == payload.message_id :
                if payload.emoji == self.bot.get_emoji(await self.bot.DBHandler.retrievesetting("LFGREACTIONEMOJI", guild.id)) and payload.user_id != self.bot.user.id:
                    member = guild.get_member(payload.user_id)
                    try:
                        role = guild.get_role(await self.bot.DBHandler.retrievesetting("LFGROLE", guild.id))
                        await member.remove_roles(role)
                        print(f"[INFO]: Role {role} removed from {member}")
                        embed=discord.Embed(title="💬 Notifications disabled.", description="You will no longer get notifications on multiplayer game listings.", color=self.bot.errorColor)
                        await member.send(embed=embed)
                    except:
                        embed=discord.Embed(title="❌ Error: Exception encountered.", description="Failed to remove role. Contact an administrator! Operation cancelled.", color=self.bot.errorColor)
                        await member.send(embed=embed)
                        print(f"[ERROR]: Unable to modify roles for {member}. Possible permissions or hierarchy issue.")

            elif await self.bot.DBHandler.retrievesetting("ANNOUNCECHANNEL", guild.id) == payload.channel_id:
                #I put a fair number of logging in here to track abuse of this feature
                if str(payload.emoji) == "⏫" and payload.user_id != self.bot.user.id:
                    #The person who reacted
                    member = guild.get_member(payload.user_id)
                    #Listing
                    listing = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
                    listingContent = listing.embeds
                    listingLines = listingContent[0].description.splitlines()
                    #Getting host
                    ctx = await self.bot.get_context(listing)
                    converter = commands.MemberConverter()
                    host = await converter.convert(ctx, listingLines[len(listingLines)-1].split("Contact ")[1].split(" in")[0])
                    #If the message is older than a week, we ignore this request
                    if (datetime.datetime.utcnow() - listing.created_at).days >= 7 :
                        print(f"[INFO]: {member.name}#{member.discriminator} tried to join an expired listing.")
                        return
                    if member != host :
                        print(f"[INFO]: {member.name}#{member.discriminator} removed themselves from a listing.")
                        embed=discord.Embed(title=f"📝 You have unsubscribed from {host.name}'s listing.", description="The host will no longer see you signed up to this listing.", color=self.bot.errorColor)
                        await member.send(embed=embed)
                        return

def setup(bot):
    print("[INFO] Adding cog: Matchmaking...")
    bot.add_cog(Matchmaking(bot))