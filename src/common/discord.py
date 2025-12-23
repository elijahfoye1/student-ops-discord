"""Discord webhook posting with embeds."""

import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from src.common.http import HTTPClient

logger = logging.getLogger(__name__)


# Discord embed colors
COLORS = {
    "red": 0xED4245,
    "orange": 0xFFA500,
    "yellow": 0xFEE75C,
    "green": 0x57F287,
    "blue": 0x5865F2,
    "purple": 0x9B59B6,
    "gray": 0x95A5A6,
    "critical": 0xED4245,
    "high": 0xFFA500,
    "medium": 0xFEE75C,
    "low": 0x57F287
}


@dataclass
class EmbedField:
    """A field in a Discord embed."""
    name: str
    value: str
    inline: bool = False


@dataclass
class Embed:
    """A Discord embed message."""
    title: str
    description: str = ""
    color: int = COLORS["blue"]
    url: Optional[str] = None
    fields: List[EmbedField] = field(default_factory=list)
    footer: Optional[str] = None
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Discord API format."""
        data = {
            "title": self.title[:256],  # Discord limit
            "description": self.description[:4096] if self.description else None,
            "color": self.color
        }
        
        if self.url:
            data["url"] = self.url
        
        if self.fields:
            data["fields"] = [
                {
                    "name": f.name[:256],
                    "value": f.value[:1024],
                    "inline": f.inline
                }
                for f in self.fields[:25]  # Discord limit
            ]
        
        if self.footer:
            data["footer"] = {"text": self.footer[:2048]}
        
        if self.timestamp:
            data["timestamp"] = self.timestamp
        
        return {k: v for k, v in data.items() if v is not None}


class DiscordWebhook:
    """Discord webhook client for posting messages and embeds."""
    
    def __init__(
        self,
        webhook_url: Optional[str] = None,
        channel_env_var: Optional[str] = None,
        dry_run: bool = False
    ):
        """
        Initialize webhook client.
        
        Args:
            webhook_url: Direct webhook URL
            channel_env_var: Environment variable name containing webhook URL
            dry_run: If True, print instead of posting
        """
        self.dry_run = dry_run
        
        if webhook_url:
            self.webhook_url = webhook_url
        elif channel_env_var:
            self.webhook_url = os.environ.get(channel_env_var)
        else:
            self.webhook_url = None
        
        self.http = HTTPClient()
    
    @property
    def is_configured(self) -> bool:
        """Check if webhook URL is available."""
        return bool(self.webhook_url) or self.dry_run
    
    def post(
        self,
        content: Optional[str] = None,
        embeds: Optional[List[Embed]] = None,
        username: Optional[str] = None
    ) -> bool:
        """
        Post a message to Discord.
        
        Args:
            content: Plain text message (optional)
            embeds: List of Embed objects (optional)
            username: Override webhook username (optional)
        
        Returns:
            True if successful (or dry-run).
        """
        if not content and not embeds:
            logger.warning("Nothing to post: no content or embeds")
            return False
        
        payload: Dict[str, Any] = {}
        
        if content:
            payload["content"] = content[:2000]  # Discord limit
        
        if embeds:
            payload["embeds"] = [e.to_dict() for e in embeds[:10]]  # Discord limit
        
        if username:
            payload["username"] = username
        
        if self.dry_run:
            self._print_dry_run(payload)
            return True
        
        if not self.webhook_url:
            logger.error("No webhook URL configured")
            return False
        
        try:
            response = self.http.post(self.webhook_url, json=payload)
            logger.info(f"Posted to Discord: {response.status_code}")
            return True
        except Exception as e:
            logger.error(f"Failed to post to Discord: {e}")
            return False
    
    def _print_dry_run(self, payload: Dict[str, Any]) -> None:
        """Print message for dry-run mode."""
        print("\n" + "=" * 60)
        print("📤 DRY-RUN: Would post to Discord")
        print("=" * 60)
        
        if "content" in payload:
            print(f"\n📝 Content: {payload['content']}")
        
        if "embeds" in payload:
            for i, embed in enumerate(payload["embeds"]):
                print(f"\n📎 Embed {i + 1}:")
                print(f"   Title: {embed.get('title', 'N/A')}")
                if embed.get("description"):
                    print(f"   Description: {embed['description'][:100]}...")
                if embed.get("fields"):
                    for field in embed["fields"]:
                        print(f"   • {field['name']}: {field['value'][:50]}...")
                if embed.get("footer"):
                    print(f"   Footer: {embed['footer']['text']}")
        
        print("\n" + "=" * 60 + "\n")


def get_webhook(channel: str, dry_run: bool = False) -> DiscordWebhook:
    """
    Get a webhook for a specific channel.
    
    Channel names map to environment variables:
    - "alerts" -> DISCORD_WEBHOOK_ALERTS
    - "daily_brief" -> DISCORD_WEBHOOK_DAILY
    etc.
    """
    env_var_map = {
        "daily_brief": "DISCORD_WEBHOOK_DAILY",
        "daily": "DISCORD_WEBHOOK_DAILY",
        "alerts": "DISCORD_WEBHOOK_ALERTS",
        "study_plan": "DISCORD_WEBHOOK_STUDYPLAN",
        "ai": "DISCORD_WEBHOOK_AI",
        "ai_tech": "DISCORD_WEBHOOK_AI",
        "earnings": "DISCORD_WEBHOOK_EARNINGS",
        "macro": "DISCORD_WEBHOOK_MACRO",
        "market_alerts": "DISCORD_WEBHOOK_MARKET_ALERTS",
        "analyst": "DISCORD_WEBHOOK_ANALYST",
        "valuation": "DISCORD_WEBHOOK_VALUATION",
        "bridge": "DISCORD_WEBHOOK_BRIDGE",
        "classroom_bridge": "DISCORD_WEBHOOK_BRIDGE"
    }
    
    env_var = env_var_map.get(channel, f"DISCORD_WEBHOOK_{channel.upper()}")
    return DiscordWebhook(channel_env_var=env_var, dry_run=dry_run)


def build_alert_embed(
    title: str,
    description: str,
    priority: str = "medium",
    url: Optional[str] = None,
    fields: Optional[List[tuple]] = None,
    footer: Optional[str] = None
) -> Embed:
    """Build a standardized alert embed."""
    color = COLORS.get(priority, COLORS["blue"])
    
    embed = Embed(
        title=title,
        description=description,
        color=color,
        url=url,
        footer=footer
    )
    
    if fields:
        for name, value, inline in fields:
            embed.fields.append(EmbedField(name=name, value=value, inline=inline))
    
    return embed


def build_daily_brief_embed(
    today_tasks: List[dict],
    tomorrow_tasks: List[dict],
    week_tasks: List[dict]
) -> Embed:
    """Build the daily brief embed with sections."""
    lines = []
    
    if today_tasks:
        lines.append("**📅 Today**")
        for task in today_tasks[:5]:
            lines.append(f"• {task['title']} ({task.get('course_name', 'Unknown')})")
        lines.append("")
    
    if tomorrow_tasks:
        lines.append("**📆 Tomorrow**")
        for task in tomorrow_tasks[:5]:
            lines.append(f"• {task['title']} ({task.get('course_name', 'Unknown')})")
        lines.append("")
    
    if week_tasks:
        lines.append("**🗓️ This Week**")
        for task in week_tasks[:5]:
            lines.append(f"• {task['title']} ({task.get('course_name', 'Unknown')})")
    
    if not lines:
        lines.append("✅ No upcoming deadlines!")
    
    return Embed(
        title="📚 Daily Academic Brief",
        description="\n".join(lines),
        color=COLORS["blue"],
        footer="Stay on top of your work!"
    )


def build_news_embed(
    title: str,
    summary: str,
    category: str,
    url: str,
    why_it_matters: Optional[str] = None
) -> Embed:
    """Build a news item embed."""
    category_colors = {
        "ai": COLORS["purple"],
        "earnings": COLORS["green"],
        "macro": COLORS["orange"]
    }
    
    color = category_colors.get(category, COLORS["gray"])
    category_emoji = {"ai": "🤖", "earnings": "💰", "macro": "📊"}.get(category, "📰")
    
    description = summary
    if why_it_matters:
        description += f"\n\n**Why it matters:** {why_it_matters}"
    
    return Embed(
        title=f"{category_emoji} {title}",
        description=description,
        color=color,
        url=url
    )
