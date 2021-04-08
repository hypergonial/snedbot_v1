import asyncio
import logging

import discord
from discord.ext import commands


async def hasOwner(ctx):
    return ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id

#Check performed to see if the user has priviliged access.
async def hasPriviliged(ctx):
    #Gets a list of all the roles the user has, then gets the ID from that.
    userRoles = [x.id for x in ctx.author.roles]
    #Also get privliged roles, then compare
    privroles = await ctx.bot.DBHandler.checkprivs(ctx.guild.id)
    #Check if any of the roles in user's roles are contained in the priviliged roles.
    return any(role in userRoles for role in privroles) or (ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id)

#This is an entirely optional extension, but you are masochistic if you are not using it :D

class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Ahh yes, the setup command... *instant PTSD*
    #It basically just collects a bunch of values from the user, in this case an admin, and then changes the settings
    #based on that, instead of the admin having to use !modify for every single value
    #TL;DR: fancy setup thing
    @commands.group(help="Starts bot configuration setups.", description = "Used to set up and configure different parts of the bot. \nValid setup-types: `matchmaking, LFG, keepontop, logging`", usage="setup <setuptype>", invoke_without_command=True)
    @commands.check(hasPriviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def setup (self, ctx):
        #This is the LFG setup variant, it will set up role reactions on either an existing message or a new one.
        #More setup variants may be added in the future
        embed = discord.Embed(title="🛠️ Setup", description=f"This is the setup command, you can configure different parts of the bot here!\n Valid setup types: `matchmaking, LFG, keepontop, logging`", color=self.bot.embedBlue)
        await ctx.send(embed=embed)

    @setup.command(help="Sets up the LFG role.")
    async def lfg(self, ctx):
        extensions = self.bot.checkExtensions
        if "Matchmaking" not in extensions :
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This setup requires the extension `matchmaking` to be active.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        embed = discord.Embed(title="🛠️ LFG role setup", description="Do you already have an existing message for rolereact?", color=self.bot.embedBlue)
        msg = await ctx.channel.send(embed=embed)
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
            await self.bot.DBHandler.modifysettings("LFGREACTIONEMOJI", reactemoji.id, ctx.guild.id)
            await self.bot.DBHandler.modifysettings("LFGROLE", role.id, ctx.guild.id)
            await self.bot.DBHandler.modifysettings("ROLEREACTMSG", msg.id, ctx.guild.id)
            embed=discord.Embed(title="🛠️ LFG role setup", description="✅ Setup completed. Role reactions set up!", color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)
            logging.info(f"Setup for LFG concluded successfully on guild {ctx.guild.id}.")

        #The common part of the LFG setup
        async def continueprocess(reactchannel, msgcontent, reactmsg, createmsg):
            try:
                def confirmemoji(payload):
                    return payload.message_id == msg.id and payload.user_id == ctx.author.id
                #Get emoji
                embed=discord.Embed(title="🛠️ LFG role setup", description="React **to this message** with the emoji you want to use!\nNote: Use a __custom__ emoji from __this server__, I have no way of accessing emojies outside this server!", color=self.bot.embedBlue)
                msg = await ctx.channel.send(embed=embed)
                payload = await self.bot.wait_for('raw_reaction_add', timeout=60.0,check=confirmemoji)
                reactemoji = payload.emoji
                embed=discord.Embed(title="🛠️ LFG role setup", description=f"Emoji to be used will be {reactemoji}", color=self.bot.embedBlue)
                msg = await ctx.channel.send(embed=embed)
                #Get the name of the role, then pass it on
                embed=discord.Embed(title="🛠️ LFG role setup", description="Name the role that will be handed out!", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
                payload = await self.bot.wait_for('message', timeout=60.0, check=idcheck)
                rolename = payload.content
                embed=discord.Embed(title="🛠️ LFG role setup", description=f"Role set to **{rolename}**", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
                #Pass all values to configurator
                await configurevalues(createmsg, reactmsg, msgcontent, reactchannel, reactemoji, rolename)
            except asyncio.TimeoutError:
                embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return
        try:
            payload = await self.bot.wait_for('raw_reaction_add', timeout=60.0, check=confirmcheck)
            if str(payload.emoji) == ("✅") :

                try:
                    #Defining these to be None, because they need to be passed to continueprocess
                    reactchannel = None
                    msgcontent = None
                    embed=discord.Embed(title="🛠️ LFG role setup", description="Send a channel mention of the channel where the message is located!", color=self.bot.embedBlue)
                    await ctx.channel.send(embed=embed)
                    payload = await self.bot.wait_for('message', timeout =60.0, check=idcheck)
                    #We will attempt to convert this from a channel mention
                    reactchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                    createmsg = True
                    embed=discord.Embed(title="🛠️ LFG role setup", description=f"Channel set to **{reactchannel.mention}**", color=self.bot.embedBlue)
                    await ctx.channel.send(embed=embed)
                    #Since the message already exists, we will try to get it's ID from the user
                    embed=discord.Embed(title="🛠️ LFG role setup", description="Please specify the ID of the message.", color=self.bot.embedBlue)
                    await ctx.channel.send(embed=embed)
                    payload = await self.bot.wait_for('message', timeout=60.0, check=idcheck)
                    #We will attempt to convert this to an int to check if it is one
                    int(payload.content)
                    reactmsg = await reactchannel.fetch_message(int(payload.content))
                    createmsg = False
                    embed=discord.Embed(title="🛠️ LFG role setup", description=f"Reaction message set to the following: \n*{reactmsg.content}* **in** {reactchannel.mention}", color=self.bot.embedBlue)
                    await ctx.channel.send(embed=embed)
                    #Pass all collected values to continue
                    await continueprocess(reactchannel, msgcontent, reactmsg, createmsg)
                    return
                except asyncio.TimeoutError:
                    embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)
                    return
                except ValueError:
                    embed=discord.Embed(title=self.bot.errorDataTitle, description=self.bot.errorDataDesc, color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)
                    return
                except commands.ChannelNotFound:
                    embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)
                    return

            elif str(payload.emoji) == ("❌"):
                embed=discord.Embed(title="🛠️ LFG role setup", description="Please specify the channel where you want the message to be sent via mentioning the channel.", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
                try:
                    reactmsg = None
                    payload = await self.bot.wait_for('message', timeout =60.0, check=idcheck)
                    #We will attempt to convert this from a channel mention
                    reactchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                    createmsg = True
                    embed=discord.Embed(title="🛠️ LFG role setup", description=f"Channel set to **{reactchannel.mention}**", color=self.bot.embedBlue)
                    await ctx.channel.send(embed=embed)
                    embed=discord.Embed(title="🛠️ LFG role setup", description="What should the content of the message be?", color=self.bot.embedBlue)
                    await ctx.channel.send(embed=embed)
                    payload = await self.bot.wait_for('message', timeout = 60.0, check=idcheck)
                    msgcontent = payload.content
                    embed=discord.Embed(title="🛠️ LFG role setup", description=f"Message content will be set to the following: \n*{msgcontent}*", color=self.bot.embedBlue)
                    await ctx.channel.send(embed=embed)

                    #Pass all collected values to continue
                    await continueprocess(reactchannel, msgcontent, reactmsg, createmsg)
                    return
                except asyncio.TimeoutError:
                    await ctx.channel.send("**Error: **Timed out. Setup process cancelled.")
                    return
                except commands.ChannelNotFound:
                    embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)
                    return
            else :
                embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return
        except asyncio.TimeoutError:
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
    @setup.command(help="Helps set up matchmaking")
    async def matchmaking(self, ctx):
    #This setup will set up the !matchmaking command to work properly.
        extensions = self.bot.checkExtensions
        if "Matchmaking" not in extensions :
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This setup requires the extension `matchmaking` to be active.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        embed=discord.Embed(title="🛠️ Matchmaking setup", description="Please mention a channel where users should send the command to start matchmaking! Type `disable` to disable this feature.", color=self.bot.embedBlue)
        await ctx.channel.send(embed=embed)
        try:
            #Gathering info
            def check(payload):
                return payload.author == ctx.author and payload.channel.id == ctx.channel.id
            payload = await self.bot.wait_for('message', timeout =60.0, check=check)
            if payload.content == "disable":
                cmdchannel = 0
                embed=discord.Embed(title="🛠️ Matchmaking setup", description="Commands channel **disabled.**", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
            else :
                cmdchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                embed=discord.Embed(title="🛠️ Matchmaking setup", description=f"Commands channel set to {cmdchannel.mention}", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)

            embed=discord.Embed(title="🛠️ Matchmaking setup", description="Now please mention the channel where the multiplayer listings should go. If you already have LFG reaction roles set up, they will also be pinged once a listing goes live.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            payload = await self.bot.wait_for('message', timeout=60.0, check=check)
            announcechannel = await commands.TextChannelConverter().convert(ctx, payload.content)
            embed=discord.Embed(title="🛠️ Matchmaking setup", description=f"Multiplayer listings channel set to {announcechannel.mention}", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)

            #Executing based on info

            if cmdchannel == 0 :
                await self.bot.DBHandler.modifysettings("COMMANDSCHANNEL", 0, ctx.guild.id)
            else :
                await self.bot.DBHandler.modifysettings("COMMANDSCHANNEL", cmdchannel.id, ctx.guild.id)
            await self.bot.DBHandler.modifysettings("ANNOUNCECHANNEL", announcechannel.id, ctx.guild.id)
            embed=discord.Embed(title="🛠️ Matchmaking setup", description="✅ Setup completed. Matchmaking set up!", color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)
            logging.info(f"Setup for matchmaking concluded successfully on guild {ctx.guild.id}.")
            return

        except commands.ChannelNotFound:
            embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        except asyncio.TimeoutError:
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return

    @setup.command(help="Helps set up a keep-on-top message, that will sticky a message on top of a channel at all times.", aliases=["keep-on-top"])
    async def keepontop(self, ctx):
        embed=discord.Embed(title="🛠️ Keep-On-Top Setup", description="Specify the channel where you want to keep a message on the top by mentioning it!", color=self.bot.embedBlue)
        await ctx.channel.send(embed=embed)
        try :
            def check(payload):
                return payload.author == ctx.author and payload.channel.id == ctx.channel.id
            payload = await self.bot.wait_for('message', timeout=60.0, check=check)
            keepOnTopChannel = await commands.TextChannelConverter().convert(ctx, payload.content)
            embed=discord.Embed(title="🛠️ Keep-On-Top Setup", description=f"Channel set to {keepOnTopChannel.mention}!", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            embed=discord.Embed(title="🛠️ Keep-On-Top Setup", description="Now type in the message you want to be kept on top!", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            payload = await self.bot.wait_for('message', timeout=300.0, check=check)
            keepOnTopMessage = payload.content
            await self.bot.DBHandler.modifysettings("KEEP_ON_TOP_CHANNEL", keepOnTopChannel.id, ctx.guild.id)
            await self.bot.DBHandler.storetext("KEEP_ON_TOP_CONTENT", keepOnTopMessage, ctx.guild.id)
            firstTop = await keepOnTopChannel.send(keepOnTopMessage)
            await self.bot.DBHandler.modifysettings("KEEP_ON_TOP_MSG", firstTop.id, firstTop.guild.id)
            embed=discord.Embed(title="🛠️ Keep-On-Top Setup", description=f"✅ Setup completed. This message will now be kept on top of {keepOnTopChannel.mention}!", color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)
            logging.info(f"Setup for keep-on-top concluded successfully on guild {ctx.guild.id}.")

        except commands.ChannelNotFound:
            embed=discord.Embed(title="❌ Error: Unable to locate channel.", description="The setup process has been cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        except asyncio.TimeoutError:
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        
    @setup.command(help="Helps you set up logging, and different logging levels.", aliases=["logs"])
    async def logging(self, ctx):
        extensions = self.bot.checkExtensions
        if "Logging" not in extensions:
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This setup requires the extension `userlog` to be active.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        embed=discord.Embed(title="🛠️ Logging Setup", description="Specify the channel where you want to send logs to by mentioning it!\n**Note:**This channel may contain sensitive information, do not let everyone access it!", color=self.bot.embedBlue)
        await ctx.channel.send(embed=embed)
        try :
            def check(payload):
                return payload.author == ctx.author and payload.channel.id == ctx.channel.id
            payload = await self.bot.wait_for('message', timeout=60.0, check=check)
            loggingChannel = await commands.TextChannelConverter().convert(ctx, payload.content)
            embed=discord.Embed(title="🛠️ Logging Setup", description=f"Logging channel set to {loggingChannel.mention}!", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            embed=discord.Embed(title="🛠️ Logging Setup", description=f"Now you can *optionally* specify an **elevated** logging channel, where more important entries, such as bans or server setting updates will be sent to. Type `skip` to skip this step.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            payload = await self.bot.wait_for('message', timeout=60.0, check=check)
            if payload.content != "skip":
                elevated_loggingChannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                elevated_loggingChannelID = elevated_loggingChannel.id
                embed=discord.Embed(title="🛠️ Logging Setup", description=f"Elevated logging channel set to {elevated_loggingChannel.mention}!", color=self.bot.embedBlue)
                await ctx.send(embed=embed)
            else:
                elevated_loggingChannelID = 0
                embed=discord.Embed(title="🛠️ Logging Setup", description=f"No elevated logging channel set.", color=self.bot.embedBlue)
                await ctx.send(embed=embed)
            await self.bot.DBHandler.modifysettings("LOGCHANNEL", loggingChannel.id, ctx.guild.id)
            await self.bot.DBHandler.modifysettings("ELEVATED_LOGCHANNEL", elevated_loggingChannelID, ctx.guild.id)
            embed=discord.Embed(title="🛠️ Logging Setup", description=f"✅ Setup completed. Logs will now be recorded!", color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)
            return
        except commands.ChannelNotFound:
            embed=discord.Embed(title="❌ Error: Unable to locate channel.", description="The setup process has been cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        except asyncio.TimeoutError:
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return

    @setup.error
    async def setup_error(self, ctx, error):
        if isinstance(error, commands.MaxConcurrencyReached):
            embed = discord.Embed(title="❌ Error: Max concurrency reached!", description="You already have a setup process running.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
        elif isinstance(error, commands.CommandNotFound):
            embed=discord.Embed(title="❌ Error: Unknown setup process", description="Unable to find requested setup process. Valid setups: `LFG, matchmaking, keepontop, logging`", color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return

def setup(bot):
    logging.info("Adding cog: Setup...")
    bot.add_cog(Setup(bot))
