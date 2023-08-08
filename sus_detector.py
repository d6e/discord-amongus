import discord
from discord.ext import commands
import os
import random
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.naive_bayes import MultinomialNB
import json
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']
MODERATORS_ROLE_NAME = 'Moderators'

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

classifier: Pipeline


class AccountAgeExtractor(BaseEstimator, TransformerMixin):
    def fit(self, x, y=None):
        return self

    def transform(self, users):
        return np.array([[(user.joined_at - user.created_at).days] for user in users]).reshape(-1, 1)


class AvatarStatusExtractor(BaseEstimator, TransformerMixin):
    def fit(self, x, y=None):
        return self

    def transform(self, users):
        return np.array([[1 if user.avatar else 0] for user in users]).reshape(-1, 1)


class UsernameExtractor(BaseEstimator, TransformerMixin):
    def __init__(self, func):
        self.func = func

    def fit(self, x, y=None):
        return self

    def transform(self, users):
        return self.func(users)


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

    # Load and train the classifier
    global classifier
    classifier = await train_classifier()


async def train_classifier():

    # Query Discord to get banned and not banned users
    banned_users, not_banned_users = await get_training_data()

    # Prepare the training data
    users = banned_users + not_banned_users
    labels = [1] * len(banned_users) + [0] * len(not_banned_users)

    feature_pipeline = FeatureUnion([
        ('username', Pipeline([
            ('extract_username', UsernameExtractor(lambda x: [user.name + "#" + user.discriminator for user in x])),
            ('vectorize', CountVectorizer())
        ])),
        # ('account_age', Pipeline([
        #     ('extract_account_age', AccountAgeExtractor()),
        #     ('scale', StandardScaler())
        # ])),
        ('avatar_status', AvatarStatusExtractor())
    ])

    _classifier = Pipeline([
        ('features', feature_pipeline),
        ('classifier', MultinomialNB())
    ])

    _classifier.fit(users, labels)
    return _classifier


@bot.event
async def on_member_join(member):
    # Predict if the user is suspicious using the trained classifier
    prediction = classifier.predict([member])

    if prediction[0] == 1:
        # Notify the Moderators
        moderators_role = discord.utils.get(member.guild.roles, name=MODERATORS_ROLE_NAME)
        moderators_bots_channel = discord.utils.get(member.guild.text_channels, name="moderators-bots")

        if moderators_bots_channel:
            msg = f"{moderators_role.mention} A suspicious user {member.mention} has joined the server. Please investigate."
            print(msg)
            await moderators_bots_channel.send(msg)
        else:
            print("Could not find the 'moderators-bots' channel. Please ensure it exists.")


@bot.event
async def on_member_join(member):
    # Predict if the user is suspicious using the trained classifier
    prediction = classifier.predict([member])

    if prediction[0] == 1:
        # Notify the Moderators
        moderators_role = discord.utils.get(member.guild.roles, name=MODERATORS_ROLE_NAME)
        msg = f"{moderators_role.mention} A suspicious user {member.mention} has joined the server. Please investigate."
        print(msg)
        # await member.guild.system_channel.send(msg)


async def get_training_data():
    banned_users = []
    not_banned_users = []

    for guild in bot.guilds:
        bans = await guild.bans()
        banned_users += [ban.user for ban in bans]

        members = guild.members
        not_banned_users += members

    return banned_users, not_banned_users


bot.run(BOT_TOKEN)
