"""Gotify notification provider."""

import httpx

from app.notifications.base import NotificationPayload, NotificationProvider


class GotifyProvider(NotificationProvider):
    """Send notifications via Gotify server."""

    async def send(self, payload: NotificationPayload) -> None:
        """Send a notification message to Gotify."""
        server_url = self.settings["server_url"].rstrip("/")
        token = self.settings["token"]
        priority = self.settings.get("priority", 5)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{server_url}/message",
                headers={"X-Gotify-Key": token},
                json={
                    "title": self.format_title(payload),
                    "message": self.format_body(payload),
                    "priority": priority,
                },
            )
            resp.raise_for_status()

    async def test(self) -> tuple[bool, str]:
        """Send a test message to verify the Gotify connection."""
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
            return True, "Gotify notification sent successfully."
        except httpx.HTTPStatusError as exc:
            return False, f"Gotify returned HTTP {exc.response.status_code}."
        except Exception as exc:
            return False, f"Gotify notification failed: {exc}"
