"""Discord bot for study tracking with streak management."""

import os
import re
import asyncio
import logging
from datetime import datetime, time
from typing import Optional

import discord
from discord.ext import commands, tasks

from src.bot.tracker import StudyTracker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
REMINDER_CHANNEL_ID = os.getenv("DISCORD_REMINDER_CHANNEL_ID")
COMMAND_PREFIX = os.getenv("BOT_PREFIX", "!")

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
tracker = StudyTracker()


def format_duration(minutes: int) -> str:
    """Format minutes as human-readable duration."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


def parse_duration(duration_str: str) -> Optional[int]:
    """Parse duration string like '45m', '1h', '1h30m' to minutes."""
    duration_str = duration_str.lower().strip()
    
    # Pattern: 1h30m, 1h, 30m, 90
    pattern = r'^(?:(\d+)h)?(?:(\d+)m?)?$'
    match = re.match(pattern, duration_str)
    
    if not match:
        return None
    
    hours = int(match.group(1) or 0)
    mins = int(match.group(2) or 0)
    
    total = hours * 60 + mins
    return total if total > 0 else None


# ========== Events ==========

@bot.event
async def on_ready():
    """Called when bot is ready."""
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    
    # Start scheduled tasks
    if not daily_reminder.is_running():
        daily_reminder.start()
    
    logger.info("Bot is ready!")


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.CommandNotFound):
        pass  # Ignore unknown commands
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(f"❌ Error: {error}")


# ========== Study Commands ==========

@bot.command(name="studied", aliases=["s", "log"])
async def studied(ctx, class_name: Optional[str] = None, duration: Optional[str] = None):
    """
    Log a study session.
    
    Usage:
      !studied FIN303 45m     - Log 45 minutes for FIN303
      !studied FIN303 1h30m   - Log 1 hour 30 minutes
      !studied FIN303         - Log 30 minutes (default)
      !studied                - Log 30 minutes (prompts for class)
    """
    # Default duration
    if duration is None:
        minutes = 30
    else:
        minutes = parse_duration(duration)
        if minutes is None:
            await ctx.send("❌ Invalid duration. Use format like `45m`, `1h`, or `1h30m`")
            return
    
    # If no class specified, ask
    if class_name is None:
        classes = tracker.get_classes()
        if classes:
            class_list = ", ".join(classes)
            await ctx.send(f"📚 Which class? Your classes: `{class_list}`\n"
                          f"Reply with class name or type a new one:")
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            
            try:
                msg = await bot.wait_for("message", timeout=30.0, check=check)
                class_name = msg.content.strip()
            except asyncio.TimeoutError:
                await ctx.send("⏰ Timed out. Use `!studied <class> <duration>`")
                return
        else:
            class_name = "General"
    
    # Log the session
    result = tracker.log_session(class_name, minutes)
    session = result["session"]
    streak = result["streak"]
    
    # Build response
    emoji = "🔥" if streak["current"] >= 3 else "📚"
    response = (
        f"{emoji} **Logged {format_duration(minutes)} for {session['class']}!**\n\n"
        f"🔥 **Streak:** {streak['current']} day{'s' if streak['current'] != 1 else ''}"
    )
    
    if streak["current"] == streak["best"] and streak["current"] > 1:
        response += " 🏆 *New personal best!*"
    
    # Add today's summary
    today = tracker.get_today_summary()
    if today["session_count"] > 1:
        response += f"\n📊 **Today:** {format_duration(today['total_minutes'])} across {len(today['classes'])} class(es)"
    
    await ctx.send(response)


@bot.command(name="streak")
async def streak(ctx):
    """Show current study streak and stats."""
    streak_data = tracker.get_streak()
    today = tracker.get_today_summary()
    
    current = streak_data.get("current", 0)
    best = streak_data.get("best", 0)
    
    # Streak display with fire emojis
    if current >= 7:
        fire = "🔥" * min(current // 7, 5)
    elif current >= 3:
        fire = "🔥"
    else:
        fire = ""
    
    response = f"## {fire} Study Streak: {current} day{'s' if current != 1 else ''}\n\n"
    
    if best > current:
        response += f"🏆 **Best streak:** {best} days\n"
    
    if today["total_minutes"] > 0:
        response += f"📊 **Today:** {format_duration(today['total_minutes'])} ({today['session_count']} session{'s' if today['session_count'] != 1 else ''})\n"
    else:
        response += "📊 **Today:** No study yet! Use `!studied <class> <time>` to log.\n"
    
    await ctx.send(response)


@bot.command(name="week", aliases=["stats", "weekly"])
async def week_stats(ctx):
    """Show this week's study breakdown by class."""
    stats = tracker.get_week_stats()
    
    if stats["total_sessions"] == 0:
        await ctx.send("📊 **No study sessions this week!**\n\nLog your first with `!studied <class> <time>`")
        return
    
    response = "## 📊 This Week's Study\n\n"
    
    # By class breakdown
    by_class = stats["by_class"]
    for cls, data in sorted(by_class.items(), key=lambda x: x[1]["minutes"], reverse=True):
        bar_len = min(data["minutes"] // 15, 10)
        bar = "█" * bar_len
        response += f"**{cls}:** {format_duration(data['minutes'])} ({data['sessions']} sessions) {bar}\n"
    
    response += f"\n**Total:** {format_duration(stats['total_minutes'])} | "
    response += f"**Days studied:** {stats['days_studied']}/7 | "
    response += f"**Avg:** {format_duration(int(stats['avg_per_day']))}/day"
    
    await ctx.send(response)


# ========== Class Management ==========

@bot.command(name="classes", aliases=["class", "courses"])
async def list_classes(ctx):
    """List all your classes."""
    classes = tracker.get_classes()
    
    if not classes:
        await ctx.send("📚 **No classes yet!**\n\nAdd one with `!addclass FIN303`")
        return
    
    response = "## 📚 Your Classes\n\n"
    response += " • ".join(f"`{c}`" for c in classes)
    response += "\n\n*Add class:* `!addclass NAME` | *Remove:* `!removeclass NAME`"
    
    await ctx.send(response)


@bot.command(name="addclass", aliases=["addClass", "newclass"])
async def add_class(ctx, class_name: str):
    """Add a new class to track."""
    if tracker.add_class(class_name):
        await ctx.send(f"✅ Added class: **{class_name.upper()}**")
    else:
        await ctx.send(f"⚠️ Class `{class_name.upper()}` already exists!")


@bot.command(name="removeclass", aliases=["removeClass", "delclass"])
async def remove_class(ctx, class_name: str):
    """Remove a class from tracking."""
    if tracker.remove_class(class_name):
        await ctx.send(f"✅ Removed class: **{class_name.upper()}**")
    else:
        await ctx.send(f"⚠️ Class `{class_name.upper()}` not found!")


# ========== Scheduled Tasks ==========

@tasks.loop(time=time(hour=20, minute=0))  # 8 PM daily
async def daily_reminder():
    """Send daily reminder with neglected classes."""
    if not REMINDER_CHANNEL_ID:
        return
    
    try:
        channel = bot.get_channel(int(REMINDER_CHANNEL_ID))
        if not channel:
            logger.warning(f"Reminder channel {REMINDER_CHANNEL_ID} not found")
            return
        
        # Check for neglected classes
        neglected = tracker.get_neglected_classes(days=7)
        streak = tracker.get_streak()
        today = tracker.get_today_summary()
        
        # Build reminder
        parts = []
        
        # Study reminder if haven't studied today
        if today["total_minutes"] == 0:
            if streak["current"] > 0:
                parts.append(f"⚠️ **Don't break your {streak['current']}-day streak!** "
                            f"Log some study time with `!studied <class> <time>`")
            else:
                parts.append("📚 **Time to study!** Start a new streak with `!studied <class> <time>`")
        
        # Neglected classes warning
        if neglected:
            classes_str = ", ".join(f"`{c}`" for c in neglected)
            parts.append(f"🔔 **Classes you haven't studied in 7+ days:** {classes_str}")
        
        if parts:
            await channel.send("\n\n".join(parts))
    
    except Exception as e:
        logger.error(f"Error sending daily reminder: {e}")


@daily_reminder.before_loop
async def before_daily_reminder():
    """Wait until bot is ready before starting reminder loop."""
    await bot.wait_until_ready()


# ========== Help ==========

@bot.command(name="studyhelp")
async def study_help(ctx):
    """Show all study tracking commands."""
    help_text = """
## 📚 Study Tracker Commands

**Logging Study:**
`!studied FIN303 45m` - Log 45 mins for FIN303
`!studied FIN303 1h30m` - Log 1 hour 30 mins  
`!studied FIN303` - Log 30 mins (default)

**Stats:**
`!streak` - View your current streak
`!week` - Weekly stats by class

**Classes:**
`!classes` - List your classes
`!addclass FIN303` - Add a class
`!removeclass FIN303` - Remove a class

**Tips:**
- Log study right after each session
- Try to maintain your streak! 🔥
- I'll remind you at 8 PM if you haven't studied
"""
    await ctx.send(help_text)


# ========== Main ==========

def main():
    """Run the bot."""
    if not BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN environment variable not set!")
        logger.info("Get your token from https://discord.com/developers/applications")
        return
    
    logger.info("Starting Study Tracker Bot...")
    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
