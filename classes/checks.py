class CustomChecks:
    """
    Custom checks for commands and cogs across the bot
    Some of these checks are not intended to be implemented directly, as they take arguments,
    instead, you should wrap them into other functions that give them said arguments.
    """

    def __init__(self, bot):
        self.bot = bot

    async def has_owner(self, ctx):
        """
        True if the invoker is either bot or guild owner
        """
        if ctx.guild:
            return ctx.author.id == ctx.bot.owner_id or ctx.author.id == ctx.guild.owner_id
        else:
            return ctx.author.id == ctx.bot.owner_id

    async def module_is_enabled(self, ctx, module_name: str):
        """
        True if module is enabled, false otherwise. module_name is the extension filename.
        """

        records = await self.bot.caching.get(table="modules", guild_id=ctx.guild.id, module_name=module_name)
        if records and records[0]["is_enabled"]:
            return records[0]["is_enabled"]
        else:
            return True

    async def has_permissions(self, ctx, perm_node: str):
        """
        Returns True if a user is in the specified permission node,
        or in the administrator node, or is a Discord administrator, or is the owner.
        """

        if ctx.guild:
            user_role_ids = [x.id for x in ctx.author.roles]
            role_ids = await ctx.bot.get_cog("Permissions").get_perms(ctx.guild, perm_node)
            admin_role_ids = await ctx.bot.get_cog("Permissions").get_perms(ctx.guild, "admin_permitted")
            return (
                any(role in user_role_ids for role in admin_role_ids)
                or any(role in user_role_ids for role in role_ids)
                or ctx.author.id == ctx.bot.owner_id
                or ctx.author.id == ctx.guild.owner_id
                or ctx.author.guild_permissions.administrator
            )
