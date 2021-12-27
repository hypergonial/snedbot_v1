import logging
from dataclasses import dataclass
from difflib import get_close_matches
from itertools import chain

import discord
from discord.ext import commands, pages

from extensions.utils import components


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)


async def has_mod_perms(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, "mod_permitted")


logger = logging.getLogger(__name__)


@dataclass
class Tag:
    """
    Dataclass that represents a tag
    """

    guild_id: int
    tag_name: str
    tag_owner_id: int
    tag_aliases: list
    tag_content: str


class TagAlreadyExists(Exception):
    """
    Raised when a tag is trying to get created but already exists
    """

    pass


class TagNotFound(Exception):
    """
    Raised when a tag is not found, although most functions just return None when this happens
    """

    pass


class TagHandler:
    """
    A class for common database operations regarding tags
    """

    def __init__(self, bot):
        self.bot = bot

    async def get(self, tag_name: str, guild_id: int):
        """
        Returns a Tag object for the given name & guild ID, returns None if not found.
        Will try to find aliases too.
        """
        async with self.bot.pool.acquire() as con:
            result = await self.bot.pool.fetch(
                """SELECT * FROM tags WHERE tag_name = $1 AND guild_id = $2""",
                tag_name.lower(),
                guild_id,
            )
            if len(result) != 0:
                tag = Tag(
                    guild_id=result[0].get("guild_id"),
                    tag_name=result[0].get("tag_name"),
                    tag_owner_id=result[0].get("tag_owner_id"),
                    tag_aliases=result[0].get("tag_aliases"),
                    tag_content=result[0].get("tag_content"),
                )
                return tag
            result = await con.fetch(
                """SELECT * FROM tags WHERE $1 = ANY(tag_aliases) AND guild_id = $2""",
                tag_name.lower(),
                guild_id,
            )
            if len(result) != 0:
                tag = Tag(
                    guild_id=result[0].get("guild_id"),
                    tag_name=result[0].get("tag_name"),
                    tag_owner_id=result[0].get("tag_owner_id"),
                    tag_aliases=result[0].get("tag_aliases"),
                    tag_content=result[0].get("tag_content"),
                )
                return tag

    async def create(self, tag: Tag):
        """
        Creates a new tag based on an instance of a Tag.
        """
        await self.bot.pool.execute(
            """
        INSERT INTO tags (guild_id, tag_name, tag_owner_id, tag_aliases, tag_content)
        VALUES ($1, $2, $3, $4, $5)""",
            tag.guild_id,
            tag.tag_name,
            tag.tag_owner_id,
            tag.tag_aliases,
            tag.tag_content,
        )

    async def get_all(self, guild_id: int):
        """
        Returns a list of all tags for the specified guild.
        """
        results = await self.bot.pool.fetch(
            """SELECT * FROM tags WHERE guild_id = $1""", guild_id
        )
        if len(results) != 0:
            tags = []
            for result in results:
                tag = Tag(
                    guild_id=result.get("guild_id"),
                    tag_name=result.get("tag_name"),
                    tag_owner_id=result.get("tag_owner_id"),
                    tag_aliases=result.get("tag_aliases"),
                    tag_content=result.get("tag_content"),
                )
                tags.append(tag)
            return tags

    async def delete(self, tag_name: str, guild_id: int):
        await self.bot.pool.execute(
            """DELETE FROM tags WHERE tag_name = $1 AND guild_id = $2""",
            tag_name,
            guild_id,
        )

    async def migrate(
        self, origin_id: int, destination_id: int, invoker_id: int, tag_name: str
    ):
        """
        Migrates a tag from one guild to another.
        """
        dest_tag = await self.get(tag_name, destination_id)
        if not dest_tag:
            tag = await self.get(tag_name, origin_id)
            if tag:
                tag.guild_id = (
                    destination_id  # Change it's ID so it belongs to the new guild
                )
                tag.tag_owner_id = invoker_id  # New owner is whoever imported the tag
                await self.create(tag)
            else:
                raise TagNotFound("This tag does not exist at origin, cannot migrate.")
        else:
            raise TagAlreadyExists(
                "This tag already exists at destination, cannot migrate."
            )

    async def migrate_all(
        self, origin_id: int, destination_id: int, invoker_id: int, strategy: str
    ):
        """
        Migrates all tags from one server to a different one. 'strategy' defines overriding behaviour.

        override - Override all tags in the destination server.
        keep - Keep conflicting tags in the destination server.

        Note: Migration of all tags does not migrate aliases.
        """
        tags = await self.get_all(origin_id)
        tags_unpacked = []
        for tag in tags:
            """
            Unpack tag objects into a 2D list that contains all the info required about them,
            for easy insertion into the database.
            """
            tag_unpacked = [
                destination_id,
                tag.tag_name,
                invoker_id,
                None,
                tag.tag_content,
            ]
            tags_unpacked.append(tag_unpacked)

        if strategy == "override":
            async with self.bot.pool.acquire() as con:
                await con.executemany(
                    """
                INSERT INTO tags (guild_id, tag_name, tag_owner_id, tag_aliases, tag_content)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id, tag_name) DO
                UPDATE SET tag_owner_id=$3, tag_aliases=$4, tag_content = $5""",
                    tags_unpacked,
                )
        elif strategy == "keep":
            async with self.bot.pool.acquire() as con:
                await con.executemany(
                    """
                INSERT INTO tags (guild_id, tag_name, tag_owner_id, tag_aliases, tag_content)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (guild_id, tag_name) DO
                NOTHING""",
                    tags_unpacked,
                )
        else:
            raise ValueError("Invalid strategy specified.")


class Tags(commands.Cog):
    """All commands relating to tags"""

    def __init__(self, bot):
        self.bot = bot
        self.tag_handler = TagHandler(bot)
        self._ = self.bot.get_localization("tags", self.bot.lang)

    async def cog_check(self, ctx):
        return await ctx.bot.custom_checks.has_permissions(
            ctx, "tags"
        ) or await ctx.bot.custom_checks.has_permissions(ctx, "mod_permitted")

    @commands.group(
        help="Calls a tag. See subcommands for tag creation & management.",
        description="Calls a tag that has been previously set. You can use the subcommands to create, delete, view, or list tags.",
        usage=f"tag <tagname>",
        invoke_without_command=True,
        case_insensitive=True,
    )
    @commands.cooldown(1, 20, type=commands.BucketType.member)
    @commands.guild_only()
    async def tag(self, ctx, *, name=None):
        if name:
            tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
            if tag:
                if (
                    ctx.message.reference != None
                ):  # If the original command was invoked as a reply to someone
                    try:
                        replytomsg = ctx.channel.get_partial_message(
                            ctx.message.reference.message_id
                        )
                        await replytomsg.reply(
                            content=tag.tag_content, mention_author=True
                        )  # Then the invoked tag will also reply to that message
                    except discord.HTTPException:
                        await ctx.channel.send(content=tag.tag_content)
                else:
                    await ctx.channel.send(content=tag.tag_content)

            else:
                embed = discord.Embed(
                    title="❌ " + self._("Error: Unknown tag"),
                    description=self._("Cannot find tag by that name."),
                    color=self.bot.errorColor,
                )
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.channel.send(embed=embed)
                ctx.command.reset_cooldown(ctx)
        else:
            await ctx.send_help(ctx.command)

    @tag.command(
        help="Creates a new tag.",
        description="Creates a new tag that will be owned by you, with the specified content.",
        usage="tag create <tagname> <content>",
    )
    @commands.cooldown(1, 20, type=commands.BucketType.member)
    @commands.guild_only()
    async def create(self, ctx, name, *, content):
        tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
        if tag:
            embed = discord.Embed(
                title="❌ " + self._("Error: Tag exists"),
                description=self._(
                    "This tag already exists. If the owner of this tag is no longer in the server, you can try doing `{prefix}tag claim {name}`"
                ).format(prefix=ctx.prefix, name=name),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.channel.send(embed=embed)
        else:
            if (
                len(ctx.message.attachments) > 0 and ctx.message.attachments[0]
            ):  # Attachment support for tags
                content = f"{content}\n{ctx.message.attachments[0].url}"

            new_tag = Tag(
                guild_id=ctx.guild.id,
                tag_name=name.lower(),
                tag_owner_id=ctx.author.id,
                tag_aliases=None,
                tag_content=content,
            )
            await self.tag_handler.create(new_tag)
            embed = discord.Embed(
                title="✅ " + self._("Tag created!"),
                description=self._(
                    "You can now call it with `{prefix}tag {name}`"
                ).format(prefix=ctx.prefix, name=name),
                color=self.bot.embedGreen,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @tag.command(
        help="Provides info about a tag.",
        description="Shows information about a tag like the owner and aliases.",
        usage="tag info <tagname>",
    )
    @commands.cooldown(1, 20, type=commands.BucketType.member)
    @commands.guild_only()
    async def info(self, ctx, *, name):
        tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
        if tag:
            owner = await self.bot.fetch_user(tag.tag_owner_id)
            if tag.tag_aliases:
                aliases = ", ".join(tag.tag_aliases)
            else:
                aliases = None
            embed = discord.Embed(
                title="💬 "
                + self._("Tag Info: {tag_name}").format(tag_name=tag.tag_name),
                description=self._(
                    "**Aliases:** `{aliases}`\n**Tag owner:** {owner}\n"
                ).format(aliases=aliases, owner=owner.mention),
                color=self.bot.embedBlue,
            )
            embed.set_author(name=str(owner), icon_url=owner.avatar.url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ " + self._("Error: Unknown tag"),
                description=self._("Cannot find tag by that name."),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @tag.command(
        help="Sets an alias for a tag.",
        description="Sets an alias for a tag, meaning that a tag can then be called with both it's original name and the new alias. A tag can have a maximum of **5** aliases.",
        usage="tag alias <tagname> <alias>",
    )
    @commands.guild_only()
    async def alias(self, ctx, name, *, alias):
        # Check if the alias is taken or not
        alias_tag = await self.tag_handler.get(alias.lower(), ctx.guild.id)
        if alias_tag:
            embed = discord.Embed(
                title="❌ " + self._("Error: Already taken"),
                description=self._(
                    "A tag or alias is already created with the same name."
                ),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
            return

        tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
        if tag and tag.tag_owner_id == ctx.author.id:
            aliases = []
            if (
                tag.tag_aliases
                and alias.lower() not in tag.tag_aliases
                or tag.tag_aliases == None
                or len(tag.tag_aliases) == 0
            ):
                if tag.tag_aliases == None:
                    aliases.append(alias.lower())
                elif len(tag.tag_aliases) <= 4:
                    aliases = tag.tag_aliases
                    aliases.append(alias.lower())
                else:
                    embed = discord.Embed(
                        title="❌ " + self._("Error: Too many aliases"),
                        description=self._(
                            "Tag `{tag}` can only have up to **5** aliases."
                        ).format(tag=tag.tag_name),
                        color=self.bot.errorColor,
                    )
                    embed = self.bot.add_embed_footer(ctx, embed)
                    await ctx.send(embed=embed)
                    return

                # Delete the tag, and recreate it with the new aliases
                await self.tag_handler.delete(tag.tag_name, ctx.guild.id)
                new_tag = Tag(
                    guild_id=ctx.guild.id,
                    tag_name=tag.tag_name,
                    tag_owner_id=tag.tag_owner_id,
                    tag_aliases=aliases,
                    tag_content=tag.tag_content,
                )
                await self.tag_handler.create(new_tag)
                embed = discord.Embed(
                    title="✅ " + self._("Alias created"),
                    description=self._(
                        "You can now call it with `{prefix}tag {name}`"
                    ).format(prefix=ctx.prefix, name=alias.lower()),
                    color=self.bot.embedGreen,
                )
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.send(embed=embed)

            else:
                embed = discord.Embed(
                    title="❌ " + self._("Error: Duplicate alias"),
                    description=self._(
                        "Tag `{tag}` already has an alias called `{alias}`."
                    ).format(tag=tag.tag_name, alias=alias),
                    color=self.bot.errorColor,
                )
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ " + self._("Error: Invalid tag"),
                description=self._(
                    "You either do not own this tag or it does not exist."
                ),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @tag.command(
        help="Deletes an alias from a tag.",
        description="Removes an alias from a tag, thus making it no longer possible for the tag to be called via that alias.",
        usage="tag delalias <tagname> <alias>",
    )
    @commands.guild_only()
    async def delalias(self, ctx, name, *, alias):
        tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
        if tag and tag.tag_owner_id == ctx.author.id:

            if tag.tag_aliases and alias in tag.tag_aliases:
                aliases = tag.tag_aliases
                aliases.remove(alias)
                # Delete the tag, and recreate it with the new aliases
                await self.tag_handler.delete(tag.tag_name, ctx.guild.id)
                new_tag = Tag(
                    guild_id=ctx.guild.id,
                    tag_name=tag.tag_name,
                    tag_owner_id=tag.tag_owner_id,
                    tag_aliases=aliases,
                    tag_content=tag.tag_content,
                )
                await self.tag_handler.create(new_tag)
                embed = discord.Embed(
                    title="✅ " + self._("Alias deleted"),
                    description=self._(
                        "Alias `{alias}` for tag `{name}` has been deleted."
                    ).format(alias=alias.lower(), name=new_tag.tag_name),
                    color=self.bot.embedGreen,
                )
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ " + self._("Error: Unknown alias"),
                    description=self._(
                        "Tag `{tag}` does not have an alias called `{alias}`."
                    ).format(tag=tag.tag_name, alias=alias),
                    color=self.bot.errorColor,
                )
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ " + self._("Error: Invalid tag"),
                description=self._(
                    "You either do not own this tag or it does not exist."
                ),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @tag.command(
        help="Transfers tag ownership to another user.",
        description="Transfers tag ownership to a specified user, giving them permissions to edit, delete, add/remove aliases, or transfer this tag. User must be a member of the server.",
        usage="tag transfer <tagname> <user>",
    )
    @commands.guild_only()
    async def transfer(self, ctx, name, receiver: discord.Member):
        tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
        if (
            tag
            and tag.tag_owner_id == ctx.author.id
            or tag
            and await has_mod_perms(ctx)
        ):
            await self.tag_handler.delete(tag.tag_name, ctx.guild.id)
            new_tag = Tag(
                guild_id=ctx.guild.id,
                tag_name=tag.tag_name,
                tag_owner_id=receiver.id,
                tag_aliases=tag.tag_aliases,
                tag_content=tag.tag_content,
            )
            await self.tag_handler.create(new_tag)
            embed = discord.Embed(
                title="✅ " + self._("Tag transferred"),
                description=self._(
                    "Tag `{name}`'s ownership was successfully transferred to {receiver}"
                ).format(name=new_tag.tag_name, receiver=receiver.mention),
                color=self.bot.embedGreen,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ " + self._("Error: Invalid tag"),
                description=self._(
                    "You either do not own this tag or it does not exist."
                ),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @tag.command(
        help="Claims a tag that was abandoned.",
        description="Lets you claim a tag that has been created by a user that has since left the server.",
        usage="tag claim <tagname>",
    )
    @commands.guild_only()
    async def claim(self, ctx, *, name):
        tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
        owner = await self.bot.fetch_user(tag.tag_owner_id)
        if tag and owner not in ctx.guild.members:
            await self.tag_handler.delete(tag.tag_name, ctx.guild.id)
            new_tag = Tag(
                guild_id=ctx.guild.id,
                tag_name=tag.tag_name,
                tag_owner_id=ctx.author.id,
                tag_aliases=tag.tag_aliases,
                tag_content=tag.tag_content,
            )
            await self.tag_handler.create(new_tag)
            embed = discord.Embed(
                title="✅ " + self._("Tag claimed"),
                description=self._("Tag `{name}` now belongs to you.").format(
                    name=new_tag.tag_name
                ),
                color=self.bot.embedGreen,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
        elif tag == None:
            embed = discord.Embed(
                title="❌ " + self._("Error: Unknown tag"),
                description=self._("Cannot find tag by that name."),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ " + self._("Error: Not owned"),
                description=self._(
                    "Tag owner is still in the server. You can only claim tags that have been abandoned."
                ),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @tag.command(
        aliases=["modify"],
        help="Edits the contents of a tag.",
        description="Lets you change the content of a tag, without modifying the name or aliases.",
        usage="tag edit <tagname> <new content>",
    )
    @commands.guild_only()
    async def edit(self, ctx, name, *, new_content: str):
        tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
        if tag and tag.tag_owner_id == ctx.author.id:
            await self.tag_handler.delete(tag.tag_name, ctx.guild.id)

            if (
                len(ctx.message.attachments) > 0 and ctx.message.attachments[0]
            ):  # Attachment support for tags
                new_content = f"{new_content}\n{ctx.message.attachments[0].url}"

            new_tag = Tag(
                guild_id=ctx.guild.id,
                tag_name=tag.tag_name,
                tag_owner_id=tag.tag_owner_id,
                tag_aliases=tag.tag_aliases,
                tag_content=new_content,
            )
            await self.tag_handler.create(new_tag)
            embed = discord.Embed(
                title="✅ " + self._("Tag edited"),
                description=self._("Tag `{name}` has been successfully edited.").format(
                    name=new_tag.tag_name
                ),
                color=self.bot.embedGreen,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ " + self._("Error: Invalid tag"),
                description=self._(
                    "You either do not own this tag or it does not exist."
                ),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @tag.command(
        aliases=["del", "remove"],
        help="Deletes a tag.",
        description="Deletes a tag that belongs to you, removing all aliases in the process. After deletion the name & aliases are freed up for other tags to use. Admins may delete any tag regardless of ownership.",
        usage="tag delete <tagname>",
    )
    @commands.guild_only()
    async def delete(self, ctx, *, name):
        tag = await self.tag_handler.get(name.lower(), ctx.guild.id)
        if (
            tag
            and tag.tag_owner_id == ctx.author.id
            or tag
            and await has_mod_perms(ctx)
        ):  # We only allow deletion if the user owns the tag or is a bot admin
            await self.tag_handler.delete(tag.tag_name, ctx.guild.id)
            embed = discord.Embed(
                title="✅ " + self._("Tag deleted"),
                description=self._("Tag `{name}` has been deleted.").format(
                    name=name.lower()
                ),
                color=self.bot.embedGreen,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ " + self._("Error: Tag not owned"),
                description=self._("You cannot delete someone else's tag."),
                color=self.bot.errorColor,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @tag.group(
        name="import",
        help="Imports a tag from a different server.",
        description="Imports a tag from a different server. You must specify the ID of the server you wish to import the tag from.\nUse the `bulk` subcommand to import all tags from a given server.",
        usage="tag import <tag_name> <origin_ID>",
        invoke_without_command=True,
        case_insensitive=True,
    )
    @commands.guild_only()
    @commands.is_owner()
    async def migrate_in(self, ctx, name: str, origin_id: int):
        """
        Move a tag from a specified guild to this guild. In case of conflict, prompts the user to delete the tag.
        """
        await ctx.channel.trigger_typing()
        try:
            await self.tag_handler.migrate(origin_id, ctx.guild.id, ctx.author.id, name)
        except TagNotFound:
            embed = discord.Embed(
                title="❌ " + self._("Error: Tag not found"),
                description=self._(
                    "This tag either does not exist in the origin server, or the bot is not a member of this server."
                ),
                color=self.bot.errorColor,
            )
            await ctx.send(embed=embed)
        except TagAlreadyExists:
            embed = discord.Embed(
                title="❌ " + self._("Error: Tag already exists"),
                description=self._(
                    "This tag already exists on this server. Try running `{prefix}tag delete {name}`"
                ).format(prefix=ctx.prefix, name=name),
                color=self.bot.errorColor,
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="✅ " + self._("Tag imported"),
                description=self._(
                    "Tag `{name}` has been successfully imported from **{guild}**."
                ).format(name=name.lower(), guild=self.bot.get_guild(origin_id).name),
                color=self.bot.embedGreen,
            )
            await ctx.send(embed=embed)

    @migrate_in.command(
        name="bulk",
        help="Tries importing all tags from a different server.",
        description="Tries importing all tags from a different server. You must specify the ID of the server you wish to import the tags from.\nAlso specify the strategy:\n`override` - Override existing tags on this server with imported ones\n`keep` - Keep existing tags in event of a conflict.",
        usage="tag import bulk <origin_ID> <strategy>",
    )
    @commands.guild_only()
    @commands.is_owner()
    async def migrate_in_bulk(self, ctx, origin_id: int, strategy: str = None):
        """
        Tries moving all tags from a specified guild to this guild. Determines what happens in the event of a conflict,
        depending on the strategy selected by the user.
        See strategies in TagHandler.migrate_all() for more.
        """
        if strategy and strategy in ["keep", "override"]:
            try:
                await self.tag_handler.migrate_all(
                    origin_id, ctx.guild.id, ctx.author.id, strategy
                )
            except Exception as error:
                embed = discord.Embed(
                    title="❌ " + self._("Error: Tag import error"),
                    description=self._(
                        "An import error occurred.\n**Error:** ```{error}```"
                    ).format(error=error),
                    color=self.bot.errorColor,
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="✅ " + self._("Tags imported"),
                    description=self._(
                        "All tags have been successfully imported from **{guild}** with strategy **{strategy}**."
                    ).format(
                        guild=self.bot.get_guild(origin_id).name, strategy=strategy
                    ),
                    color=self.bot.embedGreen,
                )
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ " + self._("Error: Invalid import strategy"),
                description=self._(
                    "Your import strategy has not been specified or is invalid.\nYou **must** specify an import strategy in case of a bulk-import."
                ),
                color=self.bot.errorColor,
            )
            await ctx.send(embed=embed)

    @tag.command(
        name="list",
        help="Displays all the tags you can call.",
        description="Shows a list of all available tags in this server.",
        usage="tag list",
    )
    @commands.cooldown(1, 20, type=commands.BucketType.member)
    @commands.guild_only()
    async def list_tags(self, ctx):

        tags = await self.tag_handler.get_all(ctx.guild.id)
        if tags:
            tags_fmt = []
            for i, tag in enumerate(tags):
                tags_fmt.append(f"**#{i+1}** {tag.tag_name}")
            tags_fmt = [
                tags_fmt[i * 10 : (i + 1) * 10]
                for i in range((len(tags_fmt) + 10 - 1) // 10)
            ]
            embed_list = []
            for page_contents in tags_fmt:
                embed = discord.Embed(
                    title="💬 " + self._("Available tags for this server:"),
                    description="\n".join(page_contents),
                    color=ctx.bot.embedBlue,
                )
                embed_list.append(embed)

            menu_paginator = components.SnedMenuPaginator(
                pages=embed_list, show_disabled=True, show_indicator=True
            )
            await menu_paginator.send(ctx, ephemeral=False)
        else:
            embed = discord.Embed(
                title="💬 " + self._("Available tags for this server:"),
                description=self._(
                    "There are currently no tags! You can create one via `{prefix}tag create`"
                ).format(prefix=ctx.prefix),
                color=self.bot.embedBlue,
            )
            await ctx.send(embed=embed)

    @tag.command(
        name="search",
        help="Tries to search for a specified tag.",
        description="Tries searching for a specified tag in the list of this server's tags.",
        usage="tag search <name>",
    )
    @commands.cooldown(1, 10, type=commands.BucketType.member)
    @commands.guild_only()
    async def search_tags(self, ctx, query: str):
        tags = await self.tag_handler.get_all(ctx.guild.id)
        if tags:
            tag_names = [tag.tag_name for tag in tags]
            tag_aliases = []
            for tag in tags:
                if tag.tag_aliases:
                    tag_aliases.append(tag.tag_aliases)
            tag_aliases = list(chain(*tag_aliases))

            name_matches = get_close_matches(query, tag_names)
            alias_matches = get_close_matches(query, tag_aliases)

            response = []
            if len(name_matches) > 0:
                for name in name_matches:
                    response.append(name)
            if len(alias_matches) > 0:
                for name in alias_matches:
                    response.append(f"*{name}*")

            if len(response) > 0:
                if len(response) < 5:
                    response = response[0:5]
                response = " \n".join(response)
                embed = discord.Embed(
                    title="🔎 " + self._("Search results:"),
                    description=f"{response}",
                    color=self.bot.embedBlue,
                )
                embed = self.bot.add_embed_footer(ctx, embed)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="🔎 " + self._("Not found"),
                    description=self._("Unable to find tags with that name.").format(
                        prefix=ctx.prefix
                    ),
                    color=self.bot.errorColor,
                )
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="🔎 " + self._("Search failed"),
                description=self._(
                    "There are currently no tags in this guild. You can create one via `{prefix}tag create`"
                ).format(prefix=ctx.prefix),
                color=self.bot.errorColor,
            )
            await ctx.send(embed=embed)


def setup(bot):
    logger.info("Adding cog: Tags...")
    bot.add_cog(Tags(bot))
