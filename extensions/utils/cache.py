import asyncio
import logging

import asyncpg

class Caching():

    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.is_ready = False
        self.bot.loop.create_task(self.startup())

    async def startup(self):
        '''
        Creates an empty dict for every table in the database
        '''
        await self.bot.wait_until_ready()
        async with self.bot.pool.acquire() as con:
            records = await con.fetch('''
            SELECT *
            FROM pg_catalog.pg_tables
            WHERE schemaname='public'
            ''')
        for record in records:
            self.cache[record.get("tablename")] = {}
        logging.info("Cache initialized!")
        self.is_ready = True


    '''
    A class aimed squarely at making caching of values easier to handle, and
    centralize it. It tries lazy-loading a dict whenever requesting data,
    or setting it.
    '''
    
    async def get(self, table:str, guild_id, **kwargs):
        '''
        Finds a value based on criteria provided as keyword arguments.
        If no keyword arguments are present, returns the entire table.
        Tries getting the value from cache, if it is not present, 
        goes to the database & retrieve it. Lazy-loads the cache.

        Returns a dict in the following structure:
        tablename -> dict(colnames, list(rowvalues))
        So to iterate through each of the row-values, you would do: for value in cache[tablename][colname]
        Or to address a singular element: cache[tablename][colname][0]

        Example:
        await get_where(table="mytable", guild_id=1234, my_column=my_value)
        
        This is practically equivalent to an SQL 'SELECT * FROM table WHERE' statement.
        '''
        if guild_id in self.cache[table].keys():
            if kwargs:
                logging.debug("Loading data from cache and filtering...")
                matches = {}
                records = self.cache[table][guild_id]
                if len(records) > 0:
                    for (key, value) in kwargs.items():
                        if key in records.keys(): #If the key is found in cache
                            matches[key] = [i for i, x in enumerate(records[key]) if x == value]
                        else:
                            raise ValueError("Invalid key passed.")
                    #Find common elements present in all match lists
                    intersection = list(set.intersection(*map(set, matches.values())))
                    if len(intersection) > 0:
                        filtered_records = {key:[] for key in records.keys()}
                        for match in intersection: #Go through every list, and check the matched positions,
                            for (key, value) in records.items():
                                filtered_records[key].append(value[match]) #Then filter them out
                        return filtered_records #That's it c:
            else:
                logging.debug("Loading data from cache...")
                return self.cache[table][guild_id] if len(self.cache[table][guild_id]) > 0 else None
        
        else:
            logging.debug("Loading data from database and loading into cache...")
            await self.refresh(table, guild_id)
            return await self.get(table, guild_id, **kwargs)

    #TODO: Add more granular options for refresh, by including a 'key' variable, that further narrows scope
    async def refresh(self, table:str, guild_id:int):
        '''
        Discards and reloads a specific part of the cache, should be called after modifying database values
        '''
        self.cache[table][guild_id] = {}
        async with self.bot.pool.acquire() as con:
            records = await con.fetch(f'''SELECT * FROM {table} WHERE guild_id = $1''', guild_id)
            for record in records:
                for (field, value) in record.items():
                    if field in self.cache[table][guild_id].keys():
                        self.cache[table][guild_id][field].append(value)
                    else:
                        self.cache[table][guild_id][field] = [value]
        logging.debug(f"Refreshed cache for table {table}, guild {guild_id}!")
    
    async def wipe(self, guild_id:int):
        '''
        Discards the entire cache for a guild.
        '''
        for table in self.cache.keys():
            self.cache[table][guild_id] = {}
