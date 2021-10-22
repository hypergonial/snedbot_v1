import json
import logging
import re
import unicodedata
from typing import Dict

import discord
from discord.ext import commands

from extensions.utils import components


async def has_mod_perms(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, "mod_permitted")
async def is_automod_excluded(ctx):
    return await ctx.bot.custom_checks.has_permissions(ctx, "automod_excluded")

logger = logging.getLogger(__name__)

#The default set of automoderation policies

default_automod_policies = {
    'invites': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True
    },
    'spam': {
        'state': 'disabled',
        'temp_dur': 15,
    },
    'mass_mentions': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'count': 10
    },
    'zalgo': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
    },
    'attach_spam': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True
    },
    'link_spam': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True
    },
    'caps': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True
    },
    'bad_words': {
        'state': 'disabled',
        'temp_dur': 15,
        'delete': True,
        'words_list': ["motherfucker", "faggot", "cockfucker", "cunt", "nigger", "nigga", "porn", "pornography", "slut", "whore"]
    },
    'escalate': {
        'state': 'disabled'
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

class AutoModConfMainView(components.AuthorOnlyView):
    def __init__(self, ctx, policies:dict, *args, **kwargs):
        super().__init__(ctx, *args, **kwargs)
        self.value = None
        self.policies = policies
        self.ctx = ctx

        for policy in policies:
            self.add_item(self.MenuSelectButton(option=policy, label=policy_strings[policy]["name"], style=discord.ButtonStyle.blurple))
        self.add_item(self.MenuSelectButton(option="quit", label="Quit", style=discord.ButtonStyle.red))

    class MenuSelectButton(discord.ui.Button):
        def __init__(self, option:str, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.option = option

        async def callback(self, interaction: discord.Interaction):
            self.view.value = self.option
            self.view.stop()



class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mod_cog = self.bot.get_cog('Moderation')

        self.spam_cd_mapping = commands.CooldownMapping.from_cooldown(8, 10, commands.BucketType.member)
        self.spam_punish_cooldown_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.attach_spam_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.link_spam_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.escalate_prewarn_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.escalate_cd_mapping = commands.CooldownMapping.from_cooldown(2, 30, commands.BucketType.member)

        self.policy_strings = policy_strings
        self.default_automod_policies = default_automod_policies


    async def get_policies(self, guild_id:int) -> dict:
        '''
        Checks for and returns the auto-moderation policies for the given guild.
        This function should always be used to retrieve auto-moderation policies.
        '''
        records = await self.bot.caching.get(table="mod_config", guild_id=guild_id)

        policies = json.loads(records[0]["automod_policies"]) if records else self.default_automod_policies

        for key in self.default_automod_policies.keys(): #Ensure that values always exist
            if key not in policies:
                policies[key] = self.default_automod_policies[key]

        invalid = []
        for key in policies:
            if key not in self.default_automod_policies.keys(): #Ensure that invalid values don't exist
                invalid.append(key) #To avoid modifying dict size during iteration
        for key in invalid:
            policies.pop(key)

        return policies

    @commands.command(name="automoderation", aliases=["automod"], help="Display and configure automoderation settings.", description="List all current automoderation settings with the ability to modify them.", usage="automoderation")
    @commands.guild_only()
    @commands.check(has_mod_perms)
    async def automod_conf_cmd(self, ctx):

        async def show_main_menu(self, message:discord.Message=None):

            policies = await self.get_policies(ctx.guild.id)
            embed = discord.Embed(title="Automoderation Settings", description="Below you can see a summary of the current automoderation settings. To see more details about a specific entry or change their settings, press the corresponding button.", color=self.bot.embedBlue)
            for key in policies.keys():
                embed.add_field(name=f"{self.policy_strings[key]['name']}", value=policies[key]["state"].capitalize(), inline=True)

            view = AutoModConfMainView(ctx, policies)
            if not message:
                message = await ctx.send(embed=embed, view=view)
            else:
                await message.edit(embed=embed, view=view)
            
            await view.wait()
            if view.value == "quit" or not view.value:
                await message.delete()
            else:
                pass # show menu thing

            return message

        msg = await show_main_menu(self)


    async def automod_punish(self, message, offender:discord.Member, offense:str, reason:str, original_offense:str=None):
        '''
        Decides and does the punishment set for the specified offense in the dashboard.
        original_offense is only used recursively with escalate
        '''
        valid_offenses = ["invites", "spam", "mass_mentions", "zalgo", "attach_spam", "link_spam", "caps", "bad_words", "escalate"]
        if offense not in valid_offenses:
            raise ValueError(f"{offense} is not a valid offense-type. Valid types are: {', '.join(valid_offenses)}")

        ctx = await self.bot.get_context(message)

        bot_perms = ctx.channel.permissions_for(ctx.guild.me)
        if not bot_perms.ban_members or not bot_perms.manage_roles or not bot_perms.manage_messages or not bot_perms.kick_members:
            return

        if not await self.bot.custom_checks.module_is_enabled(ctx, "moderation"):
            return

        if await is_automod_excluded(ctx) or await has_mod_perms(ctx):
            return

        notices = {
                    "invites": "posting discord invites",
                    "mass_mentions": "mass mentioning users",
                    "zalgo": "using zalgo in your messages",
                    "attach_spam": "spamming attachments",
                    "link_spam": "posting links too fast",
                    "caps": "using excessive caps in your message",
                    "bad_words": "using bad words in your message"
                }

        policies = await self.get_policies(ctx.guild.id)
        policy_state = policies[offense]["state"] #This will decide the type of punishment
        if not original_offense:
            temp_dur = policies[offense]["temp_dur"] #Get temporary duration
            should_delete = policies[offense]["delete"] if offense != "spam" else False
        else:
            temp_dur = policies[original_offense]["temp_dur"] #Original offense overrides current, if present
            should_delete = False

        if policy_state not in ["disabled", "delete", "warn", "notice", "escalate"]: #Get temporary punishment duration in minutes
            records = await self.bot.caching.get(table="mod_config", guild_id=ctx.guild.id)
            #TODO: Implement this
            dm_users_on_punish = records[0]["dm_users_on_punish"] if records else False

        if policy_state == "disabled":
            return
        
        if should_delete:
            await ctx.message.delete()


        if policy_state == "warn":
            await self.mod_cog.warn(ctx, offender, ctx.guild.me, reason=f"Warned by auto-moderator for {reason}.")

        elif policy_state == "notice":
            embed=discord.Embed(title="💬 Auto-Moderation Notice", description=f"**{offender}**, please refrain from {notices[offense]}!", color=self.bot.warnColor)
            await ctx.send(content=offender.mention, embed=embed)

        
        elif policy_state == "escalate":
            bucket = self.escalate_cd_mapping.get_bucket(ctx.message)
            bucket_prewarn = self.escalate_prewarn_cd_mapping.get_bucket(ctx.message)

            if bucket.update_rate_limit():
                #If user continues ignoring warnings
                await self.automod_punish(message, offender, offense="escalate", reason="previous offenses", original_offense=offense)

            elif bucket_prewarn.update_rate_limit():
                #Issue warning after notice
                await self.mod_cog.warn(ctx, offender, ctx.guild.me, reason=f"Warned by auto-moderator for previous offenses.")
            else:
                #Issue a notice, not a formal warning first

                embed=discord.Embed(title="💬 Auto-Moderation Notice", description=f"**{offender}**, please refrain from {notices[offense]}!", color=self.bot.warnColor)
                await ctx.send(content=offender.mention, embed=embed)


        elif policy_state == "tempmute":
            await self.mod_cog.mute(ctx, offender, ctx.guild.me, duration=f"{temp_dur} minutes", reason=f"Muted by auto-moderator for {reason}.")
            embed=discord.Embed(title="🔇 User muted", description="**{offender}** has been muted for **{temp_dur}** minutes.\n**Reason:**```Muted by auto-moderator for {reason}.```".format(offender=offender, temp_dur=temp_dur, reason=reason), color=self.bot.errorColor)
            await ctx.send(embed=embed)
        
        elif policy_state == "kick":
            await self.mod_cog.kick(ctx, offender, ctx.guild.me, reason=f"Kicked by auto-moderator for {reason}.")
        
        elif policy_state == "softban":
            await self.mod_cog.ban(ctx, offender, ctx.guild.me, soft=True, reason=f"Soft-banned by auto-moderator for {reason}.")
        
        elif policy_state == "tempban":
            await self.mod_cog.ban(ctx, offender, ctx.guild.me, duration=f"{temp_dur} minutes", reason=f"Temp-banned by auto-moderator for {reason}.")

        elif policy_state == "permaban":
            await self.mod_cog.ban(ctx, offender, ctx.guild.me, reason=f"Permanently banned by auto-moderator for {reason}.")

                

    @commands.Cog.listener()
    async def on_message(self, message):
        '''
        Auto-Moderation
        '''

        if not self.bot.is_ready() or not self.bot.caching.is_ready:
            return

        if message.guild is None:
            return

        if not isinstance(message.author, discord.Member) or message.author.bot:
            return


        policies = await self.get_policies(message.guild.id)

        mentions = sum(member.id != message.author.id and not member.bot for member in message.mentions)
        if mentions >= policies["mass_mentions"]["count"]:
            '''Mass Mentions'''
            await self.automod_punish(message, offender=message.author, offense="mass_mentions", reason=f"spamming {mentions} mentions in a single message")


        elif self.spam_cd_mapping.get_bucket(message).update_rate_limit(): #If user exceeded spam limits
            '''Spam'''
            punish_cd_bucket = self.spam_punish_cooldown_cd_mapping.get_bucket(message)
            if not punish_cd_bucket.update_rate_limit(): # Only try punishing once every 30 seconds
                await self.automod_punish(message, offender=message.author, offense="spam", reason="spam")
        
  
        elif len(message.content) > 7:
            '''Caps'''
            upper = 0
            for char in message.content:
                if char.isupper():
                    upper += 1
            if upper/len(message.content) > 0.8:
                await self.automod_punish(message, offender=message.author, offense="caps", reason=f"using excessive caps")
        
        for word in message.content.split(" "):
            if word in policies["bad_words"]["words_list"]:
                await self.automod_punish(message, offender=message.author, offense="bad_words", reason=f"usage of bad words")
        for bad_word in policies["bad_words"]["words_list"]: #Check bad_words with spaces in them
            if " " in bad_word and bad_word in message.content:
                await self.automod_punish(message, offender=message.author, offense="bad_words", reason=f"usage of bad words (expression)")

        else: #If the obvious stuff didn't work
            '''Discord Invites, Links, Attachments & Zalgo'''
            invite_regex = re.compile(r"(?:https?://)?discord(?:app)?\.(?:com/invite|gg)/[a-zA-Z0-9]+/?")
            link_regex = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")
            invite_matches = invite_regex.findall(message.content)
            link_matches = link_regex.findall(message.content)
            if invite_matches:
                await self.automod_punish(message, offender=message.author, offense="invites", reason="posting Discord invites")
            elif link_matches:
                if len(link_matches) > 7:
                    await self.automod_punish(message, offender=message.author, offense="link_spam", reason="having too many links in a single message")
                else:
                    bucket = self.link_spam_cd_mapping.get_bucket(message)
                    if bucket.update_rate_limit():
                        await self.automod_punish(message, offender=message.author, offense="link_spam", reason="posting links too quickly")
            elif len(message.attachments) > 0:
                bucket = self.attach_spam_cd_mapping.get_bucket(message)
                if bucket.update_rate_limit():
                    await self.automod_punish(message, offender=message.author, offense="attach_spam", reason="posting images/attachments too quickly")
            else: #Check zalgo
                count = 0
                for char in message.content:
                    if unicodedata.combining(char):
                        count += 1
                        if count > 4:
                            await self.automod_punish(message, offender=message.author, offense="zalgo", reason="using zalgo text")
                            break
                    else:
                        count = 0


def setup(bot):
    logger.info("Adding cog: AutoMod...")
    bot.add_cog(AutoMod(bot))
