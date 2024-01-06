import discord
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont
import os
import aiohttp
import random
from typing import Optional
from discord.ui import Button, View
import math
from math import floor
from discord import app_commands
from bs4 import BeautifulSoup
import requests
from flask import Flask, render_template

app = Flask(__name__)

# Your existing code for Discord bot
ASSETS_PATH = "assets"
FONTS_PATH = "fonts"
TMP_PATH = "tmp"
XP_PER_LVL = 100
ASSETS_PATH = "assets"
FONTS_PATH = "fonts"
TMP_PATH = "tmp"
XP_PER_LVL = 100

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def shadow_tuple(self):
        return (self.x + 1, self.y + 1)

    def as_tuple(self):
        return (self.x, self.y)

IMG_BG = os.path.join(ASSETS_PATH, "bg_rank.png")
IMG_FRAME = os.path.join(ASSETS_PATH, "bg_rank_border_square.png")
IMG_BG2 = os.path.join(ASSETS_PATH, "bg_rank.png")
IMG_FRAME2 = os.path.join(ASSETS_PATH, "bg_rank_border_square.png")
IMG_SM_BAR = os.path.join(ASSETS_PATH, "bg_rank_bar_small.png")
IMG_LG_BAR = os.path.join(ASSETS_PATH, "bg_rank_bar_large.png")
FONT = os.path.join(FONTS_PATH, "Roboto/Roboto-Medium.ttf")
FONT_COLOR = (208, 80, 84)
BACK_COLOR = (82, 31, 33)
USERNAME_POS = Point(90, 8)
LEVEL_POS = Point(90, 63)
RANK_POS = Point(385, 68)
BAR_X = [133, 153, 173, 193, 213, 247, 267, 287, 307, 327]
BAR_Y = 37

xp_data = {}
xp_boosts = {}

intents = discord.Intents.all()
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command("help")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

async def update_user_count(guild: discord.Guild):
    activity_mes = f"{guild.member_count} members!"
    activity_object = discord.Activity(name=activity_mes, type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity_object)

async def download_avatar(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                with open(filename, 'wb') as f:
                    f.write(data)
                return True
    return False

async def render_level_up_image(user: discord.Member, old_level: int, new_level: int) -> Optional[str]:
    if not os.path.exists(TMP_PATH):
        os.makedirs(TMP_PATH)

    out_filename = os.path.join(TMP_PATH, f"level_up_{user.id}_{user.guild.id}.png")

    bg = Image.open(IMG_BG2)
    frame = Image.open(IMG_FRAME2)

    bg.paste(frame, (14, 12), frame)

    draw = ImageDraw.Draw(bg)
    font_22 = ImageFont.load_default()

    # Add big text in the middle
    level_text = f"{old_level} -> {new_level}"
    level_width = font_22.getlength(level_text)
    draw.text((bg.width // 2 - level_width // 2, bg.height // 2 - 10), level_text, FONT_COLOR, font=font_22)

    bg.save(out_filename)
    bg.close()
    frame.close()

    return out_filename

async def render_lvl_image(user: discord.Member, username: str, xp: int, rank: int) -> Optional[str]:
    if not os.path.exists(TMP_PATH):
        os.makedirs(TMP_PATH)

    lvl = floor(xp / XP_PER_LVL)
    bar_num = math.ceil(10 * (xp - (lvl * XP_PER_LVL)) / XP_PER_LVL)

    out_filename = os.path.join(TMP_PATH, f"{user.id}_{user.guild.id}.png")
    avatar_filename = out_filename

    avatar_url = user.display_avatar.url

    success = await download_avatar(avatar_url, avatar_filename)
    if not success:
        return None

    bg = Image.open(IMG_BG)
    avatar = Image.open(avatar_filename).convert("RGBA")
    frame = Image.open(IMG_FRAME)
    small_bar = Image.open(IMG_SM_BAR)
    large_bar = Image.open(IMG_LG_BAR)

    avatar = avatar.resize((68, 68))
    bg.paste(avatar, (16, 14), avatar)
    bg.paste(frame, (14, 12), frame)

    for i in range(0, bar_num):
        if i % 5 == 4:
            bg.paste(large_bar, (BAR_X[i], BAR_Y), large_bar)
        else:
            bg.paste(small_bar, (BAR_X[i], BAR_Y), small_bar)

    draw = ImageDraw.Draw(bg)
    font_14 = ImageFont.load_default()
    font_22 = ImageFont.load_default()
    
    draw.text(USERNAME_POS.shadow_tuple(), username, BACK_COLOR, font=font_22)
    draw.text(USERNAME_POS.as_tuple(), username, FONT_COLOR, font=font_22)

    draw.text(LEVEL_POS.shadow_tuple(), f"Level {lvl}", BACK_COLOR, font=font_22)
    draw.text(LEVEL_POS.as_tuple(), f"Level {lvl}", FONT_COLOR, font=font_22)

    rank_text = f"Server Rank : {rank}"
    rank_width = font_14.getlength(rank_text)
    draw.text((RANK_POS.x - rank_width, RANK_POS.y), rank_text, BACK_COLOR, font=font_14)

    bg.save(out_filename)
    bg.close()
    avatar.close()
    frame.close()
    small_bar.close()
    large_bar.close()

    return out_filename

def get_xp(user_id, guild_id):
    return f"{xp_data.get(guild_id, {}).get(user_id, 0)} XP"

def get_rank(user_id, guild_id):
    sorted_users = sorted(xp_data.get(guild_id, {}).items(), key=lambda x: x[1], reverse=True)
    user_rank = next((i+1 for i, (uid, _) in enumerate(sorted_users) if uid == user_id), None)
    return user_rank
  
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    await check_xp(message)
    await check_level_up(message)
    await bot.process_commands(message)

async def check_xp(message):
    user_id = message.author.id
    guild_id = message.guild.id

    if guild_id not in xp_data:
        xp_data[guild_id] = {}

    user_xp = xp_data[guild_id].get(user_id, 0)
        
    # Apply XP boost if active
    xp_multiplier = xp_boosts.get(guild_id, 1)
    user_xp += random.randint(4, 15) * xp_multiplier
    xp_data[guild_id][user_id] = user_xp

async def check_level_up(message):
    user_id = message.author.id
    guild_id = message.guild.id
    
    user_xp = xp_data[guild_id].get(user_id, 0)

    old_level = floor(user_xp / XP_PER_LVL)
    new_level = floor(user_xp / XP_PER_LVL)
    
    if new_level > old_level:
        # Level up logic
        image_path = await render_level_up_image(message.author, old_level, new_level)
        if image_path:
            await message.channel.send(f"**Congrats {message.author.mention}! You have reached Level {new_level}**)", file=discord.File(image_path))
            
            # Check for specific levels and add roles
            if new_level == 20:
                role_id = 1187084842156949614  # Replace with the actual role ID
                role = message.guild.get_role(role_id)
                if role:
                    await message.author.add_roles(role, reason="Reached level 20")

            elif new_level == 30:
                role_id = 1187084755917873184  # Replace with the actual role ID
                role = message.guild.get_role(role_id)
                if role:
                    await message.author.add_roles(role, reason="Reached level 30")

            os.remove(image_path)
          
@bot.command(name='lvl', aliases=['level'])
async def lvl(ctx):
    user = ctx.author
    guild_id = ctx.guild.id
    username = user.display_name
    rank = get_rank(user.id, guild_id)
    xp = xp_data[guild_id].get(user.id, 0)
    image_path = await render_lvl_image(user, username, xp, rank)

    if image_path:
        await ctx.send(f"Hello, {user.mention}! Here's your rank!", file=discord.File(image_path))
        os.remove(image_path)

@bot.command(name='addxp')
@commands.has_permissions(administrator=True)
async def add_xp(ctx, member: discord.Member, amount: int):
    user_id = member.id
    guild_id = ctx.guild.id
    
    if amount < 0:
        await ctx.send("Please enter a positive XP amount.")
        return
    
    if guild_id not in xp_data:
        xp_data[guild_id] = {}

    current_xp = xp_data[guild_id].get(user_id, 0)
    new_xp = current_xp + amount
    xp_data[guild_id][user_id] = new_xp
    
    await ctx.send(f"{amount} XP added to {member.display_name}. New XP: {new_xp}")


@bot.command(name='setlevel')
@commands.has_permissions(administrator=True) 
async def set_level(ctx, member: discord.Member, level: int):
    user_id = member.id
    guild_id = ctx.guild.id
    
    if level < 0:
        await ctx.send("Please enter a positive level.")
        return
        
    xp_required = level * XP_PER_LVL
    xp_data[guild_id][user_id] = xp_required
    
    await ctx.send(f"{member.display_name}'s level has been set to {level}")


# Flask route to render live rankings
@app.route('/')
def live_rankings():
    guild_id = int(os.getenv('GUID'))
    sorted_users = sorted(xp_data.get(guild_id, {}).items(), key=lambda x: x[1], reverse=True)
    rankings = [{"user_id": uid, "xp": xp, "rank": i+1} for i, (uid, xp) in enumerate(sorted_users)]

    return render_template('live_rankings.html', rankings=rankings)

if __name__ == '__main__':
    bot.run(os.getenv('TOKEN'))
    app.run(debug=True)
