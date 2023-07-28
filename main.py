import asyncio
from datetime import datetime
import json
import os
import re
from collections import defaultdict
from typing import List, Optional

import discord
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from dotenv import load_dotenv
from dataclasses import dataclass

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

banned_avatars = [
    "https://cdn.discordapp.com/avatars/1127546621392064572/bf9c78940878fa7b98938ccfd0a52b07.png?size=1024",
    "https://cdn.discordapp.com/avatars/1127413539766812704/0e63aacbb6632e07b5cfdc2051d9ee96.png?size=1024",
    "https://cdn.discordapp.com/avatars/1127410432223756389/5228efe31c748da22b4e7c2672f3f150.png?size=1024",
    "https://cdn.discordapp.com/avatars/1127546209310089316/46c5336b0d912cf3ffe2e82b2d0bdcb0.png?size=1024",
    "https://cdn.discordapp.com/avatars/1127414479139909726/79d5d872b3db33433ee3ed584b8e7209.png?size=1024"
]


@dataclass
class SusUser:
    user_id: int
    username: str
    display_name: str
    date_created: datetime.datetime
    date_joined: datetime.datetime
    has_avatar: bool
    avatar_url: str
    mention: str
    reasons: List[str]


def create_sus_user(member) -> SusUser:
    return SusUser(
        user_id=member.id,
        username=f'{member.name}#{member.discriminator}',
        display_name=member.display_name,
        date_created=member.created_at,
        date_joined=member.joined_at,
        has_avatar=bool(member.avatar),
        avatar_url=str(member.avatar_url),
        mention=member.mention,
        reason=[]
    )


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


def is_13_char_mixed_lower_alphanumeric(username: str) -> bool:
    # Check if the length is exactly 13
    if len(username) != 13:
        return False

    # Check if username has alternating letters and numbers before the '#'
    if not re.fullmatch('(([a-zA-Z][0-9])+[a-zA-Z])', username):
        return False
    return True


async def is_avatar_banned(member: discord.Member, banned_avatars: list) -> bool:
    avatar_url = str(member.avatar_url)
    return avatar_url in banned_avatars


def has_duplicate_date(member, duplicate_dates) -> bool:
    date = created_joined_str(member)
    return date in duplicate_dates


def is_new_account(member, days: int = 7) -> bool:
    current_time = datetime.utcnow()
    return (current_time - member.created_at).days < days


def is_recent_join(member, days: int = 30) -> bool:
    current_time = datetime.utcnow()
    return (current_time - member.joined_at).days < days


def has_no_avatar(member) -> bool:
    return not member.avatar


async def sus_check(member, duplicate_dates) -> Optional[SusUser]:
    reasons = []
    if has_duplicate_date(member, duplicate_dates):
        # TODO: when this occurs we should post *all* matching users with similar dates and maybe store those dates
        reasons.append(f"Shares an account creation *and* join date "
                       f"with '{duplicate_dates[created_joined_str(member)]}' other users")
    if is_13_char_mixed_lower_alphanumeric(member.name):
        reasons.append("Has a 13 char name with mixed lower alphanumeric chars")
    if await is_avatar_banned(member, banned_avatars=banned_avatars):
        reasons.append("Has a known banned avatar")
    # TODO: we should also have a case where we check if duplicate (non-default) avatars
    if is_new_account(member, days=7) and has_no_avatar(member):
        reasons.append("Account is less than 7 days old and has no avatar")
    if len(reasons) > 0:
        user = create_sus_user(member)
        user.reasons = reasons
        return user
    else:
        return None


def created_joined_str(member) -> str:
    return f'{member.created_at.date()}_{member.joined_at.date()}'


def find_duplicate_dates(members):
    date_counts = defaultdict(int)
    for member in members:
        if str(member.created_at.date()) == str(member.joined_at.date()):
            continue  # skip same day create and joins
        date = created_joined_str(member)
        date_counts[date] += 1

    duplicates = {date: count for date, count in date_counts.items() if count > 5}
    print(duplicates)

    return duplicates


@slash.slash(name="sus", description="List sus users", guild_ids=guild_ids)
async def sus_users(ctx: SlashContext):
    members_data = []
    duplicate_dates = find_duplicate_dates(ctx.guild.members)
    for member in ctx.guild.members:
        if await sus_check(member, duplicate_dates):
            member_info = {
                "name": f'{member.name}#{member.discriminator}',
                "id": member.id,
                "display_name": member.display_name,
                "date_created": member.created_at.isoformat(),
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
async def airlock(ctx: SlashContext):
    duplicate_dates = find_duplicate_dates(ctx.guild.members)
    sus_members = [member for member in ctx.guild.members if await sus_check(member, duplicate_dates)]

    if not sus_members:
        await ctx.send('No sus users found matching the criteria.')
        return

    total_sus_members = len(sus_members)
    for index, member in enumerate(sus_members, start=1):
        embed = discord.Embed(title=f"{member.name}#{member.discriminator}",
                              description="Is this user sus? React with the appropriate emoji.",
                              color=discord.Color.blue())
        embed.set_thumbnail(url=member.avatar_url or member.default_avatar_url)
        embed.add_field(name="id", value=member.id, inline=False)
        embed.add_field(name="display_name", value=member.display_name, inline=False)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d"), inline=False)
        embed.add_field(name="Account Creation", value=member.created_at.strftime("%Y-%m-%d"), inline=False)
        embed.set_footer(text=f"User {index} of {total_sus_members}")

        message_data = await ctx.send(member.mention, embed=embed)
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
            return
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


@slash.slash(
    name="airlock_bulk",
    description="Check and ban sus users in bulk",
    guild_ids=guild_ids,
)
async def airlock_bulk(ctx):
    duplicate_dates = find_duplicate_dates(ctx.guild.members)
    sus_members = [
        member
        for member in ctx.guild.members
        if await sus_check(member, duplicate_dates)
    ]

    for i in range(0, len(sus_members), 10):
        embed = discord.Embed(title="Sus Users", description=f"Batch {i // 10 + 1}", color=0xFF5733)

        batch_members = []
        for index, member in enumerate(sus_members[i:i + 10], start=i + 1):
            batch_members.append(member)
            embed.add_field(name=f"{index}. {member.name}", value=f"ID: {member.id}", inline=False)
        mentions = [m.mention for m in batch_members]
        message = await ctx.send(str(mentions), embed=embed)

        for emoji in (ban_emoji, no_action_emoji):
            await message.add_reaction(emoji)

        def check(_reaction, user):
            return (
                    user == ctx.author
                    and _reaction.message.id == message.id
                    and str(_reaction.emoji) in (ban_emoji, no_action_emoji)
            )

        try:
            reaction, _ = await bot.wait_for("reaction_add", check=check, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("Timeout. No action taken.")
            return

        if str(reaction.emoji) == ban_emoji:
            for member in sus_members[i:i + 10]:
                try:
                    await ctx.guild.ban(member, reason="Sus user banned by Airlock command.")
                except discord.errors.Forbidden:
                    await ctx.send(f"Failed to ban {member.name}. Check the bot's permissions.")
        else:
            await ctx.send("No action taken.")


if __name__ == "__main__":
    bot.run(bot_token)
