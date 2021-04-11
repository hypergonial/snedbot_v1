import discord
from discord.ext import commands, tasks
import logging
import datetime
import aiosqlite
import asyncio
import re
import Levenshtein as lev
import gettext

'''
The repo https://github.com/Rapptz/RoboDanny was massive help when writing this code,
and I used the same general structure as seen in /cogs/reminder.py there.
'''

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

class Timer():
    def __init__(self, id, guild_id, user_id,event, channel_id=None, expires=None, notes=None):
        self.id = id
        self.guild_id = guild_id
        self.user_id = user_id
        self.channel_id = channel_id
        self.event = event
        self.expires = expires
        self.notes = notes

class Timers(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.current_timer = None
        self.db = bot.db
        self.currenttask = bot.loop.create_task(self.dispatch_timers())
        if self.bot.lang == "de":
            de = gettext.translation('timers', localedir=self.bot.localePath, languages=['de'])
            de.install()
            self._ = de.gettext
        elif self.bot.lang == "en":
            self._ = gettext.gettext
        #Fallback to english
        else :
            logging.error("Invalid language, fallback to English.")
            self._ = gettext.gettext

    def cog_unload(self):
        self.currenttask.cancel()
    
    #Tries converting a string to datetime.datetime via regex, returns datetime.datetime if successful, otherwise raise ValueError
    #Result of 12 hours of pain #remember
    async def converttime(self, timestr : str):
        logging.debug(f"String passed: {timestr}")
        #timestr = timestr.replace(' ', '')
        #Get any pair of <number><word> with optional space in between, and return them as a dict (sort of)
        time_regex = re.compile(r"(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)")
        time_letter_dict = {"h":3600, "s":1, "m":60, "d":86400, "w":86400*7, "M":86400*30, "Y":86400*365}
        time_word_dict = {"hour":3600, "second":1, "minute":60, "day": 86400, "week": 86400*7, "month":86400*30, "year":86400*365}
        matches = time_regex.findall(timestr)
        time = 0
        logging.debug(f"Matches: {matches}")
        for val, category in matches:
            val = val.replace(',', '.') #Replace commas with periods to correctly register decimal places
            #If this is a single letter
            if len(category) == 1:
                if category in time_letter_dict.keys():
                    time += time_letter_dict[category]*float(val)
            else:
                #If a partial match is found with any of the keys
                #Reason for making the same code here is because words are case-insensitive, as opposed to single letters
                for string in time_word_dict.keys():
                    if lev.distance(category.lower(), string.lower()) <= 2: #If str has 2 or less different letters (One for plural, one for being dumb)
                        time += time_word_dict[string]*float(val)
                        break

        logging.debug(f"Time: {time}")
        if time > 0:
            time = datetime.datetime.utcnow() + datetime.timedelta(seconds=time)
        else: #If time is 0, then we failed to parse or the user indeed provided 0, which makes no sense, so we raise an error.
             raise ValueError("Failed converting time from string.")
        return time

    #Gets the timer the first timer that is about to expire in X days, and returns it. Return None if no timers are found in that scope.
    async def get_latest_timer(self, days=7):
        await self.bot.wait_until_ready() #This must be included or you get a lot of NoneType errors while booting up, and timers do not get delivered
        logging.debug("Getting latest timer...")
        cursor = await self.db.execute("SELECT * FROM timers WHERE expires < ? ORDER BY expires LIMIT 1", [round((datetime.datetime.utcnow() + datetime.timedelta(days=days)).timestamp())])
        result = await cursor.fetchone()
        logging.debug(f"Latest timer: {result}")
        if result != None:
            timer = Timer(id=result[0],guild_id=result[1],user_id=result[2],channel_id=result[3],event=result[4],expires=result[5],notes=result[6])
            #self.current_timer = timer
            logging.debug(f"Timer latest: {timer}")
            return timer
    

    #The actual calling of the timer, deletes it from the db & dispatches the event
    async def call_timer(self, timer : Timer):
        logging.debug("Deleting timer from DB")
        logging.debug("Deleting entry {timerid}".format(timerid=timer.id))
        await self.db.execute("DELETE FROM timers WHERE id = ?", [timer.id])
        await self.db.commit()
        #Set the currently evaluated timer to None
        self.current_timer = None
        logging.debug("Deleted")
        '''
        Dispatch an event named eventname_timer_complete, which will cause all listeners 
        for this event to fire. This function is not documented, so if anything breaks, it
        is probably in here. It passes on the timer's dict.
        '''
        logging.debug("Dispatching..")
        event = timer.event
        event_name = f'{event}_timer_complete'
        logging.debug(event_name)
        self.bot.dispatch(event_name, timer)
        logging.debug("Dispatched.")

    async def dispatch_timers(self):
        logging.debug("Dispatching timers.")
        try:
            while not self.bot.is_closed():
                logging.debug("Getting timer")
                timer = await self.get_latest_timer(days=40)
                self.current_timer=timer
                now = round(datetime.datetime.utcnow().timestamp())
                logging.debug(f"Now: {now}")
                logging.debug(f"Timer: {timer}")
                logging.debug(f"Expiry: {timer.expires}")
                logging.debug("Has timer")
                if timer:
                    logging.debug("Evaluating timer.")
                    if timer.expires >= now:
                        sleep_time = (timer.expires - now)
                        logging.info(f"Awaiting next timer: '{timer.event}', which is in {sleep_time}s")
                        await asyncio.sleep(sleep_time)

                    logging.info(f"Dispatching timer: {timer.event}")
                    await self.call_timer(timer)
                else:
                    break #This is necessary because if on start-up there is no stored timer, it will go into an infinite loop
        
        except asyncio.CancelledError:
            raise
        except(OSError, discord.ConnectionClosed):
            self.currenttask.cancel()
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())


    async def create_timer(self, expiry : datetime.datetime, event :str, guild_id : int, user_id:int, channel_id:int=None, *, notes:str=None):
        logging.debug(f"Expiry: {expiry}")
        delta = (datetime.datetime.utcnow() - expiry).total_seconds()
        expiry=round(expiry.timestamp()) #Converting it to time since epoch
        if delta >= (86400 * 40):
            logging.warn("Tried creating timer that is too long.")
            return
        await self.db.execute("INSERT INTO timers (guild_id, channel_id, user_id, event, expires, notes) VALUES (?, ?, ?, ?, ?, ?)", [guild_id, channel_id, user_id, event, expiry, notes])
        await self.db.commit()
        logging.debug("Saved to database.")
        #If there is already a timer in queue, and it has an expiry that is further than the timer we just created
        #Then we reboot the dispatch_timers() function to re-check for the latest timer.
        if self.current_timer and expiry < self.current_timer.expires:
            logging.debug("Reshuffled timers, this is now the latest timer.")
            self.currenttask.cancel()
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())
        elif self.current_timer is None:
            self.currenttask = self.bot.loop.create_task(self.dispatch_timers())


    
    @commands.command(aliases=["remindme", "remind"], usage="reminder <when>", help="Sets a reminder to the specified time.", description="Sets a reminder with at the specified time, with an optional message.\n\n**Time formatting:**\n`s` or `second(s)`\n`m` or `minute(s)`\n`h` or `hour(s)`\n`d` or `day(s)`\n`w` or `week(s)`\n`M` or `month(s)`\n`Y` or `year(s)`\n\n**Example:** `reminder in 2 hours to go sleep` or `reminder 5d example message`")
    @commands.guild_only()
    async def reminder(self, ctx, *, timestr):
        note = timestr+f"\n\n[Jump to original message!]({ctx.message.jump_url})"
        if len(note) >= 2048:
            embed = discord.Embed(title="❌ " + self._("Reminder too long"), description=self._("Your reminder cannot exceed **2048** characters!"),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        try:
            time = await self.converttime(timestr)
            logging.debug(f"Received conversion: {time}")
        except ValueError:
            embed = discord.Embed(title=self.bot.errorDataTitle, description=self._("Your timeformat is invalid! Type `{prefix}help reminder` to see valid time formatting.").format(prefix=self.bot.prefix),color=self.bot.errorColor)
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(title="✅ " + self._("Reminder set"), description=self._("Reminder set for: `{time_year}-{time_month}-{time_day} {time_hour}:{time_minute} (UTC)`").format(time_year=time.year, time_month=str(time.month).rjust(2, '0'), time_day=str(time.day).rjust(2, '0'), time_hour=str(time.hour).rjust(2, '0'), time_minute=str(time.minute).rjust(2, '0')), color=self.bot.embedGreen)
        embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
        await self.create_timer(expiry=time, event="reminder", guild_id=ctx.guild.id,user_id=ctx.author.id, channel_id=ctx.channel.id, notes=note)
    
    @commands.command(usage="reminders", help="Lists all reminders you have pending.", description="Lists all your pending reminders, you can get a reminder's ID here to delete it.", aliases=["myreminders", "listreminders"])
    @commands.guild_only()
    async def reminders(self, ctx):
        cursor = await self.db.execute("SELECT * FROM timers WHERE guild_id = ? AND user_id = ?", [ctx.guild.id, ctx.author.id])
        results = await cursor.fetchall()
        timers = []
        reminderstr = ""
        for result in results :
            if result[4] == "reminder":
                timers.append(Timer(id=result[0],guild_id=result[1],user_id=result[2],channel_id=result[3],event=result[4],expires=result[5],notes=result[6]))
        print(timers)
        i = 0
        if len(timers) != 0:
            for timer in timers:
                time = datetime.datetime.fromtimestamp(timer.expires)
                if timer.notes:
                    reminderstr = reminderstr + f"ID: **{timer.id}** - `{time.year}-{time.month}-{time.day} {time.hour}:{time.minute} (UTC)` - `{timer.notes[slice(15)]}...`\n"
                else:
                    reminderstr = reminderstr + f"ID: **{timer.id}** - `{time.year}-{time.month}-{time.day} {time.hour}:{time.minute} (UTC)`\n"
                if i == 10:
                    break
                i +=1
        else:
            reminderstr = self._("You have no reminders. You can set one via `{prefix}reminder`!").format(prefix=self.bot.prefix)
        embed=discord.Embed(title="✉️ " + self._("Your reminders:"),description=reminderstr, color=self.bot.embedBlue)
        embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)
    
    @commands.command(usage="delreminder <reminder_ID>", help="Deletes a reminder.", description="Deletes a reminder by it's ID, which you can obtain via the `reminders` command.")
    @commands.guild_only()
    async def delreminder(self, ctx, ID):
        cursor = await self.db.execute("SELECT ID FROM timers WHERE user_id = ? AND id = ?", [ctx.author.id, ID])
        result = await cursor.fetchone()
        if result:
            await self.db.execute("DELETE FROM timers WHERE user_id = ? AND id = ?", [ctx.author.id, ID])
            await self.db.commit()
            embed = discord.Embed(title="✅ " + self._("Reminder deleted"), description=self._("Reminder **{ID}** has been deleted.").format(ID=ID), color=self.bot.embedGreen)
            embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)
            #If we just deleted the currently running timer, then we re-evaluate to find the next timer.
            if self.current_timer and self.current_timer.id == int(ID):
                self.currenttask.cancel()
                self.currenttask = self.bot.loop.create_task(self.dispatch_timers())
        else:
            embed = discord.Embed(title="❌ " + self._("Reminder not found"), description=self._("Cannot find reminder with ID **{ID}**.").format(ID=ID), color=self.bot.errorColor)
            embed.set_footer(text=self.bot.requestFooter.format(user_name=ctx.author.name, discrim=ctx.author.discriminator), icon_url=ctx.author.avatar_url)
            await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer : Timer):
        logging.debug("on_reminder_timer_complete received.")
        guild = self.bot.get_guild(timer.guild_id)
        channel = await self.bot.fetch_channel(timer.channel_id)
        user = guild.get_member(timer.user_id)
        embed=discord.Embed(title=self._("{user}, your reminder:").format(user=user.name), description="{note}".format(user=user.mention, note=timer.notes), color=self.bot.embedBlue)
        await channel.send(embed=embed, content=user.mention)

def setup(bot):
    logging.info("Adding cog: Timers...")
    bot.add_cog(Timers(bot))