import asyncio
import copy
import itertools
import logging

import discord
from discord.ext import commands


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_admin_perms(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, 'admin_permitted')

class AdminCommands(commands.Cog, name="Admin Commands"):
    '''All commands relating to the administration of the server'''

    def __init__(self, bot):

        self.bot = bot
        self._ = self.bot.get_localization('admin_commands', self.bot.lang)

    async def cog_check(self, ctx):
            return await ctx.bot.custom_checks.has_permissions(ctx, 'admin_permitted')


    @commands.command(help="Resets all settings for this guild.", description = "Resets all settings for this guild. Requires priviliged access and administrator permissions. Will also erase all tags, reminders, reaction roles and pending moderation actions. Irreversible.", usage="resetsettings")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def resetsettings(self, ctx):
        embed = discord.Embed(title="Are you sure you want to reset all settings?", description="This will also **erase** any created tags, pending moderation actions (e.g. tempbans), reminders, role-buttons and more.\n**This action is __irreversible__ and may break things!**", color=self.bot.errorColor)
        should_delete = await ctx.confirm(embed=embed, delete_after=True)

        if should_delete == True:
            def check(payload):
                return payload.channel.id == ctx.channel.id and payload.author == ctx.author
            embed=discord.Embed(title="Confirmation", description="Please type in the name of the server to confirm deletion.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            message = await self.bot.wait_for('message', timeout=30.0, check=check)

            if message.content == ctx.guild.name :
                await self.bot.global_config.deletedata(ctx.guild.id)
                embed=discord.Embed(title="✅ Settings reset", description="Goodbye cruel world! 😢", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
            else :
                embed=discord.Embed(title="❌ Error: Incorrect server name", description="Settings deletion cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
        elif should_delete == False:
            embed=discord.Embed(title="❌ Cancelled", description="Settings deletion aborted by user.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
        else :
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description="Timed out. Settings deletion cancelled.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)


    @commands.command(help="Sets the bot's nickname.", description="Sets the bot's nickname for this server. Provide `Null` or `None` to reset nickname.", usage="setnick <nickname>")
    @commands.guild_only()
    async def setnick(self, ctx, *, nick):
        '''
        Sets the bot's nick to the specified name
        '''
        try:
            if nick.lower() == "none" or nick.lower() == "null":  #Simple way to clear nick
                nick=None
            await ctx.guild.me.edit(nick=nick)
            embed = discord.Embed(title="✅ Nickname changed", description=f"Bot nickname has been changed to `{nick}`.", color=self.bot.embedGreen)
            await ctx.send(embed=embed)
        except:
            embed = discord.Embed(title="❌ Error: Unable to change nickname", description=f"This could be due to a permissions issue.", color=self.bot.errorColor)
            await ctx.send(embed=embed)

    
    @commands.group(aliases=["prefixes"], help="Check the bot's prefixes. Subcommands of this command allow you to customize your prefix.", description="Check the bot's prefixes. You can also use `add/del` to add or remove a prefix. By adding a prefix you override the default one. The bot can have up to **5** custom prefixes per server. If you forget your prefix, mention the bot!", usage="prefix", invoke_without_command=True, case_insensitive=True)
    @commands.guild_only()
    async def prefix(self, ctx):
        '''
        Prefix management commands/features are found here
        '''
        records = await self.bot.caching.get(table="global_config", guild_id=ctx.guild.id)
        if records and records[0]["prefix"] and len(records[0]["prefix"]) > 0:
            prefixes = records[0]["prefix"]
            desc = ""
            for prefix in prefixes:
                desc = f"{desc}**#{prefixes.index(prefix)+1}** - `{prefix}` \n"
            embed=discord.Embed(title="❕ " + self._("**Active prefixes on this server**"), description=desc, color=self.bot.embedBlue)
            await ctx.send(embed=embed)
        else:
            embed=discord.Embed(title="❕ " + self._("**Active prefixes on this server**"), description=f"*#0* - `{self.bot.DEFAULT_PREFIX}` *(Default)*", color=self.bot.embedBlue)
            await ctx.send(embed=embed)
    
    @prefix.command(name="add", aliases=["new"], help="Adds a new prefix.", description="Adds a prefix to the list of valid prefixes.", usage="prefix add <prefix>")
    @commands.guild_only()
    async def add_prefix(self, ctx, *, prefix:str):
        prefix = prefix.replace('"', '')
        prefix = prefix.replace("'", "")
        if prefix == "": return
        records = await self.bot.caching.get(table="global_config", guild_id=ctx.guild.id)
        if not records or not records[0]["prefix"] or (prefix not in records[0]["prefix"] and len(records[0]["prefix"]) <= 5):
            await self.bot.pool.execute('''
            UPDATE global_config SET prefix = array_append(prefix,$1) WHERE guild_id = $2
            ''', prefix, ctx.guild.id)
            await self.bot.caching.refresh(table="global_config", guild_id=ctx.guild.id)

            embed = discord.Embed(title="✅ Prefix added", description=f"Prefix **{prefix}** has been added to the list of valid prefixes.\n\n**Note:** Setting a custom prefix disables the default prefix. If you forget your prefix, mention the bot!", color=self.bot.embedGreen)
            await ctx.send(embed=embed)

        elif prefix in records["prefix"][0]:
            embed=discord.Embed(title="❌ Prefix already added", description=f"This prefix is already added.", color=self.bot.errorColor)
            await ctx.send(embed=embed)
        elif len(records["prefix"][0]) > 5:
            embed=discord.Embed(title="❌ Too many prefixes", description=f"This server has reached the maximum amount of prefixes.", color=self.bot.errorColor)
            await ctx.send(embed=embed)

    @prefix.command(name="del", aliases=["remove", "delete"], help="Removes a prefix.", description="Removes a prefix from the list of valid prefixes.", usage="prefix del <prefix>")
    @commands.guild_only()
    async def del_prefix(self, ctx, *, prefix:str):
        prefix = prefix.replace('"', '')
        prefix = prefix.replace("'", "")
        if prefix == "": return
        records = await self.bot.caching.get(table="global_config", guild_id=ctx.guild.id)
        if records and records[0]["prefix"] and prefix in records[0]["prefix"]:
            await self.bot.pool.execute('''
            UPDATE global_config SET prefix = array_remove(prefix,$1) WHERE guild_id = $2
            ''', prefix, ctx.guild.id)
            await self.bot.caching.refresh(table="global_config", guild_id=ctx.guild.id)

            embed = discord.Embed(title="✅ Prefix removed", description=f"Prefix **{prefix}** has been removed from the list of valid prefixes.\n\n**Note:** Removing all custom prefixes will re-enable the default prefix. If you forget your prefix, mention the bot!", color=self.bot.embedGreen)
            await ctx.send(embed=embed)

        elif records and prefix not in records[0]["prefix"]:
            embed=discord.Embed(title="❌ Prefix not found", description=f"The specified prefix cannot be removed as it is not found.", color=self.bot.errorColor)
            await ctx.send(embed=embed)

    @commands.command(help="Edits one of the bot's messages.", description="Edits one of the bot's messages via the specified channel and message ID.", usage="edit <channel_ID> <message_ID> <new_content>")
    @commands.guild_only()
    async def edit(self, ctx, channel_id:int, msg_id:int, *, content:str):
        channel = ctx.guild.get_channel(channel_id)
        if channel:
            try:
                message = await channel.fetch_message(msg_id)
            except discord.NotFound:
                embed=discord.Embed(title="❌ Message not found", description=f"Could not find this message.", color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                if message.author.id == self.bot.user.id:
                    await message.edit(content=content)
                    embed = discord.Embed(title="✅ Message edited", description=f"Message `{msg_id}` has been edited in {channel.mention}!", color=self.bot.embedGreen)
                    await ctx.send(embed=embed)
                else:
                    embed=discord.Embed(title="❌ Message not owned by bot", description=f"This message was not posted by the bot, and cannot be edited by it.", color=self.bot.errorColor)
                    await ctx.send(embed=embed)
        else:
            embed=discord.Embed(title="❌ Channel not found", description=f"Could not find this channel.", color=self.bot.errorColor)
            await ctx.send(embed=embed)

    @commands.command(help="Copies a message to the current channel.", description="Edits one of the bot's messages via the specified channel and message ID.", usage="edit <channel_ID> <message_ID>")
    @commands.guild_only()
    async def copy(self, ctx, channel_id:int, msg_id:int):
        channel = ctx.guild.get_channel(channel_id)
        if channel:
            try:
                message = await channel.fetch_message(msg_id)
            except discord.NotFound:
                embed=discord.Embed(title="❌ Message not found", description=f"Could not find this message.", color=self.bot.errorColor)
                await ctx.send(embed=embed)
            else:
                embed = message.embeds[0] if message.embeds and message.embeds[0] else None
                await ctx.send(content=message.content, embed=embed)
        else:
            embed=discord.Embed(title="❌ Channel not found", description=f"Could not find this channel.", color=self.bot.errorColor)
            await ctx.send(embed=embed)


    @commands.command(help="Run a command while bypassing checks and cooldowns.", description="Run a specified command while bypassing any checks and cooldowns. Requires server administator permissions for the user to run this command alongside priviliged access.", usage="sudo <command> [arguments]")
    @commands.has_permissions(administrator=True)
    async def sudo(self, ctx, *, command):
        '''
        Completely bypasses command checks for the command
        It can break commands and is a very dangerous permission to grant
        Of course there is a blacklist of commands that we do not want used, ever.
        '''
        blacklist = ["jsk", "jishaku", "shutdown"] #Stuff that I don't want to work
        disabled_list = ["help", "sudo", "leave"] #Stuff that literally does not work
        disabled_cogs = ["Events", "Permissions", "Annoverse", "Matchmaking", "AdminCommands", "Moderation", "Role-Buttons", "Keep On Top", "Setup"] #Entire cogs can be disabled too

        for cog in disabled_cogs:
            try:
                disabled_list = disabled_list + [command.name.lower() for command in self.bot.get_cog(cog).get_commands()]
                disabled_list = disabled_list + [alias.lower() for alias in list(itertools.chain(*[command.aliases for command in self.bot.get_cog(cog).get_commands()]))]
            except AttributeError: #Ignore missing cogs
                pass
        if command.lower().startswith(tuple(blacklist)):
            embed = discord.Embed(title="❌ Command unavailable", description=f"👍 Nice try though...", color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        elif command.lower().startswith(tuple(disabled_list)):
            embed = discord.Embed(title="❌ Command unavailable", description=f"This command is not available while using `{ctx.prefix}sudo`", color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        msg = copy.copy(ctx.message)
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg)
        if new_ctx and new_ctx.valid:
            await new_ctx.command.reinvoke(new_ctx)
        else:
            raise commands.CommandNotFound


    @commands.command(help="Shut down the bot.", description="Shuts the bot down properly and closes all pending connections.", usage="shutdown")
    @commands.is_owner()
    async def shutdown(self, ctx):
        embed=discord.Embed(title="Shutting down...", description="Closing all connections...", color=self.bot.errorColor)
        #await ctx.send("https://media.tenor.com/images/529aed02dae515a28de82141cfd0b019/tenor.gif")
        await ctx.send(embed=embed)
        await self.bot.pool.close()
        await self.bot.close()
        logging.info("Bot shut down successfully!")


    @commands.command(help="Forces the bot to leave this server.", description="Forces the bot to leave this server. Takes no arguments.", usage="leave")
    @commands.is_owner()
    @commands.guild_only()
    async def leave(self, ctx):
        embed = discord.Embed(title="Are you sure you want the bot to leave?", description="You need an invite link and `Manage Server` permissions to undo this.", color=self.bot.embedBlue)
        msg = await ctx.channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        def check(payload):
            return payload.message_id == msg.id and payload.user_id == ctx.author.id
        payload = await self.bot.wait_for('raw_reaction_add', timeout=60.0,check=check)
        if str(payload.emoji) == "✅":
            embed = discord.Embed(title="🚪 See you soon! (hopefully)", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            await ctx.guild.leave()
        else:
            embed = discord.Embed(title="Leaving aborted", description="The bot will stay in this server.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
    
    @commands.group(help="Blacklists a member from using the bot.", description="Blacklists a member from using any of the bot's commands. To query a user's blacklisted status, use the `whois` command.", usage="blacklist <user>", invoke_without_command=True, case_insensitive=True)
    @commands.is_owner()
    async def blacklist(self, ctx):
        await ctx.send_help(ctx.command)

    @blacklist.command(name="add", help="Adds a member to the blacklist.", usage="blacklist add <user>")
    @commands.is_owner()
    async def blacklist_add(self, ctx, user:discord.User):
        records = await self.bot.caching.get(table="blacklist", guild_id=0, user_id=user.id)
        print(records)
        if not records or len(records) == 0:
            await self.bot.pool.execute('''INSERT INTO blacklist (user_id) VALUES ($1)''', user.id)
            await self.bot.caching.refresh(table="blacklist", guild_id=0)
            embed = discord.Embed(title="✅ User blacklisted", description=f"User has been blacklisted!", color=self.bot.embedGreen)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="❌ User already blacklisted", description=f"User is already present in the blacklist!", color=self.bot.errorColor)
            await ctx.send(embed=embed)
    
    @blacklist.command(name="del", aliases=["delete", "remove"], help="Removes a member from the blacklist.", usage="blacklist del <user>")
    @commands.is_owner()
    async def blacklist_del(self, ctx, user:discord.User):
        records = await self.bot.caching.get(table="blacklist", guild_id=0, user_id=user.id)
        if records and records[0]["user_id"] == user.id:
            await self.bot.pool.execute('''DELETE FROM blacklist WHERE user_id = $1''', user.id)
            await self.bot.caching.refresh(table="blacklist", guild_id=0)
            embed = discord.Embed(title="✅ User removed from blacklist", description=f"User has been removed from the blacklist!", color=self.bot.embedGreen)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="❌ User is not in blacklist", description=f"User is not present in the blacklist!", color=self.bot.errorColor)
            await ctx.send(embed=embed)



def setup(bot):
    logging.info("Adding cog: AdminCommands...")
    bot.add_cog(AdminCommands(bot))
