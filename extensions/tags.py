import gettext
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

class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.lang == "de":
            de = gettext.translation('tags', localedir=self.bot.localePath, languages=['de'])
            de.install()
            self._ = de.gettext
        elif self.bot.lang == "en":
            self._ = gettext.gettext
        #Fallback to english
        else :
            logging.error("Invalid language, fallback to English.")
            self._ = gettext.gettext

    @commands.command(help="Calls a tag.", description="Calls a tag that has been previously set. You can get a list of tags via the command `tags`.", usage=f"tag <tagname>")
    @commands.cooldown(1, 60, type=commands.BucketType.member)
    @commands.guild_only()
    async def tag(self, ctx, *, name):
        if name in self.bot.reservedTextNames :
            embed=discord.Embed(title="❌ " + self._("Error: Reserved."), description=self._("This name is reserved for internal functions. Try another name."), color=self.bot.errorColor)
            embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            await ctx.channel.send(embed=embed)
            self.tag.reset_cooldown(ctx)
            return
        else :
            tagContent = await self.bot.DBHandler.retrievetext(name, ctx.guild.id)
            if tagContent == None :
                embed=discord.Embed(title="❌ " + self._("Error: Unknown tag."), description=self._("Cannot find tag by that name."), color=self.bot.errorColor)
                embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
                await ctx.channel.send(embed=embed)
                self.tag.reset_cooldown(ctx)
                return
            else :
                if ctx.message.reference != None: #If the original command was invoked as a reply to someone
                    try:
                        replytomsg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                        await replytomsg.reply(content=tagContent, mention_author=True) #Then the invoked tag will also reply to that message
                    except discord.HTTPException:
                        await ctx.channel.send(content=tagContent)
                else :
                    await ctx.channel.send(content=tagContent)

    @commands.command(help="Displays all the tags you can call.", description="Shows a list of all available tags.", usage="tags")
    @commands.cooldown(1, 60, type=commands.BucketType.member)
    @commands.guild_only()
    async def tags(self, ctx):
        tags = ", ".join(await self.bot.DBHandler.getTags(ctx.guild.id))
        embed = discord.Embed(title="💬 " + self._("Available tags for this guild:"), description=f"`{tags}`", color=self.bot.embedBlue)
        embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        await ctx.channel.send(embed=embed)
#
#Admin-only
#
#Only admins can access these tag related commands.

    @commands.command(help="Creates a tag.", description=f"Creates a tag for all users to call. \n**__Must be executed__** in the same channel as the message.", usage="createtag <tagname> <messageID>", aliases=['addtag'])
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def createtag(self, ctx, name, messageID):
        if name in self.bot.reservedTextNames :
            embed=discord.Embed(title="❌ " + self._("Error: Reserved."), description=self._("This name is reserved for internal functions. Try another name."), color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        elif len(name) >= 3:
            try:
                #Store it
                msgToTag = await ctx.channel.fetch_message(messageID)
                await self.bot.DBHandler.storetext(name, msgToTag.content, ctx.guild.id)
                embed=discord.Embed(title="✅ " + self._("Tag added."), description=self._("Tag added! You can now call it via `{prefix}tag {tag_name}`!").format(prefix=self.bot.prefix, tag_name=name), color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)
                return
            except discord.NotFound:
                embed=discord.Embed(title="❌ " + self._("Error: Message not found."), description=self._("Please **__make sure__** you ran the command in the channel you want to get the message from!"), color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return
        else :
            embed=discord.Embed(title="❌ " + self._("Error: Tag name too short."), description=self._("Your tag name must be 3 characters long or more."), color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
    @commands.command(help="Deletes a tag.", description="Permanently erases a tag, removing it from the list of callable tags.", usage="deltag <tagname>", aliases=['deletetag, removetag'])
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def deltag(self, ctx, name) :
        if name in self.bot.reservedTextNames :
            embed=discord.Embed(title="❌ " + self._("Error: Reserved."), description=self._("This name is reserved for internal functions. Try another name."), color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        else:
            if name in await self.bot.DBHandler.getTags(ctx.guild.id) :
                await self.bot.DBHandler.deltext(name, ctx.guild.id)
                embed=discord.Embed(title="✅ " + self._("Tag deleted."), description=self._("Tag {tag_name} has been removed.").format(tag_name=name), color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)
                return
            else :
                embed=discord.Embed(title="❌ " + self._("Error: Tag not found."), description=self._("Unable to locate tag. Please run `{prefix}tags` for a list of tags!").format(prefix=self.bot.prefix), color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return

def setup(bot):
    logging.info("Adding cog: Tags...")
    bot.add_cog(Tags(bot))
