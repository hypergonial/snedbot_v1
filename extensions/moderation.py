import gettext
import logging

import aiosqlite
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

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.lang == "de":
            de = gettext.translation('moderation', localedir=self.bot.localePath, languages=['de'])
            de.install()
            self._ = de.gettext
        elif self.bot.lang == "en":
            self._ = gettext.gettext
        #Fallback to english
        else :
            logging.error("Invalid language, fallback to English.")
            self._ = gettext.gettext
    
    #Warn a user & print it to logs, needs logs to be set up
    @commands.command(help="Warns a user.", description="Warns the user and logs it.", usage="warn <user> [reason]")
    @commands.check(hasPriviliged)
    async def warn(self, ctx, offender:discord.Member, *, reason:str=None):
        db_user = await self.bot.DBHandler.getUser(ctx.author.id, ctx.guild.id)
        warns = db_user["warns"]
        warns +=1
        await self.bot.DBHandler.updateUser(ctx.author.id, "warns", warns, ctx.guild.id) #Update warns for user by incrementing it
        if reason == None :
            embed=discord.Embed(title="⚠️" + self._("Warning issued."), description=self._("{offender} has been warned.").format(offender=offender.mention), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{offender.mention} has been warned by {ctx.author.mention}.\n**Warns:** {warns}\n\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        else :
            embed=discord.Embed(title="⚠️" + self._("Warning issued."), description=self._("{offender} has been warned.\n**Reason:** {reason}").format(offender=offender.mention, reason=reason), color=self.bot.warnColor)
            warnembed=discord.Embed(title="⚠️ Warning issued.", description=f"{offender.mention} has been warned by {ctx.author.mention}.\n**Warns:** {warns}\n**Reason:** ```{reason}```\n[Jump!]({ctx.message.jump_url})", color=self.bot.warnColor)
        try:
            await self.bot.get_cog("Logging").log_elevated(warnembed, ctx.guild.id)
            await ctx.send(embed=embed)
        except AttributeError:
            embed=discord.Embed(title="❌ " + self._("Warning failed."), description=self._("Logging is not set up properly."), color=self.bot.errorColor)
            await ctx.send(embed=embed, delete_after=20)
            await ctx.message.delete()
        
    




def setup(bot):
    logging.info("Adding cog: Moderation...")
    bot.add_cog(Moderation(bot))
