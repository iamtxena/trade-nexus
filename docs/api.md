# Trade Nexus API Reference

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: Set via `ML_BACKEND_URL` environment variable

## Authentication

API requests should include authentication headers when required:

```
X-API-Key: your-api-key
Authorization: Bearer <token>
```

## Endpoints

### Health Check

#### GET /health

Check service health status.

**Response:**
```json
{
  "status": "healthy"
}
```

#### GET /api/health

Check ML service health.

**Response:**
```json
{
  "status": "healthy",
  "service": "trade-nexus-ml"
}
```

---

### Predictions

#### POST /api/predict

Generate ML prediction for a symbol.

**Request Body:**
```json
{
  "symbol": "BTC",
  "prediction_type": "price",
  "timeframe": "24h",
  "features": {
    "current_price": 50000,
    "momentum": 0.5,
    "volume_ratio": 1.2
  }
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| symbol | string | Yes | Trading symbol (BTC, ETH, etc.) |
| prediction_type | string | Yes | Type: price, volatility, sentiment, trend |
| timeframe | string | No | Prediction horizon (default: 24h) |
| features | object | No | Additional features for prediction |

**Response:**
```json
{
  "symbol": "BTC",
  "prediction_type": "price",
  "value": {
    "predicted": 51500.00,
    "upper": 54075.00,
    "lower": 48925.00,
    "timeframe": "24h",
    "confidence": 72.5
  },
  "confidence": 72.5,
  "timeframe": "24h"
}
```

---

### Anomaly Detection

#### POST /api/anomaly

Detect anomalies in market data.

**Request Body:**
```json
{
  "symbol": "BTC",
  "data": [100, 101, 102, 103, 150]
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| symbol | string | Yes | Trading symbol |
| data | number[] | Yes | Time series data to analyze |

**Response:**
```json
{
  "symbol": "BTC",
  "is_anomaly": true,
  "score": 0.85,
  "details": {
    "z_score": 3.2,
    "mean": 103.0,
    "std": 15.5,
    "latest_value": 150,
    "threshold": 2.5,
    "analysis": "Significant price spike detected..."
  }
}
```

---

### Portfolio Optimization

#### POST /api/optimize

Get optimal portfolio allocation.

**Request Body:**
```json
{
  "holdings": {
    "BTC": 1.0,
    "ETH": 10.0
  },
  "predictions": [
    {
      "symbol": "BTC",
      "confidence": 70,
      "value": {
        "direction": "bullish"
      }
    },
    {
      "symbol": "ETH",
      "confidence": 60,
      "value": {
        "direction": "bullish"
      }
    }
  ],
  "constraints": {
    "max_position_size": 0.4,
    "min_position_size": 0.1
  }
}
```

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| holdings | object | Yes | Current holdings {symbol: quantity} |
| predictions | array | Yes | ML predictions for assets |
| constraints | object | No | Optimization constraints |

**Response:**
```json
{
  "allocations": {
    "BTC": 0.54,
    "ETH": 0.46
  },
  "expected_return": 6.5,
  "risk_score": 54.0
}
```

---

## Error Responses

All endpoints return errors in the following format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common Status Codes:**
| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid or missing authentication |
| 404 | Not Found - Resource doesn't exist |
| 422 | Unprocessable Entity - Validation error |
| 500 | Internal Server Error |

---

## Rate Limits

| Tier | Requests/min | Requests/day |
|------|--------------|--------------|
| Free | 60 | 1,000 |
| Pro | 300 | 10,000 |
| Enterprise | Unlimited | Unlimited |

---

## Webhooks

Configure webhooks to receive real-time updates:

### Prediction Webhook

Triggered when a new prediction is generated.

**Payload:**
```json
{
  "event": "prediction.created",
  "data": {
    "symbol": "BTC",
    "prediction_type": "price",
    "value": {...},
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Anomaly Webhook

Triggered when an anomaly is detected.

**Payload:**
```json
{
  "event": "anomaly.detected",
  "data": {
    "symbol": "BTC",
    "score": 0.85,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

---

## SDK Examples

### TypeScript (Frontend)

```typescript
// Using the predictor agent
import { getPrediction } from '@/lib/ai/predictor-agent';

const prediction = await getPrediction({
  symbol: 'BTC',
  predictionType: 'price',
  timeframe: '24h',
  features: { current_price: 50000 },
});
```

### Python

```python
import httpx

async def get_prediction(symbol: str, prediction_type: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/predict",
            json={
                "symbol": symbol,
                "prediction_type": prediction_type,
                "timeframe": "24h",
            },
        )
        return response.json()
```

### cURL

```bash
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "prediction_type": "price",
    "timeframe": "24h"
  }'
```
