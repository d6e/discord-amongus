import asyncio
from datetime import datetime
import json
import os

import discord
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)
slash = SlashCommand(bot, sync_commands=True)

bot_token = os.environ['DISCORD_BOT_TOKEN']

guild_id = os.getenv("DISCORD_GUILD_ID", None)
guild_ids = [int(guild_id)] if guild_id is not None else None

ban_emoji = "🔨"
kick_emoji = "👢"
no_action_emoji = "🚫"


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


async def is_sus(member, current_time):
    new_account = (current_time - member.created_at).days < 60
    recently_joined = (current_time - member.joined_at).days < 30
    no_avatar = not member.avatar
    eight_char_name = len(member.name) == 8
    return new_account and recently_joined and no_avatar and eight_char_name


@slash.slash(name="sus", description="List sus users", guild_ids=guild_ids)
async def sus_users(ctx: SlashContext):
    current_time = datetime.utcnow()
    members_data = []
    for member in ctx.guild.members:
        if await is_sus(member, current_time):
            member_info = {
                "name": f'{member.name}#{member.discriminator}',
                "date_joined": member.joined_at.isoformat(),
                "has_avatar": bool(member.avatar)
            }
            members_data.append(member_info)

    if not members_data:
        await ctx.send('No users found matching the criteria.', hidden=True)
    else:
        with open('users.json', 'w', encoding='utf-8') as f:
            json.dump(members_data, f, ensure_ascii=False, indent=4)

        await ctx.send(
            f'{len(members_data)} users found matching the criteria. The list has been saved to "users.json".',
            hidden=True)


@slash.slash(name="airlock", description="Ban or kick sus users with confirmation", guild_ids=guild_ids)
async def _airlock(ctx: SlashContext):
    current_time = datetime.utcnow()
    sus_members = [member for member in ctx.guild.members if await is_sus(member, current_time)]

    if not sus_members:
        await ctx.send('No sus users found matching the criteria.')
        return

    total_sus_members = len(sus_members)
    for index, member in enumerate(sus_members, start=1):
        embed = discord.Embed(title=f"{member.name}#{member.discriminator}",
                              description="Is this user sus? React with the appropriate emoji.",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=member.avatar_url or member.default_avatar_url)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="Joined Discord", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.set_footer(text=f"User {index} of {total_sus_members}")

        message_data = await ctx.send(embed=embed)
        await message_data.add_reaction(ban_emoji)
        await message_data.add_reaction(kick_emoji)
        await message_data.add_reaction(no_action_emoji)

        def check(_reaction, _user):
            return _user == ctx.author and _reaction.message.id == message_data.id \
                and str(_reaction.emoji) in [ban_emoji, kick_emoji, no_action_emoji]

        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send(f"Timeout. No action taken for {member.name}#{member.discriminator}.")
        else:
            if str(reaction.emoji) == ban_emoji:
                try:
                    await ctx.guild.ban(member)
                    await ctx.send(f"{member.name}#{member.discriminator} has been banned.")
                except discord.errors.Forbidden:
                    await ctx.send("Failed to ban the user. Check the bot's permissions.")
            elif str(reaction.emoji) == kick_emoji:
                try:
                    await ctx.guild.kick(member)
                    await ctx.send(f"{member.name}#{member.discriminator} has been kicked.")
                except discord.errors.Forbidden:
                    await ctx.send("Failed to kick the user. Check the bot's permissions.")
            elif str(reaction.emoji) == no_action_emoji:
                await ctx.send(f"No action taken for {member.name}#{member.discriminator}.")



bot.run(bot_token)
