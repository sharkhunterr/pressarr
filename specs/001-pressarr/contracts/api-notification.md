# API Contract: Notification

**Base path**: `/api/v1/notification`

---

## GET /api/v1/notification

List all configured notifications.

**Response** `200 OK`: `NotificationResource[]`

```json
[
  {
    "id": 1,
    "name": "My Discord",
    "notificationType": "discord",
    "settings": {
      "webhookUrl": "https://discord.com/api/webhooks/..."
    },
    "onGrab": true,
    "onDownload": true,
    "onImport": true,
    "onUpgrade": true,
    "onError": true,
    "enabled": true
  }
]
```

---

## GET /api/v1/notification/{id}

Get a single notification.

**Response** `200 OK`: `NotificationResource`

---

## POST /api/v1/notification

Add a notification channel.

**Request Body**: `NotificationCreateResource`

```json
{
  "name": "My Discord",
  "notificationType": "discord",
  "settings": {
    "webhookUrl": "https://discord.com/api/webhooks/..."
  },
  "onGrab": true,
  "onDownload": true,
  "onImport": true,
  "onUpgrade": true,
  "onError": true,
  "enabled": true
}
```

**Response** `201 Created`: `NotificationResource`

---

## PUT /api/v1/notification/{id}

Update a notification channel.

**Response** `200 OK`: `NotificationResource`

---

## DELETE /api/v1/notification/{id}

Delete a notification channel.

**Response** `200 OK`: `{}`

---

## POST /api/v1/notification/test

Send a test notification.

**Request Body**: Full notification config (same as create).

**Response** `200 OK`:

```json
{
  "isValid": true,
  "message": "Test notification sent successfully"
}
```
