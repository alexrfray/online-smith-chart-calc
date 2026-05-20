# Smith Chart Visualization Service

Stateless FastAPI backend for RF Smith chart computations and visualization. Built for educational use and Kubernetes-friendly deployment.

## Features

- **POST /smith/move** — compute input impedance after moving along a lossless transmission line, with a rendered Smith chart
- Returns both SVG (primary) and base64-encoded PNG (fallback)
- Fully stateless — no database, no sessions
- Docker-ready with multi-worker support

---

## Quick Start

### Run locally

```bash
pip install -r requirements.txt
python main.py
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### Run with Docker

```bash
docker-compose up --build
```

---

## API Reference

### `GET /health`

```json
{ "status": "ok", "service": "smith-chart-service" }
```

---

### `POST /smith/move`

Compute Zin after moving along a transmission line. Returns computed RF values **and** a rendered Smith chart.

#### Request body

```json
{
  "ZL": { "real": 75, "imag": 25 },
  "Z0": 50,
  "length_lambda": 0.2,
  "direction": "toward_generator"
}
```

| Field | Type | Range | Description |
|---|---|---|---|
| `ZL.real` | float | ≥ 0 | Load resistance (Ω) |
| `ZL.imag` | float | any | Load reactance (Ω) |
| `Z0` | float | > 0 | Characteristic impedance (Ω) |
| `length_lambda` | float | [0, 0.5] | Line length in wavelengths |
| `direction` | string | enum | `"toward_generator"` or `"toward_load"` |

#### Response body

```json
{
  "ZL": { "real": 75.0, "imag": 25.0 },
  "Zin": { "real": 36.357, "imag": -20.49 },
  "Z0": 50.0,
  "length_lambda": 0.2,
  "direction": "toward_generator",
  "gamma_L":  { "real": 0.23077, "imag": 0.15385 },
  "gamma_in": { "real": -0.09627, "imag": -0.26011 },
  "gamma_magnitude": 0.27735,
  "VSWR": 1.7676,
  "return_loss_dB": 11.1372,
  "rotation_deg": 144.0,
  "chart_svg": "<svg ...>...</svg>",
  "chart_png_b64": "iVBORw0KGgo..."
}
```

---

## RF Theory

The core computation uses standard transmission line theory:

```
Γ_in = Γ_L · exp(−j2βℓ)   [toward generator]
Γ_in = Γ_L · exp(+j2βℓ)   [toward load]

where:
  β = 2π/λ
  βℓ = 2π · length_lambda   (radians)

Zin = Z0 · (1 + Γ_in) / (1 − Γ_in)
```

Moving toward the generator rotates the point **clockwise** on the Smith chart. Each full rotation (360°) corresponds to 0.5λ.

### Key identities (useful for testing)

| Condition | Result |
|---|---|
| `ZL = Z0` | `Γ = 0`, `Zin = Z0` for any length |
| `length = 0.5λ` | `Zin = ZL` (half-wave identity) |
| `length = 0.25λ`, real loads | `Zin = Z0²/ZL` (quarter-wave transformer) |
| Short circuit (`ZL=0`) + `0.25λ` | Open circuit at input |

---

## Project Structure

```
smith-chart-service/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, routes
│   ├── models.py         # Pydantic request/response models
│   ├── rf_engine.py      # Pure RF math (transmission line theory)
│   └── smith_renderer.py # Matplotlib Smith chart rendering
├── tests.py              # 31 unit + integration tests
├── main.py               # uvicorn entrypoint
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Running Tests

```bash
pip install pytest httpx
pytest tests.py -v
```

31 tests covering:
- RF physics identities (matched load, half-wave, quarter-wave, short/open circuit)
- API validation (direction enum, Z0 sign, ZL resistance, length bounds)
- Response format (SVG string, PNG magic bytes, field presence)
- Edge cases (zero length, degenerate cases)
