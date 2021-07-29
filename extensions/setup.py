import asyncio
import logging

import asyncpg
import discord
from discord.ext import commands


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)
def is_anno_guild(ctx):
    return ctx.guild.id in ctx.bot.anno_guilds
def is_whitelisted_guild(ctx):
    return ctx.guild.id in ctx.bot.whitelisted_guilds

#This is an entirely optional extension, but you are masochistic if you are not using it :D

class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Ahh yes, the setup command... *instant PTSD*
    #It basically just collects a bunch of values from the user, in this case an admin, and then changes the settings
    #based on that, instead of the admin having to use !modify for every single value
    #TL;DR: fancy setup thing
    @commands.group(help="Starts bot configuration setups.", description = "Used to set up and configure different parts of the bot.", usage="setup <setuptype>", invoke_without_command=True, case_insensitive=True)
    @commands.check(has_priviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def setup (self, ctx):
        await ctx.send_help(ctx.command)

    @setup.command(help="Helps set up matchmaking")
    @commands.check(has_priviliged)
    @commands.check(is_anno_guild)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def matchmaking(self, ctx):
    #This setup will set up the !matchmaking command to work properly.
        cogs = await self.bot.current_cogs()
        if "Matchmaking" not in cogs:
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

            embed=discord.Embed(title="🛠️ Matchmaking setup", description="Now please mention the channel where the multiplayer listings should go.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            payload = await self.bot.wait_for('message', timeout=60.0, check=check)
            announcechannel = await commands.TextChannelConverter().convert(ctx, payload.content)
            embed=discord.Embed(title="🛠️ Matchmaking setup", description=f"Multiplayer listings channel set to {announcechannel.mention}", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)

            embed=discord.Embed(title="🛠️ Matchmaking setup", description=f"Now specify the role that should be mentioned when a new listing is created. Type `skip` to skip this step.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            message = await self.bot.wait_for('message', timeout=60.0, check=check)
            if message.content == "skip":
                lfg_role_id = None
            else:
                lfg_role = await commands.RoleConverter().convert(ctx, message.content)
                lfg_role_id = lfg_role.id
                embed=discord.Embed(title="🛠️ Matchmaking setup", description=f"Multiplayer LFG role set to {lfg_role.mention}", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)

            #Executing based on info

            async with self.bot.pool.acquire() as con:
                await con.execute('''
                INSERT INTO matchmaking_config (guild_id, init_channel_id, announce_channel_id, lfg_role_id) VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id) DO
                UPDATE SET init_channel_id = $2, announce_channel_id = $3, lfg_role_id = $4''', ctx.guild.id, cmdchannel_id, announcechannel.id, lfg_role_id)

            embed=discord.Embed(title="🛠️ Matchmaking setup", description="✅ Setup completed. Matchmaking set up!", color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)
            logging.info(f"Setup for matchmaking concluded successfully on guild {ctx.guild.id}.")
            return

        except commands.ChannelNotFound:
            embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        except commands.RoleNotFound:
            embed=discord.Embed(title="❌ Error: Role not found.", description="Unable to locate role. Operation cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        except asyncio.TimeoutError:
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description=self.bot.errorTimeoutDesc, color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return

    @setup.command(help="Helps set up a keep-on-top message, that will sticky a message on top of a channel at all times.", aliases=["keep-on-top"])
    @commands.check(has_priviliged)
    @commands.check(is_whitelisted_guild)
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
    @commands.check(has_priviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def logging(self, ctx):
        cogs = await self.bot.current_cogs()
        if "Logging" not in cogs:
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
            await self.bot.caching.refresh(table="log_config", guild_id=ctx.guild.id)

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


    @setup.command(help="Helps you set up a role-button.", description="Helps you set up a role-button, the command for managing reaction roles is `rolebutton`.", aliases=["rb", "rr", "reactionrole"], usage="setup rolebutton")
    @commands.check(has_priviliged)
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def role_buttons(self, ctx):
        try:
            await ctx.invoke(self.bot.get_command('rolebutton add'))
        except AttributeError:
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This setup requires the extension `role_buttons` to be active.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed); return


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
