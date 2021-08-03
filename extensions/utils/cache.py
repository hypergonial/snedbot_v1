import asyncio
import logging
from typing import Type

import asyncpg
from sql_metadata import Parser


class SQLParsingError(Exception):
    pass

class Caching():
    '''
    A class aimed squarely at making caching of values easier to handle, and
    centralize it. It tries lazy-loading a dict whenever requesting data,
    or setting it.
    '''

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

    
    async def format_records(self, records:dict) -> list[dict]:
        '''
        Helper function that transforms a record into an easier to use format.
        Returns a list of dicts, each representing a row in the database.
        '''
        first_key = list(records.keys())[0]
        records_fmt = []
        for i, value in enumerate(records[first_key]):
            record = {}
            for key in records.keys():
                record[key] = records[key][i]
            records_fmt.append(record)
        return records_fmt
                

    async def get(self, table:str, guild_id:int, **kwargs) -> list[dict]:
        '''
        Finds a value based on criteria provided as keyword arguments.
        If no keyword arguments are present, returns all values for that guild_id.
        Tries getting the value from cache, if it is not present, 
        goes to the database & retrieves it. Lazy-loads the cache.

        Returns a list of dicts with each dict being a row, and the dict-keys being the columns.

        Example:
        await Caching.get(table="mytable", guild_id=1234, my_column=my_value)
        
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
                        if len(filtered_records) > 0:
                            return await self.format_records(filtered_records)
            else:
                logging.debug("Loading data from cache...")
                if len(self.cache[table][guild_id]) > 0:
                    return await self.format_records(self.cache[table][guild_id])
        
        else:
            logging.debug("Loading data from database and loading into cache...")
            await self.refresh(table, guild_id)
            return await self.get(table, guild_id, **kwargs)

    async def update(self, sql_query:str, *args):
        '''
        Takes an SQL query and arguments, one of which must be the guild_id, and tries
        executing it. Refreshes the cache afterwards with the new values.
        '''
        #Note: DELETE FROM crashes the whole thing, I dunno why :/ seems to be a lib issue
        parser = Parser(sql_query)

        if parser.query_type == 'SELECT':
            raise TypeError('SELECT queries are not supported.')

        tables = parser.tables
        for table in tables:
            if table not in self.cache.keys(): #Verify tablenames
                tables.remove(table)
        if len(tables) == 0: raise SQLParsingError("Failed parsing tables from query!")

        if len(parser.columns) == 0: raise SQLParsingError("Failed parsing columns from query!")
        if "guild_id" not in parser.columns:
            return SQLParsingError('guild_id must be in the query!')
        else:
            for i, col in enumerate(parser.columns):
                if col == "guild_id":
                    guild_id = args[i]

        async with self.bot.pool.acquire() as con:
            await con.execute(sql_query, *args)
        for table in tables:
            await self.refresh(table=table, guild_id=guild_id)


    #TODO: Add more granular options for refresh, by including a 'key' variable, that further narrows scope
    async def refresh(self, table:str, guild_id:int):
        '''
        Discards and reloads a specific part of the cache, should be called after modifying database values.
        Please use update() unless your query is too complex for it to be parsed by the function, as it
        automatically calls this function.
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
