# API Contract: Quality Profile

**Base path**: `/api/v1/qualityprofile`

---

## GET /api/v1/qualityprofile

List all quality profiles.

**Response** `200 OK`: `QualityProfileResource[]`

```json
[
  {
    "id": 1,
    "name": "Default",
    "cutoff": "pdf_hq",
    "isDefault": true,
    "items": [
      {"quality": "unknown", "allowed": false, "sortOrder": 0},
      {"quality": "scan", "allowed": true, "sortOrder": 1},
      {"quality": "pdf_lq", "allowed": true, "sortOrder": 2},
      {"quality": "pdf_hq", "allowed": true, "sortOrder": 3},
      {"quality": "retail", "allowed": true, "sortOrder": 4},
      {"quality": "truepdf", "allowed": true, "sortOrder": 5}
    ]
  }
]
```

---

## GET /api/v1/qualityprofile/{id}

Get a single quality profile.

**Response** `200 OK`: `QualityProfileResource`

---

## POST /api/v1/qualityprofile

Create a quality profile.

**Request Body**: `QualityProfileCreateResource`

```json
{
  "name": "Best Quality Only",
  "cutoff": "truepdf",
  "items": [
    {"quality": "retail", "allowed": true, "sortOrder": 0},
    {"quality": "truepdf", "allowed": true, "sortOrder": 1}
  ]
}
```

**Response** `201 Created`: `QualityProfileResource`

---

## PUT /api/v1/qualityprofile/{id}

Update a quality profile.

**Response** `200 OK`: `QualityProfileResource`

**Response** `404 Not Found`

---

## DELETE /api/v1/qualityprofile/{id}

Delete a quality profile.

**Response** `200 OK`: `{}`

**Response** `409 Conflict`: `{"message": "Profile is in use by N magazines"}`
