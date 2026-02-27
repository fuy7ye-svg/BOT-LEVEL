import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import os
from flask import Flask
from threading import Thread

# --- كود حل مشكلة Render ---
app = Flask('')
@app.route('/')
def home(): return "Bot is running!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- إعدادات البوت ---
TOKEN = os.environ.get('DISCORD_TOKEN')

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ تم مزامنة أوامر السلاش")

bot = MyBot()

# --- قاعدة البيانات ---
conn = sqlite3.connect('levels.db')
cursor = conn.cursor()
# جدول المستخدمين
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, xp INTEGER, level INTEGER)''')
# جدول الإعدادات (لحفظ روم التلفيل)
cursor.execute('''CREATE TABLE IF NOT EXISTS settings 
                  (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)''')
conn.commit()

LEVEL_ROLES = {
    10: 1477037250708766944, 20: 1477037367067021432, 30: 1477037407558828082,
    40: 1477040533904818399, 50: 1477037439410372651, 60: 1477037522222846145,
    70: 1477037350709235803, 80: 1477037602883375275, 90: 1477037634483388460,
    100: 1477037663788863579
}

async def update_member_roles(member, level):
    eligible_role_id = None
    for lvl in sorted(LEVEL_ROLES.keys(), reverse=True):
        if level >= lvl:
            eligible_role_id = LEVEL_ROLES[lvl]
            break
    if eligible_role_id:
        new_role = member.guild.get_role(eligible_role_id)
        if new_role and new_role not in member.roles:
            try:
                await member.add_roles(new_role)
                for rid in LEVEL_ROLES.values():
                    if rid != eligible_role_id:
                        old_role = member.guild.get_role(rid)
                        if old_role in member.roles: await member.remove_roles(old_role)
            except: pass

@bot.event
async def on_ready():
    print(f'✅ البوت متصل: {bot.user}')
    if not voice_xp_task.is_running(): voice_xp_task.start()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    user_id = message.author.id
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, 0, 1)", (user_id,))
    cursor.execute("UPDATE users SET xp = xp + 10 WHERE user_id = ?", (user_id,))
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
    xp, level = cursor.fetchone()
    
    if xp >= (level * 200):
        new_level = level + 1
        cursor.execute("UPDATE users SET level = ?, xp = 0 WHERE user_id = ?", (new_level, user_id))
        conn.commit()
        
        # جلب روم التلفيل المخصص
        cursor.execute("SELECT channel_id FROM settings WHERE guild_id = ?", (message.guild.id,))
        channel_data = cursor.fetchone()
        
        target_channel = message.channel # الافتراضي هو نفس الروم
        if channel_data:
            custom_channel = bot.get_channel(channel_data[0])
            if custom_channel: target_channel = custom_channel
            
        await target_channel.send(f"🎉 كفو {message.author.mention}! ارتقيت للمستوى **{new_level}**")
        await update_member_roles(message.author, new_level)
    
    conn.commit()
    await bot.process_commands(message)

# --- أمر السلاش /setup ---
@bot.tree.command(name="setup", description="تحديد الروم الذي تظهر فيه رسائل التلفيل")
@app_commands.checks.has_permissions(administrator=True) # للمسؤولين فقط
async def setup(interaction: discord.Interaction):
    cursor.execute("INSERT OR REPLACE INTO settings (guild_id, channel_id) VALUES (?, ?)", 
                   (interaction.guild.id, interaction.channel.id))
    conn.commit()
    await interaction.response.send_message(f"✅ تم بنجاح! رسائل التلفيل ستظهر في هذا الروم: {interaction.channel.mention}")

# --- أمر السلاش /rank ---
@bot.tree.command(name="rank", description="عرض مستواك ونقاطك الحالية")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (member.id,))
    data = cursor.fetchone()
    if data:
        xp, level = data
        needed_xp = level * 200
        embed = discord.Embed(title=f"📊 ملف {member.display_name}", color=discord.Color.blue())
        embed.add_field(name="المستوى", value=f"⭐ `{level}`", inline=True)
        embed.add_field(name="النقاط", value=f"✨ `{xp}/{needed_xp}`", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ لا توجد بيانات لك حالياً.", ephemeral=True)

# حلقة الصوت (نفس الكود السابق)
@tasks.loop(minutes=1)
async def voice_xp_task():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot or member.voice.self_deaf or member.voice.mute: continue
                user_id = member.id
                cursor.execute("INSERT OR IGNORE INTO users VALUES (?, 0, 1)", (user_id,))
                cursor.execute("UPDATE users SET xp = xp + 20 WHERE user_id = ?", (user_id,))
                cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
                xp, level = cursor.fetchone()
                if xp >= (level * 200):
                    new_level = level + 1
                    cursor.execute("UPDATE users SET level = ?, xp = 0 WHERE user_id = ?", (new_level, user_id))
                    await update_member_roles(member, new_level)
    conn.commit()

keep_alive()
if TOKEN: bot.run(TOKEN)
