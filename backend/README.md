# Trade Nexus ML Backend

Python ML backend for Trade Nexus autonomous trading orchestrator.

## Features

- **ML Predictions**: LSTM-based price forecasting
- **Anomaly Detection**: Statistical anomaly detection for market data
- **Portfolio Optimization**: AI-powered allocation recommendations
- **LangGraph Agents**: Orchestrated ML workflows with LangChain

## Tech Stack

- **Framework**: FastAPI
- **ML**: PyTorch, scikit-learn, pandas
- **Agents**: LangGraph, LangChain
- **AI Provider**: xAI Grok

## Getting Started

### Prerequisites

- Python >= 3.11
- [uv](https://github.com/astral-sh/uv)

### Installation

```bash
# Install dependencies
uv sync

# Copy environment file
cp .env.example .env
# Edit .env with your credentials

# Run development server
uv run uvicorn src.main:app --reload
```

### Running Tests

```bash
uv run pytest
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/predict` | Generate ML predictions |
| POST | `/api/anomaly` | Detect market anomalies |
| POST | `/api/optimize` | Portfolio optimization |
| GET | `/api/health` | Health check |

## Project Structure

```
backend/
├── src/
│   ├── api/           # FastAPI routes
│   ├── agents/        # LangGraph agents
│   ├── models/        # ML models
│   ├── services/      # Business logic
│   └── schemas/       # Pydantic schemas
├── notebooks/         # Jupyter prototyping
└── tests/             # Test files
```

## License

MIT
