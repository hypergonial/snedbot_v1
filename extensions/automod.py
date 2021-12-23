import asyncio
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



class AutoMod(commands.Cog, name="Auto-Moderation"):
    def __init__(self, bot):
        self.bot = bot
        self.mod_cog = self.bot.get_cog('Moderation')

        self.spam_cd_mapping = commands.CooldownMapping.from_cooldown(8, 10, commands.BucketType.member)
        self.spam_punish_cooldown_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.attach_spam_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.link_spam_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.escalate_prewarn_cd_mapping = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.member)
        self.escalate_cd_mapping = commands.CooldownMapping.from_cooldown(2, 30, commands.BucketType.member)

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

            for nested_key in self.default_automod_policies[key].keys(): #Ensure that nested values always exist
                if nested_key not in policies[key]:
                    policies[key][nested_key] = self.default_automod_policies[key][nested_key]

        invalid = []
        for key in policies:
            if key not in self.default_automod_policies.keys(): #Ensure that invalid values don't exist
                invalid.append(key) #To avoid modifying dict size during iteration
        for key in invalid:
            policies.pop(key)

        return policies


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

        if not original_offense and ctx.channel.id in policies[offense]["excluded_channels"]:
            return

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
            await self.bot.maybe_delete(ctx.message)


        if policy_state == "warn":
            await self.mod_cog.warn(ctx, offender, ctx.guild.me, reason=f"Warned by auto-moderator for {reason}.")

        elif policy_state == "notice":
            embed=discord.Embed(title="💬 Auto-Moderation Notice", description=f"**{offender}**, please refrain from {notices[offense]}!", color=self.bot.warnColor)
            await ctx.send(content=offender.mention, embed=embed, delete_after=20)

        
        elif policy_state == "escalate":
            bucket = self.escalate_cd_mapping.get_bucket(ctx.message)
            bucket_prewarn = self.escalate_prewarn_cd_mapping.get_bucket(ctx.message)

            if bucket.update_rate_limit():
                #If user continues ignoring warnings
                await self.automod_punish(message, offender, offense="escalate", reason=f"previous offenses ({offense})", original_offense=offense)

            elif bucket_prewarn.update_rate_limit():
                #Issue warning after notice
                await self.mod_cog.warn(ctx, offender, ctx.guild.me, reason=f"Warned by auto-moderator for previous offenses. ({offense})")
            else:
                #Issue a notice, not a formal warning first

                embed=discord.Embed(title="💬 Auto-Moderation Notice", description=f"**{offender}**, please refrain from {notices[offense]}!", color=self.bot.warnColor)
                await ctx.send(content=offender.mention, embed=embed, delete_after=20)


        elif policy_state == "timeout":
            await self.mod_cog.timeout(ctx, offender, ctx.guild.me, duration=f"{temp_dur} minutes", reason=f"Timed out by auto-moderator for {reason}.")
            embed=discord.Embed(title="🔇 User timed out", description="**{offender}** has been timed out for **{temp_dur}** minutes.\n**Reason:**```Timed out by auto-moderator for {reason}.```".format(offender=offender, temp_dur=temp_dur, reason=reason), color=self.bot.errorColor)
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
            msg_content = ''.join(char for char in message.content if char.isalnum()) #Remove non-alphanumerical chars
            for char in msg_content:
                if char.isupper():
                    upper += 1
            if upper/len(msg_content) > 0.3:
                await self.automod_punish(message, offender=message.author, offense="caps", reason=f"using excessive caps")
        
        for word in message.content.split(" "):
            if word in policies["bad_words"]["words_list"]:
                return await self.automod_punish(message, offender=message.author, offense="bad_words", reason=f"usage of bad words")
            else:
                for bad_word in policies["bad_words"]["words_list"]: #Check bad_words with spaces in them
                    if " " in bad_word and bad_word in message.content:
                        return await self.automod_punish(message, offender=message.author, offense="bad_words", reason=f"usage of bad words (expression)")
                    else:
                        for word in policies["bad_words"]["words_list_wildcard"]:
                            if word in message.content:
                                return await self.automod_punish(message, offender=message.author, offense="bad_words", reason=f"usage of bad words (wildcard)")

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
    logger.info("Adding cog: Auto-Moderation...")
    bot.add_cog(AutoMod(bot))
