import logging

import discord
from discord.ext import commands


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)


class ReactionRoles(commands.Cog, name="Reaction Roles"):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id:
            records = await self.bot.caching.get(table="reaction_roles", guild_id=payload.guild_id)
            if records:
                for i, msg_id in enumerate(records["reactionrole_msg_id"]):
                    if msg_id == payload.message_id and records["reactionrole_channel_id"][i] == payload.channel_id and records["reactionrole_emoji_id"][i] == payload.emoji.id:
                        guild = self.bot.get_guild(records["guild_id"][i])
                        member = guild.get_member(payload.user_id)
                        if member.bot: return
                        role = guild.get_role(records["reactionrole_role_id"][i])
                        await member.add_roles(role, reason=f"Granted by reaction role (ID: {records['reactionrole_id'][i]}")
                        break #So we do not iterate further pointlessly
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id:
            records = await self.bot.caching.get(table="reaction_roles", guild_id=payload.guild_id)
            if records:
                for i, msg_id in enumerate(records["reactionrole_msg_id"]):
                    if msg_id == payload.message_id and records["reactionrole_channel_id"][i] == payload.channel_id and records["reactionrole_emoji_id"][i] == payload.emoji.id:
                        guild = self.bot.get_guild(records["guild_id"][i])
                        member = guild.get_member(payload.user_id)
                        if member.bot: return
                        role = guild.get_role(records["reactionrole_role_id"][i])
                        await member.remove_roles(role, reason=f"Removed by reaction role (ID: {records['reactionrole_id'][i]})")
                        break
    


    @commands.group(aliases=["rr"], help="Manages reaction roles.", description="Lists all reaction roles set for this guild, if any. Subcommands allow you to remove or set additional ones.", usage="reactionrole", invoke_without_command=True, case_insensitive=True)
    @commands.guild_only()
    @commands.check(has_priviliged)
    async def reactionrole(self, ctx):
        records = await self.bot.caching.get(table="reaction_roles", guild_id=ctx.guild.id)
        if records:
            text = ""
            for i, rr_id in enumerate(records["reactionrole_id"]):
                text = f"{text}**#{rr_id}** - {ctx.guild.get_channel(records['reactionrole_channel_id'][i]).mention} - {ctx.guild.get_role(records['reactionrole_role_id'][i]).mention}\n"
            embed=discord.Embed(title="Reaction Roles for this server:", description=text, color=self.bot.embedBlue)
            await ctx.send(embed=embed)
        else:
            embed=discord.Embed(title="❌ Error: No reaction roles", description="There are no reaction roles for this server.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)


    @reactionrole.command(name="delete", aliases=["del", "remove"], help="Removes a reaction role by ID.", description="Removes a reaction role of the specified ID. You can get the ID via the `reactionrole` command.", usage="reactionrole delete <ID>")
    @commands.guild_only()
    @commands.check(has_priviliged)
    async def rr_delete(self, ctx, id:int):
        async with self.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM reaction_roles WHERE guild_id = $1 AND reactionrole_id = $2''', ctx.guild.id, id)
            record = await self.caching.get(table="reaction_roles", guild_id=ctx.guild.id, reactionrole_id = id)
            if record:
                reactchannel = ctx.guild.get_channel(record['reactionrole_channel_id'][0])
                reactmsg = await reactchannel.fetch_message(record['reactionrole_msg_id'][0])
                try:
                    await reactmsg.remove_reaction(self.bot.get_emoji(record['reactionrole_emoji_id'][0]), ctx.guild.me)
                except discord.NotFound:
                    pass
                await con.execute('''DELETE FROM reaction_roles WHERE guild_id = $1 AND reactionrole_id = $2''', ctx.guild.id, id)
                await self.bot.caching.refresh(table="reaction_roles", guild_id=ctx.guild.id)
                embed=discord.Embed(title="✅ Reaction Role deleted", description="Reaction role has been successfully deleted!", color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)
            else:
                embed=discord.Embed(title="❌ Error: Not found", description="There is no reaction role by that ID.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)


    @reactionrole.command(name="add", aliases=["new", "setup", "create"], help="Initializes setup to add a new reaction role.", description="Initializes a setup to help you add a new reaction role. You can also access this setup via the `setup` command. Takes no arguments.", usage="reactionrole add")
    @commands.guild_only()
    @commands.check(has_priviliged)
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def rr_setup(self, ctx):
        '''
        Here is where end-users would set up a reaction role for their server
        This is not exposed as a command directly, instead it is invoked in setup
        '''
        records = await self.bot.caching.get(table="reaction_roles", guild_id=ctx.guild.id)
        
        if records and len(records["reactionrole_id"]) >= 10:
            embed=discord.Embed(title="❌ Error: Too many reaction roles", description="A server can only have up to **10** reaction roles at a time.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        
        embed=discord.Embed(title="🛠️ Reaction Roles Setup", description="Do you already have an existing message for the role-reaction?", color=self.bot.embedBlue)
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        def confirmcheck(payload):
            return payload.message_id == msg.id and payload.user_id == ctx.author.id
        def idcheck(payload):
            return payload.author == ctx.author and payload.channel.id == ctx.channel.id
        def confirmemoji(reaction, user):
            return reaction.message.id == msg.id and user.id == ctx.author.id

        payload = await self.bot.wait_for('raw_reaction_add', timeout=60.0, check=confirmcheck)

        if str(payload.emoji) == ("✅") :
            try:

                reactchannel = None
                msgcontent = None
                embed=discord.Embed(title="🛠️ Reaction Roles setup", description="Send a channel mention of the channel where the message is located!", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
                payload = await self.bot.wait_for('message', timeout =60.0, check=idcheck)

                reactchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                embed=discord.Embed(title="🛠️ Reaction Roles setup", description=f"Channel set to **{reactchannel.mention}**", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)

                embed=discord.Embed(title="🛠️ Reaction Roles setup", description="Please specify the ID of the message. If you don't know how to get the ID of a message, [follow this link!](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-)", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
                payload = await self.bot.wait_for('message', timeout=60.0, check=idcheck)

                int(payload.content)
                reactmsg = await reactchannel.fetch_message(int(payload.content))
                createmsg = False
                embed=discord.Embed(title="🛠️ Reaction Roles setup", description=f"Reaction message set to the following message in {reactchannel.mention}: \n```{reactmsg.content}```", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)


            except ValueError:
                embed=discord.Embed(title=self.bot.errorDataTitle, description=self.bot.errorDataDesc, color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return

            except commands.ChannelNotFound:
                embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return

            except commands.MessageNotFound:
                embed=discord.Embed(title="❌ Error: Message not found.", description="Unable to locate message. Operation cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return


        elif str(payload.emoji) == ("❌"):
            embed=discord.Embed(title="🛠️ Reaction Role setup", description="Please specify the channel where you want the message to be sent via mentioning the channel.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
            try:
                reactmsg = None
                payload = await self.bot.wait_for('message', timeout =60.0, check=idcheck)

                reactchannel = await commands.TextChannelConverter().convert(ctx, payload.content)
                createmsg = True
                embed=discord.Embed(title="🛠️ Reaction Roles setup", description=f"Channel set to **{reactchannel.mention}**", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
                embed=discord.Embed(title="🛠️ Reaction Roles setup", description="What should the content of the message be?", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)
                payload = await self.bot.wait_for('message', timeout = 60.0, check=idcheck)
                msgcontent = payload.content
                embed=discord.Embed(title="🛠️ Reaction Roles setup", description=f"Message content will be set to the following: \n```{msgcontent}```", color=self.bot.embedBlue)
                await ctx.channel.send(embed=embed)

            except commands.ChannelNotFound:
                embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return
        
        embed=discord.Embed(title="🛠️ Reaction Roles setup", description="React **to this message** with the emoji you want to use!\nNote: Use an  emoji from __this server__, I have no way of accessing emojies outside this server!", color=self.bot.embedBlue)
        msg = await ctx.channel.send(embed=embed)
        reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0,check=confirmemoji)

        reactemoji = reaction.emoji
        embed=discord.Embed(title="🛠️ Reaction Roles setup", description=f"Emoji to be used will be {reactemoji}", color=self.bot.embedBlue)
        msg = await ctx.channel.send(embed=embed)

        embed=discord.Embed(title="🛠️ Reaction Roles setup", description="Provide the name, ID or mention of the role that will be handed out!", color=self.bot.embedBlue)
        await ctx.channel.send(embed=embed)
        message = await self.bot.wait_for('message', timeout=60.0, check=idcheck)
        try:
            reactionrole = await commands.RoleConverter().convert(ctx, message.content)
            embed=discord.Embed(title="🛠️ Reaction Roles setup", description=f"Role set to {reactionrole.mention}", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)

        except commands.RoleNotFound:
            embed=discord.Embed(title="❌ Error: Role not found", description="Unable to locate role. Operation cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return

        if createmsg == True :
            #Create message
            reactmsg = await reactchannel.send(str(msgcontent))
        try:
            reactemoji.id #Test if it is a custom emoji
            await reactmsg.add_reaction(reactemoji)
        except:
            embed=discord.Embed(title="❌ Error: Invalid emoji", description="The emoji specified is not a custom emoji, or is not in this server.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return

        record = await self.bot.caching.get(table="reaction_roles", guild_id=ctx.guild.id, reactionrole_channel_id=reactchannel.id, reactionrole_msg_id=reactmsg.id, reactionrole_emoji_id=reactemoji.id)
        if record:
            embed=discord.Embed(title="❌ Error: Duplicate", description=f"This role reaction already exists. Please remove it first via `{ctx.prefix}rolereaction delete <ID>`", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        async with self.bot.pool.acquire() as con:
            await con.execute('''
            INSERT INTO reaction_roles (guild_id, reactionrole_channel_id, reactionrole_msg_id, reactionrole_emoji_id, reactionrole_role_id)
            VALUES ($1, $2, $3, $4, $5)
            ''', ctx.guild.id, reactchannel.id, reactmsg.id, reactemoji.id, reactionrole.id)
        await self.bot.caching.refresh(table="reaction_roles", guild_id=ctx.guild.id)

        embed=discord.Embed(title="🛠️ Reaction Roles setup", description="✅ Setup completed. Reaction role set up!", color=self.bot.embedGreen)
        await ctx.channel.send(embed=embed)

        embed=discord.Embed(title="❇️ Reaction Role added", description=f"A reaction role for role {reactionrole.mention} has been created by {ctx.author.mention} in channel {reactchannel.mention}.\n__Note:__ Anyone who can see this channel can now obtain this role!", color=self.bot.embedGreen)
        try:
            await self.bot.get_cog('Logging').log_elevated(embed, ctx.guild.id)
        except AttributeError:
            pass
        


def setup(bot):
    logging.info("Adding cog: ReactionRoles...")
    bot.add_cog(ReactionRoles(bot))
