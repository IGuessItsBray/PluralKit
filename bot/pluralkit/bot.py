import logging
import os

import discord

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("websockets").setLevel(logging.INFO)

logger = logging.getLogger("pluralkit.bot")
logger.setLevel(logging.DEBUG)

client = discord.Client()


@client.event
async def on_error(evt, *args, **kwargs):
    logger.exception(
        "Error while handling event {} with arguments {}:".format(evt, args))


@client.event
async def on_ready():
    # Print status info
    logger.info("Connected to Discord.")
    logger.info("Account: {}#{}".format(
        client.user.name, client.user.discriminator))
    logger.info("User ID: {}".format(client.user.id))


@client.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return

    # Split into args. shlex sucks so we don't bother with quotes
    args = message.content.split(" ")

    from pluralkit import proxy, utils

    cmd = None
    # Look up commands with subcommands
    if len(args) >= 2:
        lookup = utils.command_map.get((args[0], args[1]), None)
        if lookup:
            # Curry with arg slice
            cmd = lambda c, m, a: lookup[0](conn, message, args[2:])
    # Look up root commands
    if not cmd and len(args) >= 1:
        lookup = utils.command_map.get((args[0], None), None)
        if lookup:
            # Curry with arg slice
            cmd = lambda c, m, a: lookup[0](conn, message, args[1:])

    # Found anything? run it
    if cmd:
        async with client.pool.acquire() as conn:
            await cmd(conn, message, args)
            return

    # Try doing proxy parsing
    async with client.pool.acquire() as conn:
        await proxy.handle_proxying(conn, message)


@client.event
async def on_reaction_add(reaction, user):
    from pluralkit import proxy

    # Pass reactions to proxy system
    async with client.pool.acquire() as conn:
        await proxy.handle_reaction(conn, reaction, user)


async def run():
    from pluralkit import db
    try:
        logger.info("Connecting to database...")
        pool = await db.connect()

        logger.info("Attempting to create tables...")
        async with pool.acquire() as conn:
            await db.create_tables(conn)

        logger.info("Connecting to InfluxDB...")

        client.pool = pool
        logger.info("Connecting to Discord...")
        await client.start(os.environ["TOKEN"])
    finally:
        logger.info("Logging out from Discord...")
        await client.logout()
