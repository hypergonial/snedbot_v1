import asyncio
import os

import asyncpg
from dotenv import load_dotenv

#Modify this line & change it to your PSQL DB address
#Do not modify the variables, DBPASS is retrieved from .env,
#while db_name is decided on runtime.
dsn="postgres://postgres:{DBPASS}@192.168.1.101:5432/{db_name}"

try:
    print('''Sned-Bot Database Initialization

    The following steps need to be taken BEFORE running this script:

    1) Create a postgresql database on the address specified in the DSN,
    and/or change the DSN in line 10 of this script. The database's name 
    must be either 'sned' or 'sned_exp' with default user 'postgres'.
    Current DSN: {dsn}

    2) Create a .env file which contains the bot's token and the database's password in the same
    directory as this script.
    Example .env:
    TOKEN=yourtokenhere
    DBPASS=yourdbpasswordhere\n'''.format(dsn=dsn.format(DBPASS="PASSWORD EXAMPLE", db_name="name example")))


    load_dotenv()
    DBPASS = os.getenv("DBPASS")
    while True:
        is_experimental = input("Do you want to initialize the database for the stable or the experimental version? Type 'stable' for stable, 'exp' for experimental.\n> ")
        if is_experimental in ['stable', 'exp']:
            if is_experimental == 'stable':
                db_name = 'sned'
            else:
                db_name = 'sned_exp'
            break
        else:
            print('Invalid input. Try again.\n')


    async def init_tables():
        '''
        Create all tables necessary for the functioning of this bot.
        '''

        pool = await asyncpg.create_pool(dsn=dsn.format(DBPASS=DBPASS, db_name=db_name))
        async with pool.acquire() as con:
            print('Creating tables...')
            await con.execute('''
                CREATE TABLE IF NOT EXISTS public.global_config
                (
                    guild_id bigint NOT NULL,
                    prefix text[],
                    PRIMARY KEY (guild_id)
                )''')
            await con.execute('''
                CREATE TABLE IF NOT EXISTS public.users
                (
                    user_id bigint NOT NULL,
                    guild_id bigint NOT NULL,
                    flags text[],
                    warns integer NOT NULL DEFAULT 0,
                    is_muted bool NOT NULL DEFAULT false,
                    notes text,
                    PRIMARY KEY (user_id, guild_id),
                    FOREIGN KEY (guild_id)
                        REFERENCES global_config (guild_id)
                        ON DELETE CASCADE
                )''')
            #New:
            #policies_*
            #dm_users_on_punish
            #clean_up_mod_commands
            #temp_dur

            await con.execute("""
                CREATE TABLE IF NOT EXISTS public.mod_config
                (
                    guild_id bigint,
                    mute_role_id bigint,
                    dm_users_on_punish bool NOT NULL DEFAULT true,
                    clean_up_mod_commands bool NOT NULL DEFAULT false,
                    temp_dur integer NOT NULL DEFAULT 15,
                    policies_invites text NOT NULL DEFAULT 'disabled',
                    policies_spam text NOT NULL DEFAULT 'disabled',
                    policies_mass_mentions text NOT NULL DEFAULT 'disabled',
                    policies_zalgo text NOT NULL DEFAULT 'disabled',
                    policies_attach_spam text NOT NULL DEFAULT 'disabled',
                    policies_link_spam text NOT NULL DEFAULT 'disabled',
                    policies_escalate text NOT NULL DEFAULT 'disabled',
                    PRIMARY KEY (guild_id),
                    FOREIGN KEY (guild_id)
                        REFERENCES global_config (guild_id)
                        ON DELETE CASCADE
                )""")
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.timers
                    (
                        id serial NOT NULL,
                        guild_id bigint NOT NULL,
                        user_id bigint NOT NULL,
                        channel_id bigint,
                        event text NOT NULL,
                        expires bigint NOT NULL,
                        notes text,
                        PRIMARY KEY (id),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )''')
            #New:
            #All
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.permissions
                    (
                        guild_id bigint NOT NULL,
                        ptype text NOT NULL,
                        role_ids bigint[] NOT NULL DEFAULT '{}',
                        PRIMARY KEY (guild_id, ptype),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )''')
            #New:
            #All
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.modules
                    (
                        guild_id bigint NOT NULL,
                        module_name text NOT NULL,
                        is_enabled bool NOT NULL DEFAULT true,
                        PRIMARY KEY (guild_id, module_name),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )
            ''')
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.priviliged
                    (
                        guild_id bigint NOT NULL,
                        priviliged_role_id bigint NOT NULL,
                        PRIMARY KEY (guild_id, priviliged_role_id),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )''')
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.reaction_roles
                    (
                        guild_id bigint NOT NULL,
                        reactionrole_id serial NOT NULL,
                        reactionrole_channel_id bigint NOT NULL,
                        reactionrole_msg_id bigint NOT NULL,
                        reactionrole_emoji_id bigint NOT NULL,
                        reactionrole_role_id bigint NOT NULL,
                        PRIMARY KEY (guild_id, reactionrole_id),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )''')
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.matchmaking_config
                    (
                        guild_id bigint,
                        init_channel_id bigint,
                        announce_channel_id bigint,
                        lfg_role_id bigint,
                        PRIMARY KEY (guild_id),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )''')
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.matchmaking_listings
                    (
                        id text,
                        ubiname text NOT NULL,
                        host_id bigint NOT NULL,
                        gamemode text NOT NULL,
                        playercount text NOT NULL,
                        DLC text NOT NULL,
                        mods text NOT NULL,
                        timezone text NOT NULL,
                        additional_info text NOT NULL,
                        timestamp bigint NOT NULL,
                        guild_id bigint NOT NULL,
                        PRIMARY KEY (id)
                    )''')
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.tags
                    (
                        guild_id bigint NOT NULL,
                        tag_name text NOT NULL,
                        tag_owner_id bigint NOT NULL,
                        tag_aliases text[],
                        tag_content text NOT NULL,
                        PRIMARY KEY (guild_id, tag_name),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )''')
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.log_config
                    (
                        guild_id bigint NOT NULL,
                        log_channel_id bigint NOT NULL,
                        elevated_log_channel_id bigint,
                        PRIMARY KEY (guild_id),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )''')
            await con.execute('''
                    CREATE TABLE IF NOT EXISTS public.ktp
                    (
                        guild_id bigint NOT NULL,
                        ktp_id serial NOT NULL,
                        ktp_channel_id bigint NOT NULL,
                        ktp_msg_id bigint NOT NULL,
                        ktp_content text NOT NULL,
                        PRIMARY KEY (guild_id, ktp_id),
                        FOREIGN KEY (guild_id)
                            REFERENCES global_config (guild_id)
                            ON DELETE CASCADE
                    )''')
            
            print('Tables created, database is ready!')

    asyncio.get_event_loop().run_until_complete(init_tables())
    input('\nPress enter to exit...')

except KeyboardInterrupt:
    print("\nKeyboard interrupt received, exiting...")