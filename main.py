import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import os
from flask import Flask
from threading import Thread

# --- 1. حل مشكلة Render (سيرفر Flask) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is running!"
def run_flask(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# --- 2. إعدادات البوت ---
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

# --- 4. دالة التحقق من الرتب ---
async def check_roles(member, level):
    for lvl in sorted(LEVEL_ROLES.keys(), reverse=True):
        if level >= lvl:
            role_id = LEVEL_ROLES[lvl]
            role = member.guild.get_role(role_id)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                    # سحب الرتب القديمة
                    for r_id in LEVEL_ROLES.values():
                        if r_id != role_id:
                            old_role = member.guild.get_role(r_id)
                            if old_role in member.roles: await member.remove_roles(old_role)
                except: pass
            break

# --- 5. الأوامر والفعاليات ---
@bot.event
async def on_ready():
    print(f'✅ سجل الدخول باسم {bot.user}')
    if not voice_xp_task.is_running(): voice_xp_task.start()

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
        needed_xp = level * 200
        embed = discord.Embed(title=f"📊 الإحصائيات لـ {target.display_name}", color=discord.Color.blue())
        embed.add_field(name="المستوى", value=f"⭐ `{level}`", inline=True)
        embed.add_field(name="النقاط", value=f"✨ `{xp}/{needed_xp}`", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ لا توجد بيانات!", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    
    uid = message.author.id
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, 0, 1)", (uid,))
    cursor.execute("UPDATE users SET xp = xp + 10 WHERE user_id = ?", (uid,))
    conn.commit()
    
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (uid,))
    xp, level = cursor.fetchone()
    
    # تصحيح المستوى بناءً على النقاط المتراكمة (مثل 2220/400)
    leveled_up = False
    while xp >= (level * 200): # حلقة تكرارية لرفع المستويات المتعددة
        xp -= (level * 200)
        level += 1
        leveled_up = True
    
    if leveled_up:
        cursor.execute("UPDATE users SET level = ?, xp = ? WHERE user_id = ?", (level, xp, uid))
        conn.commit()
        
        cursor.execute("SELECT channel_id FROM settings WHERE guild_id = ?", (message.guild.id,))
        set_ch = cursor.fetchone()
        channel = bot.get_channel(set_ch[0]) if set_ch else message.channel
        
        if channel:
            try: await channel.send(f"🎉 كفو {message.author.mention}! ارتقيت للمستوى **{level}**")
            except: pass
        await check_roles(message.author, level)

@tasks.loop(minutes=1)
async def voice_xp_task():
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if not member.bot and not member.voice.self_deaf:
                    uid = member.id
                    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, 0, 1)", (uid,))
                    cursor.execute("UPDATE users SET xp = xp + 20 WHERE user_id = ?", (uid,))
                    conn.commit()
                    # سيتم تصحيح المستوى عند أول رسالة يرسلها العضو بفضل نظام while في on_message
    conn.commit()

keep_alive()
if TOKEN: bot.run(TOKEN)
