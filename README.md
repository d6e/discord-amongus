# Discord Amongus Bot
This is a bot for countering raids by finding spammer accounts in a discord server and banning them.
This bot is intended to be run as an adhoc utility to clean up after raids.

### Commands:
- airlock - Iterates over every sus account and prompts the user whether to ban it
- airlock_bulk - Iterates over every sus account in batches of 10 and prompts whether to ban them all
- sus - Finds all sus accounts, prints the total count and writes a json file called "users.json"

### A "sus" account is defined as:
- a name that is 8 characters in length
- lack profile picture
- joined in the last month 


## The Dotenv
To run it you'll want to provide your Discord server specific info in a `.env` file:
```bash
DISCORD_BOT_TOKEN=""
DISCORD_GUILD_ID=""
```