import asyncio
import json
import logging
import gettext
import aiohttp
import discord
from discord.ext import commands

async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)
def is_anno_guild(ctx):
    return ctx.guild.id in ctx.bot.anno_guilds

class Annoverse(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.annowiki_color = discord.Color.from_rgb(218, 166, 100)

        self._ = self.bot.get_localization('annoverse', self.bot.lang)

    def cog_check(self,ctx):
        return is_anno_guild(ctx)
    

    @commands.Cog.listener
    async def on_message(self, message):
        '''
        Quick hack for giveaway on Annoverse, remove this after done
        '''
        if message.guild.id == 372128553031958529 and message.channel.id == 846472729981222922 and not message.author.bot:
            ctx = await self.bot.get_context(message)
            if not await has_priviliged(ctx):
                await message.channel.set_permissions(message.author, send_messages=False, reason="Giveaway submission")


    '''
    Searches the fandom specified with the link and query via opensearch, then
    return a formatted description for insertion in an embed or message.
    Will only search for up to five items
    '''
    async def search_fandom(self, site, query):

        link_root = "https://{site}.fandom.com/wiki/" #Redirect here if no query is specified
        link = "https://{site}.fandom.com/api.php?action=opensearch&search={query}&limit=5"
        if query is None:
            return link_root.format(site=site)
        query = query.replace(" ", "+")

        async with aiohttp.ClientSession() as session:
            async with session.get(link.format(query=query, site=site)) as response:
                results_dict = await response.json()
                results_text = results_dict[1] #2nd element contains text, 4th links
                results_link = results_dict[3]

        desc=""
        if len(results_text) > 0:
            for result in results_text:
                desc = f"{desc}[{result}]({results_link[results_text.index(result)]})\n"
            return desc
        else:
            raise NameError
    

    async def maybe_reply_embed(self, ctx, embed):
        '''
        If message is a reply to someone, the bot's reply will also be a reply
        to that message.
        '''
        if ctx.message.reference != None: #If the original command was invoked as a reply to someone
            try:
                replytomsg = ctx.channel.get_partial_message(ctx.message.reference.message_id)
                await replytomsg.reply(embed=embed, mention_author=True) #Then the invoked tag will also reply to that message
            except discord.HTTPException:
                await ctx.channel.send(embed=embed)
        else :
            await ctx.channel.send(embed=embed)


    @commands.group(aliases=["aw"], help="Retrieve wiki articles from an Anno wiki!", description="Retrieve wiki articles from one of the Anno wikis! Defaults to the 1800 one.\n\n**Possible wikis:**\n`1800,2205,2070,1404`", usage="annowiki [wiki] <search term>", invoke_without_command=True, case_insensitive=True)
    @commands.guild_only()
    async def annowiki(self, ctx, *, query:str=None):
        if query and query.startswith(tuple(["1602", "1503", "1701", "anno1602", "anno1503", "anno1701"])):
            embed=discord.Embed(title="❌ " + self._("Wiki does not exist or unsupported"), description=self._("This wiki is either not supported or does not exist!").format(query=query), color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        await ctx.invoke(self.annowiki.get_command("anno1800"), query=query) # pylint: disable=<no-member>
    
    @annowiki.command(aliases=["1800"])
    @commands.guild_only()
    async def anno1800(self, ctx, *, query:str=None):
        await ctx.channel.trigger_typing()
        site = "anno1800"
        try:
            results = await self.search_fandom(site, query)
            embed=discord.Embed(title=f"Anno 1800 Wiki: {query}", description=results, color=self.annowiki_color)
            await self.maybe_reply_embed(ctx, embed)
        except NameError:
            embed=discord.Embed(title="❌ " + self._("Not found"), description=self._("Could not find anything for `{query}`!").format(query=query), color=self.bot.errorColor)
            await ctx.send(embed=embed)

    
    @annowiki.command(aliases=["2205"])
    @commands.guild_only()
    async def anno2205(self, ctx, *, query:str=None):
        await ctx.channel.trigger_typing()
        site = "anno2205"
        try:
            results = await self.search_fandom(site, query)
            embed=discord.Embed(title=f"Anno 2205 Wiki: {query}", description=results, color=self.annowiki_color)
            await self.maybe_reply_embed(ctx, embed)
        except NameError:
            embed=discord.Embed(title="❌ " + self._("Not found"), description=self._("Could not find anything for `{query}`!").format(query=query), color=self.bot.errorColor)
            await ctx.send(embed=embed)
    
    @annowiki.command(aliases=["2070"])
    @commands.guild_only()
    async def anno2070(self, ctx, *, query:str=None):
        await ctx.channel.trigger_typing()
        site = "anno2070"
        try:
            results = await self.search_fandom(site, query)
            embed=discord.Embed(title=f"Anno 2070 Wiki: {query}", description=results, color=self.annowiki_color)
            await self.maybe_reply_embed(ctx, embed)
        except NameError:
            embed=discord.Embed(title="❌ " + self._("Not found"), description=self._("Could not find anything for `{query}`!").format(query=query), color=self.bot.errorColor)
            await ctx.send(embed=embed)
    
    @annowiki.command(aliases=["1404"])
    @commands.guild_only()
    async def anno1404(self, ctx, *, query:str=None):
        await ctx.channel.trigger_typing()
        site = "anno1404"
        try:
            results = await self.search_fandom(site, query)
            embed=discord.Embed(title=f"Anno 1404 Wiki: {query}", description=results, color=self.annowiki_color)
            await self.maybe_reply_embed(ctx, embed)
        except NameError:
            embed=discord.Embed(title="❌ " + self._("Not found"), description=self._("Could not find anything for `{query}`!").format(query=query), color=self.bot.errorColor)
            await ctx.send(embed=embed)




def setup(bot):
    logging.info("Adding cog: Annoverse...")
    bot.add_cog(Annoverse(bot))