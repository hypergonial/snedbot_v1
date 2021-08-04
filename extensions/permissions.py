import logging

import discord
from discord.ext import commands

async def has_admin_perms(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, "admin_permitted")

class Permissions(commands.Cog):
    '''
    Assigns roles to permission lists, which determine their access level.
    Implementation of checks is outside the scope of this cog.
    '''


    def __init__(self, bot):
        self.bot = bot

        self.VALID_TYPES = {
            "mod_permitted": "moderation", 
            "automod_excluded":"automod_exclusions", 
            "admin_permitted":"administrator",
            "tags":"tags",
            "role_buttons":"role_buttons",
            "giveaway":"giveaways",
            "fun":"fun",
            "events":"events"
            }
        
        self.DEFAULT_PERMS = {
            "mod_permitted": None,
            "automod_excluded": None,
            "admin_permitted": None,
            "tags": "@everyone",
            "role_buttons": None,
            "giveaway": None,
            "fun": "@everyone",
            "events": None
        }
        self.PERM_INFO = {
            "mod_permitted": "Allows control of all moderation commands. Also excluded from auto-moderation. Includes the following nodes automatically: `automod_exclusions`, `tags`, `giveaways`, `fun`, `events`.",
            "automod_excluded": "Excludes roles from auto-moderation. For more granular control please see the dashboard.",
            "admin_permitted": "Allows total control over the bot, with all commands. Also excludes from auto-moderation. This is a dangerous permission to grant.",
            "tags": "Allows creation & basic management of tags. Users with `moderation` get additional permissions.",
            "role_buttons": "Allows creation and management of role-buttons. This may be a dangerous permission to grant as it can be exploited to gain roles.",
            "giveaway": "Allows creation and management of giveaways. This permission node is not necessary to enter them.",
            "fun": "Allows usage of commands in the `Fun` category.",
            "events": "Allows creation and management of events. This permission node is not necessary to sign up for them.",
        }
    
    async def get_perms(self, guild:discord.Guild, ptype:str) -> list[int]:
        '''Get a permission node's roles'''
        if ptype in self.VALID_TYPES.keys():
            records = await self.bot.caching.get(table="permissions", guild_id=guild.id, ptype=ptype)
            if records and records[0]["role_ids"] and len(records[0]["role_ids"]) > 0:
                return records[0]["role_ids"]
            else:
                if self.DEFAULT_PERMS[ptype] == "@everyone":
                    return [guild.id] 
                elif not self.DEFAULT_PERMS[ptype]:
                    return [] #So iteration & stuff does not break
        else:
            raise ValueError("Invalid permission-node specified.")

    async def set_perms(self, guild:discord.Guild, ptype:str, role_ids:list) -> None:
        '''Override a list of roles with a new set. Used by the dashboard.'''
        if not role_ids: role_ids = []
        guild_role_ids = [role.id for role in guild.roles]
        if ptype in self.VALID_TYPES:
            for role_id in role_ids:
                if role_id not in guild_role_ids:
                    raise ValueError("One of the role_ids specified is invalid, or not found in the current guild.")

            await self.bot.pool.execute('''
            INSERT INTO permissions (guild_id, ptype, role_ids)
            VALUES ($1, $2, $3) 
            ON CONFLICT (guild_id, ptype) DO
            UPDATE SET role_ids = $3''', guild.id, ptype, role_ids)
            await self.bot.caching.refresh(table="permissions", guild_id=guild.id)
            
        else:
            raise ValueError("Invalid permission type specified.")


    async def add_perms(self, guild:discord.Guild, ptype:str, role_id:int) -> None:
        role = guild.get_role(role_id)
        records = await self.bot.caching.get(table="permissions", guild_id=guild.id, ptype=ptype)
        role_ids = records[0]["role_ids"] if records and records[0]["role_ids"] else []
        if role_id not in role_ids:
            role_ids.append(role_id)

            await self.bot.pool.execute('''
            INSERT INTO permissions (guild_id, ptype, role_ids)
            VALUES ($1, $2, $3) 
            ON CONFLICT (guild_id, ptype) DO
            UPDATE SET role_ids = $3''', guild.id, ptype, role_ids)
            await self.bot.caching.refresh(table="permissions", guild_id=guild.id)
        else:
            raise ValueError('Role already added to permission node.')

    async def del_perms(self, guild:discord.Guild, ptype:str, role_id:int) -> None:
        records = await self.bot.caching.get(table="permissions", guild_id=guild.id, ptype=ptype)
        role_ids = records[0]["role_ids"] if records and records[0]["role_ids"] else []
        if role_id in role_ids:
            role_ids.remove(role_id)

            await self.bot.pool.execute('''
            INSERT INTO permissions (guild_id, ptype, role_ids)
            VALUES ($1, $2, $3) 
            ON CONFLICT (guild_id, ptype) DO
            UPDATE SET role_ids = $3''', guild.id, ptype, role_ids)
            await self.bot.caching.refresh(table="permissions", guild_id=guild.id)
        else:
            raise ValueError('Role not in permission node.')
    
    @commands.group(help="View server permissions. See subcommands for modifying them.", description="Provides a detailed overview of all server permissions. You can edit them with the subcommands below.", aliases=["perms", "perm", "permission"], invoke_without_command=True, case_insensitive=True, usage="permissions")
    @commands.guild_only()
    @commands.check(has_admin_perms)
    async def permissions(self, ctx):
        embed = discord.Embed(title="🛠️ Permissions Configuration", description=f"""These are the current permission nodes and the roles assigned to them.
        To change this, use the command `{ctx.prefix}permission add/del <node> <role>`
        To get more information about a node, use `{ctx.prefix}permission info <node>`

        *Hint: To add @everyone to a node, you can copy the ID of the server!*\n""", color=self.bot.embedBlue)
        records = await self.bot.caching.get(table="permissions", guild_id=ctx.guild.id)
        if records:
            ptypes = list(self.VALID_TYPES.keys())
            for record in records:
                role_ids = record["role_ids"]
                if role_ids and len(role_ids) > 0:
                    embed.add_field(name=self.VALID_TYPES[record["ptype"]], value=', '.join([ctx.guild.get_role(role_id).mention for role_id in role_ids]))
                else:
                    embed.add_field(name=self.VALID_TYPES[record["ptype"]], value=str(self.DEFAULT_PERMS[record["ptype"]]))
                ptypes.remove(record["ptype"])
            for ptype in ptypes:
                embed.add_field(name=self.VALID_TYPES[ptype], value=str(self.DEFAULT_PERMS[ptype]))
        else:
            for ptype in self.VALID_TYPES:
                embed.add_field(name=self.VALID_TYPES[ptype], value=str(self.DEFAULT_PERMS[ptype]))
        embed.insert_field_at(7, name="​", value="​") #Spacer
        await ctx.send(embed=embed)
    
    @permissions.command(name="info", help="Provides information about a specified permission node.", description="Provides detailed information about a specified permission node.", usage="permission info <node>")
    @commands.guild_only()
    @commands.check(has_admin_perms)
    async def perm_info(self, ctx, node:str):
        if node.lower() not in self.VALID_TYPES.values():
            embed=discord.Embed(title="❌ Error: Invalid node", description=f"Invalid permission node provided! See `{ctx.prefix}permissions` for valid node-types.", color=self.bot.errorColor)
            return await ctx.send(embed=embed)

        for key, value in self.VALID_TYPES.items():

            if value.lower() == node.lower():
                info = self.PERM_INFO[key]
                role_ids = await self.get_perms(ctx.guild, key)

                if role_ids and len(role_ids) > 0:
                    roles = ", ".join([ctx.guild.get_role(role_id).mention for role_id in role_ids])
                else:
                    roles = "*None*"

                embed = discord.Embed(title=f"🛠️ Permissions Configuration > Node: {node}", description=info, color=self.bot.embedBlue)
                embed.add_field(name="Currently added roles", value=roles, inline=False)
                await ctx.send(embed=embed)
    
    @permissions.command(name="add", aliases=["new"], help="Adds a role to a permission-node.", description="Adds the specified role to the permission-node.", usage="permission add <node> <role>")
    @commands.guild_only()
    @commands.check(has_admin_perms)
    async def perm_add(self, ctx, node:str, role:discord.Role):
        try:
            ptype = [key for key, value in self.VALID_TYPES.items() if value==node]

            if len(ptype) != 0:
                await self.add_perms(ctx.guild, ptype=ptype[0], role_id=role.id)
                embed=discord.Embed(title="✅ Role added", description=f"Role {role.mention} was added to `{node}`!", color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            else:
                raise KeyError

        except KeyError:
            embed=discord.Embed(title="❌ Error: Invalid node", description=f"Invalid permission node provided See `{ctx.prefix}permissions` for valid node-types.", color=self.bot.errorColor)
            return await ctx.send(embed=embed)

        except ValueError:
            embed=discord.Embed(title="❌ Error: Invalid role", description=f"This role is already added to this node.", color=self.bot.errorColor)
            return await ctx.send(embed=embed)

    @permissions.command(name="delete", aliases=["del", "remove"], help="Removes a role from a permission-node.", description="Removes specified role from the permission-node.", usage="permission delete <node> <role>")
    @commands.guild_only()
    @commands.check(has_admin_perms)
    async def perm_del(self, ctx, node:str, role:discord.Role):
        try:
            ptype = [key for key, value in self.VALID_TYPES.items() if value==node]

            if len(ptype) != 0:
                await self.del_perms(ctx.guild, ptype=ptype[0], role_id=role.id)
                embed=discord.Embed(title="✅ Role removed", description=f"Role {role.mention} was removed from `{node}`!", color=self.bot.embedGreen)
                await ctx.send(embed=embed)
            else:
                raise KeyError

        except KeyError:
            embed=discord.Embed(title="❌ Error: Invalid node", description=f"Invalid permission node provided! See `{ctx.prefix}permissions` for valid node-types.", color=self.bot.errorColor)
            return await ctx.send(embed=embed)
            
        except ValueError:
            embed=discord.Embed(title="❌ Error: Invalid role", description=f"This role is not present on the permission-node.", color=self.bot.errorColor)
            return await ctx.send(embed=embed)


def setup(bot):
    logging.info("Adding cog: Permissions...")
    bot.add_cog(Permissions(bot))