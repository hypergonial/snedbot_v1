import discord
from discord.ext import commands
import logging

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

class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Calls a tag!", description="Calls a tag that has been previously set.", usage=f"tag <tagname>")
    @commands.cooldown(1, 60, type=commands.BucketType.member)
    @commands.guild_only()
    async def tag(self, ctx, name):
        if name in self.bot.reservedTextNames :
            embed=discord.Embed(title="❌ Error: Reserved.", description="This name is reserved for internal functions. Try another name.", color=self.bot.errorColor)
            embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
            await ctx.channel.send(embed=embed)
            #self.tag.reset_cooldown(ctx)
            return
        else :
            tagContent = await self.bot.DBHandler.retrievetext(name, ctx.guild.id)
            if tagContent == None :
                embed=discord.Embed(title="❌ Error: Unknown tag.", description="Cannot find tag by that name.", color=self.bot.errorColor)
                embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
                await ctx.channel.send(embed=embed)
                self.tag.reset_cooldown(ctx)
                return
            else :
                
                await ctx.channel.send(content=tagContent + f"\nTag requested by {ctx.author.name}#{ctx.author.discriminator}")

    @commands.command(brief="Displays all tags.", description="Shows a list of all available tags.", usage="tags")
    @commands.cooldown(1, 60, type=commands.BucketType.member)
    @commands.guild_only()
    async def tags(self, ctx):
        tags = ", ".join(await self.bot.DBHandler.getTags(ctx.guild.id))
        embed = discord.Embed(title="💬 Available tags for this guild:", description=f"`{tags}`", color=self.bot.embedBlue)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        await ctx.channel.send(embed=embed)
#
#Admin-only
#
#Only admins can access these tag related commands.

    @commands.command(hidden=True, brief="Creates a tag.", description=f"Creates a tag for all users to call. \n**__Must be executed__** in the same channel as the message.", usage="createtag <tagname> <messageID>", aliases=['addtag'])
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def createtag(self, ctx, name, messageID):
        if name in self.bot.reservedTextNames :
            embed=discord.Embed(title="❌ Error: Reserved.", description="This name is reserved for internal functions. Try another name.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        elif len(name) >= 3:
            try:
                #Store it
                msgToTag = await ctx.channel.fetch_message(messageID)
                await self.bot.DBHandler.storetext(name, msgToTag.content, ctx.guild.id)
                embed=discord.Embed(title="✅ Tag added.", description=f"Tag added! You can now call it via `{self.bot.prefix}tag {name}`!", color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)
                return
            except discord.NotFound:
                embed=discord.Embed(title="❌ Error: Message not found.", description="Please **__make sure__** you ran the command in the channel you want to get the message from!", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return
        else :
            embed=discord.Embed(title="❌ Error: Tag name too short.", description="Your tag name must be 3 characters long or more.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
    @commands.command(hidden=True, brief="Deletes a tag.", description="Permanently erases a tag, removing it from the list of callable tags.", usage="deltag <tagname>", aliases=['deletetag, removetag'])
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def deltag(self, ctx, name) :
        if name in self.bot.reservedTextNames :
            embed=discord.Embed(title="❌ Error: Reserved.", description="This name is reserved for internal functions. Try another name.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        else:
            if name in await self.bot.DBHandler.getTags(ctx.guild.id) :
                await self.bot.DBHandler.deltext(name, ctx.guild.id)
                embed=discord.Embed(title="✅ Tag deleted.", description=f"Tag {name} has been removed.", color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)
                return
            else :
                embed=discord.Embed(title="❌ Error: Tag not found.", description=f"Unable to locate tag. Please run `{self.bot.prefix}tags` for a list of tags!", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return

def setup(bot):
    logging.info("Adding cog: Tags...")
    bot.add_cog(Tags(bot))