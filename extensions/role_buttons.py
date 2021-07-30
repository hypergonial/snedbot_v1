import asyncio
import logging

import discord
from discord.ext import commands
from extensions.utils import components


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)


class PersistentRoleView(discord.ui.View):
    def __init__(self, buttons:list=None):
        super().__init__(timeout=None)
        if buttons:
            for button in buttons:
                self.add_item(button)

class ButtonRoleButton(discord.ui.Button):
    def __init__(self, entry_id:int, role:discord.Role, emoji:discord.PartialEmoji, style:discord.ButtonStyle, label:str=None):
        super().__init__(style=style, label=label, emoji=emoji, custom_id=f"{entry_id}:{role.id}")
        self.entry_id = entry_id
        self.role = role
    
    #Called whenever the button is called
    async def callback(self, interaction: discord.Interaction):
        if interaction.guild_id:
            if self.role in interaction.user.roles:
                await interaction.user.remove_roles(self.role, reason=f"Removed by role-button (ID: {self.entry_id}")
                await interaction.response.send_message(f'Removed role: {self.role.mention}', ephemeral=True)
            else:
                await interaction.user.add_roles(self.role, reason=f"Granted by role-button (ID: {self.entry_id}")
                await interaction.response.send_message(f'Added role: {self.role.mention}', ephemeral=True)

class RoleButtons(commands.Cog, name="Role-Buttons"):
    '''
    Create and manage buttons that hand out roles to users.
    Formerly "reaction roles"
    '''
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.buttonroles_init())
        self.button_styles = {
            "Blurple": discord.ButtonStyle.primary,
            "Grey": discord.ButtonStyle.secondary,
            "Green": discord.ButtonStyle.success,
            "Red": discord.ButtonStyle.danger
        }


    async def buttonroles_init(self):
        '''Re-acquire all persistent buttons'''
        await self.bot.wait_until_ready()
        logging.info("Adding persistent views to button roles...")
        async with self.bot.pool.acquire() as con:
            records = await con.fetch('''
            SELECT 
            guild_id, 
            entry_id, 
            msg_id, 
            role_id, 
            emoji, 
            buttonlabel, 
            buttonstyle 
            FROM button_roles''')

            add_to_persistent_views = {}

        for record in records:
            guild = self.bot.get_guild(record.get('guild_id'))
            emoji = discord.PartialEmoji.from_str(record.get('emoji'))
            button = ButtonRoleButton(record.get('entry_id'), guild.get_role(record.get('role_id')), label=record.get('buttonlabel'), style=self.button_styles[record.get('buttonstyle')], emoji=emoji)
            if record.get('msg_id') not in add_to_persistent_views.keys():
                add_to_persistent_views[record.get('msg_id')] = [button]
            else:
                add_to_persistent_views[record.get('msg_id')].append(button)
                
        for msg_id, buttons in add_to_persistent_views.items():
            self.bot.add_view(PersistentRoleView(buttons), message_id=msg_id)

        logging.info('Button roles ready!')

    @commands.group(aliases=["rr", "rb", "reactionrole"], help="Manages role-buttons. See subcommands for more.", description="Lists all button roles set for this guild, if any. Subcommands allow you to remove or set additional ones.", usage="buttonrole", invoke_without_command=True, case_insensitive=True)
    @commands.guild_only()
    @commands.check(has_priviliged)
    async def rolebutton(self, ctx):
        records = await self.bot.caching.get(table="button_roles", guild_id=ctx.guild.id)
        if records:
            text = ""
            for i, rr_id in enumerate(records["entry_id"]):
                text = f"{text}**#{rr_id}** - {ctx.guild.get_channel(records['channel_id'][i]).mention} - {ctx.guild.get_role(records['role_id'][i]).mention}\n"
            embed=discord.Embed(title="Role-Buttons for this server:", description=text, color=self.bot.embedBlue)
            await ctx.send(embed=embed)
        else:
            embed=discord.Embed(title="❌ Error: No role-buttons", description="There are no role-buttons for this server.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)


    @rolebutton.command(name="delete", aliases=["del", "remove"], help="Removes a role-button by ID.", description="Removes a role-button of the specified ID. You can get the ID via the `rolebutton` command.", usage="rolebutton delete <ID>")
    @commands.guild_only()
    @commands.check(has_priviliged)
    async def rb_delete(self, ctx, id:int):
            record = await self.bot.caching.get(table="button_roles", guild_id=ctx.guild.id, entry_id = id)
            if record:
                channel = ctx.guild.get_channel(record['channel_id'][0])
                message = await channel.fetch_message(record['msg_id'][0]) if channel else None
                if message: #Remove button if the message still exists
                    view = discord.ui.View.from_message(message)
                    for item in view.children:
                        if item.custom_id == f"{record['entry_id'][0]}:{record['role_id'][0]}":
                            remove_me = item; break
                    view.remove_item(remove_me)
                    await message.edit(view=view)

                async with self.bot.pool.acquire() as con:
                    await con.execute('''DELETE FROM button_roles WHERE guild_id = $1 AND entry_id = $2''', ctx.guild.id, id)
                    await self.bot.caching.refresh(table="button_roles", guild_id=ctx.guild.id)
                    embed=discord.Embed(title="✅ Role-Button deleted", description="Role-Button has been successfully deleted!", color=self.bot.embedGreen)
                    await ctx.channel.send(embed=embed)
            else:
                embed=discord.Embed(title="❌ Error: Not found", description="There is no role-button by that ID.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)


    @rolebutton.command(name="add", aliases=["new", "setup", "create"], help="Initializes setup to add a new role-button.", description="Initializes a setup to help you add a new role-button. You can also access this setup via the `setup` command. Takes no arguments.", usage="reactionrole add")
    @commands.guild_only()
    @commands.check(has_priviliged)
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def rb_setup(self, ctx):
        '''
        Here is where end-users would set up a button role for their server
        '''
        records = await self.bot.caching.get(table="button_roles", guild_id=ctx.guild.id)
        
        if records and len(records["entry_id"]) >= 200:
            embed=discord.Embed(title="❌ Error: Too many role-buttons", description="A server can only have up to **200** role-buttons at a time.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        

        embed=discord.Embed(title="🛠️ Role-Buttons Setup", description="Do you already have an existing message for the role-button?\nPlease note that the message must be a message from the bot.", color=self.bot.embedBlue)
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

            
            embed=discord.Embed(title="🛠️ Role-Buttons setup", description="Please specify the channel where you want the message to be sent!", color=self.bot.embedBlue)
            value, asked, setup_msg = await components.select_or_ask(ctx, options=options, placeholder="Select a channel", embed=embed)
            
            if value and not asked:
                reactchannel = ctx.guild.get_channel(int(value["values"][0]))
            elif value and asked:
                try:
                    reactchannel = await commands.GuildChannelConverter().convert(ctx, value)
                    if reactchannel.type not in [discord.ChannelType.news, discord.ChannelType.text]:
                        embed=discord.Embed(title="❌ Error: Invalid channel", description="Channel must be of type `text` or `news`. Operation cancelled.", color=self.bot.errorColor)
                        await setup_msg.edit(embed=embed); return
                except commands.ChannelNotFound:
                    embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
                    await setup_msg.edit(embed=embed);  return          
            
            else:
                raise asyncio.exceptions.TimeoutError

            reactmsg = None
            embed=discord.Embed(title="🛠️ Role-Buttons setup", description="What should the content of the message be? Type it below!", color=self.bot.embedBlue)
            await setup_msg.edit(embed=embed, view=None)
            message = await self.bot.wait_for('message', timeout = 60.0, check=idcheck)
            msgcontent = message.content
            await message.delete()


        elif has_msg == True:
            try:

                options = []
                for channel in ctx.guild.channels:
                    if channel.type in [discord.ChannelType.text, discord.ChannelType.news]:
                        options.append(discord.SelectOption(label=f"#{channel.name}", value=channel.id))

                embed=discord.Embed(title="🛠️ Role-Buttons setup", description="Please specify the channel where the message is located!", color=self.bot.embedBlue)
                value, asked, setup_msg = await components.select_or_ask(ctx, options=options, placeholder="Select a channel", embed=embed)
                
                if value and not asked:
                    reactchannel = ctx.guild.get_channel(int(value["values"][0]))
                elif value and asked:
                    try:
                        reactchannel = await commands.GuildChannelConverter().convert(ctx, value)
                        if reactchannel.type not in [discord.ChannelType.news, discord.ChannelType.text]:
                            embed=discord.Embed(title="❌ Error: Invalid channel", description="Channel must be of type `text` or `news`. Operation cancelled.", color=self.bot.errorColor)
                            await setup_msg.edit(embed=embed); return
                    except commands.ChannelNotFound:
                        embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
                        await ctx.channel.send(embed=embed);  return          
                
                else:
                    raise asyncio.exceptions.TimeoutError

                msgcontent = None
                embed=discord.Embed(title="🛠️ Role-Buttons setup", description="Please specify the ID of the message. If you don't know how to get the ID of a message, [follow this link!](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-)", color=self.bot.embedBlue)
                await setup_msg.edit(embed=embed, view=None)
                message = await self.bot.wait_for('message', timeout=60.0, check=idcheck)
                await message.delete()

                reactmsg = await reactchannel.fetch_message(int(message.content))
                if reactmsg.author != self.bot.user:
                    embed=discord.Embed(title="❌ Error: Message not by bot", description="The message **must** be a message posted previously by the bot. Operation cancelled.", color=self.bot.errorColor)
                    await setup_msg.edit(embed=embed); return
                elif len(reactmsg.components) > 10:
                    embed=discord.Embed(title="❌ Error: Too many components", description="This message has too many components. Please try reducing the number of buttons. Operation cancelled.", color=self.bot.errorColor)
                    await setup_msg.edit(embed=embed); return

            except ValueError:
                embed=discord.Embed(title=self.bot.errorDataTitle, description=self.bot.errorDataDesc, color=self.bot.errorColor)
                await ctx.channel.send(embed=embed); return

            except discord.errors.NotFound:
                embed=discord.Embed(title="❌ Error: Message not found.", description="Unable to locate message. Operation cancelled.", color=self.bot.errorColor)
                await setup_msg.edit(embed=embed); return

        else:
            raise asyncio.exceptions.TimeoutError
        
        embed=discord.Embed(title="🛠️ Role-Buttons setup", description="React **to this message** with the emoji you want to appear on the button! This can be any emoji, be it custom or Discord default!", color=self.bot.embedBlue)
        await setup_msg.edit(embed=embed)
        reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0,check=confirmemoji)

        reactemoji = reaction.emoji
        await setup_msg.clear_reactions()

        embed=discord.Embed(title="🛠️ Role-Buttons setup", description="What text should be printed on the button? Type it below! Type `skip` to leave it empty.", color=self.bot.embedBlue)
        await setup_msg.edit(embed=embed)
        message = await self.bot.wait_for('message', timeout = 60.0, check=idcheck)
        label = message.content if message.content != "skip" else None
        await message.delete()

        role_options = []
        for role in ctx.guild.roles:
            if role.name != "@everyone":
                role_options.append(discord.SelectOption(label=role.name, value=role.id))

        embed=discord.Embed(title="🛠️ Role-Buttons setup", description="Select the role that will be handed out!", color=self.bot.embedBlue)
        value, asked = await components.select_or_ask(ctx, options=role_options, placeholder="Select a role!", embed=embed, message_to_edit=setup_msg)
        if value and not asked:
            reactionrole = ctx.guild.get_role(int(value["values"][0]))
        elif value and asked:
            try:
                reactionrole = await commands.RoleConverter().convert(ctx, value)
                if reactionrole.name == "@everyone":
                    raise commands.RoleNotFound
            except commands.RoleNotFound:
                embed=discord.Embed(title="❌ Error: Role not found", description="Unable to locate role. Operation cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed); return
        else:
            raise asyncio.exceptions.TimeoutError

        view = discord.ui.View()
        options = []
        for name in self.button_styles.keys():
            options.append(discord.SelectOption(label=name))
        view.add_item(components.CustomSelect(placeholder="Select a style!", options=options))
        embed=discord.Embed(title="🛠️ Role-Buttons setup", description="Select the style of the button!", color=self.bot.embedBlue)
        await setup_msg.edit(embed=embed, view=view)
        await view.wait()
        if view.value:
            buttonstyle = view.value["values"][0]
        else:
            raise asyncio.exceptions.TimeoutError
        #entry_id is assigned manually because the button needs it before it is in the db
        async with self.bot.pool.acquire() as con: 
            record = await con.fetch('''SELECT entry_id FROM button_roles ORDER BY entry_id DESC LIMIT 1''')
        entry_id = record[0].get('entry_id')+1 if record and record[0] else 1 #Calculate the entry id

        button = ButtonRoleButton(entry_id=entry_id, role=reactionrole, label=label, emoji=reactemoji, style=self.button_styles[buttonstyle])
        if has_msg == False :
            #Create message
            view = PersistentRoleView([button])
            reactmsg = await reactchannel.send(str(msgcontent), view=view)
        else:
            if reactmsg.components:
                view = discord.ui.View.from_message(reactmsg, timeout=None)
                view.add_item(button)
            else:
                view = PersistentRoleView([button])
            await reactmsg.edit(view=view)

        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO button_roles (entry_id, guild_id, channel_id, msg_id, emoji, buttonlabel, buttonstyle, role_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ''',entry_id, ctx.guild.id, reactchannel.id, reactmsg.id, str(reactemoji), label, buttonstyle, reactionrole.id)
        await self.bot.caching.refresh(table="button_roles", guild_id=ctx.guild.id)

        embed=discord.Embed(title="🛠️ Role-Buttons setup", description="✅ Setup completed. Role-Button set up!", color=self.bot.embedGreen)
        await setup_msg.edit(embed=embed, view=None)

        embed=discord.Embed(title="❇️ Role-Button was added", description=f"A role-button for role {reactionrole.mention} has been created by {ctx.author.mention} in channel {reactchannel.mention}.\n__Note:__ Anyone who can see this channel can now obtain this role!", color=self.bot.embedGreen)
        try:
            await self.bot.get_cog('Logging').log_elevated(embed, ctx.guild.id)
        except AttributeError:
            pass
        


def setup(bot):
    logging.info("Adding cog: Role Buttons...")
    bot.add_cog(RoleButtons(bot))
