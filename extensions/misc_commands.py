import argparse
import logging
import shlex

import discord
import psutil
from discord.ext import commands

async def has_mod_perms(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, 'mod_permitted')

logger = logging.getLogger(__name__)

class MiscCommands(commands.Cog, name="Miscellaneous Commands"):
    '''Commands that do not belong in any other category'''

    def __init__(self, bot):
        self.bot = bot
        self._ = self.bot.get_localization('misc_commands', self.bot.lang)
        psutil.cpu_percent(interval=1) #We need to do this here so that subsequent CPU % calls will be non-blocking


        #Gets the ping of the bot.
    @commands.command(help="Displays bot ping.", description="Displays the current ping of the bot in miliseconds. Takes no arguments.", usage="ping")
    @commands.guild_only()
    async def ping(self, ctx):
        embed=discord.Embed(title="🏓 Pong!", description=self._("Latency: `{latency}ms`").format(latency=round(self.bot.latency * 1000)), color=self.bot.miscColor)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.channel.send(embed=embed)

    #A more fun way to get the ping.
    @commands.command(hidden = True, help="A better way to get the ping.", description="Why? because yes. Displays the current ping of the bot in miliseconds. Takes no arguments.", usage=f"LEROY")
    @commands.guild_only()
    async def leroy(self, ctx):
        embed=discord.Embed(title="JEEEEENKINS!", description=f"... Oh my god he just ran in. 👀 `{round(self.bot.latency * 1000)}ms`", color =self.bot.miscColor)
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.channel.send(embed=embed)
    
    @commands.command(help="Generates an embed with the given parameters.", description="Generates an embed, and displays it according to the parameters specified. Uses shell-like arguments. Valid parameters:\n\n`--title` or `-t` (Required) Sets embed title\n`--desc` or `-d` (Required) Sets embed description\n`--color` or `-c` Sets embed color (line on the left side)\n`--thumbnail_url` or `-tu` Sets thumbnail to the specified image URL\n`--image_url` or `-iu` Sets the image field to the specified image URL\n`--footer` or `-f` Sets the footer text", usage="embed <args>")
    @commands.cooldown(1, 20, type=commands.BucketType.member)
    @commands.guild_only()
    async def embed(self, ctx, *, args):
        
        parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
        parser.add_argument('--title', '-t')
        parser.add_argument('--desc', '-d')
        parser.add_argument('--footer', '-f')
        parser.add_argument('--thumbnail_url', '-tu')
        parser.add_argument('--image_url', '-iu')
        parser.add_argument('--color', '-c')
        try: 
            args = parser.parse_args(shlex.split(str(args)))
        except Exception as e:
            embed = discord.Embed(title="❌ " + self._("Failed parsing arguments"), description=self._("Please see `{prefix}help embed` for argument formatting!\n**Exception:** ```{exception}```").format(prefix=ctx.prefix, exception=str(e)), color=self.bot.errorColor)
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
            return
        except SystemExit as s: #god this is dumb
            embed = discord.Embed(title="❌ " + self._("Failed parsing arguments"), description=self._("Please see `{prefix}help embed` for argument formatting!\n**Exception:** ```SystemExit: {exception}```\n**Note:** If you are trying to pass multiple words as an argument, wrap them in quotation marks.").format(prefix=ctx.prefix, exception=str(s)), color=self.bot.errorColor)
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
            return
        if args.title == None or args.desc == None:
            embed = discord.Embed(title="❌ " + self._("Missing required argument"), description=self._("You are missing a required argument. Please check `{prefix}help embed` for command usage.").format(prefix=ctx.prefix), color=self.bot.errorColor)
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
            return
        if args.color:
            try:
                color = await commands.ColorConverter().convert(ctx, args.color)
                genEmbed = discord.Embed(title=f"{args.title}", description=f"{args.desc}", color=color)
            except commands.BadArgument:
                embed = discord.Embed(title="❌ " + self._("Invalid color"), description=self._("For valid colors, see the [discord.py API reference](https://discordpy.readthedocs.io/en/latest/api.html#discord.Colour)"), color=self.bot.errorColor)
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.send(embed=embed)
                return
        else:
            genEmbed = discord.Embed(title=f"{args.title}", description=f"{args.desc}")
        if args.footer:
            genEmbed.set_footer(text=f"{args.footer}")
        if args.thumbnail_url:
            genEmbed.set_thumbnail(url=f"{args.thumbnail_url}")
        if args.image_url:
            genEmbed.set_image(url=f"{args.image_url}")
        try:
            await ctx.send(embed=genEmbed)
        except discord.HTTPException as e:
            embed = discord.Embed(title="❌ " + self._("Failed parsing arguments."), description=self._("**Exception:** ```{exception}```").format(exception=str(e)), color=self.bot.errorColor)
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
            return

    #Shows bot version, creator, etc..
    @commands.command(help="Displays information about the bot.", description="Displays information about the bot. Takes no arguments.", usage="about", aliases=["info"])
    @commands.guild_only()
    async def about(self, ctx):
        embed=discord.Embed(title=f"ℹ️ About {self.bot.user.name}", description=f"""**Version:** {self.bot.current_version} 
        **Language:** {self.bot.lang} 
        **Made by:** Hyper#0001
        **Invite:** [Invite me!](https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=3691506934&scope=bot%20applications.commands)
        **Support:** [Click here!](https://discord.gg/KNKr8FPmJa)
        Blob emoji is licensed under [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.html)""", color=self.bot.embedBlue)
        embed = self.bot.add_embed_footer(ctx, embed)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        embed.add_field(name="CPU utilization", value=f"`{round(psutil.cpu_percent(interval=None))}%`")
        process = psutil.Process() #gets current process
        embed.add_field(name="Memory utilization", value=f"`{round(process.memory_info().vms / 1048576)}MB`")
        embed.add_field(name="Latency", value=f"`{round(self.bot.latency * 1000)}ms`")
        await ctx.channel.send(embed=embed)
    
    @commands.command(help="Provides you with an invite link for the bot!", description="Provides you with an invite link so you can add the bot to your own server!", usage="invite")
    async def invite(self, ctx):
        if not self.bot.EXPERIMENTAL:
            invite_url = f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=3691506934&scope=bot%20applications.commands"
            embed=discord.Embed(title="🌟 Yay!", description=self._("[Click here]({invite_url}) for an invite link!").format(invite_url=invite_url), color=self.bot.miscColor)
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.channel.send(embed=embed)

    @commands.command(help="Provides a link to the support Discord.", description="Provides a link to the support Discord, where you can ask for help or provide feedback!", usage="support")
    async def support(self, ctx):
        await ctx.send("https://discord.gg/KNKr8FPmJa")
    
    @commands.command(help="Provides a link to source-code.", description="Provides a link to the GitHub repository where the bot's source-code is hosted.", usage="source")
    async def source(self, ctx):
        await ctx.send("<https://github.com/HyperGH/SnedBot>")
    
    #Retrieves info about the current guild for the end-user
    @commands.command(help="Get information about the server.", description="Provides detailed information about this server.", usage="serverinfo")
    @commands.guild_only()
    @commands.cooldown(1, 30, type=commands.BucketType.member)
    async def serverinfo(self, ctx):
        guild = ctx.guild
        embed=discord.Embed(title="ℹ️ " + self._("Server information"), description=self._("""**Name:** `{guild_name}`
        **ID:** `{guild_id}`
        **Owner:** `{owner}`
        **Created at:** {creation_date}
        **Member count:** `{member_count}`
        **Channels:** `{channel_count}`
        **Roles:** `{role_count}`
        **Region:** `{region}`
        **Filesize limit:** `{filecap}`
        **Nitro Boost count:** `{premium_sub_count}`
        **Nitro Boost level:** `{premium_tier}`""").format(guild_name=guild.name, 
        guild_id=guild.id, 
        owner=guild.owner, 
        creation_date=discord.utils.format_dt(guild.created_at), 
        member_count=guild.member_count, 
        channel_count=len(guild.channels),
        role_count=len(guild.roles),
        region=guild.region, 
        filecap=f"{guild.filesize_limit/1048576}MB", 
        premium_sub_count=guild.premium_subscription_count, 
        premium_tier=guild.premium_tier), 
        color=self.bot.embedBlue)

        embed = self.bot.add_embed_footer(ctx, embed)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.discovery_splash: #If the server has a discovery splash/invite background, we put it as an embed image for extra fancyTM
            embed.set_image(url=guild.discovery_splash.url)
        await ctx.send(embed=embed)

    @commands.command(help="Get information about yourself.", description="Provide detailed information about your user account.", usage="whoami")
    @commands.guild_only()
    @commands.cooldown(1, 30, type=commands.BucketType.member)
    async def whoami(self, ctx):
        whois = self.bot.get_command("whois")
        await ctx.invoke(whois, user=ctx.author)
    
    @commands.command(help = "Displays the amount of warnings for a user.", description="Displays the amount of warnings issued to a user. If user is not specified, it will default to self.", usage="warns [user]")
    @commands.guild_only()
    async def warns(self, ctx, user:discord.Member=None):
        if user is None:
            user = ctx.author
        extensions = await self.bot.current_cogs()
        if "Moderation" not in extensions :
            embed=discord.Embed(title=self.bot.errorMissingModuleTitle, description="This command requires the extension `moderation` to be active.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        db_user = await self.bot.global_config.get_user(user.id, ctx.guild.id)
        warns = db_user.warns
        embed = discord.Embed(title=self._("{user}'s warnings").format(user=user), description=self._("**Warnings:** `{warns}`").format(warns=warns), color=self.bot.warnColor)
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        await ctx.send(embed=embed)

    @commands.group(brief="Repeats what you said.", description="Repeats the provided message, while deleting the command message.", usage="echo <message>", invoke_without_command=True, case_insensitive=True)
    @commands.guild_only()
    @commands.check(has_mod_perms)
    @commands.bot_has_permissions(manage_messages=True)
    async def echo(self, ctx, *, content:str):
        await ctx.message.delete()
        await ctx.send(content=content)

    @echo.command(name="to", help="Repeats what you said in a different channel.", description="Repeats the provided message in a given channel, while deleting the command message.", usage="echo to <channel> <message>")
    @commands.guild_only()
    @commands.check(has_mod_perms)
    @commands.bot_has_permissions(manage_messages=True)
    async def echo_to(self, ctx, channel:discord.TextChannel, *, content:str):
        await ctx.message.delete()
        await channel.send(content=content)



def setup(bot):
    logger.info("Adding cog: MiscCommands...")
    bot.add_cog(MiscCommands(bot))
