"""Discord webhook notification provider."""

import httpx

from app.notifications.base import NotificationPayload, NotificationProvider

# Embed colors per event type
EVENT_COLORS = {
    "grab": 0xE85D04,
    "download": 0x22C55E,
    "import": 0x22C55E,
    "upgrade": 0x3B82F6,
    "error": 0xEF4444,
}


class DiscordProvider(NotificationProvider):
    """Send notifications via Discord webhook."""

    def _build_embed(self, payload: NotificationPayload) -> dict:
        """Build a Discord embed object from the payload."""
        embed: dict = {
            "title": self.format_title(payload),
            "description": self.format_body(payload),
            "color": EVENT_COLORS.get(payload.event_type, 0x808080),
        }
        if payload.cover_url:
            embed["thumbnail"] = {"url": payload.cover_url}
        return embed

    async def send(self, payload: NotificationPayload) -> None:
        """Send a notification embed to the Discord webhook."""
        webhook_url = self.settings["webhook_url"]
        embed = self._build_embed(payload)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                webhook_url,
                json={"embeds": [embed]},
            )
            resp.raise_for_status()

    async def test(self) -> tuple[bool, str]:
        """Send a test embed to verify the webhook works."""
        test_payload = NotificationPayload(
            event_type="grab",
            magazine_title="Test Magazine",
            issue_number=1,
            issue_title="Test Issue",
            quality="PDF",
            message="This is a test notification from Pressarr.",
        )
        try:
            await self.send(test_payload)
            return True, "Discord notification sent successfully."
        except httpx.HTTPStatusError as exc:
            return False, f"Discord returned HTTP {exc.response.status_code}."
        except Exception as exc:
            return False, f"Discord notification failed: {exc}"
