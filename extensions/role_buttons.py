import asyncio
import logging

import discord
from discord.ext import commands, pages
from classes.bot import SnedBot
from typing import List

from classes import components


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)


async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)


logger = logging.getLogger(__name__)


class PersistentRoleView(discord.ui.View):
    def __init__(self, buttons: List[discord.ui.Button] = None):
        super().__init__(timeout=None)
        if buttons:
            for button in buttons:
                self.add_item(button)


class ButtonRoleButton(discord.ui.Button):
    def __init__(
        self,
        entry_id: int,
        role: discord.Role,
        emoji: discord.PartialEmoji,
        style: discord.ButtonStyle,
        label: str = None,
    ):
        super().__init__(style=style, label=label, emoji=emoji, custom_id=f"{entry_id}:{role.id}")
        self.entry_id = entry_id
        self.role = role

    # Called whenever the button is called
    async def callback(self, interaction: discord.Interaction):
        if interaction.guild_id:
            try:
                if self.role in interaction.user.roles:
                    await interaction.user.remove_roles(
                        self.role,
                        reason=f"Removed by role-button (ID: {self.entry_id})",
                    )
                    embed = discord.Embed(
                        title="✅ Role removed",
                        description=f"Removed role: {self.role.mention}",
                        color=0x77B255,
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.user.add_roles(
                        self.role,
                        reason=f"Granted by role-button (ID: {self.entry_id})",
                    )
                    embed = discord.Embed(
                        title="✅ Role added",
                        description=f"Added role: {self.role.mention}",
                        color=0x77B255,
                    )
                    embed.set_footer(text="If you would like it removed, click the button again!")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌ Insufficient permissions",
                    description="Failed adding role due to an issue with permissions and/or role hierarchy! Please contact an administrator!",
                    color=0xFF0000,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)


class RoleButtons(commands.Cog, name="Role-Buttons"):
    """
    Create and manage buttons that hand out roles to users.
    Formerly "reaction roles"
    """

    def __init__(self, bot: SnedBot):
        self.bot = bot
        self.button_styles = {
            "Blurple": discord.ButtonStyle.primary,
            "Grey": discord.ButtonStyle.secondary,
            "Green": discord.ButtonStyle.success,
            "Red": discord.ButtonStyle.danger,
        }

    async def cog_check(self, ctx):
        return await ctx.bot.custom_checks.has_permissions(ctx, "role_buttons")

    @commands.Cog.listener()
    async def on_ready(self):
        # READY clears state, including persistent views
        # Thus views must be re-added
        await self.buttonroles_init()

    async def buttonroles_init(self):
        """Re-acquire all persistent buttons"""
        await self.bot.wait_until_ready()
        logger.info("Adding persistent views to button roles...")
        records = await self.bot.pool.fetch(
            """
        SELECT 
        guild_id, 
        entry_id, 
        msg_id, 
        role_id, 
        emoji, 
        buttonlabel, 
        buttonstyle 
        FROM button_roles"""
        )

        add_to_persistent_views = {}

        for record in records:
            guild = self.bot.get_guild(record.get("guild_id"))
            emoji = discord.PartialEmoji.from_str(record.get("emoji"))
            button = ButtonRoleButton(
                record.get("entry_id"),
                guild.get_role(record.get("role_id")),
                label=record.get("buttonlabel"),
                style=self.button_styles[record.get("buttonstyle")],
                emoji=emoji,
            )
            if record.get("msg_id") not in add_to_persistent_views.keys():
                add_to_persistent_views[record.get("msg_id")] = [button]
            else:
                add_to_persistent_views[record.get("msg_id")].append(button)

        for msg_id, buttons in add_to_persistent_views.items():
            self.bot.add_view(PersistentRoleView(buttons), message_id=msg_id)

        logger.info("Button roles ready!")

    @commands.group(
        aliases=["rr", "rb", "reactionrole", "rolebuttons"],
        help="Manages role-buttons. See subcommands for more.",
        description="Lists all button roles set for this guild, if any. Subcommands allow you to remove or set additional ones.",
        usage="buttonrole",
        invoke_without_command=True,
        case_insensitive=True,
    )
    @commands.guild_only()
    async def rolebutton(self, ctx):

        records = await self.bot.caching.get(table="button_roles", guild_id=ctx.guild.id)
        if records:
            paginator = commands.Paginator(prefix="", suffix="", max_size=500)
            for record in records:
                paginator.add_line(
                    f"**#{record['entry_id']}** - {ctx.guild.get_channel(record['channel_id']).mention} - {ctx.guild.get_role(record['role_id']).mention}"
                )
            embed_list = []
            for page in paginator.pages:
                embed = discord.Embed(
                    title="Rolebuttons on this server:",
                    description=page,
                    color=self.bot.embed_blue,
                )
                embed_list.append(embed)

            menu_paginator = components.SnedMenuPaginator(pages=embed_list, show_disabled=True, show_indicator=True)
            await menu_paginator.send(ctx)
        else:
            embed = discord.Embed(
                title="❌ Error: No role-buttons",
                description="There are no role-buttons for this server.",
                color=self.bot.error_color,
            )
            await ctx.channel.send(embed=embed)

    @rolebutton.command(
        name="delete",
        aliases=["del", "remove"],
        help="Removes a role-button by ID.",
        description="Removes a role-button of the specified ID. You can get the ID via the `rolebutton` command.",
        usage="rolebutton delete <ID>",
    )
    @commands.guild_only()
    async def rb_delete(self, ctx, id: int):
        records = await self.bot.caching.get(table="button_roles", guild_id=ctx.guild.id, entry_id=id)

        if records:  # Button cleanup

            await self.bot.pool.execute(
                """DELETE FROM button_roles WHERE guild_id = $1 AND entry_id = $2""",
                ctx.guild.id,
                id,
            )
            await self.bot.caching.refresh(table="button_roles", guild_id=ctx.guild.id)

            channel = ctx.guild.get_channel(records[0]["channel_id"])
            message = await channel.fetch_message(records[0]["msg_id"]) if channel else None
            if message:  # Re-sync buttons if message still exists
                records = await self.bot.caching.get(table="button_roles", guild_id=ctx.guild.id, msg_id=message.id)
                buttons = []
                if records:
                    for record in records:
                        emoji = discord.PartialEmoji.from_str(record.get("emoji"))
                        buttons.append(
                            ButtonRoleButton(
                                record.get("entry_id"),
                                ctx.guild.get_role(record.get("role_id")),
                                label=record.get("buttonlabel"),
                                style=self.button_styles[record.get("buttonstyle")],
                                emoji=emoji,
                            )
                        )
                    view = PersistentRoleView(buttons) if len(buttons) > 0 else None
                else:
                    view = None

                try:
                    await message.edit(view=view)
                except discord.NotFound:
                    pass

            embed = discord.Embed(
                title="✅ Role-Button deleted",
                description="Role-Button has been successfully deleted!",
                color=self.bot.embed_green,
            )
            await ctx.channel.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Error: Not found",
                description="There is no role-button by that ID.",
                color=self.bot.error_color,
            )
            await ctx.channel.send(embed=embed)

    @rolebutton.command(
        name="add",
        aliases=["new", "setup", "create"],
        help="Initializes setup to add a new role-button.",
        description="Initializes a setup to help you add a new role-button. Takes no arguments.",
        usage="reactionrole add",
    )
    @commands.guild_only()
    @commands.max_concurrency(1, per=commands.BucketType.guild, wait=False)
    @commands.bot_has_permissions(manage_roles=True)
    async def rb_setup(self, ctx):
        """
        Here is where end-users would set up a button role for their server
        """

        records = await self.bot.caching.get(table="button_roles", guild_id=ctx.guild.id)

        if records and len(records) >= 200:
            embed = discord.Embed(
                title="❌ Error: Too many role-buttons",
                description="A server can only have up to **200** role-buttons at a time.",
                color=self.bot.error_color,
            )
            await ctx.channel.send(embed=embed)
            return

        embed = discord.Embed(
            title="🛠️ Role-Buttons Setup",
            description="Do you already have an existing message for the role-button?\nPlease note that the message must be a message from the bot.",
            color=self.bot.embed_blue,
        )
        has_msg = await ctx.confirm(embed=embed, delete_after=True)

        def idcheck(payload):
            return payload.author == ctx.author and payload.channel.id == ctx.channel.id

        def confirmemoji(reaction, user):
            return reaction.message.id == setup_msg.id and user.id == ctx.author.id

        if has_msg == False:

            options = []
            for channel in ctx.guild.channels:
                if channel.type in [discord.ChannelType.text, discord.ChannelType.news]:
                    options.append(discord.SelectOption(label=f"#{channel.name}", value=channel.id))

            embed = discord.Embed(
                title="🛠️ Role-Buttons setup",
                description="Please specify the channel where you want the message to be sent!",
                color=self.bot.embed_blue,
            )
            value, asked, setup_msg = await components.select_or_ask(
                ctx, options=options, placeholder="Select a channel", embed=embed
            )

            if value and not asked:
                reactchannel = ctx.guild.get_channel(int(value["values"][0]))
            elif value and asked:
                try:
                    reactchannel = await commands.GuildChannelConverter().convert(ctx, value)
                    if reactchannel.type not in [
                        discord.ChannelType.news,
                        discord.ChannelType.text,
                    ]:
                        embed = discord.Embed(
                            title="❌ Error: Invalid channel",
                            description="Channel must be of type `text` or `news`. Operation cancelled.",
                            color=self.bot.error_color,
                        )
                        await setup_msg.edit(embed=embed)
                        return
                except commands.ChannelNotFound:
                    embed = discord.Embed(
                        title="❌ Error: Channel not found.",
                        description="Unable to locate channel. Operation cancelled.",
                        color=self.bot.error_color,
                    )
                    await setup_msg.edit(embed=embed)
                    return

            else:
                raise asyncio.exceptions.TimeoutError

            reactmsg = None
            embed = discord.Embed(
                title="🛠️ Role-Buttons setup",
                description="What should the content of the message be? Type it below!",
                color=self.bot.embed_blue,
            )
            await setup_msg.edit(embed=embed, view=None)
            message = await self.bot.wait_for("message", timeout=60.0, check=idcheck)
            msgcontent = message.content
            await message.delete()

        elif has_msg == True:
            try:

                options = []
                for channel in ctx.guild.channels:
                    if channel.type in [
                        discord.ChannelType.text,
                        discord.ChannelType.news,
                    ]:
                        options.append(discord.SelectOption(label=f"#{channel.name}", value=channel.id))

                embed = discord.Embed(
                    title="🛠️ Role-Buttons setup",
                    description="Please specify the channel where the message is located!",
                    color=self.bot.embed_blue,
                )
                value, asked, setup_msg = await components.select_or_ask(
                    ctx, options=options, placeholder="Select a channel", embed=embed
                )

                if value and not asked:
                    reactchannel = ctx.guild.get_channel(int(value["values"][0]))
                elif value and asked:
                    try:
                        reactchannel = await commands.GuildChannelConverter().convert(ctx, value)
                        if reactchannel.type not in [
                            discord.ChannelType.news,
                            discord.ChannelType.text,
                        ]:
                            embed = discord.Embed(
                                title="❌ Error: Invalid channel",
                                description="Channel must be of type `text` or `news`. Operation cancelled.",
                                color=self.bot.error_color,
                            )
                            await setup_msg.edit(embed=embed)
                            return
                    except commands.ChannelNotFound:
                        embed = discord.Embed(
                            title="❌ Error: Channel not found.",
                            description="Unable to locate channel. Operation cancelled.",
                            color=self.bot.error_color,
                        )
                        await ctx.channel.send(embed=embed)
                        return

                else:
                    raise asyncio.exceptions.TimeoutError

                msgcontent = None
                embed = discord.Embed(
                    title="🛠️ Role-Buttons setup",
                    description="Please specify the ID of the message. If you don't know how to get the ID of a message, [follow this link!](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-)",
                    color=self.bot.embed_blue,
                )
                await setup_msg.edit(embed=embed, view=None)
                message = await self.bot.wait_for("message", timeout=60.0, check=idcheck)
                await message.delete()

                reactmsg = await reactchannel.fetch_message(int(message.content))
                if reactmsg.author != self.bot.user:
                    embed = discord.Embed(
                        title="❌ Error: Message not by bot",
                        description="The message **must** be a message posted previously by the bot. Operation cancelled.",
                        color=self.bot.error_color,
                    )
                    await setup_msg.edit(embed=embed)
                    return
                elif len(reactmsg.components) > 10:
                    embed = discord.Embed(
                        title="❌ Error: Too many components",
                        description="This message has too many components. Please try reducing the number of buttons. Operation cancelled.",
                        color=self.bot.error_color,
                    )
                    await setup_msg.edit(embed=embed)
                    return

            except ValueError:
                embed = discord.Embed(
                    title="❌ Error: Invalid data entered",
                    description="Operation cancelled.",
                    color=self.bot.error_color,
                )
                await ctx.channel.send(embed=embed)
                return

            except discord.NotFound:
                embed = discord.Embed(
                    title="❌ Error: Message not found.",
                    description="Unable to locate message. Operation cancelled.",
                    color=self.bot.error_color,
                )
                await setup_msg.edit(embed=embed)
                return

        else:
            raise asyncio.exceptions.TimeoutError

        embed = discord.Embed(
            title="🛠️ Role-Buttons setup",
            description="React **to this message** with the emoji you want to appear on the button! This can be any emoji, be it custom or Discord default!",
            color=self.bot.embed_blue,
        )
        await setup_msg.edit(embed=embed)
        reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=confirmemoji)

        reactemoji = reaction.emoji
        await setup_msg.clear_reactions()

        embed = discord.Embed(
            title="🛠️ Role-Buttons setup",
            description="What text should be printed on the button? Type it below! Type `skip` to leave it empty.",
            color=self.bot.embed_blue,
        )
        await setup_msg.edit(embed=embed)
        message = await self.bot.wait_for("message", timeout=60.0, check=idcheck)
        label = message.content if message.content != "skip" else None
        await message.delete()

        role_options = []
        for role in ctx.guild.roles:
            if role.name != "@everyone" and role < ctx.guild.me.top_role:
                role_options.append(discord.SelectOption(label=role.name, value=role.id))
        if len(role_options) == 0:
            embed = discord.Embed(
                title="❌ Error: No valid roles",
                description="There are no roles the bot could assign. Try changing the role hierarchy.",
                color=self.bot.error_color,
            )
            await ctx.channel.send(embed=embed)
            return

        embed = discord.Embed(
            title="🛠️ Role-Buttons setup",
            description="Select the role that will be handed out!",
            color=self.bot.embed_blue,
        )
        value, asked = await components.select_or_ask(
            ctx,
            options=role_options,
            placeholder="Select a role!",
            embed=embed,
            message_to_edit=setup_msg,
        )
        if value and not asked:
            reactionrole = ctx.guild.get_role(int(value["values"][0]))
        elif value and asked:
            try:
                reactionrole = await commands.RoleConverter().convert(ctx, value)
                if reactionrole.name == "@everyone":
                    raise commands.RoleNotFound
            except commands.RoleNotFound:
                embed = discord.Embed(
                    title="❌ Error: Role not found",
                    description="Unable to locate role. Operation cancelled.",
                    color=self.bot.error_color,
                )
                await ctx.channel.send(embed=embed)
                return
        else:
            raise asyncio.exceptions.TimeoutError

        view = discord.ui.View()
        options = []
        for name in self.button_styles.keys():
            options.append(discord.SelectOption(label=name))
        view.add_item(components.CustomSelect(placeholder="Select a style!", options=options))
        embed = discord.Embed(
            title="🛠️ Role-Buttons setup",
            description="Select the style of the button!",
            color=self.bot.embed_blue,
        )
        await setup_msg.edit(embed=embed, view=view)
        await view.wait()
        if view.value:
            buttonstyle = view.value["values"][0]
        else:
            raise asyncio.exceptions.TimeoutError
        # entry_id is assigned manually because the button needs it before it is in the db
        record = await self.bot.pool.fetch("""SELECT entry_id FROM button_roles ORDER BY entry_id DESC LIMIT 1""")
        entry_id = record[0].get("entry_id") + 1 if record and record[0] else 1  # Calculate the entry id

        button = ButtonRoleButton(
            entry_id=entry_id,
            role=reactionrole,
            label=label,
            emoji=reactemoji,
            style=self.button_styles[buttonstyle],
        )
        try:
            if has_msg == False:
                # Create message
                view = PersistentRoleView([button])
                reactmsg = await reactchannel.send(str(msgcontent), view=view)
            else:
                if reactmsg.components:
                    # Reconstruct all buttons from db to keep them working
                    embed = discord.Embed(
                        title="⚠️ Role-Buttons Setup",
                        description="This message already has buttons or other components attached. Any components that are not role-buttons will be **removed** from this message. (e.g. components from other bots) If you are trying to add multiple role-buttons to this message, ignore this warning.\n\n**Are you sure you want to proceed?**",
                        color=self.bot.warn_color,
                    )
                    ignore_warning = await ctx.confirm(embed=embed, delete_after=True)
                    if ignore_warning:
                        records = await self.bot.caching.get(
                            table="button_roles",
                            guild_id=ctx.guild.id,
                            msg_id=reactmsg.id,
                        )
                        buttons = []
                        if records:
                            for record in records:
                                emoji = discord.PartialEmoji.from_str(record.get("emoji"))
                                buttons.append(
                                    ButtonRoleButton(
                                        record.get("entry_id"),
                                        ctx.guild.get_role(record.get("role_id")),
                                        label=record.get("buttonlabel"),
                                        style=self.button_styles[record.get("buttonstyle")],
                                        emoji=emoji,
                                    )
                                )

                        buttons.append(button)
                        view = PersistentRoleView(buttons)
                    else:
                        return
                else:
                    view = PersistentRoleView([button])
                await reactmsg.edit(view=view)
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Error: No permissions",
                description="The bot has no permissions to create the message. Please check if the bot can send and edit messages in the specified channel. Operation cancelled.",
                color=self.bot.error_color,
            )
            await setup_msg.edit(embed=embed, view=None)
            return

        await self.bot.pool.execute(
            """
        INSERT INTO button_roles (entry_id, guild_id, channel_id, msg_id, emoji, buttonlabel, buttonstyle, role_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
            entry_id,
            ctx.guild.id,
            reactchannel.id,
            reactmsg.id,
            str(reactemoji),
            label,
            buttonstyle,
            reactionrole.id,
        )
        await self.bot.caching.refresh(table="button_roles", guild_id=ctx.guild.id)

        embed = discord.Embed(
            title="🛠️ Role-Buttons setup",
            description="✅ Setup completed. Role-Button set up!",
            color=self.bot.embed_green,
        )
        await setup_msg.edit(embed=embed, view=None)

        embed = discord.Embed(
            title="❇️ Role-Button was added",
            description=f"A role-button for role {reactionrole.mention} has been created by {ctx.author.mention} in channel {reactchannel.mention}.\n__Note:__ Anyone who can see this channel can now obtain this role!",
            color=self.bot.embed_green,
        )
        try:
            await self.bot.get_cog("Logging").log("roles", embed, ctx.guild.id)
        except AttributeError:
            pass


def setup(bot: SnedBot):
    logger.info("Adding cog: Role Buttons...")
    bot.add_cog(RoleButtons(bot))
