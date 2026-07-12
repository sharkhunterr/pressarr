"""Generic webhook notification provider."""

from dataclasses import asdict

import httpx

from app.notifications.base import NotificationPayload, NotificationProvider


class WebhookProvider(NotificationProvider):
    """Send notifications via a configurable HTTP webhook."""

    async def send(self, payload: NotificationPayload) -> None:
        """Send the notification payload to the configured webhook URL."""
        url = self.settings["url"]
        method = self.settings.get("method", "POST").upper()
        headers = self.settings.get("headers", {})
        body_template = self.settings.get("body_template")

        json_body: dict
        if body_template:
            # body_template is a dict that can reference payload fields
            json_body = body_template
        else:
            json_body = asdict(payload)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body,
            )
            resp.raise_for_status()

    async def test(self) -> tuple[bool, str]:
        """Send a test payload to verify the webhook works."""
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
            return True, "Webhook notification sent successfully."
        except httpx.HTTPStatusError as exc:
            return False, f"Webhook returned HTTP {exc.response.status_code}."
        except Exception as exc:
            return False, f"Webhook notification failed: {exc}"
