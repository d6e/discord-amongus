import asyncio
from datetime import datetime
import json
import os
import re
from collections import defaultdict, OrderedDict
from typing import List, Optional, Dict

import discord
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.model import SlashMessage
from discord_slash.utils.manage_commands import create_option, create_choice
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

notify_channel_id = os.environ["DISCORD_NOTIFY_CHANNEL"]

mod_role_id = os.environ["DISCORD_MOD_ROLE"]

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
    id: int
    username: str
    display_name: str
    date_created: datetime
    date_joined: datetime
    has_avatar: bool
    avatar_url: str
    mention: str
    reasons: List[str]


def create_sus_user(member: discord.Member, reasons: list) -> SusUser:
    return SusUser(
        id=member.id,
        username=f'{member.name}#{member.discriminator}',
        display_name=member.display_name,
        date_created=member.created_at,
        date_joined=member.joined_at,
        has_avatar=bool(member.avatar),
        avatar_url=str(member.avatar_url or member.default_avatar_url),
        mention=member.mention,
        reasons=reasons
    )


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


@bot.event
async def on_member_join(new_user: discord.Member):
    notify_channel = bot.get_channel(int(notify_channel_id))
    duplicate_dates = find_duplicate_dates(new_user.guild.members)
    sus = await sus_check(new_user, duplicate_dates)
    if sus is None:
        return
    embed = make_sus_user_embed(sus)
    if notify_channel is None or mod_role_id is None:
        print(f"Cannot notify of new user join because unspecified ids: DISCORD_NOTIFY_CHANNEL={notify_channel} "
              f"DISCORD_MOD_ROLE={mod_role_id}")
        return
    await notify_channel.send(f'New sus user detected! {sus.mention} <@&{mod_role_id}>', embed=embed)
    if has_duplicate_date(new_user, duplicate_dates):
        group_size = duplicate_dates[created_joined_str(new_user)]
        await notify_channel.send(f"This user={new_user.mention} shares the same join-create "
                                  f"date with these `{group_size}` users:")
        sus_grp = find_sus_group(new_user)
        message = [sus.mention for sus in sus_grp]
        await notify_channel.send(','.join(message))


def find_sus_group(user: discord.Member) -> List[SusUser]:
    sus_grp = []
    for member in user.guild.members:
        if created_joined_str(member) != created_joined_str(user):
            continue
        sus = create_sus_user(member, [created_joined_str(member)])
        if sus is None:
            continue
        sus_grp.append(sus)
    return sus_grp


@slash.slash(name="sus_group", description="List users joined and created on the same date", guild_ids=guild_ids,
             options=[
                 create_option(
                     name="user",
                     description="Select a user",
                     option_type=6,
                     required=True
                 )
             ], )
async def sus_group(ctx: SlashContext, user: discord.Member):
    duplicate_dates = find_duplicate_dates(user.guild.members)
    if not has_duplicate_date(user, duplicate_dates):
        await ctx.channel.send(f"No users were found with similar join-create dates to user={user.mention}.")
        return
    group_size = duplicate_dates[created_joined_str(user)]
    await ctx.channel.send(f"This user={user.mention} shares the same join-create date with these `{group_size}` "
                           f"users:")
    sus_grp = find_sus_group(user)
    message = [sus.mention for sus in sus_grp]
    await ctx.channel.send(','.join(message))


def is_13_char_mixed_lower_alphanumeric(username: str) -> bool:
    # Check if the length is exactly 13
    if len(username) != 13:
        return False

    # Check if username has alternating letters and numbers before the '#'
    if not re.fullmatch(r'(([a-zA-Z][0-9])+[a-zA-Z])', username):
        return False
    return True


async def is_avatar_banned(member: discord.Member) -> bool:
    avatar_url = str(member.avatar_url)
    return avatar_url in banned_avatars


def has_duplicate_date(member: discord.Member, duplicate_dates) -> bool:
    date = created_joined_str(member)
    return date in duplicate_dates


def is_new_account(member: discord.Member, days: int = 7) -> bool:
    current_time = datetime.utcnow()
    return (current_time - member.created_at).days < days


def is_recent_join(member: discord.Member, days: int = 30) -> bool:
    current_time = datetime.utcnow()
    return (current_time - member.joined_at).days < days


def has_no_avatar(member: discord.Member) -> bool:
    return not member.avatar


async def sus_check(member: discord.Member, duplicate_dates) -> Optional[SusUser]:
    reasons = []
    if has_duplicate_date(member, duplicate_dates):
        # TODO: when this occurs we should post *all* matching users with similar dates and maybe store those dates
        reasons.append(f"Shares an account creation *and* join date "
                       f"with `{duplicate_dates[created_joined_str(member)]}` other users")
    if is_13_char_mixed_lower_alphanumeric(member.name):
        reasons.append("Has a 13 char name with mixed lower alphanumeric chars")
    if await is_avatar_banned(member):
        reasons.append("Has a known banned avatar")
    # TODO: we should also have a case where we check if duplicate (non-default) avatars
    if is_new_account(member, days=7) and has_no_avatar(member):
        reasons.append("Account is less than 7 days old and has no avatar")
    if len(reasons) > 0:
        return create_sus_user(member, reasons)
    else:
        return None


def created_joined_str(member: discord.Member) -> str:
    return f'{member.created_at.date()}_{member.joined_at.date()}'


def find_duplicate_dates(members: List[discord.Member]) -> Dict[str, int]:
    date_counts = defaultdict(int)
    for member in members:
        if str(member.created_at.date()) == str(member.joined_at.date()):
            continue  # skip same day create and joins
        date = created_joined_str(member)
        date_counts[date] += 1

    return {date: count for date, count in date_counts.items() if count > 5}


def find_duplicate_dates_users(members: List[discord.Member]) -> Dict[str, List[discord.Member]]:
    date_members = defaultdict(list)
    for member in members:
        if str(member.created_at.date()) == str(member.joined_at.date()):
            continue  # skip same day create and joins
        date = created_joined_str(member)
        date_members[date].append(member)

    # Sort items by the length of the value lists in descending order and filter out items with less than 5 members
    sorted_items = sorted(((date, members) for date, members in date_members.items() if len(members) > 5),
                          key=lambda x: len(x[1]), reverse=True)

    # Create an OrderedDict to maintain the order
    return OrderedDict(sorted_items)


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
            f'`{len(members_data)}` users found matching the criteria. The list has been saved to "users.json".',
            hidden=True)


async def find_sus(members) -> List[SusUser]:
    duplicate_dates = find_duplicate_dates(members)
    sus_members = []
    for member in members:
        sus_member = await sus_check(member, duplicate_dates)
        if sus_member is None:
            continue
        sus_members.append(sus_member)
    return sus_members


def make_sus_user_embed(sus: SusUser, description=""):
    embed = discord.Embed(title=f"{sus.username}",
                          description=description,
                          color=discord.Color.blue())
    embed.set_thumbnail(url=sus.avatar_url)
    embed.add_field(name="id", value=str(sus.id), inline=False)
    embed.add_field(name="display_name", value=sus.display_name, inline=False)
    embed.add_field(name="Joined Server", value=sus.date_joined.strftime("%Y-%m-%d"), inline=False)
    embed.add_field(name="Account Creation", value=sus.date_created.strftime("%Y-%m-%d"), inline=False)
    embed.add_field(name="Reasons", value=f"[{','.join(sus.reasons)}]", inline=False)
    return embed


@slash.slash(name="airlock", description="Ban or kick sus users with confirmation", guild_ids=guild_ids)
async def airlock(ctx: SlashContext):
    sus_members: List[SusUser] = await find_sus(ctx.guild.members)

    if not sus_members:
        await ctx.send('No sus users found matching the criteria.')
        return

    total_sus_members = len(sus_members)
    for index, sus in enumerate(sus_members, start=1):
        embed = make_sus_user_embed(sus, "Is this user sus? React with the appropriate emoji.")
        embed.set_footer(text=f"User {index} of {total_sus_members}")

        message_data = await ctx.send(sus.mention, embed=embed)
        await ban_kick_abort_react_to_message(ctx, message_data, [sus])


async def ban_kick_abort_react_to_message(ctx: SlashContext, slash_msg: SlashMessage, sus_members: List[SusUser]):
    await slash_msg.add_reaction(ban_emoji)
    await slash_msg.add_reaction(kick_emoji)
    await slash_msg.add_reaction(no_action_emoji)

    def check(_reaction, _user):
        return (
                _user == ctx.author
                and _reaction.message.id == slash_msg.id
                and str(_reaction.emoji) in (ban_emoji, kick_emoji, no_action_emoji)
        )
    try:
        reaction, _ = await bot.wait_for("reaction_add", check=check, timeout=300)
    except asyncio.TimeoutError:
        await ctx.send("Timeout. No action taken.")
        return
    if str(reaction.emoji) == ban_emoji:
        for sus in sus_members:
            try:
                await ctx.guild.ban(sus, reason="Sus user banned by Airlock command.")
            except discord.errors.Forbidden:
                await ctx.send(f"Failed to ban {sus.username}. Check the bot's permissions.")
    elif str(reaction.emoji) == kick_emoji:
        for sus in sus_members:
            try:
                await ctx.guild.kick(sus)
                await ctx.send(f"{sus.username} has been kicked.")
            except discord.errors.Forbidden:
                await ctx.send("Failed to kick the user. Check the bot's permissions.")
    else:
        await ctx.send("No action taken.")


@slash.slash(
    name="airlock_bulk",
    description="Check and ban sus users in bulk",
    guild_ids=guild_ids,
    options=[
        create_option(
            name="mode",
            description="Choose the mode for banning users",
            option_type=3,  # 3 means STRING type
            required=True,
            choices=[
                create_choice(
                    name="ANY",
                    value="ANY"
                ),
                create_choice(
                    name="JOIN_CREATED_DATES",
                    value="JOIN_CREATED_DATES"
                )
            ]
        )
    ]
)
async def airlock_bulk(ctx: SlashContext, mode: str):
    sus_members: List[SusUser] = []
    batch_size: int = 10
    if mode == "ANY":
        sus_members = await find_sus(ctx.guild.members)
    elif mode == "JOIN_CREATED_DATES":
        dates_users = find_duplicate_dates_users(ctx.guild.members)
        for member in next(iter(dates_users.values())):
            reason = f"({member.created_at.isoformat()},{member.joined_at.isoformat()})"
            sus = create_sus_user(member, [reason])
            sus_members.append(sus)
        sus_members.sort(key=lambda m: m.reasons[0])  # sort by the first reason string
        batch_size = len(sus_members)  # for this mode, we should handle all the sus members in one batch

    for i in range(0, len(sus_members), batch_size):
        embed = discord.Embed(title="Sus Users", description=f"Batch {i // batch_size + 1}, Size {batch_size}",
                              color=0xFF5733)
        batch = sus_members[i:i + batch_size]

        for index, sus in enumerate(batch, start=i + 1):
            embed.add_field(name=f"{index}. {sus.username}", value=f"[{','.join(sus.reasons)}]", inline=False)
        mentions = [m.mention for m in batch]
        message = await ctx.send(str(mentions), embed=embed)
        await ban_kick_abort_react_to_message(ctx, message, batch)


if __name__ == "__main__":
    bot.run(bot_token)
