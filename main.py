import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import os
from flask import Flask
from threading import Thread

# --- 1. حل مشكلة Render (Flask Server) ---
app = Flask('')

@app.route('/')
def home():
    return "I am alive!"

def run_flask():
    # Render يبحث غالباً عن بورت 8080 أو 10000
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. إعداد البوت ---
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
        # مزامنة أوامر السلاش
        await self.tree.sync()
        print("✅ Slash Commands Synced")

bot = MyBot()

# --- 3. قاعدة البيانات ---
conn = sqlite3.connect('levels.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER, level INTEGER)')
cursor.execute('CREATE TABLE IF NOT EXISTS settings (guild_id INTEGER PRIMARY KEY, channel_id INTEGER)')
conn.commit()

LEVEL_ROLES = {
    10: 1477037250708766944, 20: 1477037367067021432, 30: 1477037407558828082,
    40: 1477040533904818399, 50: 1477037439410372651, 60: 1477037522222846145,
    70: 1477037350709235803, 80: 1477037602883375275, 90: 1477037634483388460,
    100: 1477037663788863579
}

# --- 4. الأوامر والفعاليات ---

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    if not voice_xp_task.is_running():
        voice_xp_task.start()

@bot.tree.command(name="setup", description="تحديد روم إشعارات التلفيل")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    cursor.execute("INSERT OR REPLACE INTO settings (guild_id, channel_id) VALUES (?, ?)", 
                   (interaction.guild.id, interaction.channel.id))
    conn.commit()
    await interaction.response.send_message(f"✅ تم! الإشعارات ستصل هنا: {interaction.channel.mention}")

@bot.tree.command(name="rank", description="عرض مستواك الحالي")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (target.id,))
    data = cursor.fetchone()
    if data:
        xp, level = data
        embed = discord.Embed(title=f"📊 الإحصائيات لـ {target.display_name}", color=discord.Color.green())
        embed.add_field(name="المستوى", value=str(level))
        embed.add_field(name="النقاط", value=f"{xp}/{level*200}")
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("لا توجد بيانات لك بعد!", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    
    uid = message.author.id
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, 0, 1)", (uid,))
    cursor.execute("UPDATE users SET xp = xp + 10 WHERE user_id = ?", (uid,))
    
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (uid,))
    xp, level = cursor.fetchone()
    
    if xp >= (level * 200):
        new_lvl = level + 1
        cursor.execute("UPDATE users SET level = ?, xp = 0 WHERE user_id = ?", (new_lvl, uid))
        conn.commit()
        
        # إرسال التهنئة
        cursor.execute("SELECT channel_id FROM settings WHERE guild_id = ?", (message.guild.id,))
        set_ch = cursor.fetchone()
        channel = bot.get_channel(set_ch[0]) if set_ch else message.channel
        
        if channel:
            await channel.send(f"🎉 مبروك {message.author.mention} وصلت ليفل {new_lvl}!")
            # تحديث الرتب (تلقائي)
            role_id = LEVEL_ROLES.get(new_lvl // 10 * 10) # يجلب رتبة مضاعفات الـ 10
            if role_id:
                role = message.guild.get_role(role_id)
                if role: await message.author.add_roles(role)

    conn.commit()

@tasks.loop(minutes=1)
async def voice_xp_task():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot and not member.voice.self_deaf:
                    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, 0, 1)", (member.id,))
                    cursor.execute("UPDATE users SET xp = xp + 20 WHERE user_id = ?", (member.id,))
    conn.commit()

# --- 5. التشغيل النهائي ---
if __name__ == "__main__":
    keep_alive() # تشغيل Flask لحل مشكلة بورت Render
    bot.run(TOKEN)
