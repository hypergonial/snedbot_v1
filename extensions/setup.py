import asyncio
import logging

import asyncpg
import discord
from discord.ext import commands


async def hasOwner(ctx):
    return await ctx.bot.CommandChecks.hasOwner(ctx)
async def hasPriviliged(ctx):
    return await ctx.bot.CommandChecks.hasPriviliged(ctx)

#This is an entirely optional extension, but you are masochistic if you are not using it :D

class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Ahh yes, the setup command... *instant PTSD*
    #It basically just collects a bunch of values from the user, in this case an admin, and then changes the settings
    #based on that, instead of the admin having to use !modify for every single value
    #TL;DR: fancy setup thing
    @commands.group(help="Starts bot configuration setups.", description = "Used to set up and configure different parts of the bot.", usage="setup <setuptype>", invoke_without_command=True, case_insensitive=True)
    @commands.check(hasPriviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def setup (self, ctx):
        #This is the LFG setup variant, it will set up role reactions on either an existing message or a new one.
        #More setup variants may be added in the future
        await ctx.send_help(ctx.command)

    @setup.command(help="Helps set up matchmaking")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
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
                cmdchannel_id = None
                embed=discord.Embed(title="🛠️ Matchmaking setup", description="Commands channel **disabled.**", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
            else :
                cmdchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                cmdchannel_id = cmdchannel.id
                embed=discord.Embed(title="🛠️ Matchmaking setup", description=f"Commands channel set to {cmdchannel.mention}", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)

            embed=discord.Embed(title="🛠️ Matchmaking setup", description="Now please mention the channel where the multiplayer listings should go. If you already have LFG reaction roles set up, they will also be pinged once a listing goes live.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            payload = await self.bot.wait_for('message', timeout=60.0, check=check)
            announcechannel = await commands.TextChannelConverter().convert(ctx, payload.content)
            embed=discord.Embed(title="🛠️ Matchmaking setup", description=f"Multiplayer listings channel set to {announcechannel.mention}", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)

            #Executing based on info

            async with self.bot.pool.acquire() as con:
                await con.execute('''
                INSERT INTO matchmaking_config (guild_id, init_channel_id, announce_channel_id) VALUES ($1, $2, $3)
                ON CONFLICT (guild_id) DO
                UPDATE SET init_channel_id = $2, announce_channel_id = $3''', ctx.guild.id, cmdchannel_id, announcechannel.id)

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
    @commands.check(hasPriviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def keepontop(self, ctx):
        try:
            await ctx.invoke(self.bot.get_command('keepontop add'))
        except AttributeError:
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This setup requires the extension `ktp` to be active.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        
    @setup.command(help="Helps you set up logging, and different logging levels.", aliases=["logs"])
    @commands.check(hasPriviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
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
                elevated_loggingChannelID = None
                embed=discord.Embed(title="🛠️ Logging Setup", description=f"No elevated logging channel set.", color=self.bot.embedBlue)
                await ctx.send(embed=embed)
            
            async with self.bot.pool.acquire() as con:
                await con.execute('''
            INSERT INTO log_config (guild_id, log_channel_id, elevated_log_channel_id) VALUES ($1, $2, $3)
            ON CONFLICT (guild_id) DO
            UPDATE SET log_channel_id  = $2, elevated_log_channel_id = $3''', ctx.guild.id, loggingChannel.id, elevated_loggingChannelID)

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

    @setup.command(help="Helps you set up different parts of moderation.", aliases=["mod"])
    @commands.check(hasPriviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def moderation(self, ctx):
        extensions = self.bot.checkExtensions
        if "Moderation" not in extensions:
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This setup requires the extension `moderation` to be active.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        
        def check(payload):
            return payload.author == ctx.author and payload.channel.id == ctx.channel.id
        
        async def setupmuting(self, ctx):
            embed=discord.Embed(title="🛠️ Moderation Setup", description="Please specify the role you want to be used for muting!\n**__Note:__** This role should have `Send Messages` permissions disabled in every channel. It also must be below the bot's role in the hierarchy.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            message = await self.bot.wait_for('message', timeout=60.0, check=check)
            try:
                muterole = await commands.RoleConverter().convert(ctx, message.content)
                async with self.bot.pool.acquire() as con:
                    await con.execute('''
                    INSERT INTO mod_config (guild_id, mute_role_id) VALUES ($1, $2)
                    ON CONFLICT (guild_id) DO
                    UPDATE SET mute_role_id  = $2''', ctx.guild.id, muterole.id)
            except commands.RoleNotFound:
                embed=discord.Embed(title="❌ Error: Unable to locate role.", description="The setup process has been cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return
            embed=discord.Embed(title="🛠️ Moderation Setup", description="✅ Muting is now set up! You can now utilize the `{prefix}mute`, `{prefix}tempmute` and `{prefix}unmute` commands.".format(prefix=ctx.prefix), color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)
        


        embed=discord.Embed(title="🛠️ Moderation Setup", description="Which setup do you want to enter?\n**🔇 - Muting**", color=self.bot.embedBlue)
        msg = await ctx.channel.send(embed=embed)
        await msg.add_reaction("🔇")
        def reactioncheck(payload):
            return payload.message_id == msg.id and payload.user_id == ctx.author.id
        payload = await self.bot.wait_for('raw_reaction_add', timeout=60.0, check=reactioncheck)
        if str(payload.emoji) == "🔇":
            await setupmuting(self, ctx)
        else:
            embed=discord.Embed(title=self.bot.errorDataTitle, description="Invalid reaction provided.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return

    @setup.command(help="Helps you set up a reaction role.", description="Helps you set up a reaction role, the command for managing reaction roles is `reactionrole`.", aliases=["rr"], usage="setup reactionrole")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def reaction_roles(self, ctx):
        try:
            await ctx.invoke(self.bot.get_command('reactionrole add'))
        except AttributeError:
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This setup requires the extension `reaction_roles` to be active.", color=self.bot.errorColor)
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
