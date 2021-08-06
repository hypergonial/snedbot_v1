import asyncio
import logging
import time
import uuid
from dataclasses import dataclass

import discord
from discord.ext import commands
from discord.ext import tasks
'''
Disclaimer: This extension is proprietary to Annoverse, and should not be used elsewhere without heavy modifications!
It is also really old & may need a rewrite to properly handle buttons, and just a general code cleanup.
'''
#Check to see if matchmaking is set up or not
async def is_setup(ctx):
    result = await ctx.bot.pool.fetch('''SELECT * FROM matchmaking_config WHERE guild_id = $1''', ctx.guild.id)
    if len(result) != 0 and result[0]:
        if result[0].get('announce_channel_id'):
            return True
    return False

def is_anno_guild(ctx):
    return ctx.guild.id in ctx.bot.anno_guilds
        
#Managing the DB config
class Matchmaking_Config():
    def __init__(self, bot):
        self.bot = bot

    
    async def load(self, data : str, guild_id : int):
        result = await self.bot.pool.fetch('''SELECT * FROM matchmaking_config WHERE guild_id = $1''', guild_id)
        if len(result) != 0 and result[0]:
            return result[0].get(data)
    
    #This one is actually not used anywhere currently, but I thought I would include it for completeness's sake
    async def save(self, data : str, value : int, guild_id : int):
        await self.bot.pool.execute('''
        INSERT INTO matchmaking_config (guild_id, $1) VALUES ($2, $3)
        ON CONFLICT (guild_id) DO
        UPDATE SET $1 = $3''')


@dataclass
class Listing:
    '''
    Represents an instance of a multiplayer listing in the database
    '''

    id:str
    ubiname:str
    host_id:int
    gamemode:str
    playercount:str
    DLC:str
    mods:str
    timezone:str
    additional_info:str
    timestamp:int
    guild_id:int

#Class for managing multiplayer Listing dataclasses in relation to the DB
class Listings():
    def __init__(self, bot):
        self.bot = bot

    
    async def retrieve(self, id):
        result = await self.bot.pool.fetch('''SELECT * FROM matchmaking_listings WHERE id = $1''', id)
        if len(result) != 0 and result[0]:
            listing = Listing(id=result[0].get('id'), ubiname=result[0].get('ubiname'), host_id=result[0].get('host_id'), 
            gamemode=result[0].get('gamemode'), playercount=result[0].get('playercount'), DLC=result[0].get('DLC'), mods=result[0].get('mods'), 
            timezone=result[0].get('timezone'), additional_info=result[0].get('additional_info'), timestamp=result[0].get('timestamp'), 
            guild_id=result[0].get('guild_id'))

            return listing
    
    async def retrieve_all(self):
        results = await self.bot.pool.fetch('''SELECT * FROM matchmaking_listings ORDER BY timestamp''')

        if len(results) != 0:
            listings = []
            for result in results:
                listing = Listing(id=result.get('id'), ubiname=result.get('ubiname'), host_id=result.get('host_id'), 
                gamemode=result.get('gamemode'), playercount=result.get('playercount'), DLC=result.get('DLC'), mods=result.get('mods'), 
                timezone=result.get('timezone'), additional_info=result.get('additional_info'), timestamp=result.get('timestamp'), 
                guild_id=result.get('guild_id'))
                
                listings.append(listing)
            return listings
    
    async def create(self, listing):
        await self.bot.pool.execute('''
        INSERT INTO matchmaking_listings (id, ubiname, host_id, gamemode, playercount, DLC, mods, timezone, additional_info, timestamp, guild_id) 
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)''', 
        listing.id, listing.ubiname, listing.host_id, listing.gamemode, listing.playercount, listing.DLC, listing.mods, listing.timezone, 
        listing.additional_info, listing.timestamp, listing.guild_id)
    
    async def delete(self, id):
        await self.bot.pool.execute('''
        DELETE FROM matchmaking_listings WHERE id = $1
        ''', id)




class Matchmaking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Matchmaking_Config(bot)
        self.listings = Listings(bot)
        self._ = self.bot.get_localization('matchmaking', self.bot.lang)
        
        self.delExpiredListings.start() # pylint: disable=<no-member>
    
    def cog_unload(self):
        self.delExpiredListings.cancel() # pylint: disable=<no-member>
    

    #Command to initalize matchmaking.
    #The TL;DR version of this command is the following: It DMs the user, asks them some questions,
    #evaluates the answers based on some criteria, then use those answers to construct a formatted
    #multiplayer listing, which will then in turn go into a preconfigured channel. It will also ping a
    #designated role if set. Can be limited as to which channels it can be run from via the COMMANDSCHANNEL setting.
    @commands.command(help="Start setting up a new multiplayer listing.", description="Start matchmaking! After command execution, you will receive a direct message to help you set up a multiplayer listing! Takes no arguments.", aliases=['multiplayer', 'init', 'match','multi','mp'], usage=f"matchmaking")
    @commands.guild_only()
    @commands.check(is_setup) #If not set up properly, it will not initialize
    @commands.check(is_anno_guild)
    @commands.max_concurrency(1, per=commands.BucketType.user,wait=False)
    @commands.cooldown(1, 72000, type=commands.BucketType.member)
    async def matchmaking(self, ctx):
        cmdchannel = await self.config.load('init_channel_id', ctx.guild.id)
        #Performs check if the command is executed in the right channel, if this is None, this feature is disabled.
        if cmdchannel:
            if cmdchannel != ctx.channel.id :
                logging.info(f"User {ctx.author} tried to initialize matchmaking in disabled channel.")
                ctx.command.reset_cooldown(ctx)
                return
        mpsessiondata = []
        mpEmbedColor = 0xd76b00
        #This should be a list of all the names of the functions below
        #Note: The questions will be asked in this order specified here, change it here to change the order. confirmlisting must be last.
        #Scroll to the bottom of the command scope to see how & where this is used.
        qtypes = ["UbiName", "GameMode", "PlayerCount", "DLC", "Mods", "TimeZone", "Additional", "ConfirmListing"]
        #Messaging the channel to provide feedback
        #It sends these seperately to ideally grab the user's attention, but can be merged.
        embed=discord.Embed(title=self._("**Starting matchmaking...**"), description=self._("Started matchmaking for **{name}#{discrim}**. Please check your DMs!").format(name=ctx.author.name, discrim=ctx.author.discriminator), color=mpEmbedColor)
        embed.set_footer(text=self._("If you didn't receive a DM, make sure you have direct messages enabled from server members."))
        await ctx.channel.send(embed=embed)
        embed=discord.Embed(title=self._("**Hello!**"), description=self._("I will help you set up a new multiplayer listing!  Follow the steps below! \n__Note:__ You can edit your submission at the end in case you made any errors!"), color=mpEmbedColor)
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
                embed=discord.Embed(title=self._("Ubisoft Connect username"), description=self._("Please type in your Ubisoft Connect username!"), color=mpEmbedColor)
                embed.set_footer(text="Note: Maximum length is 32 characters")
                msg = await ctx.author.send(embed=embed)
                def usernamecheck(payload):
                    return payload.author == ctx.author and payload.guild is None
                try:
                    payload = await self.bot.wait_for('message', timeout=300.0, check=usernamecheck)
                    #32char username limit
                    if len(payload.content) > 32 :
                        await msg.delete()
                        embed=discord.Embed(title=self.bot.warnDataTitle, description=self._("Username too long. Maximum 32 characters"), color=self.bot.warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                    else :
                        await modifymatchmaking(qType, payload.content, isModifying)
                        embed=discord.Embed(title="✅ " + self._("Username set."), description=self._("Your Ubisoft Connect username is: **{name}**").format(name=payload.content), color=mpEmbedColor)
                        await ctx.author.send(embed=embed)
                        return 0

                except:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1

            elif qType == "GameMode" :
                embed=discord.Embed(title=self._("Choose your preferred style of play!"), description="⚔️ - PvP (Player versus Player) \n🛡️ - PvE (Players versus Environment)\n⛏️ - Co-Op (Cooperative)", color=mpEmbedColor)
                embed.set_footer(text=self._("React below with your choice!"))
                msg = await ctx.author.send(embed=embed)
                #Add two reactions to this message
                gamemode_emoji = ["⚔️", "🛡️", "⛏️"]
                gamemodes = ["PvP", "PvE", "Co-Op"]
                for emoji in gamemode_emoji:
                    await msg.add_reaction(emoji) 

                #We check if the message ID is the same, so this is not a different message.
                #We also check if the user who reacted was the user who sent the command.
                def gamemodecheck(payload):
                    return payload.message_id == msg.id and payload.user_id == ctx.author.id
                try:
                    payload = await self.bot.wait_for('raw_reaction_add', timeout=300.0, check=gamemodecheck)
                    #Check reaction emoji
                    i = 0
                    gamemode = "Default"
                    while i != len(gamemodes):
                        if str(payload.emoji) not in gamemode_emoji :
                            await msg.delete()
                            embed = discord.Embed(title=self.bot.warnEmojiTitle, description=self.bot.warnEmojiDesc, color=self.bot.warnColor)
                            await ctx.author.send(embed=embed)
                            return -2
                        elif str(payload.emoji) == gamemode_emoji[i]:
                            gamemode = gamemodes[i]
                            await msg.delete()
                            break
                        i += 1

                    #Save it to list
                    await modifymatchmaking(qType, gamemode, isModifying)
                    
                    embed=discord.Embed(title="✅ " + self._("Gamemode set."), description=self._("Your gamemode is set to:  **{gamemode}**.").format(gamemode=gamemode), color=mpEmbedColor)
                    await ctx.author.send(embed=embed)
                    return 0
                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1

            elif qType == "PlayerCount" :
                embed=discord.Embed(title=self._("How many players you want to play with?"), description="2️⃣ - 2 \n 3️⃣ - 3 \n 4️⃣ - 4 \n ♾️ -" + self._("5 or more"), color=mpEmbedColor)
                embed.set_footer(text=self._("This should be the minimum amount of players you are willing to play with!"))
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
                    playernum = "Default"
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
                    embed=discord.Embed(title="✅ " + self._("Number of players set."), description=self._("Number of players: **{playernum}**").format(playernum=playernum), color=mpEmbedColor)
                    await ctx.author.send(embed=embed)
                    return 0
                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1
            elif qType == "DLC" :
                embed=discord.Embed(title=self._("Now react with the symbol of **all** the DLCs you want to use! Click the green checkmark ({checkmark}) once done!").format(checkmark= "✅"), description=self._(" {DLC0} - The Anarchist \n {DLC1} - Sunken Treasures \n {DLC2} - Botanica \n {DLC3} - The Passage \n {DLC4} - Seat of Power \n {DLC5} - Bright Harvest \n {DLC6} - Land of Lions \n {DLC7} - Docklands \n {DLC8} - Tourist Season").format(DLC0="🔥", DLC1="🤿", DLC2="🌹", DLC3="❄️", DLC4="🏛️", DLC5="🚜", DLC6="🦁", DLC7="⚓", DLC8="🏖️"), color=mpEmbedColor)
                embed.set_footer(text=self._("Note: If you do not own any DLC, just simply press {check} to continue.").format(check="✅"))
                msg = await ctx.author.send(embed=embed)
                #Add to the list of DLC here. Note: the emojies & DLC must be in the same order, & a green tick must be at the end of emojies. 
                DLCemojies = ["🔥", "🤿", "🌹", "❄️", "🏛️", "🚜", "🦁", "⚓", "🏖️", "✅"]
                allDLCs = [self._("The Anarchist"), self._("Sunken Treasures"), self._("Botanica"), self._("The Passage"), self._("Seat of Power"), self._("Bright Harvest"), self._("Land of Lions"), self._("Docklands"), self._("Tourist Season") ]
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
                    embed=discord.Embed(title="✅ " + self._("DLC set."), description=self._("Your DLC for this match: {DLC}").format(DLC=DLC), color=mpEmbedColor)
                    await ctx.author.send(embed=embed)
                    return 0

                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1

            elif qType == "Mods" :
                #Add msg
                embed=discord.Embed(title=self._("Are you going to use mods in this match?"), description=self._("React below with your response!"), color=mpEmbedColor)
                embed.set_footer(text=self._("Note: Mods are not officially supported. All participants must share the same mods to play together. Please share the mods you want to use at the end of the form."))
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
                    embed=discord.Embed(title="✅ " +  self._("Mods set."), description=self._("Modded: **{is_modded}**").format(is_modded=modded), color=mpEmbedColor)
                    await ctx.author.send(embed=embed)
                    return 0

                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1
            
            elif qType == "TimeZone" :
                embed=discord.Embed(title=self._("Specify your timezone as an UTC offset!"), description=self._("For example: If your timezone is UTC+1, **type in 1!**"), color=mpEmbedColor)
                embed.set_footer(text=self._("If you are unsure what timezone you are in, you can check here: https://www.timeanddate.com/time/map"))
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
                            embed=discord.Embed(title="⚠️ " + self._("Invalid timezone!"), description=self._("Please enter a valid timezone."), color=self.bot.warnColor)
                            await ctx.author.send(embed=embed)
                            return -2
                        #If it is smaller than 0, we will make it UTC-
                        elif int(payload.content) < 0 :
                            timezone = int(payload.content)
                            await modifymatchmaking(qType, f"UTC{timezone}", isModifying)
                            await msg.delete()
                            embed=discord.Embed(title="✅ " + self._("Timezone set."), description=self._("Your timezone: UTC{timezone}").format(timezone=timezone), color=mpEmbedColor)
                            await ctx.author.send(embed=embed)
                            return 0
                        #Otherwise UTC+
                        else :
                            timezone = int(payload.content)
                            await modifymatchmaking(qType, f"UTC+{timezone}", isModifying)
                            await msg.delete()
                            embed=discord.Embed(title="✅ " + self._("Timezone set."), description=self._("Your timezone: UTC+{timezone}").format(timezone=timezone), color=mpEmbedColor)
                            await ctx.author.send(embed=embed)
                            return 0
                    except ValueError:
                        await msg.delete()
                        embed=discord.Embed(title="⚠️ " + self._("Invalid timezone!"), description=self._("Please enter a valid timezone."), color=self.bot.warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                except asyncio.TimeoutError:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1

            elif qType == "Additional" :
                embed=discord.Embed(title=self._("If you want to add additional notes to your listing, type it in now!"), description=self._("Examples of what to include (not mandatory): When you want to start, Duration of a match, Mods (if any)"), color=mpEmbedColor)
                embed.set_footer(text=self._("Type in 'skip' to skip this step! Max length: 256 characters"))
                msg = await ctx.author.send(embed=embed)
                def additionalinfocheck(payload):
                    return payload.author == ctx.author and payload.guild is None
                try:
                    payload = await self.bot.wait_for('message', timeout=300.0, check=additionalinfocheck)
                    if len(payload.content) > 256 :
                        await msg.delete()
                        embed = discord.Embed(title=self.bot.warnDataTitle, description=self._("Additional info exceeded character limit! Maximum length: 256 characters"), color=self.bot.warnColor)
                        await ctx.author.send(embed=embed)
                        return -2
                    else :
                        if payload.content.lower() == "skip" :
                            await modifymatchmaking(qType, "-", isModifying)
                            await msg.delete()
                            embed=discord.Embed(title="✅ " + self._("Additional info skipped."), description=self._("You skipped this step."), color=mpEmbedColor)
                            await ctx.author.send(embed=embed)
                            return 0
                        else :
                            await modifymatchmaking(qType, payload.content, isModifying)
                            await msg.delete()
                            embed=discord.Embed(title="✅ " + self._("Additional info set."), description=self._("You typed: ```{content}```").format(content=payload.content), color=mpEmbedColor)
                            await ctx.author.send(embed=embed)
                            return 0
                except:
                    embed = discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    return -1
            
            elif qType == "ConfirmListing" :
                #Send listing preview
                embed=discord.Embed(title=self._("**__Looking for Players: Anno 1800__**"), description=self._("**Ubisoft Connect Username: ** {name} \n **Gamemode: ** {gamemode} \n **Players: ** {playercount} \n **DLC: ** {DLC} \n **Mods:** {mods} \n **Timezone:** {timezone} \n **Additional info:** {additional_info} \n \n Contact {author} in DMs if you are interested, or subscribe by reacting with {arrow}! This will notify the host when {subcap} players have subscribed! (including the host)").format(name=mpsessiondata[0], gamemode=mpsessiondata[1], playercount=mpsessiondata[2], DLC=mpsessiondata[3], mods=mpsessiondata[4], timezone=mpsessiondata[5], additional_info=mpsessiondata[6], author=ctx.author.mention, arrow="⏫", subcap=mpsessiondata[2]), color=mpEmbedColor)
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/310078048525615106/830900971680038962/union_crop.jpg")
                embed.set_footer(text=self._("Note: This listing is valid for 7 days, after that, no more subscriptions can be submitted."))
                await ctx.author.send(embed=embed)
                embed=discord.Embed(title=self._("Please review your listing!"), description=self._("If everything looks good, hit {check} to submit! If you want to edit any information, hit {pen}. If you want to cancel your submission, hit {cross}.").format(check="✅", pen="🖊️", cross="❌"), color=mpEmbedColor)
                msg = await ctx.author.send(embed=embed)
                await msg.add_reaction("✅")
                await msg.add_reaction("🖊️")
                await msg.add_reaction("❌")
                #Called to create a new multiplayer posting
                async def createposting(mpsessiondata):
                    try:
                        channel = self.bot.get_channel(await self.config.load('announce_channel_id', ctx.guild.id))
                        lfgrole_id = await self.config.load('lfg_role_id', ctx.guild.id)
                        listingID = uuid.uuid4()
                        listing_timestamp = int(round(time.time()))
                        #If LFG role is not set up, we will not include a mention to it at the end.
                        if lfgrole_id == None:
                            #yeah this is long lol
                            embed=discord.Embed(title=self._("**__Looking for Players: Anno 1800__**"), description=self._("**Ubisoft Connect Username: ** {name} \n **Gamemode: ** {gamemode} \n **Players: ** {playercount} \n **DLC: ** {DLC} \n **Mods:** {mods} \n **Timezone:** {timezone} \n **Additional info:** {additional_info} \n \n Contact {author} in DMs if you are interested, or subscribe by reacting with {arrow}! This will notify the host when {subcap} players have subscribed! (including the host)").format(name=mpsessiondata[0], gamemode=mpsessiondata[1], playercount=mpsessiondata[2], DLC=mpsessiondata[3], mods=mpsessiondata[4], timezone=mpsessiondata[5], additional_info=mpsessiondata[6], author=ctx.author.mention, arrow="⏫", subcap=mpsessiondata[2]), color=mpEmbedColor)
                            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/310078048525615106/830900971680038962/union_crop.jpg")
                            embed.set_footer(text="Note: This listing is valid for 7 days, after that, no more subscriptions can be submitted.\nID: {listing_id}".format(listing_id=listingID))
                            posting = await channel.send(embed=embed)
                            await posting.add_reaction("⏫")
                            logging.info(f"{ctx.author} User created new multiplayer listing with ID {listingID}. Session data dump: {mpsessiondata}")
                        else :
                            lfgrole = ctx.guild.get_role(lfgrole_id)
                            embed=discord.Embed(title=self._("**__Looking for Players: Anno 1800__**"), description=self._("**Ubisoft Connect Username: ** {name} \n **Gamemode: ** {gamemode} \n **Players: ** {playercount} \n **DLC: ** {DLC} \n **Mods:** {mods} \n **Timezone:** {timezone} \n **Additional info:** {additional_info} \n \n Contact {author} in DMs if you are interested, or subscribe by reacting with {arrow}! This will notify the host when {subcap} players have subscribed! (including the host)").format(name=mpsessiondata[0], gamemode=mpsessiondata[1], playercount=mpsessiondata[2], DLC=mpsessiondata[3], mods=mpsessiondata[4], timezone=mpsessiondata[5], additional_info=mpsessiondata[6], author=ctx.author.mention, arrow="⏫", subcap=mpsessiondata[2]), color=mpEmbedColor)
                            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/310078048525615106/830900971680038962/union_crop.jpg")
                            embed.set_footer(text="Note: This listing is valid for 7 days, after that, no more subscriptions can be submitted.\nID: {listing_id}".format(listing_id=listingID))
                            posting = await channel.send(embed=embed,content=lfgrole.mention)
                            await posting.add_reaction("⏫")
                            logging.info(f"{ctx.author} User created new multiplayer listing with ID {listingID}. Session data dump: {mpsessiondata}")
                        listing = Listing(str(listingID), mpsessiondata[0], ctx.author.id, mpsessiondata[1], mpsessiondata[2], mpsessiondata[3], mpsessiondata[4], mpsessiondata[5], mpsessiondata[6], listing_timestamp, ctx.guild.id)
                        await self.listings.create(listing)
                    except Exception as error:
                            #If for whatever reason the message cannot be made, we message the user about it.
                            logging.error(f"Could not create listing for {ctx.author} due to unhandled exception. Did you set up matchmaking?")
                            embed=discord.Embed(title="❌ " + self._("Error: Exception encountered."), description=self._("Failed to generated listing. Contact an administrator! Operation cancelled.\n**Exception:** ```{exception}```").format(exception=error), color=self.bot.errorColor)
                            await ctx.author.send(embed=embed)
                            return -1

                #Returns -1 for fail, 0 for successful modification
                async def modifylisting():
                    embed=discord.Embed(title=self._("What do you want to change in your listing?"), description=self._("{em} - Ubisoft Username \n{em0} - Gamemode \n{em1} - Player count \n{em2} - DLC \n{em3} - Mods\n{em4} - Timezone \n{em5} - Additional details").format(em="👤",em0="🕹️", em1="🧮",em2="💿",em3="🏗️", em4="🕘",em5="✉️"), color=mpEmbedColor)
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
                                        embed=discord.Embed(title="❌ " + self._("Exceeded error limit."), description=self._("You have made too many errors. Please retry your submission."), color=self.bot.errorColor)
                                        await ctx.author.send(embed=embed)
                                        return -1
                                    else:
                                        warns += 1
                            return 0
                            
                        else :
                            #We have to cancel the entire command here, as it would be way too difficult to implement looping here as well
                            embed = discord.Embed(title=self.bot.errorEmojiTitle, description=self._("Cancelled matchmaking."), color=self.bot.errorColor)
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
                            embed=discord.Embed(title="✅ " + self._("Listing submitted!"), description=self._("Thanks for using the service! If you have found a bug or want to give feedback, please contact `Hyper#0001`!"), color=self.bot.embedGreen)
                            await ctx.author.send(embed=embed)
                            return 1
                    elif str(payload.emoji) == "🖊️":
                        if await modifylisting() == 0 :
                            #If modification is successful, repeat this step (confirmcheck)
                            return -3
                        else :
                            embed=discord.Embed(title="❌ " + self._("Modification failed."), description=self._("If you have found a bug or want to give feedback, please contact `Hyper#0001`!"), color=self.bot.errorColor)
                            await ctx.author.send(embed=embed)
                            logging.info(f"{ctx.author} User failed modification.")
                            return -1


                    elif str(payload.emoji) == "❌":
                        embed=discord.Embed(title="❌ " + self._("Submission cancelled."), description=self._("If you have found a bug or want to give feedback, please contact `Hyper#0001`!"), color=self.bot.errorColor)
                        await ctx.author.send(embed=embed)
                        logging.info(f"{ctx.author} User cancelled matchmaking.")
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
        
        '''
        Call all the functions defined earlier
        Return codes:
         1 = finished
         0 = success, continue
         -1 = Fatal error, cancel command
         -2 = Invalid value, repeat question
         -3 = Repeat question, no error, only triggered when editing
          
        
        This means that we keep looping until our error code is -2 or -3, stop loop when it is 0
        And return the whole command if it is -1
        '''
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
                ctx.command.reset_cooldown(ctx)
                return
            #If it succeeds, we move to the next question
            elif errcode == 0:
                question += 1
            #If editing, we will add one to the edits variable.
            elif errcode == -3:
                if edits == 6:
                    embed=discord.Embed(title="❌ " + self._("Exceeded edit limit."), description=self._("You cannot make more edits to your submission. Please try executing the command again."),color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    logging.info(f"{ctx.author} exceeded listing edit limit in matchmaking.")
                    ctx.command.reset_cooldown(ctx)
                    return
                else :
                    edits += 1
            #If it is an invalid value, add a warn
            elif errcode == -2 :
                if warns == 4:
                    embed=discord.Embed(title="❌ " + self._("Exceeded error limit."), description=self._("You have made too many errors. Please retry your submission."), color=self.bot.errorColor)
                    await ctx.author.send(embed=embed)
                    logging.info(f"{ctx.author} exceeded listing error limit in matchmaking.")
                    ctx.command.reset_cooldown(ctx)
                    return
                else:
                    warns += 1
        logging.info(f"Matchmaking command executed successfully. Generated listing for {ctx.author}!")


    @matchmaking.error
    async def matchmaking_error(self, ctx, error):
        #Due to it's performance requirements and complexity, this command is limited to 1 per user
        if isinstance(error, commands.MaxConcurrencyReached):
            embed = discord.Embed(title=self.bot.errorMaxConcurrencyReachedTitle, description=self._("You already have a matchmaking request in progress."), color=self.bot.errorColor)
            embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar.url)
            await ctx.channel.send(embed=embed)

    
    #Remove listings older than a week from the database
    @tasks.loop(seconds=3600.0)
    async def delExpiredListings(self):
        await self.bot.wait_until_ready()
        listings = await self.listings.retrieve_all()
        if listings and len(listings) !=0:
            for listing in listings:
                if (int(round(time.time())) - listing.timestamp) > 604800:
                    await self.listings.delete(listing.id)
                    logging.info("Deleted listing {ID} from database.".format(ID=listing.id))


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        '''
        This is where listing subscriptions are handled via reactions
        '''
        #Check if we are in a guild so we dont bombard the database with Null errors.
        if payload.guild_id != None and payload.guild_id in self.bot.anno_guilds: 
            if await self.config.load('announce_channel_id', payload.guild_id) == payload.channel_id:
                guild = self.bot.get_guild(payload.guild_id)
                #I put a fair number of logging in here to track abuse of this feature
                if str(payload.emoji) == "⏫" and payload.user_id != self.bot.user.id:
                    #The listing message
                    listing = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
                    #The person who reacted
                    member = guild.get_member(payload.user_id)  
                    #Get context for this message
                    ctx = await self.bot.get_context(listing)
                    #Get the content, then lines seperated into a list of the listing
                    listingContent = listing.embeds
                    listingFooter = listingContent[0].footer
                    listingID = listingFooter.text.split("ID: ")[1]
                    db_listing = await self.listings.retrieve(listingID)
                    #Detect missing data
                    if db_listing == None :
                        logging.info(f"{member} tried to subscribe to an expired listing.")
                        return
                    #The second line contains information about playercount
                    playerCount = db_listing.playercount
                    #We get the host from the DB
                    host = ctx.guild.get_member(db_listing.host_id)
                    #We get a list of users who reacted to this
                    interestedPlayers = await listing.reactions[0].users().flatten()
                    #Remove bot accounts from this list, and join them together in a new str.
                    for player in interestedPlayers :
                        if player.bot == True or player.id == host.id :
                            interestedPlayers.remove(player)
                    interestedMentions = ", ".join([member.mention for member in interestedPlayers])
                    #Convert the playercount to int, subtract 1 as to not count the host itself
                    try :
                        playerCount = int(playerCount)-1
                    except ValueError :
                        playerCount = 4
                    #Sending confirmation to user who signed up
                    if member.id != host.id :
                        embed=discord.Embed(title="📝 " + self._("You have subscribed to {hostname}'s game!").format(hostname=host.name), description=self._("They will receive a notification when their desired playercap has been reached."), color=self.bot.embedGreen)
                        await member.send(embed=embed)
                        logging.info(f"{member.name}#{member.discriminator} expressed interest to join {host.name}#{host.discriminator}'s game.")
                    else :
                        logging.info(f"{host.name} tried to subscribe to their own listing.")
                        return #Return so that the host can't ping themselves lol
                    #If we have reached the desired playercount, we will message to the host. This message will get every time a new player reacts.
                    if len(interestedPlayers) >= playerCount :
                        embed=discord.Embed(title="📝 " + self._("Your listing reached your set playercap!"), description=self._("Hello! Just letting you know that your multiplayer listing on **{guild_name}** has reached {player_count} or more interested players.\nPlayers who want to play with you in this match: {interested_mentions}").format(guild_name=guild.name, player_count=playerCount, interested_mentions=interestedMentions), color=self.bot.embedGreen)
                        embed.set_footer(text=self._("If you believe that this feature was abused, contact a moderator immediately!"))
                        await host.send(embed=embed, content=f"Players that want to play with you: {interestedMentions}")
                        #Add a little emoji as feedback that the listing has reached max subscriber cap
                        if "🎉" not in str(listing.reactions):
                            await listing.add_reaction("🎉")
                        logging.info(f"{host.name}#{host.discriminator}'s listing reached cap. Host notified.")
                    return



    #Same thing but in reverse
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id != None and payload.guild_id in self.bot.anno_guilds:
            if await self.config.load('announce_channel_id', payload.guild_id) == payload.channel_id:
                guild = self.bot.get_guild(payload.guild_id)
                #I put a fair number of logging in here to track abuse of this feature
                if str(payload.emoji) == "⏫" and payload.user_id != self.bot.user.id:
                    #The person who reacted
                    member = guild.get_member(payload.user_id)
                    #Listing
                    listing = await guild.get_channel(payload.channel_id).fetch_message(payload.message_id)
                    #Context
                    ctx = await self.bot.get_context(listing)
                    #More listing
                    listingContent = listing.embeds
                    listingFooter = listingContent[0].footer
                    listingID = listingFooter.text.split("ID: ")[1]
                    db_listing = await self.listings.retrieve(listingID)
                    if listing == None :
                        logging.info(f"{member} tried to unsubscribe from an expired listing.")
                        return
                    host = ctx.guild.get_member(db_listing.host_id)
                    if member.id != host.id :
                        logging.info(f"{member.name}#{member.discriminator} removed themselves from a listing.")
                        embed=discord.Embed(title=f"📝 " + self._("You have unsubscribed from {hostname}'s listing.").format(hostname=host.name), description=self._("The host will no longer see you signed up to this listing."), color=self.bot.errorColor)
                        await member.send(embed=embed)
                        return
                    else :
                        logging.info(f"{host.name} tried to unsubscribe from their own listing.")

def setup(bot):
    logging.info("Adding cog: Matchmaking...")
    bot.add_cog(Matchmaking(bot))
