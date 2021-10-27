import asyncio
import json
import logging
from typing import List

import discord
from discord.components import SelectOption
from discord.ext import commands

from extensions.utils import components

logger = logging.getLogger(__name__)

async def has_admin_perms(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, 'admin_permitted')

async def can_mute(ctx) -> bool:
    '''A check performed to see if the configuration is correct for muting to be done.'''
    records = await ctx.bot.caching.get(table="mod_config", guild_id=ctx.guild.id)
    if records and records[0]["mute_role_id"]:
        mute_role = ctx.guild.get_role(records[0]["mute_role_id"])
        if mute_role:
            return True
        return False

mod_settings_strings = {
    "dm_users_on_punish": "DM users after punishment",
    "clean_up_mod_commands": "Clean up mod commands",
    "mute_role_id": "Mute role"
}

default_automod_policies = {
    'invites': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'excluded_channels': []
    },
    'spam': {
        'state': 'disabled',
        'temp_dur': 15,
        'excluded_channels': []
    },
    'mass_mentions': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'count': 10,
        'excluded_channels': []
    },
    'zalgo': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'excluded_channels': []
    },
    'attach_spam': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'excluded_channels': []
    },
    'link_spam': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'excluded_channels': []
    },
    'caps': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'excluded_channels': []
    },
    'bad_words': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'excluded_channels': [],
        'words_list': ["motherfucker", "cock", "cockfucker", "anal", "cum", "anus", "porn", "pornography", "slut", "whore"],
        'words_list_wildcard': ["blowjob", "boner", "dildo", "faggot", "dick", "whore", "pussy", "nigg", "cunt", "cnut", "d1ck"]
    },
    'escalate': {
        'state': 'disabled'
    }
}

# Policy state configuration
policy_states = {
    "disabled": {
        "name": "Disabled",
        "excludes": []
    },
    "notice": {
        "name": "Notice",
        "excludes": ["spam"]
    },
    "warn": {
        "name": "Warn",
        "excludes": ["spam"]
    },
    "escalate": {
        "name": "Smart",
        "excludes": ["spam", "escalate"]
    },
    "tempmute": {
        "name": "Tempmute",
        "excludes": []
    },
    "kick": {
        "name": "Kick",
        "excludes": []
    },
    "softban": {
        "name": "Softban",
        "excludes": []
    },
    "tempban": {
        "name": "Tempban",
        "excludes": []
    },
    "permaban": {
        "name": "Ban",
        "excludes": []
    }
}

# Strings for the automod config menu
policy_strings = {
    'invites': {
        'name': 'Invites',
        'description': 'This event is triggered when a Discord invite is sent in chat.'
    },
    'spam': {
        'name': 'Spam',
        'description': 'This event is triggered a user sends multiple messages in quick succession.'
    },
    'mass_mentions': {
        'name': 'Mass Mentions',
        'description': 'This event is triggered when a pre-determined number of mentions is sent in a single message. This does not include mentions of self or bots.'
    },
    'zalgo': {
        'name': 'Zalgo',
        'description': 'This event is triggered when the bot detects zalgo text in a message.'
    },
    'attach_spam': {
        'name': 'Attachment spam',
        'description': 'This event is triggered when multiple messages containing attachments are sent in quick succession (e.g. images) by the same user..'
    },
    'link_spam': {
        'name': 'Link spam',
        'description': 'This event is triggered when multiple messages containing links are sent in quick succession by the same user.'
    },
    'caps': {
        'name': 'Caps',
        'description': 'This event is triggered when a message includes 80% capitalized characters and is over a certain length.'
    },
    'bad_words': {
        'name': 'Bad words',
        'description': 'This event is triggered when a message includes any of the bad words configured below.'
    },
    'escalate': {
        'name': 'Smart',
        'description': "This event is triggered when any other event's punishment is set to smart, when the bot deemes that warning the user is not enough. Other parameters such as the duration of temporary punishment (if temporary), the deletion of message etc.. are inherited from the original event."
    },
    
}

log_event_strings = {
    "ban": "Ban",
    "kick": "Kick",
    "mute": "Mute",
    "message_delete": "Message Deletion",
    "message_delete_mod": "Message Deletion by Mod",
    "message_edit": "Message Edits",
    "bulk_delete": "Message Purging",
    "invites": "Invites",
    "roles": "Roles",
    "channels": "Channels",
    "member_join": "Member join",
    "member_leave": "Member leave",
    "nickname": "Nickname change",
    "guild_settings": "Server settings"
}

class SettingsMainView(components.AuthorOnlyView):
    '''Main settings view'''
    def __init__(self, ctx, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.value = None
    
    @discord.ui.button(label="Moderation", style=discord.ButtonStyle.primary)
    async def mod_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        self.value = "moderation"
        self.stop()
    
    @discord.ui.button(label="Automoderator", style=discord.ButtonStyle.primary)
    async def automod_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        self.value = "automod"
        self.stop()

    @discord.ui.button(label="Logging", style=discord.ButtonStyle.primary)
    async def logging_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        self.value = "logging"
        self.stop()
    @discord.ui.button(label="Quit", style=discord.ButtonStyle.danger)
    async def quit_button(self, button:discord.ui.Button, interaction:discord.Interaction):
        self.value = "quit"
        self.stop()

class ModConfMainView(components.AuthorOnlyView):
    '''Moderation settings main view'''
    def __init__(self, ctx, options:dict, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.value = None
        self.options = options
        self.ctx = ctx

        self.add_item(self.MenuSelectButton(option="back", label="Back", emoji="⬅️", style=discord.ButtonStyle.primary))
        for option in options:
            self.add_item(self.MenuSelectButton(option=option, label=options[option], style=discord.ButtonStyle.secondary))

    class MenuSelectButton(discord.ui.Button):
        def __init__(self, option:str, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.option = option

        async def callback(self, interaction: discord.Interaction):
            self.view.value = self.option
            self.view.stop()
    
class AutoModConfMainView(components.AuthorOnlyView):
    '''Automoderator main view'''
    def __init__(self, ctx, policies:dict, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.value = None
        self.policies = policies
        self.ctx = ctx

        self.add_item(self.MenuSelectButton(option="back", label="Back", emoji="⬅️", style=discord.ButtonStyle.primary))
        for policy in policies:
            self.add_item(self.MenuSelectButton(option=policy, label=policy_strings[policy]["name"], style=discord.ButtonStyle.secondary))

    class MenuSelectButton(discord.ui.Button):
        def __init__(self, option:str, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.option = option

        async def callback(self, interaction: discord.Interaction):
            self.view.value = self.option
            self.view.stop()

class AutoModOptionsView(components.AuthorOnlyView):
    '''Submenu for automoderator options'''
    def __init__(self, ctx, button_labels:dict, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.value = None
        self.button_labels = button_labels
        self.ctx = ctx
    
        self.add_item(self.OptionsMenuSelectButton(option="back",emoji="⬅️", label="Back", style=discord.ButtonStyle.blurple))
        for key in button_labels:
            self.add_item(self.OptionsMenuSelectButton(option=key, label=button_labels[key], style=discord.ButtonStyle.secondary))

    class OptionsMenuSelectButton(discord.ui.Button):
        def __init__(self, option:str, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.option = option

        async def callback(self, interaction: discord.Interaction):
            self.view.value = self.option
            self.view.stop()

class StateChangeView(components.AuthorOnlyView):
    '''State change view for automoderator states'''
    def __init__(self, ctx, states:dict, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.value = None
        self.state_options = []
        for state, label in states.items():
            self.state_options.append(discord.SelectOption(label=label, value=state))
        self.add_item(self.StateSelect(options=self.state_options))
    
    class StateSelect(components.CustomSelect):
        def __init__(self, options):
            super().__init__(placeholder="Select a state...", options=options)

class LoggingConfMainView(components.AuthorOnlyView):
    '''Logging main view'''
    def __init__(self, ctx, logging_channels:dict, emojies:List[str],  *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.value = None
        self.logging_channels = logging_channels
        self.ctx = ctx
        self.emojies = emojies

        self.add_item(self.MenuSelectButton(option="back", label="Back", emoji="⬅️", style=discord.ButtonStyle.primary))
        for i, key in enumerate(logging_channels.keys()):
            self.add_item(self.MenuSelectButton(option=key, emoji=self.emojies[i], style=discord.ButtonStyle.secondary))

    class MenuSelectButton(discord.ui.Button):
        def __init__(self, option:str, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.option = option

        async def callback(self, interaction: discord.Interaction):
            self.view.value = self.option
            self.view.stop()


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name="settings", aliases=["config"], help="Set up and configure the bot.", description="Set up and configure the bot through interactive menus.", usage="settings")
    @commands.guild_only()
    @commands.check(has_admin_perms)
    async def settings_cmd(self, ctx):
        await self.settings_main(ctx)

    async def settings_main(self, ctx, message:discord.Message=None):
        embed=discord.Embed(title="Sned Configuration", description="""**Welcome to settings!**
            
            Here you can configure various aspects of the bot, such as moderation settings, automoderator, logging options, permissions, and more. 
            Click one of the buttons below to get started!""", color=self.bot.embedBlue)
        view = SettingsMainView(ctx)
        if message:
            await self.bot.maybe_edit(message, embed=embed, view=view)
        else:
            message = await ctx.send(embed=embed, view=view)
        await view.wait()
        if view.value == "quit" or not view.value:
            await self.bot.maybe_delete(message)
        elif view.value == "moderation":
            await self.mod_conf(ctx, message)
        elif view.value == "automod":
            await self.automod_conf(ctx, message)
        elif view.value == "logging":
            await self.logging_conf(ctx, message)


    async def mod_conf(self, ctx, message:discord.Message=None):

        mod = self.bot.get_cog("Moderation")

        async def show_mod_menu(self, message:discord.Message=None):

            options = await mod.get_settings(ctx.guild.id)
            options_dict = {}
            embed = discord.Embed(title="Moderation Settings", description="Below you can see the current moderation settings, to change any of them, press the corresponding button!", color=self.bot.embedBlue)
            if not await can_mute(ctx):
                embed.add_field(name="⚠️ Warning!", value="There is **no mute role** set! Without a mute role, muting and tempmuting is unavailable! Please configure one here!", inline=False)

            for field in options.__dataclass_fields__:
                value = getattr(options, field)
                if field == "mute_role_id":
                    mute_role = ctx.guild.get_role(value)
                    if mute_role:
                        value = mute_role.mention
                    else:
                        value = "Not set"

                embed.add_field(name=f"{mod_settings_strings[field]}", value=value, inline=True)
                options_dict[field] = mod_settings_strings[field]

            view = ModConfMainView(ctx, options_dict)
            if not message:
                message = await ctx.send(embed=embed, view=view)
            else:
                await self.bot.maybe_edit(message, embed=embed, view=view)
            
            def check(message):
                return message.author.id == ctx.author.id and  ctx.channel.id == message.channel.id

            await view.wait()
            if not view.value:
                await self.bot.maybe_delete(message)

            if view.value == "back":
                await self.settings_main(ctx, message)

            elif view.value == "dm_users_on_punish":
                await self.bot.pool.execute('''
                INSERT INTO mod_config (guild_id, dm_users_on_punish)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO
                UPDATE SET dm_users_on_punish = $2''', ctx.guild.id, not options.dm_users_on_punish)
                await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                await show_mod_menu(self, message)

            elif view.value == "clean_up_mod_commands":
                await self.bot.pool.execute('''
                INSERT INTO mod_config (guild_id, clean_up_mod_commands)
                VALUES ($1, $2)
                ON CONFLICT (guild_id) DO
                UPDATE SET clean_up_mod_commands = $2''', ctx.guild.id, not options.clean_up_mod_commands)
                await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                await show_mod_menu(self, message)

            elif view.value == "mute_role_id":
                embed = discord.Embed(title=f"Configuring mute role", description="Please enter a mention, ID, or name of the role you want to use as a mute role! This role should **not be able** to send messages or add reactions in any channels for muting to work correctly!", color=self.bot.embedBlue)
                await self.bot.maybe_edit(message, embed=embed, view=None)

                try:
                    input = await self.bot.wait_for('message', check=check, timeout=180)
                except asyncio.TimeoutError:
                    await self.bot.maybe_delete(message)
                else:
                    try:
                        mute_role = await commands.RoleConverter().convert(ctx, input.content)

                        await self.bot.pool.execute('''
                        INSERT INTO mod_config (guild_id, mute_role_id)
                        VALUES ($1, $2)
                        ON CONFLICT (guild_id) DO
                        UPDATE SET mute_role_id = $2''', ctx.guild.id, mute_role.id)
                        await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)

                        await self.bot.maybe_delete(input)
                        await show_mod_menu(self, message)

                    except commands.RoleNotFound:
                        view = components.BackButtonView(ctx)
                        embed = discord.Embed(title="❌ Role not found", description="Unable to find role! Please make sure what you entered is correct.", color=self.bot.errorColor)
                        await self.bot.maybe_edit(message, view=view, embed=embed)
                        await self.bot.maybe_delete(input)

                        await view.wait()
                        if view.value == "back":
                            await show_mod_menu(self, message)
                        else:
                            await self.bot.maybe_delete(message)

        await show_mod_menu(self, message)


    async def automod_conf(self, ctx, message:discord.Message):

        automod = self.bot.get_cog("Auto-Moderation")

        async def show_automod_menu(self, message:discord.Message=None):

            policies = await automod.get_policies(ctx.guild.id)
            embed = discord.Embed(title="Automoderation Settings", description="Below you can see a summary of the current automoderation settings. To see more details about a specific entry or change their settings, press the corresponding button.", color=self.bot.embedBlue)
            if not await can_mute(ctx):
                embed.add_field(name="⚠️ Warning!", value=f"There is **no mute role** set! Without a mute role, muting and tempmuting is unavailable! Please configure one with `{ctx.prefix}moderation`", inline=False)
            for key in policies.keys():
                embed.add_field(name=f"{policy_strings[key]['name']}", value=policies[key]["state"].capitalize(), inline=True)
            view = AutoModConfMainView(ctx, policies)
            if not message:
                message = await ctx.send(embed=embed, view=view)
            else:
                await self.bot.maybe_edit(message, embed=embed, view=view)
            
            await view.wait()
            if not view.value:
                await self.bot.maybe_delete(message)
            elif view.value == "back":
                await self.settings_main(ctx, message)
            else:
                await show_policy_options(self, view.value, message)

        async def show_policy_options(self, offense_str:str, message:discord.Message=None):
            policies = await automod.get_policies(ctx.guild.id)
            policy_data = policies[offense_str]
            embed = discord.Embed(title=f"Options for: {policy_strings[offense_str]['name']}", description=f"{policy_strings[offense_str]['description']}", color=self.bot.embedBlue)
            button_labels = {}

            if policy_data["state"] == "disabled" and offense_str not in ["spam", "escalate"]:
                embed.add_field(name="ℹ️ Disclaimer:", value="More configuration options will appear if you enable/change the state of this entry!", inline=False)

            embed.add_field(name="State:", value=policy_data["state"].capitalize(), inline=False)
            button_labels["state"] = "State"

            if policy_data["state"] != "disabled":
                for key in policy_data:
                    if key == "temp_dur" and policy_data["state"].startswith("temp") or key == "temp_dur" and policies["escalate"]["state"].startswith("temp") and policy_data["state"] == "escalate":
                        embed.add_field(name="Temporary punishment duration:", value=f"{policy_data[key]} minute(s)", inline=False)
                        button_labels["temp_dur"] = "Duration"
                    elif key == "delete":
                        embed.add_field(name="Delete offending messages:", value=policy_data[key], inline=False)
                        button_labels["delete"] = "Deletion"
                    elif key == "count":
                        embed.add_field(name="Count:", value=policy_data[key], inline=False)
                        button_labels["count"] = "Count"
                    elif key == "words_list":
                        bad_words = ', '.join(policy_data[key])
                        embed.add_field(name="Blacklisted words (Exact):", value=f"||{bad_words}||", inline=False)
                        button_labels["words_list"] = "Bad words (Exact)"
                    elif key == "words_list_wildcard":
                        bad_words = ", ".join(policy_data[key])
                        embed.add_field(name="Blacklisted words (Wildcard):", value=f"||{bad_words}||", inline=False)
                        button_labels["words_list_wildcard"] = "Bad words (Wildcard)"
                    elif key == "excluded_channels":
                        channels = []
                        for channel_id in policy_data[key]:
                            channel = ctx.guild.get_channel(channel_id)
                            if channel:
                                channels.append(channel)
                        if len(channels) > 0:
                            embed.add_field(name="Excluded channels:", value=" ".join([channel.mention for channel in channels]))
                        else:
                            embed.add_field(name="Excluded channels:", value="None set")
                        button_labels["excluded_channels"] = "Excluded channels"
            
            view = AutoModOptionsView(ctx, button_labels)
            await self.bot.maybe_edit(message, embed=embed, view=view)
            await view.wait()

            def check(message):
                return message.author.id == ctx.author.id and  ctx.channel.id == message.channel.id

            '''Menu navigation for policy options'''

            sql = '''
            INSERT INTO mod_config (automod_policies, guild_id)
            VALUES ($1, $2) 
            ON CONFLICT (guild_id) DO
            UPDATE SET automod_policies = $1
            '''

            if view.value == "back":
                await show_automod_menu(self, message)

            elif view.value == "state":
                embed = discord.Embed(title=f"Set state for {policy_strings[offense_str]['name']}", description="Please change the current state of this moderation policy below!", color=self.bot.embedBlue)
                states = {}
                for state, data in policy_states.items():
                    if offense_str not in data["excludes"]:
                        if state in ["mute", "tempmute"] and not await can_mute(ctx):
                            continue
                        else:
                            states[state] = data["name"]

                view = StateChangeView(ctx, states)
                await self.bot.maybe_edit(message, embed=embed, view=view)
                await view.wait()
                state = view.value["values"][0]
                policies[offense_str]["state"] = state
                await self.bot.pool.execute(sql, json.dumps(policies), ctx.guild.id)
                await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                await show_policy_options(self, offense_str, message)

            elif view.value == "delete":
                policies[offense_str]["delete"] = not policies[offense_str]["delete"]
                await self.bot.pool.execute(sql, json.dumps(policies), ctx.guild.id)
                await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                await show_policy_options(self, offense_str, message)

            elif view.value == "temp_dur":
                embed = discord.Embed(title=f"Temporary punishment duration for {policy_strings[offense_str]['name']}", description="Please enter a valid integer value between **1 and 525960**! This will set how long temporary punishments for this category should last, in minutes.", color=self.bot.embedBlue)
                await self.bot.maybe_edit(message, embed=embed, view=None)
                try:
                    input = await self.bot.wait_for('message', check=check, timeout=180)
                except asyncio.TimeoutError:
                    await self.bot.maybe_delete(message)
                else:
                    try:
                        temp_dur = int(input.content)
                        if temp_dur < 1 or temp_dur > 525960:
                            raise ValueError
                        policies[offense_str]["temp_dur"] = temp_dur
                        await self.bot.pool.execute(sql, json.dumps(policies), ctx.guild.id)
                        await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                        await self.bot.maybe_delete(input)
                        await show_policy_options(self, offense_str, message)

                    except ValueError:
                        view = components.BackButtonView(ctx)
                        embed = discord.Embed(title="❌ Invalid data entered", description="You did not enter a valid integer between 1 and 525960.", color=self.bot.errorColor)
                        await self.bot.maybe_edit(message, embed=embed, view=view)
                        await self.bot.maybe_delete(input)

                        await view.wait()
                        if view.value == "back":
                            await show_policy_options(self, offense_str, message)
                        else:
                            await self.bot.maybe_delete(message)

            elif view.value == "count":
                embed = discord.Embed(title=f"Count for {policy_strings[offense_str]['name']}", description="Please enter a valid integer value **between 1 and 50**! This will set how many infractions count as a breach of the rules. (E.g. in the case of mention spamming, the number of mentions that count as mention spam)", color=self.bot.embedBlue)
                await self.bot.maybe_edit(message, embed=embed, view=None)
                try:
                    input = await self.bot.wait_for('message', check=check, timeout=180)
                except asyncio.TimeoutError:
                    await self.bot.maybe_delete(message)
                else:
                    try:
                        count = int(input.content)
                        if count < 1 or count > 50:
                            raise ValueError
                        policies[offense_str]["count"] = count
                        await self.bot.pool.execute(sql, json.dumps(policies), ctx.guild.id)
                        await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                        await self.bot.maybe_delete(input)
                        await show_policy_options(self, offense_str, message)

                    except ValueError:
                        view = components.BackButtonView(ctx)
                        embed = discord.Embed(title="❌ Invalid data entered", description="You did not enter a valid integer between 1 and 50.", color=self.bot.errorColor)
                        await self.bot.maybe_edit(message, embed=embed, view=view)
                        await self.bot.maybe_delete(input)

                        await view.wait()
                        if view.value == "back":
                            await show_policy_options(self, offense_str, message)
                        else:
                            await self.bot.maybe_delete(message)

            elif view.value == "words_list":
                words_list = ", ".join(policies[offense_str]["words_list"])
                embed = discord.Embed(title=f"Words list for {policy_strings[offense_str]['name']}", description=f"Please enter a list of comma-separated words that will be blacklisted! Current list of bad words:\n ||{bad_words}||", color=self.bot.embedBlue)
                await self.bot.maybe_edit(message, embed=embed, view=None)
                try:
                    input = await self.bot.wait_for('message', check=check, timeout=180)
                except asyncio.TimeoutError:
                    await self.bot.maybe_delete(message)
                else:
                    words_list = input.content.split(',')
                    for i, item in enumerate(words_list):
                        words_list[i] = item.strip()
                    words_list = list(filter(None, words_list)) # Remove empty values

                    policies[offense_str]["words_list"] = words_list
                    await self.bot.pool.execute(sql, json.dumps(policies), ctx.guild.id)
                    await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                    await self.bot.maybe_delete(input)
                    await show_policy_options(self, offense_str, message)

            elif view.value == "words_list_wildcard":
                words_list = ", ".join(policies[offense_str]["words_list_wildcard"])
                embed = discord.Embed(title=f"Words list (wildcard) for {policy_strings[offense_str]['name']}", description=f"Please enter a list of comma-separated words that will be blacklisted! Current list of bad words:\n ||{bad_words}||", color=self.bot.embedBlue)
                await self.bot.maybe_edit(message, embed=embed, view=None)
                try:
                    input = await self.bot.wait_for('message', check=check, timeout=180)
                except asyncio.TimeoutError:
                    await self.bot.maybe_delete(message)
                else:
                    words_list = input.content.split(',')
                    for i, item in enumerate(words_list):
                        words_list[i] = item.strip()
                    words_list = list(filter(None, words_list)) # Remove empty values

                    policies[offense_str]["words_list_wildcard"] = words_list
                    await self.bot.pool.execute(sql, json.dumps(policies), ctx.guild.id)
                    await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                    await self.bot.maybe_delete(input)
                    await show_policy_options(self, offense_str, message)
            
            elif view.value == "excluded_channels":
                embed = discord.Embed(title=f"Excluded channels for {policy_strings[offense_str]['name']}", description=f"Please enter a list of channel-mentions **seperated by spaces**! Enter `None` to reset the list. These will be excluded from the current automoderation action.", color=self.bot.embedBlue)
                await self.bot.maybe_edit(message, embed=embed, view=None)
                try:
                    input = await self.bot.wait_for('message', check=check, timeout=180)
                except asyncio.TimeoutError:
                    await self.bot.maybe_delete(message)
                else:
                    if input.content.lower() == "none":
                        channel_ids = []
                    else:
                        channel_mentions = input.content.split(' ')
                        channel_ids = []
                        try:
                            for channel_mention in channel_mentions:
                                channel = await commands.TextChannelConverter().convert(ctx, channel_mention)
                                channel_ids.append(channel.id)
                        except commands.ChannelNotFound:
                            embed = discord.Embed(title="❌ Invalid data entered", description="Could not find one or more channels. Please make sure you seperate all mentions by spaces.", color=self.bot.errorColor)
                            await self.bot.maybe_edit(message, embed=embed, view=view)
                            await self.bot.maybe_delete(input)

                    policies[offense_str]["excluded_channels"] = channel_ids
                    await self.bot.pool.execute(sql, json.dumps(policies), ctx.guild.id)
                    await self.bot.caching.refresh(table="mod_config", guild_id=ctx.guild.id)
                    await self.bot.maybe_delete(input)
                    await show_policy_options(self, offense_str, message)

            else:
                await self.bot.maybe_delete(message)

        await show_automod_menu(self, message)

    async def logging_conf(self, ctx, message:discord.Message):

        logging = self.bot.get_cog("Logging")

        async def show_logging_menu(self, message:discord.Message=None):

            log_channels = await logging.get_all_log_channels(ctx.guild.id)
            embed = discord.Embed(title="Logging Settings", description="Below you can see a list of logging events and channels associated with them. To change where a certain event's logs should be sent, click on the corresponding button.", color=self.bot.embedBlue)
            emojies = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🇦", "🇧", "🇨", "🇩"]

            for i, key in enumerate(log_channels.keys()):
                channel = ctx.guild.get_channel(log_channels[key])
                embed.add_field(name=f"{emojies[i]} {log_event_strings[key]}", value=channel.mention if channel else "Not set", inline=True)
            embed.add_field(name="​", value="​") #Spacer
            view = LoggingConfMainView(ctx, log_channels, emojies)
            if not message:
                message = await ctx.send(embed=embed, view=view)
            else:
                await self.bot.maybe_edit(message, embed=embed, view=view)
            
            await view.wait()
            if not view.value:
                await self.bot.maybe_delete(message)
            elif view.value == "back":
                await self.settings_main(ctx, message)
            else:
                await change_logging_channel(self, view.value, message)

        async def change_logging_channel(self, event:str, message:discord.Message):
            select_options = []
            select_options.append(discord.SelectOption(label="Disable", value="disable", description="Stop logging this event"))
            for channel in ctx.guild.channels:
                if isinstance(channel, (discord.TextChannel)):
                    select_options.append(discord.SelectOption(label="#"+channel.name, value=channel.id))
            embed = discord.Embed(title="Logging Settings", description=f"Please select a channel where the following event should be logged: `{log_event_strings[event]}`\nType/select `Disable` to disable this event.", color=self.bot.embedBlue)
            value, asked = await components.select_or_ask(ctx, options=select_options, placeholder="Select a channel...", embed=embed, message_to_edit=message)

            if value and not asked:
                if value["values"][0].lower() == "disable":
                    logging_channel = None
                else:
                    logging_channel = ctx.guild.get_channel(int(value["values"][0]))
            elif value and asked:
                if value.lower() == "disabled":
                    logging_channel = None
                else:
                    try:
                        logging_channel = await commands.GuildChannelConverter().convert(ctx, value)
                        if logging_channel.type not in [discord.ChannelType.news, discord.ChannelType.text]:
                            embed=discord.Embed(title="❌ Error: Invalid channel", description="Channel must be of type `text` or `news`. Operation cancelled.", color=self.bot.errorColor)
                            view = components.BackButtonView
                            await message.edit(embed=embed, view=components.BackButtonView)
                            await view.wait()
                            await show_logging_menu(self, message) if view.value == "back" else await self.bot.maybe_delete(message)
                    except commands.ChannelNotFound:
                        embed=discord.Embed(title="❌ Error: Channel not found.", description="Unable to locate channel. Operation cancelled.", color=self.bot.errorColor)
                        view = components.BackButtonView
                        await message.edit(embed=embed, view=components.BackButtonView)
                        await view.wait()
                        await show_logging_menu(self, message) if view.value == "back" else await self.bot.maybe_delete(message)
            if logging_channel:
                await logging.set_log_channel(event, ctx.guild.id, logging_channel.id)
            else:
                await logging.set_log_channel(event, ctx.guild.id, None)
            await show_logging_menu(self, message)

        await show_logging_menu(self, message)




def setup(bot):
    logger.info("Adding cog: Settings...")
    bot.add_cog(Settings(bot))
