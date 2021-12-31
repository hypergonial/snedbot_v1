import logging

import aiohttp
import discord
from discord.ext import commands


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)


def is_ff_guild(ctx):
    return ctx.guild.id in [684324252786360476, 813803567445049414]


logger = logging.getLogger(__name__)


class FallingFrontier(commands.Cog, name="Falling Frontier"):
    """
    Commands & functionality related to the Falling Frontier Discord
    """

    def __init__(self, bot):
        self.bot = bot
        self.ffwiki_color = discord.Colour.from_rgb(75, 170, 147)

    def cog_check(self, ctx):
        return is_ff_guild(ctx)

    """
    Searches the fandom specified with the link and query via opensearch, then
    return a formatted description for insertion in an embed or message.
    Will only search for up to five items
    """

    async def search_fandom(self, site, query):

        link_root = "https://{site}.fandom.com/wiki/"  # Redirect here if no query is specified
        link = "https://{site}.fandom.com/api.php?action=opensearch&search={query}&limit=5"
        if query is None:
            return link_root.format(site=site)
        query = query.replace(" ", "+")

        async with aiohttp.ClientSession() as session:
            async with session.get(link.format(query=query, site=site)) as response:
                results_dict = await response.json()
                results_text = results_dict[1]  # 2nd element contains text, 4th links
                results_link = results_dict[3]

        desc = ""
        if len(results_text) > 0:
            for result in results_text:
                desc = f"{desc}[{result}]({results_link[results_text.index(result)]})\n"
            return desc
        else:
            raise NameError

    async def maybe_reply_embed(self, ctx, embed):
        """
        If message is a reply to someone, the bot's reply will also be a reply
        to that message.
        """
        if ctx.message.reference != None:  # If the original command was invoked as a reply to someone
            try:
                replytomsg = ctx.channel.get_partial_message(ctx.message.reference.message_id)
                await replytomsg.reply(
                    embed=embed, mention_author=True
                )  # Then the invoked tag will also reply to that message
            except discord.HTTPException:
                await ctx.channel.send(embed=embed)
        else:
            await ctx.channel.send(embed=embed)

    @commands.command(
        aliases=["ffwiki"],
        brief="Searches the Falling Frontier Wiki",
        description="Searches the Falling Frontier Wiki for the given query.",
        usage="fallingfrontierwiki <query>",
    )
    @commands.guild_only()
    async def fallingfrontierwiki(self, ctx, *, query: str = None):
        await ctx.channel.trigger_typing()
        site = "falling-frontier"
        try:
            results = await self.search_fandom(site, query)
            embed = discord.Embed(
                title=f"Falling Frontier Wiki: {query}",
                description=results,
                color=self.ffwiki_color,
            )
            await self.maybe_reply_embed(ctx, embed)
        except NameError:
            embed = discord.Embed(
                title="❌ " + self._("Not found"),
                description=self._("Could not find anything for `{query}`!").format(query=query),
                color=self.bot.errorColor,
            )
            await ctx.send(embed=embed)


def setup(bot):
    logger.info("Adding cog: Falling Frontier...")
    bot.add_cog(FallingFrontier(bot))
