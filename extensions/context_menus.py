import logging

import discord
from classes.bot import SnedBot
from discord.commands import user_command
from discord.ext import commands

from extensions.utils import components

logger = logging.getLogger(__name__)


async def has_mod_perms(ctx) -> bool:
    return await ctx.bot.custom_checks.has_permissions(ctx, "mod_permitted")


async def has_fun_perms(ctx) -> bool:
    return await ctx.bot.custom_checks.has_permissions(ctx, "fun") or await ctx.bot.custom_checks.has_permissions(
        ctx, "mod_permitted"
    )


class ContextMenus(commands.Cog):
    def __init__(self, bot: SnedBot):
        self.bot = bot
        self.mod_cog = self.bot.get_cog("Moderation")
        self.checkfailure_embed = discord.Embed(
            title="❌ Missing permissions",
            description="You require additional permissions to execute this action.",
            color=self.bot.error_color,
        )

    @user_command(name="Show Userinfo")
    async def whois_context(self, ctx, member: discord.Member):
        if await has_mod_perms(ctx):
            await ctx.respond(embed=await self.mod_cog.whois(ctx, member), ephemeral=True)
        else:
            await ctx.respond(embed=self.checkfailure_embed, ephemeral=True)

    @user_command(name="Show Journal")
    async def journal_context(self, ctx, member: discord.Member):
        if await has_mod_perms(ctx):
            notes = await self.mod_cog.get_notes(member.id, ctx.guild.id)
            notes_new = []
            if notes:
                for i, note in enumerate(notes):
                    notes_new.append(f"`#{i}` {note}")
                notes_new.reverse()  # Show newest first
                paginator = commands.Paginator(prefix="", suffix="", max_size=1500)
                for note in notes_new:
                    paginator.add_line(note)
                embed_list = []
                for page in paginator.pages:
                    embed = discord.Embed(
                        title="📒 " + "Journal entries for this user:",
                        description=page,
                        color=ctx.bot.embed_blue,
                    )
                    embed_list.append(embed)

                menu_paginator = components.SnedMenuPaginator(pages=embed_list, show_disabled=True, show_indicator=True)

                await menu_paginator.respond(ctx.interaction, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="📒 " + "Journal entries for this user:",
                    description=f"There are no journal entries for this user yet.",
                    color=ctx.bot.embed_blue,
                )
                await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond(embed=self.checkfailure_embed, ephemeral=True)

    @user_command(name="Show Avatar")
    async def avatar_context(self, ctx, member: discord.Member):
        if await has_fun_perms(ctx):
            embed = discord.Embed(
                title="{member_name}'s avatar:".format(member_name=member.name),
                color=member.colour,
            )
            embed.set_image(url=member.display_avatar.url)
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond(embed=self.checkfailure_embed, ephemeral=True)


def setup(bot):
    logger.info("Adding cog: ContextMenus...")
    bot.add_cog(ContextMenus(bot))
