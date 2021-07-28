import asyncio
import copy
import datetime
import gettext
import itertools
import logging

import asyncpg
import discord
from discord.ext import commands


async def has_owner(ctx):
    return await ctx.bot.custom_checks.has_owner(ctx)
async def has_priviliged(ctx):
    return await ctx.bot.custom_checks.has_priviliged(ctx)

class AdminCommands(commands.Cog, name="Admin Commands"):
    def __init__(self, bot):

        self.bot = bot
        self._ = self.bot.get_localization('admin_commands', self.bot.lang)

    #Returns basically all information we know about a given member of this guild.
    @commands.command(help="Get information about a user.", description="Provides information about a specified user. If they are in the server, more detailed information will be provided.\n\n__Note:__ To receive information about users outside this server, you must use their ID.", usage=f"whois <userID|userMention|userName>")
    @commands.check(has_priviliged)
    @commands.guild_only()
    async def whois(self, ctx, *, user : discord.User) :
        if user in ctx.guild.members:
            db_user = await self.bot.global_config.get_user(user.id, ctx.guild.id)
            member = ctx.guild.get_member(user.id)
            rolelist = [role.mention for role in member.roles]
            rolelist.pop(0)
            roleformatted = ", ".join(rolelist) if len(rolelist) > 0 else "`-`"
            embed=discord.Embed(title=f"User information: {member.name}", description=f"""Username: `{member.name}`
            Nickname: `{member.display_name if member.display_name != member.name else "-"}`
            User ID: `{member.id}`
            Bot: `{member.bot}`
            Account creation date: {discord.utils.format_dt(member.created_at)} ({discord.utils.format_dt(member.created_at, style='R')})
            Join date: {discord.utils.format_dt(member.joined_at)} ({discord.utils.format_dt(member.joined_at, style='R')})
            Warns: `{db_user.warns}`
            Muted: `{db_user.is_muted}`
            Flags: `{db_user.flags}`
            Notes: `{db_user.notes}`
            Roles: {roleformatted}""", color=member.colour)
            embed.set_thumbnail(url=member.avatar.url)

        else: #Retrieve limited information about the user if they are not in the guild
            embed=discord.Embed(title=f"User information: {user.name}", description=f"""Username: `{user}`
            Nickname: `-` 
            User ID: `{user.id}` 
            Status: `-` 
            Bot: `{user.bot}` 
            Account creation date: {discord.utils.format_dt(user.created_at)} ({discord.utils.format_dt(user.created_at, style='R')})
            Join date: `-`
            Roles: `-`
            *Note: This user is not a member of this server*""", color=self.bot.embedBlue)
            embed.set_thumbnail(url=user.avatar.url)

        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar.url)
        await ctx.channel.send(embed=embed)


    #Command used for deleting a guild settings file
    @commands.command(help="Resets all settings for this guild.", description = "Resets all settings for this guild. Requires priviliged access and administrator permissions. Will also erase all tags, reminders, reaction roles and pending moderation actions. Irreversible.", usage="resetsettings")
    @commands.check(has_priviliged)
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def resetsettings(self, ctx):
        embed = discord.Embed(title="Are you sure you want to reset all settings?", description="This will also erase any created tags, pending moderation actions (e.g. tempbans), reminders, reaction roles and more.\n**This action is __irreversible__ and may break things!**", color=self.bot.errorColor)
        msg = await ctx.channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        def check(payload):
            return payload.message_id == msg.id and payload.user_id == ctx.author.id
        try:
            payload = await self.bot.wait_for('raw_reaction_add', timeout=10.0,check=check)
            if str(payload.emoji) == "✅":

                def check2(payload):
                    return payload.channel.id == msg.channel.id and payload.author == ctx.author
                embed=discord.Embed(title="Confirmation", description="Please type in the name of the server to confirm deletion.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
                payload = await self.bot.wait_for('message', timeout=20.0, check=check2)

                if payload.content == ctx.guild.name :

                    await self.bot.global_config.deletedata(ctx.guild.id)
                    embed=discord.Embed(title="✅ Settings reset", description="Goodbye cruel world! 😢", color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)

                else :
                    embed=discord.Embed(title="❌ Error: Incorrect name", description="Settings deletion cancelled.", color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)
            elif str(payload.emoji) == "❌" :
                embed=discord.Embed(title="❌ Cancelled", description="Settings deletion cancelled by user.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
            else :
                embed=discord.Embed(title=self.bot.errorEmojiTitle, description="Settings deletion cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
        except asyncio.TimeoutError:
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description="Settings deletion cancelled.")
            await ctx.channel.send(embed=embed)


    @commands.group(aliases=['privrole', 'botadmin', 'privroles', 'priviligedroles'],help="List all priviliged roles. Subcommands may add or remove priviliged roles.", description="Returns all priviliged roles on this server. You can optionally set or remove new roles as priviliged roles.", usage=f"priviligedrole", invoke_without_command=True, case_insensitive=True)
    @commands.check(has_owner)
    @commands.guild_only()
    async def priviligedrole(self, ctx) :
        '''
        This is where bot-admin (AKA priviliged) roles are added.
        Members with these roles can execute commands to set up and
        configure the bot. Note: Some commands may require additional permissions
        '''
        records = await self.bot.caching.get(table="priviliged", guild_id=ctx.guild.id)
        if not records or records and len(records["priviliged_role_id"]) == 0 :
            embed=discord.Embed(title="❌ Error: No priviliged roles set.", description=f"You can add a priviliged role via `{ctx.prefix}priviligedrole add <rolename>`.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        else :
            roles = []
            roleNames = []
            for item in records["priviliged_role_id"] :
                roles.append(ctx.guild.get_role(item))
            for item in roles :
                roleNames.append(item.name)
            roleNames = ", ".join(roleNames)
            embed=discord.Embed(title="Priviliged roles for this guild:", description=f"`{roleNames}`", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)

        #Commands used to add and/or remove other roles from executing potentially unwanted things
    @priviligedrole.command(aliases=['set'], help="Add role to priviliged roles", description="Adds a role to the list of priviliged roles, allowing them to execute admin commands.", usage="priviligedrole add <rolename>")
    @commands.check(has_owner)
    @commands.guild_only()
    async def add(self, ctx, *, role:discord.Role):
        if role is None:
            embed=discord.Embed(title="❌ Error: Role not found.", description=f"Unable to locate role, please make sure typed everything correctly.\n__Note:__ Rolenames are case-sensitive.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed); return
        records = await self.bot.caching.get(table="priviliged", guild_id=ctx.guild.id)
        #privroles = [role for role in roleIDs]
        if records and role.id in records["priviliged_role_id"] :
            embed=discord.Embed(title="❌ Error: Role already added.", description=f"This role already has priviliged access.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
        else :
            async with self.bot.pool.acquire() as con:
                await con.execute('''INSERT INTO priviliged (guild_id, priviliged_role_id) VALUES ($1, $2)''', ctx.guild.id, role.id)
                await self.bot.caching.refresh(table="priviliged", guild_id=ctx.guild.id)
                embed=discord.Embed(title="✅ Priviliged access granted.", description=f"**{role.name}** has been granted bot admin priviliges.", color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)


    @priviligedrole.command(aliases=['rem', 'del', 'delete'], help="Remove role from priviliged roles.", description="Removes a role to the list of priviliged roles, revoking their permission to execute admin commands.", usage=f"priviligedrole remove <rolename>")
    @commands.check(has_owner)
    @commands.guild_only()
    async def remove(self, ctx, *, role:discord.Role):
        if role is None:
            embed=discord.Embed(title="❌ Error: Role not found.", description=f"Unable to locate role, please make sure typed everything correctly.\n__Note:__ Rolenames are case-sensitive.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed); return
        records = await self.bot.caching.get(table="priviliged", guild_id=ctx.guild.id)
        if not records or records and role.id not in records["priviliged_role_id"] :
            embed=discord.Embed(title="❌ Error: Role not priviliged.", description=f"This role is not priviliged.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
        else :
            async with self.bot.pool.acquire() as con:
                await con.execute('''DELETE FROM priviliged WHERE guild_id = $1 AND priviliged_role_id = $2''', ctx.guild.id, role.id)
                await self.bot.caching.refresh(table="priviliged", guild_id=ctx.guild.id)
                embed=discord.Embed(title="✅ Priviliged access revoked.", description=f"**{role}** has had it's bot admin priviliges revoked.", color=self.bot.embedGreen)
                await ctx.channel.send(embed=embed)



    @commands.command(help="Sets the bot's nickname.", description="Sets the bot's nickname for this server. Provide `Null` or `None` to reset nickname.", usage="setnick <nickname>")
    @commands.check(has_priviliged)
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
            embed = discord.Embed(title="❌ Error: Unable to change nickname.", description=f"This could be due to a permissions issue.", color=self.bot.errorColor)
            await ctx.send(embed=embed)

    
    @commands.group(aliases=["prefixes"], help="Check the bot's prefixes. Subcommands of this command allow you to customize your prefix.", description="Check the bot's prefixes. You can also use `add/del` to add or remove a prefix. By adding a prefix you override the default one. The bot can have up to **5** custom prefixes per server. If you forget your prefix, mention the bot!", usage="prefix", invoke_without_command=True, case_insensitive=True)
    @commands.check(has_priviliged)
    @commands.guild_only()
    async def prefix(self, ctx):
        '''
        Prefix management commands/features are found here
        '''
        records = await self.bot.caching.get(table="global_config", guild_id=ctx.guild.id)
        if records and records["prefix"][0]:
            prefixes = records["prefix"][0]
            desc = ""
            for prefix in prefixes:
                desc = f"{desc}**#{prefixes.index(prefix)+1}** - `{prefix}` \n"
            embed=discord.Embed(title="❕ " + self._("**Active prefixes on this server**"), description=desc, color=self.bot.embedBlue)
            await ctx.send(embed=embed)
        else:
            embed=discord.Embed(title="❕ " + self._("**Active prefixes on this server**"), description=f"*#0* - `{self.bot.DEFAULT_PREFIX}` *(Default)*", color=self.bot.embedBlue)
            await ctx.send(embed=embed)
    
    @prefix.command(name="add", aliases=["new"], help="Adds a new prefix.", description="Adds a prefix to the list of valid prefixes.", usage="prefix add <prefix>")
    @commands.check(has_priviliged)
    @commands.guild_only()
    async def add_prefix(self, ctx, *, prefix:str):
        prefix = prefix.replace('"', '')
        prefix = prefix.replace("'", "")
        if prefix == "": return
        records = await self.bot.caching.get(table="global_config", guild_id=ctx.guild.id)
        if not records or not records["prefix"][0] or (prefix not in records["prefix"][0] and len(records["prefix"][0]) <= 5):
            async with self.bot.pool.acquire() as con:
                await con.execute('''
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
    @commands.check(has_priviliged)
    @commands.guild_only()
    async def del_prefix(self, ctx, *, prefix:str):
        prefix = prefix.replace('"', '')
        prefix = prefix.replace("'", "")
        if prefix == "": return
        records = await self.bot.caching.get(table="global_config", guild_id=ctx.guild.id)
        if records and records["prefix"][0] and prefix in records["prefix"][0]:
            async with self.bot.pool.acquire() as con:
                await con.execute('''
                UPDATE global_config SET prefix = array_remove(prefix,$1) WHERE guild_id = $2
                ''', prefix, ctx.guild.id)
                await self.bot.caching.refresh(table="global_config", guild_id=ctx.guild.id)

                embed = discord.Embed(title="✅ Prefix removed", description=f"Prefix **{prefix}** has been removed from the list of valid prefixes.\n\n**Note:** Removing all custom prefixes will re-enable the default prefix. If you forget your prefix, mention the bot!", color=self.bot.embedGreen)
                await ctx.send(embed=embed)

        elif records and prefix not in records["prefix"][0]:
            embed=discord.Embed(title="❌ Prefix not found", description=f"The specified prefix cannot be removed as it is not found.", color=self.bot.errorColor)
            await ctx.send(embed=embed)



    @commands.group(help="Run a command while bypassing checks and cooldowns.", description="Run a specified command while bypassing any checks and cooldowns. Requires server administator permissions for the user to run this command alongside priviliged access.", usage="sudo <command> [arguments]")
    @commands.check(has_priviliged)
    @commands.has_permissions(administrator=True)
    async def sudo(self, ctx, *, command):
        '''
        Completely bypasses command checks for the command
        It can break commands and is a very dangerous permission to grant
        Of course there is a blacklist of commands that we do not want used, ever.
        '''
        blacklist = ["jsk", "jishaku", "shutdown"] #Stuff that I don't want to work
        disabled_list = ["help", "sudo", "leave"] #Stuff that literally does not work
        disabled_cogs = ["Annoverse", "Matchmaking", "AdminCommands", "Moderation", "Reaction Roles", "Keep On Top", "Setup"] #Entire cogs can be disabled too

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


def setup(bot):
    logging.info("Adding cog: AdminCommands...")
    bot.add_cog(AdminCommands(bot))
