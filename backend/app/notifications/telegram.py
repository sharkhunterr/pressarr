"""Telegram notification provider."""

import httpx

from app.notifications.base import NotificationPayload, NotificationProvider

TELEGRAM_API = "https://api.telegram.org"


class TelegramProvider(NotificationProvider):
    """Send notifications via the Telegram Bot API."""

    def _format_markdown(self, payload: NotificationPayload) -> str:
        """Format the notification body as Telegram Markdown."""
        title = self.format_title(payload)
        body = self.format_body(payload)
        return f"*{title}*\n{body}"

    async def send(self, payload: NotificationPayload) -> None:
        """Send a notification message (or photo) to a Telegram chat."""
        token = self.settings["token"]
        chat_id = self.settings["chat_id"]
        base_url = f"{TELEGRAM_API}/bot{token}"

        async with httpx.AsyncClient(timeout=10) as client:
            if payload.cover_url:
                resp = await client.post(
                    f"{base_url}/sendPhoto",
                    json={
                        "chat_id": chat_id,
                        "photo": payload.cover_url,
                        "caption": self._format_markdown(payload),
                        "parse_mode": "Markdown",
                    },
                )
            else:
                resp = await client.post(
                    f"{base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": self._format_markdown(payload),
                        "parse_mode": "Markdown",
                    },
                )
            resp.raise_for_status()

    async def test(self) -> tuple[bool, str]:
        """Send a test message to verify the Telegram bot works."""
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
            return True, "Telegram notification sent successfully."
        except httpx.HTTPStatusError as exc:
            return False, f"Telegram returned HTTP {exc.response.status_code}."
        except Exception as exc:
            return False, f"Telegram notification failed: {exc}"
