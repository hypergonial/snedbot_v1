import logging

import aiohttp
import discord
from classes.bot import SnedBot
from discord.ext import commands


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)


def is_aestris_guild(ctx):
    return ctx.guild.id in [581296099826860033]


logger = logging.getLogger(__name__)


class Aestris(commands.Cog, name="Aestris's Stuff"):
    """
    Commands & functionality related to the Aestris's Discord
    """

    def __init__(self, bot: SnedBot):
        self.bot = bot
        self.svwiki_color = discord.Colour.from_rgb(224, 161, 0)

    def cog_check(self, ctx):
        return is_aestris_guild(ctx)

    """
    Searches the stardew wiki specified with the link and query via opensearch, then
    return a formatted description for insertion in an embed or message.
    Will only search for up to five items
    """

    async def search_stardew(self, query):

        link_root = "https://www.stardewvalleywiki.com/"  # Redirect here if no query is specified
        link = (
            "https://www.stardewvalleywiki.com/mediawiki/api.php?action=opensearch&format=json&search={query}&limit=5"
        )
        if query is None:
            return link_root
        query = query.replace(" ", "+")

        async with aiohttp.ClientSession() as session:
            async with session.get(link.format(query=query)) as response:
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
        aliases=["svwiki"],
        brief="Searches the Stardew Valley Wiki",
        description="Searches the Stardew Valley Wiki for the given query.",
        usage="stardewwiki <query>",
    )
    @commands.guild_only()
    async def stardewwiki(self, ctx, *, query: str = None):
        await ctx.channel.trigger_typing()
        try:
            results = await self.search_stardew(query)
            embed = discord.Embed(
                title=f"Stardew Valley Wiki: {query}",
                description=results,
                color=self.svwiki_color,
            )
            await self.maybe_reply_embed(ctx, embed)
        except NameError:
            embed = discord.Embed(
                title="❌ Not found",
                description="Could not find anything for `{query}`!".format(query=query),
                color=self.bot.error_color,
            )
            await ctx.send(embed=embed)


def setup(bot: SnedBot):
    logger.info("Adding cog: Aestris's Stuff...")
    bot.add_cog(Aestris(bot))
