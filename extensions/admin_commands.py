import asyncio
import gettext
import logging

import discord
from discord.ext import commands


async def hasOwner(ctx):
    return ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id

#Check performed to see if the user has priviliged access.
async def hasPriviliged(ctx):
    #Gets a list of all the roles the user has, then gets the ID from that.
    userRoles = [x.id for x in ctx.author.roles]
    #Also get privliged roles, then compare
    privroles = await ctx.bot.DBHandler.checkprivs(ctx.guild.id)
    #Check if any of the roles in user's roles are contained in the priviliged roles.
    return any(role in userRoles for role in privroles) or (ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id)

class AdminCommands(commands.Cog, name="Admin Commands"):
    def __init__(self, bot):
        self.bot = bot
        if self.bot.lang == "de":
            de = gettext.translation('admin_commands', localedir=self.bot.localePath, languages=['de'])
            de.install()
            self._ = de.gettext
        elif self.bot.lang == "en":
            self._ = gettext.gettext
        #Fallback to english
        else :
            logging.error("Invalid language, fallback to English.")
            self._ = gettext.gettext

    #Returns basically all information we know about a given member of this guild.
    @commands.command(help="Get information about a user.", description="Provides information about a specified user in the guild.", usage=f"whois <userID|userMention|userName>")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def whois(self, ctx, member : discord.Member) :
        db_user = await self.bot.DBHandler.getUser(member.id, ctx.guild.id)
        rolelist = [role.name for role in member.roles]
        roleformatted = ", ".join(rolelist)
        warns = db_user["warns"]
        flags = db_user["flags"] #I have to do this because f-string bad
        if db_user["is_muted"] == 0:
            is_muted = False
        else :
            is_muted = True 
        notes = db_user["notes"]
        embed=discord.Embed(title=f"User information: {member.name}", description=f"Username: `{member.name}` \nNickname: `{member.display_name}` \nUser ID: `{member.id}` \nStatus: `{member.raw_status}` \nBot: `{member.bot}` \nAccount creation date: `{member.created_at}` \nJoin date: `{member.joined_at}`\nWarns: `{warns}`\nMuted: `{is_muted}`\nFlags: `{flags}`\nNotes: `{notes}` \nRoles: `{roleformatted}`", color=member.colour)
        embed.set_footer(text=f"Requested by {ctx.author.name}#{ctx.author.discriminator}", icon_url=ctx.author.avatar_url)
        embed.set_thumbnail(url=member.avatar_url)
        await ctx.channel.send(embed=embed)


    #Command used for deleting a guild settings file
    @commands.command(help="Resets all settings for this guild.", description = "Resets all settings for this guild. Will also erase all tags. Irreversible.", usage="resetsettings")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def resetsettings(self, ctx):
        embed = discord.Embed(title="Are you sure you want to reset all settings?", description="This will also erase any created tags.\n**This action is __irreversible__ and may break things!**", color=self.bot.errorColor)
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
                    await self.bot.DBHandler.deletedata(ctx.guild.id)
                    embed=discord.Embed(title="✅ Settings reset.", description="Goodbye cruel world! 😢", color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)
                else :
                    embed=discord.Embed(title="❌ Error: Incorrect name.", description="Settings deletion cancelled.", color=self.bot.errorColor)
                    await ctx.channel.send(embed=embed)
            elif str(payload.emoji) == "❌" :
                embed=discord.Embed(title="❌ Cancelled.", description="Settings reset cancelled by user.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
            else :
                embed=discord.Embed(title=self.bot.errorEmojiTitle, description="Settings deletion cancelled.", color=self.bot.errorColor)
                await ctx.channel.send(embed=embed)
        except asyncio.TimeoutError:
            embed=discord.Embed(title=self.bot.errorTimeoutTitle, description="Settings deletion cancelled.")
            await ctx.channel.send(embed=embed)


    #Display the current settings for this guild.
    @commands.command(help="Displays settings.", description="Displays the settings for the current guild.", usage="settings")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def settings(self, ctx):
        settingsdata = await self.bot.DBHandler.displaysettings(ctx.guild.id)
        if settingsdata == -1 :
            await ctx.channel.send("**Error:** No settings for this guild.")
        else :
            formatteddata = "".join(settingsdata)
            embed=discord.Embed(title=f"⚙️ Settings for this guild:    ({ctx.guild.id})", description=f"```{formatteddata}```", color=self.bot.embedBlue)
            embed.set_footer(text="Do not change these values directly, unless you know what you're doing!")
            await ctx.channel.send(embed=embed)


    #Modify a value in the settings, use with care or it will break things
    @commands.command(help="Modifies a setting value. Recommended to use setup instead.", description="Modifies a single value in the settings, improper use can and will break things! Use setup instead.", usage="modify <datatype> <value>")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def modify(self, ctx, datatype, value) :
        if datatype not in self.bot.datatypes :
            embed=discord.Embed(title="❌ Error: Invalid datatype.", description="Please enter a valid datatype.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        try:
            int(value)
            await self.bot.DBHandler.modifysettings(datatype, int(value), ctx.guild.id)
            embed=discord.Embed(title="Data modified.", description=f"**{datatype}** is now set to **{value}** for guild **{ctx.guild.id}**.", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)
        except ValueError:
            embed=discord.Embed(title="❌ Error: Invalid value.", description="Please enter a valid value.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        except:
            embed=discord.Embed(title="❌ Error: Unknown error encountered.", description="Please check database settings.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
    

        #Commands used to add and/or remove other roles from executing potentially unwanted things
    @commands.command(aliases=['addprivrole', 'addbotadminrole'], help="Add role to priviliged roles", description="Adds a role to the list of priviliged roles, allowing them to execute admin commands.", usage="addpriviligedrole <rolename>")
    @commands.check(hasOwner)
    @commands.guild_only()
    async def addpriviligedrole(self, ctx, *, rolename):
        role = discord.utils.get(ctx.guild.roles, name=rolename)
        if role == None:
            embed=discord.Embed(title="❌ Error: Role not found.", description=f"Unable to locate role, please make sure typed everything correctly.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        privs = await self.bot.DBHandler.checkprivs(ctx.guild.id)
        if role.id in privs :
            embed=discord.Embed(title="❌ Error: Role already added.", description=f"This role already has priviliged access.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        else :
            await self.bot.DBHandler.setpriv(role.id, ctx.guild.id)
            embed=discord.Embed(title="✅ Priviliged access granted.", description=f"**{role.name}** has been granted bot admin priviliges.", color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)
            return


    @commands.command(aliases=['remprivrole', 'removeprivrole', 'removebotadminrole', 'rembotadminrole'], help="Remove role from priviliged roles.", description="Removes a role to the list of priviliged roles, revoking their permission to execute admin commands.", usage=f"removepriviligedrole <rolename>")
    @commands.check(hasOwner)
    @commands.guild_only()
    async def removepriviligedrole(self, ctx, *, rolename):

        role = discord.utils.get(ctx.guild.roles, name=rolename)
        if role == None:
            embed=discord.Embed(title="❌ Error: Role not found.", description=f"Unable to locate role, please make sure typed everything correctly.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        privroles = await self.bot.DBHandler.checkprivs(ctx.guild.id)
        if role.id not in privroles :
            embed=discord.Embed(title="❌ Error: Role not priviliged.", description=f"This role is not priviliged.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        else :
            await self.bot.DBHandler.delpriv(role.id, ctx.guild.id)
            embed=discord.Embed(title="✅ Priviliged access revoked.", description=f"**{role}** has had it's bot admin priviliges revoked.", color=self.bot.embedGreen)
            await ctx.channel.send(embed=embed)
            return

    @commands.command(aliases=['privroles', 'botadminroles'],help="List all priviliged roles.", description="Returns all priviliged roles on this server.", usage=f"priviligedroles")
    @commands.check(hasOwner)
    @commands.guild_only()
    async def priviligedroles(self, ctx) :
        roleIDs = await self.bot.DBHandler.checkprivs(ctx.guild.id)
        if len(roleIDs) == 0 :
            embed=discord.Embed(title="❌ Error: No priviliged roles set.", description=f"You can add a priviliged role via `{self.bot.prefix}addpriviligedrole <rolename>`.", color=self.bot.errorColor)
            await ctx.channel.send(embed=embed)
            return
        else :
            roles = []
            roleNames = []
            for item in roleIDs :
                roles.append(ctx.guild.get_role(item))
            for item in roles :
                roleNames.append(item.name)
            roleNames = ", ".join(roleNames)
            embed=discord.Embed(title="Priviliged roles for this guild:", description=f"`{roleNames}`", color=self.bot.embedBlue)
            await ctx.channel.send(embed=embed)

    @commands.command(help="Sets the bot's nickname.", description="Sets the bot's nickname for this server. Provide `Null` or `None` to reset nickname.", usage="setnick <nickname>")
    @commands.check(hasPriviliged)
    @commands.guild_only()
    async def setnick(self, ctx, *, nick):
        try:
            if nick.lower() == "none" or nick.lower() == "null":  #Simple way to clear nick
                nick=None
            await ctx.guild.me.edit(nick=nick)
            embed = discord.Embed(title="✅ Nickname changed", description=f"Bot nickname has been changed to `{nick}`.", color=self.bot.embedGreen)
            await ctx.send(embed=embed)
        except:
            embed = discord.Embed(title="❌ Error: Unable to change nickname.", description=f"This could be due to a permissions issue.", color=self.bot.errorColor)
            await ctx.send(embed=embed)

    @commands.command(help="Shut down the bot.", description="Shuts the bot down properly and closes all pending connections.", usage="shutdown")
    @commands.is_owner()
    async def shutdown(self, ctx):
        embed=discord.Embed(title="Shutting down...", description="Closing connections...", color=self.bot.errorColor)
        await ctx.send("https://media.tenor.com/images/529aed02dae515a28de82141cfd0b019/tenor.gif")
        await ctx.send(embed=embed)
        await self.bot.close()
        logging.info("Bot shut down successfully!")

def setup(bot):
    logging.info("Adding cog: AdminCommands...")
    bot.add_cog(AdminCommands(bot))
