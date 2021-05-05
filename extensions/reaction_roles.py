import logging

import discord
from discord.ext import commands


async def hasOwner(ctx):
    return await ctx.bot.CommandChecks.hasOwner(ctx)
async def hasPriviliged(ctx):
    return await ctx.bot.CommandChecks.hasPriviliged(ctx)


class ReactionRoles(commands.Cog, name="Reaction Roles"):
    def __init__(self, bot):
        self.bot = bot


    async def check_rr(self, payload):
        '''
        Checks if the reaction was added to a message in the RR cache or not,
        falls back to the database if no cache entry for the guild was found.
        Returns the reaction role and the member who reacted
        '''
        #WIP TBD
        if payload.guild_id in self.bot.cache['rr'][payload.guild_id]:
            pass
        else:
            async with self.bot.pool.acquire() as con:
                results = await con.fetch('''SELECT * FROM reaction_roles WHERE guild_id = $1''', payload.guild_id)
                for result in results:
                    if result.get('reactionrole_msg_id') == payload.message_id and result.get('reactionrole_channel_id') == payload.channel_id and result.get('reactionrole_emoji_id') == payload.emoji.id:
                        guild = self.bot.get_guild(result.get('guild_id'))
                        member = guild.get_member(payload.user_id)
                        if not member.bot:
                            role = guild.get_role(result.get('reactionrole_role_id'))
                            return member, role




    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id:
            async with self.bot.pool.acquire() as con:
                results = await con.fetch('''SELECT * FROM reaction_roles WHERE guild_id = $1''', payload.guild_id)
                for result in results:
                    if result.get('reactionrole_msg_id') == payload.message_id and result.get('reactionrole_channel_id') == payload.channel_id and result.get('reactionrole_emoji_id') == payload.emoji.id:
                        guild = self.bot.get_guild(result.get('guild_id'))
                        member = guild.get_member(payload.user_id)
                        role = guild.get_role(result.get('reactionrole_role_id'))
                        await member.add_roles(role, reason=f"Granted by reaction role (ID: {result.get('reactionrole_id')})")
                        break #So we do not iterate further pointlessly
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id:
            async with self.bot.pool.acquire() as con:
                results = await con.fetch('''SELECT * FROM reaction_roles WHERE guild_id = $1''', payload.guild_id)
                for result in results:
                    if result.get('reactionrole_msg_id') == payload.message_id and result.get('reactionrole_channel_id') == payload.channel_id and result.get('reactionrole_emoji_id') == payload.emoji.id:
                        guild = self.bot.get_guild(result.get('guild_id'))
                        member = guild.get_member(payload.user_id)
                        role = guild.get_role(result.get('reactionrole_role_id'))
                        await member.remove_roles(role, reason=f"Removed by reaction role (ID: {result.get('reactionrole_id')})")
                        break
    


    @commands.group(aliases=["rr"], help="Manages reaction roles.", description="Lists all reaction roles set for this guild, if any. Subcommands allow you to remove or set additional ones.", usage="reactionrole", invoke_without_command=True, case_insensitive=True)
    @commands.guild_only()
    @commands.check(hasPriviliged)
    async def reactionrole(self, ctx):
        async with ctx.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM reaction_roles WHERE guild_id = $1''', ctx.guild.id)
            if results and len(results) != 0:
                text = ""
                for result in results:
                    text = f"{text}**#{result.get('reactionrole_id')}** - {ctx.guild.get_channel(result.get('reactionrole_channel_id')).mention} - {ctx.guild.get_role(result.get('reactionrole_role_id')).mention}\n"
                embed=discord.Embed(title="Reaction Roles for this server:", description=text, color=self.bot.embedBlue)
                await ctx.send(embed=embed)
            else:
                embed=discord.Embed(title="❌ Error: No reaction roles", description="There are no reaction roles for this server.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)


    @reactionrole.command(name="delete", aliases=["del", "remove"], help="Removes a reaction role by ID.", description="Removes a reaction role of the specified ID. You can get the ID via the `reactionrole` command.", usage="reactionrole delete <ID>")
    @commands.guild_only()
    @commands.check(hasPriviliged)
    async def rr_delete(self, ctx, id:int):
        async with self.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM reaction_roles WHERE guild_id = $1 AND reactionrole_id = $2''', ctx.guild.id, id)
            if results and len(results) != 0:
                reactchannel = ctx.guild.get_channel(results[0].get('reactionrole_channel_id'))
                reactmsg = await reactchannel.fetch_message(results[0].get('reactionrole_msg_id'))
                try:
                    await reactmsg.remove_reaction(self.bot.get_emoji(results[0].get('reactionrole_emoji_id')), ctx.guild.me)
                except discord.NotFound:
                    pass
                await con.execute('''DELETE FROM reaction_roles WHERE guild_id = $1 AND reactionrole_id = $2''', ctx.guild.id, id)
                embed=discord.Embed(title="✅ Reaction Role deleted", description="Reaction role has been successfully deleted!", color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)
            else:
                embed=discord.Embed(title="❌ Error: Not found", description="There is no reaction role by that ID.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)


    @reactionrole.command(name="add", aliases=["new", "setup", "create"], help="Initializes setup to add a new reaction role.", description="Initializes a setup to help you add a new reaction role. You can also access this setup via the `setup` command. Takes no arguments.", usage="reactionrole add")
    @commands.guild_only()
    @commands.check(hasPriviliged)
    @commands.max_concurrency(1, per=commands.BucketType.guild,wait=False)
    async def rr_setup(self, ctx):
        '''
        Here is where end-users would set up a reaction role for their server
        This is not exposed as a command directly, instead it is invoked in setup
        '''
        async with self.bot.pool.acquire() as con:
            results = await con.fetch('''SELECT * FROM reaction_roles WHERE guild_id = $1''', ctx.guild.id)
        
        if results and len(results) >= 10:
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

        async with self.bot.pool.acquire() as con:
            results = await con.fetch('''
            SELECT * FROM reaction_roles WHERE guild_id = $1 AND reactionrole_channel_id = $2 AND reactionrole_msg_id = $3 AND reactionrole_emoji_id = $4
            ''', ctx.guild.id, reactchannel.id, reactmsg.id, reactemoji.id)
            if results and len(results) != 0:
                embed=discord.Embed(title="❌ Error: Duplicate", description=f"This role reaction already exists. Please remove it first via `{ctx.prefix}rolereaction delete <ID>`", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                return

            await con.execute('''
            INSERT INTO reaction_roles (guild_id, reactionrole_channel_id, reactionrole_msg_id, reactionrole_emoji_id, reactionrole_role_id)
            VALUES ($1, $2, $3, $4, $5)
            ''', ctx.guild.id, reactchannel.id, reactmsg.id, reactemoji.id, reactionrole.id)

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
