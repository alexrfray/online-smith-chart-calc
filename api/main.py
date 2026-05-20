"""
Smith Chart Visualization Service
Stateless FastAPI backend for RF Smith chart computations.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from smithChart.models import SmithMoveRequest, SmithMoveResponse
from smithChart.rf_engine import compute_tl_move
from smithChart.smith_renderer import render_smith_move

app = FastAPI(
    title="Smith Chart Service",
    description="Stateless RF Smith chart computation and visualization API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "smith-chart-service"}


@app.post("/smith/move", response_model=SmithMoveResponse)
def smith_move(req: SmithMoveRequest) -> SmithMoveResponse:
    """
    Compute input impedance after moving along a lossless transmission line,
    and return a rendered Smith chart showing the transformation path.

    - **ZL**: Load impedance (complex)
    - **Z0**: Characteristic impedance (real, Ω)
    - **length_lambda**: Line length in wavelengths (λ)
    - **direction**: "toward_generator" or "toward_load"
    """
    try:
        rf_result = compute_tl_move(
            ZL=complex(req.ZL.real, req.ZL.imag),
            Z0=req.Z0,
            length_lambda=req.length_lambda,
            direction=req.direction,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        chart = render_smith_move(rf_result, req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering error: {e}")

    return SmithMoveResponse(
        ZL=req.ZL,
        Zin={"real": round(rf_result["Zin"].real, 6), "imag": round(rf_result["Zin"].imag, 6)},
        Z0=req.Z0,
        length_lambda=req.length_lambda,
        direction=req.direction,
        gamma_L={"real": round(rf_result["gamma_L"].real, 6), "imag": round(rf_result["gamma_L"].imag, 6)},
        gamma_in={"real": round(rf_result["gamma_in"].real, 6), "imag": round(rf_result["gamma_in"].imag, 6)},
        gamma_magnitude=round(rf_result["gamma_magnitude"], 6),
        VSWR=round(rf_result["VSWR"], 4),
        return_loss_dB=round(rf_result["return_loss_dB"], 4),
        rotation_deg=round(rf_result["rotation_deg"], 4),
        chart_svg=chart["svg"],
        chart_png_b64=chart["png_b64"],
    )
