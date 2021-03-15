import discord
from discord.ext import commands


async def hasOwner(ctx):
    return ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id

#Check performed to see if the user has priviliged access.
async def hasPriviliged(ctx):
    #Gets a list of all the roles the user has, then gets the ID from that.
    userRoles = [x.id for x in ctx.author.roles]
    #Also get privliged roles, then compare
    privroles = [role[0] for role in await ctx.bot.DBHandler.checkprivs(ctx.guild.id)]
    #Check if any of the roles in user's roles are contained in the priviliged roles.
    return any(role in userRoles for role in privroles) or (ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id)



class MiscCommands(commands.Cog, name="Miscellaneous Commands"):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(brief="Displays a user's avatar.", description="Displays a user's avatar for your viewing (or stealing) pleasure.", usage=f"avatar <userID|userMention|userName>")
    @commands.cooldown(1, 30, type=commands.BucketType.member)
    async def avatar(self, ctx, member : discord.Member) :
        embed=discord.Embed(title=f"{member.name}'s avatar:", color=member.colour)
        embed.set_image(url=member.avatar_url)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.channel.send(embed=embed)

    @avatar.error
    async def avatar_error(self, ctx, error):
        if isinstance(error, discord.ext.commands.errors.MemberNotFound) :
            embed=discord.Embed(title="❌ Unable to find user.", description="Please check if you typed everything correctly, then try again.", color=self.bot.errorColor)
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)

        #Gets the ping of the bot.
    @commands.command(brief="Displays bot ping.", description="Displays the current ping of the bot in miliseconds. Takes no arguments.", usage="ping")
    async def ping(self, ctx):
        embed=discord.Embed(title="🏓 Pong!", description=f"Latency: `{round(self.bot.latency * 1000)}ms`", color=self.bot.miscColor)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.channel.send(embed=embed)

    #A more fun way to get the ping.
    @commands.command(hidden = True, brief="A better way to get the ping.", description="Why? because yes. Displays the current ping of the bot in miliseconds. Takes no arguments.", usage=f"LEROY")
    async def leroy(self, ctx):
        embed=discord.Embed(title="JEEEEENKINS!", description=f"... Oh my god he just ran in. 👀 `{round(self.bot.latency * 1000)}ms`", color =self.bot.miscColor)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.channel.send(embed=embed)

    @commands.command(brief="Displays information about the bot.", description="Displays information about the bot. Takes no arguments.", usage="about")
    async def about(self, ctx):
        embed=discord.Embed(title=f"ℹ️ About {self.bot.user.name}", description=f"**Version:** {self.bot.currentVersion} \n**Made by:** Hyper#0001 \n**GitHub:** https://github.com/HyperGH/AnnoSnedBot", color=self.bot.embedBlue)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        await ctx.channel.send(embed=embed)
    #Fun command, because yes. (Needs mod privilege as it can be abused for spamming)
    @commands.command(hidden = True, brief = "Deploys the duck army.", description="🦆 I am surprised you even need help for this...", usage=f"quack")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def quack(self, ctx):
        await ctx.channel.send("🦆")
        await ctx.message.delete()

def setup(bot):
    print("[INFO] Adding cog: MiscCommands...")
    bot.add_cog(MiscCommands(bot))