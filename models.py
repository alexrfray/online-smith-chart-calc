"""
Pydantic models for Smith chart API request/response validation.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ComplexImpedance(BaseModel):
    real: float = Field(..., description="Real part (resistance), Ω")
    imag: float = Field(0.0, description="Imaginary part (reactance), Ω")

    model_config = {"json_schema_extra": {"example": {"real": 75.0, "imag": 25.0}}}


class SmithMoveRequest(BaseModel):
    ZL: ComplexImpedance = Field(..., description="Load impedance")
    Z0: float = Field(50.0, gt=0, description="Characteristic impedance, Ω")
    length_lambda: float = Field(
        ...,
        ge=0.0,
        le=0.5,
        description="Transmission line length in wavelengths (0–0.5λ)",
    )
    direction: Literal["toward_generator", "toward_load"] = Field(
        "toward_generator",
        description="Direction of travel along the transmission line",
    )

    @field_validator("ZL")
    @classmethod
    def load_resistance_positive(cls, v: ComplexImpedance) -> ComplexImpedance:
        if v.real < 0:
            raise ValueError("Load resistance (real part of ZL) must be ≥ 0")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "ZL": {"real": 75, "imag": 25},
                "Z0": 50,
                "length_lambda": 0.2,
                "direction": "toward_generator",
            }
        }
    }


class SmithMoveResponse(BaseModel):
    # --- Inputs echoed back ---
    ZL: ComplexImpedance
    Z0: float
    length_lambda: float
    direction: str

    # --- Computed values ---
    Zin: dict  # {"real": float, "imag": float}
    gamma_L: dict  # reflection coefficient at load
    gamma_in: dict  # reflection coefficient at input
    gamma_magnitude: float = Field(..., description="|Γ| — same for both ends")
    VSWR: float = Field(..., description="Voltage Standing Wave Ratio")
    return_loss_dB: float = Field(..., description="Return loss in dB")
    rotation_deg: float = Field(..., description="Clockwise rotation on Smith chart (degrees)")

    # --- Rendered chart ---
    chart_svg: Optional[str] = Field(None, description="SVG string of Smith chart")
    chart_png_b64: Optional[str] = Field(None, description="Base64-encoded PNG fallback")
