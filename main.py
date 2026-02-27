import discord
from discord.ext import commands, tasks
import sqlite3
import os

# --- الإعدادات الأساسية ---
# جلب التوكن من إعدادات Render (Environment Variables)
TOKEN = os.environ.get('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- قاموس الرتب (استبدل الأصفار بآيديات الرتب من سيرفرك) ---
LEVEL_ROLES = {
    10: 1477037250708766944,
    20: 1477037367067021432,
    30: 1477037407558828082,
    40: 1477040533904818399,
    50: 1477037439410372651,
    60: 1477037522222846145,
    70: 1477037350709235803,
    80: 1477037602883375275,
    90: 1477037634483388460,
    100: 1477037663788863579
}

# --- إعداد قاعدة البيانات ---
# ملاحظة: في Render، إذا لم تستخدم Database خارجية، البيانات ستُحذف عند إعادة التشغيل
conn = sqlite3.connect('levels.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (user_id INTEGER PRIMARY KEY, xp INTEGER, level INTEGER)''')
conn.commit()

async def update_member_roles(member, level):
    """تحديث رتبة العضو بناءً على ليفله"""
    if not member or not hasattr(member, 'add_roles'): return
    
    eligible_role_id = None
    for lvl in sorted(LEVEL_ROLES.keys(), reverse=True):
        if level >= lvl:
            eligible_role_id = LEVEL_ROLES[lvl]
            break
            
    if eligible_role_id and eligible_role_id != 0:
        new_role = member.guild.get_role(eligible_role_id)
        if new_role and new_role not in member.roles:
            await member.add_roles(new_role)
            # تنظيف الرتب القديمة
            for lvl, rid in LEVEL_ROLES.items():
                if rid != eligible_role_id and rid != 0:
                    old_role = member.guild.get_role(rid)
                    if old_role and old_role in member.roles:
                        await member.remove_roles(old_role)

@bot.event
async def on_ready():
    print(f'✅ البوت متصل الآن: {bot.user}')
    if not voice_xp_task.is_running():
        voice_xp_task.start()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    
    user_id = message.author.id
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, 0, 1)", (user_id,))
    cursor.execute("UPDATE users SET xp = xp + 10 WHERE user_id = ?", (user_id,))
    
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
    xp, level = cursor.fetchone()
    
    # معادلة التلفيل: كل ليفل يحتاج 200 نقطة
    if xp >= (level * 200):
        new_level = level + 1
        cursor.execute("UPDATE users SET level = ?, xp = 0 WHERE user_id = ?", (new_level, user_id))
        conn.commit()
        try:
            await message.channel.send(f"🎉 مبروك {message.author.mention}! وصلت للمستوى **{new_level}**")
            await update_member_roles(message.author, new_level)
        except: pass
    
    conn.commit()
    await bot.process_commands(message)

@tasks.loop(minutes=1)
async def voice_xp_task():
    """زيادة نقاط المتواجدين في الصوت كل دقيقة"""
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

@bot.command()
async def rank(ctx, member: discord.Member = None):
    """أمر معرفة المستوى"""
    member = member or ctx.author
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (member.id,))
    data = cursor.fetchone()
    if data:
        xp, level = data
        await ctx.send(f"📊 **{member.display_name}**\n⭐ المستوى: `{level}`\n✨ النقاط: `{xp}/{level*200}`")
    else:
        await ctx.send("لا توجد بيانات حالياً.")

# التشغيل
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: لم يتم ضبط DISCORD_TOKEN في إعدادات Render")
