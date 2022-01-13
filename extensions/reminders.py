import datetime
import json
import logging

import discord
from discord.ext import commands

from classes.bot import SnedBot
from classes.timer import Timer

logger = logging.getLogger(__name__)


class ReminderView(discord.ui.View):
    """
    A view to handle reminder additional recipients support
    """

    def __init__(self, ctx, timer_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ctx = ctx
        self.timer_id = timer_id

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if hasattr(self, "message"):
            await self.message.edit(view=self)

    @discord.ui.button(
        emoji="✉️",
        label="Remind me too!",
        style=discord.ButtonStyle.blurple,
    )
    async def add_recipient(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        try:
            timer_cog = self.ctx.bot.get_cog("Timers")
            timer = await timer_cog.get_timer(self.timer_id, self.ctx.guild.id)
        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid interaction",
                description="Oops! It looks like this reminder is no longer valid!",
                color=self.ctx.bot.error_color,
            )
            return await interaction.response.send_message(
                embed=embed,
                ephemeral=True,
            )
        else:
            notes = json.loads(timer.notes)
            if timer.user_id == interaction.user.id:
                embed = discord.Embed(
                    title="❌ Invalid interaction",
                    description="You cannot do this on your own reminder.",
                    color=self.ctx.bot.error_color,
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            if interaction.user.id not in notes["additional_recipients"]:
                if len(notes["additional_recipients"]) < 50:
                    notes["additional_recipients"].append(interaction.user.id)
                    await timer_cog.update_timer(
                        datetime.datetime.fromtimestamp(timer.expires, tz=datetime.timezone.utc),
                        self.timer_id,
                        self.ctx.guild.id,
                        new_notes=json.dumps(notes),
                    )
                    embed = discord.Embed(
                        title="✅ Signed up to reminder",
                        description="You will also be notified when this reminder is due!",
                        color=self.ctx.bot.embed_green,
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    embed = discord.Embed(
                        title="❌ Invalid interaction",
                        description="Oops! Looks like too many people signed up for this reminder. Try creating a new reminder! (Max cap: 50)",
                        color=self.ctx.bot.error_color,
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                notes["additional_recipients"].remove(interaction.user.id)
                await timer_cog.update_timer(
                    datetime.datetime.fromtimestamp(timer.expires, tz=datetime.timezone.utc),
                    self.timer_id,
                    self.ctx.guild.id,
                    new_notes=json.dumps(notes),
                )
                embed = discord.Embed(
                    title="✅ Removed from reminder",
                    description="Removed you from the list of recipients!",
                    color=self.ctx.bot.embed_green,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)


class Reminders(commands.Cog):
    def __init__(self, bot: SnedBot):
        self.bot = bot
        self.timer_cog = self.bot.get_cog("Timers")

    async def remindertime(self, timestr: str):
        """
        Tries removing the times & dates from the beginning or end of a string, while converting the times to datetime object via converttime()
        Used to create a reminder note
        """
        # Yeah this is stupid lol
        # TODO: Rework this garbage
        time, strings = await self.timer_cog.converttime(timestr)

        for string in strings:
            timestr = timestr.strip()
            if timestr.startswith(string):
                timestr = timestr.replace(string, "")
            elif timestr.startswith("in " + string + " to"):
                timestr = timestr.replace("in " + string + " to", "")
            elif timestr.startswith("in " + string):
                timestr = timestr.replace("in " + string, "")
            elif timestr.startswith(string + " from now"):
                timestr = timestr.replace(string + " from now", "")
            elif timestr.startswith(string + " later"):
                timestr = timestr.replace(string + " later", "")
            elif timestr.startswith("to "):
                timestr = timestr[3 : len(timestr)]
            elif timestr.startswith("for "):
                timestr = timestr[4 : len(timestr)]
            elif timestr.startswith("and "):
                timestr = timestr[4 : len(timestr)]
            if timestr.startswith(" "):
                timestr = timestr[1 : len(timestr)]

        for string in strings:
            timestr = timestr.strip()
            if timestr.endswith("in " + string):
                timestr = timestr.replace("in " + string, "")
            elif timestr.endswith("after " + string):
                timestr = timestr.replace("after" + string, "")
            elif timestr.endswith("in " + string + " from now"):
                timestr = timestr.replace("in " + string + " from now", "")
            elif timestr.endswith(string + " from now"):
                timestr = timestr.replace(string + " from now", "")
            elif timestr.endswith(string + " later"):
                timestr = timestr.replace(string + " later", "")
            elif timestr.endswith(string):
                timestr = timestr.replace(string, "")

        timestr = timestr.capitalize()
        return time, timestr

    @commands.command(
        aliases=["remindme", "remind"],
        usage="reminder <when>",
        help="Sets a reminder to the specified time.",
        description="""Sets a reminder to the specified time, with an optional message.
**Time formatting:**

__Relative:__
`s` or `second(s)`
`m` or `minute(s)`
`h` or `hour(s)`
`d` or `day(s)`
`w` or `week(s)`
`M` or `month(s)`
`Y` or `year(s)`

*Examples:* `reminder in 2 hours to go sleep` or `reminder 5d example message`

__Absolute:__
`YYYY-MM-dd hh-mm` (in UTC)
`YYYY-MM-dd` (in UTC)

*Examples:* `reminder 2021-04-03 12:35 example` or `reminder 2021-04-03 test`
    """,
    )
    @commands.guild_only()
    async def reminder(self, ctx, *, timestr):
        if len(timestr) >= 1000:

            embed = discord.Embed(
                title="❌ Reminder too long",
                description="Your reminder cannot exceed **1000** characters!",
                color=self.bot.error_color,
            )
            await ctx.send(embed=embed)
            return

        await ctx.channel.trigger_typing()

        try:
            time, timestr = await self.remindertime(timestr)
            logger.debug(f"Received conversion: {time}")
            print(timestr)

        except ValueError as error:

            embed = discord.Embed(
                title="❌ Error: Invalid data entered",
                description=f"Your timeformat is invalid! Type `{ctx.prefix}help reminder` to see valid time formatting.\n**Error:** {error}",
                color=self.bot.error_color,
            )
            await ctx.send(embed=embed)

        else:

            if (time - datetime.datetime.now(datetime.timezone.utc)).total_seconds() >= 31536000 * 5:

                embed = discord.Embed(
                    title="❌ Error: Invalid data entered",
                    description="Sorry, but that's a bit too far in the future.",
                    color=self.bot.error_color,
                )
                await ctx.send(embed=embed)
            else:

                logger.debug(f"Timestrs length is: {len(timestr)}")
                if timestr is None or len(timestr) == 0:
                    timestr = "..."
                reminder_data = {
                    "message": timestr,
                    "jump_url": ctx.message.jump_url,
                    "additional_recipients": [],
                }
                embed = discord.Embed(
                    title="✅ Reminder set",
                    description="Reminder set for:  {timestamp} ({timestampR})".format(
                        timestamp=discord.utils.format_dt(time),
                        timestampR=discord.utils.format_dt(time, style="R"),
                    ),
                    color=self.bot.embed_green,
                )
                embed = self.bot.add_embed_footer(ctx, embed)
                timer = await self.timer_cog.create_timer(
                    expires=time,
                    event="reminder",
                    guild_id=ctx.guild.id,
                    user_id=ctx.author.id,
                    channel_id=ctx.channel.id,
                    notes=json.dumps(reminder_data),
                )
                view = ReminderView(ctx, timer.id, timeout=300)
                view.message = await ctx.send(embed=embed, view=view)

    @commands.command(
        usage="reminders",
        help="Lists all reminders you have pending.",
        description="Lists all your pending reminders, you can get a reminder's ID here to delete it.",
        aliases=["myreminders", "listreminders"],
    )
    @commands.guild_only()
    async def reminders(self, ctx):
        results = await self.bot.pool.fetch(
            """SELECT * FROM timers WHERE guild_id = $1 AND user_id = $2 AND event = 'event' ORDER BY expires LIMIT 10""",
            ctx.guild.id,
            ctx.author.id,
        )
        timers = []
        reminderstr = ""
        for result in results:

            note_stripped = json.loads(result.get("notes"))["message"].replace(
                "\n", " "
            )  # Avoid the reminder dialog breaking
            if len(note_stripped) > 50:
                note_stripped = f"{note_stripped[slice(47)]}..."

            timers.append(
                Timer(
                    id=result.get("id"),
                    guild_id=result.get("guild_id"),
                    user_id=result.get("user_id"),
                    channel_id=result.get("channel_id"),
                    event=result.get("event"),
                    expires=result.get("expires"),
                    notes=note_stripped,
                )
            )

        if len(timers) != 0:

            for timer in timers:

                time = datetime.datetime.fromtimestamp(timer.expires)

                if timer.notes:
                    reminderstr = (
                        reminderstr
                        + f"**ID: {timer.id}** - {discord.utils.format_dt(time)} ({discord.utils.format_dt(time, style='R')})\n{timer.notes}\n"
                    )
                else:
                    reminderstr = (
                        reminderstr
                        + f"**ID: {timer.id}** - {discord.utils.format_dt(time)} ({discord.utils.format_dt(time, style='R')})\n"
                    )
        else:
            reminderstr = f"You have no reminders. You can set one via `{ctx.prefix}reminder`!"
        embed = discord.Embed(
            title="✉️ Your reminders:",
            description=reminderstr,
            color=self.bot.embed_blue,
        )
        embed = self.bot.add_embed_footer(ctx, embed)
        await ctx.send(embed=embed)

    @commands.command(
        usage="delreminder <reminder_ID>",
        help="Deletes a reminder.",
        description="Deletes a reminder by it's ID, which you can obtain via the `reminders` command.",
    )
    @commands.guild_only()
    async def delreminder(self, ctx, entry_id: int):

        try:
            self.timer_cog.cancel_timer(entry_id, ctx.guild.id)
        except ValueError:
            embed = discord.Embed(
                title="❌ Reminder not found",
                description=f"Cannot find reminder with ID **{entry_id}**.",
                color=self.bot.error_color,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="✅ Reminder deleted",
                description=f"Reminder **{entry_id}** has been deleted.",
                color=self.bot.embed_green,
            )
            embed = self.bot.add_embed_footer(ctx, embed)
            await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer: Timer):
        logger.debug("on_reminder_timer_complete received.")
        guild = self.bot.get_guild(timer.guild_id)
        if guild is None:  # Check if bot did not leave guild
            return
        channel = await self.bot.fetch_channel(timer.channel_id)
        if guild.get_member(timer.user_id) != None:  # Check if user did not leave guild
            user = guild.get_member(timer.user_id)
            notes = json.loads(timer.notes)
            embed = discord.Embed(
                title=f"✉️ {user.display_name}, your reminder:",
                description=f"{notes['message']}\n\n[Jump to original message!]({notes['jump_url']})",
                color=self.bot.embed_blue,
            )
            pings = [user.mention]
            if len(notes["additional_recipients"]) > 0:
                for user_id in notes["additional_recipients"]:
                    if guild.get_member(user_id):
                        pings.append(guild.get_member(user_id).mention)
            try:
                await channel.send(embed=embed, content=" ".join(pings))
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                try:  # Fallback to DM if cannot send in channel
                    await user.send(
                        embed=embed,
                        content="I lost access to the channel this reminder was sent from, so here it is!",
                    )
                except discord.Forbidden:
                    logger.info(f"Failed to deliver a reminder to user {user}.")
                    return


def setup(bot: SnedBot):
    logger.info("Adding cog: Timers...")
    bot.add_cog(Reminders(bot))
