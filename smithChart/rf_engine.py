"""
RF computation engine for transmission line input impedance.

All calculations use standard RF transmission line theory:
  Γ_in = Γ_L · exp(∓j2βℓ)

where:
  β  = 2π/λ   (phase constant)
  ℓ  = length in meters
  βℓ = 2π · (length_lambda)   (electrical length in radians)

Sign convention:
  toward_generator → Γ_in = Γ_L · exp(-j2βℓ)  [clockwise on Smith chart]
  toward_load      → Γ_in = Γ_L · exp(+j2βℓ)  [counter-clockwise]
"""

import numpy as np
from typing import Literal


def compute_tl_move(
    ZL: complex,
    Z0: float,
    length_lambda: float,
    direction: Literal["toward_generator", "toward_load"],
) -> dict:
    """
    Compute the input impedance seen looking into a lossless transmission line.

    Parameters
    ----------
    ZL : complex
        Load impedance (Ω).
    Z0 : float
        Characteristic impedance (Ω), must be real and positive.
    length_lambda : float
        Line length in wavelengths (0 ≤ ℓ ≤ 0.5λ).
    direction : str
        "toward_generator" or "toward_load".

    Returns
    -------
    dict with keys:
        gamma_L, gamma_in, Zin (complex)
        gamma_magnitude, VSWR, return_loss_dB, rotation_deg (float)
        arc_angles (np.ndarray of angles along the rotation arc, radians)
        angle_L, angle_in (float, radians)
    """
    if Z0 <= 0:
        raise ValueError(f"Z0 must be positive, got {Z0}")
    if length_lambda < 0 or length_lambda > 0.5:
        raise ValueError(f"length_lambda must be in [0, 0.5], got {length_lambda}")

    # --- Normalize load ---
    zL_norm = ZL / Z0  # normalized load impedance

    # --- Reflection coefficient at load ---
    gamma_L = (zL_norm - 1) / (zL_norm + 1)

    # --- Electrical length (radians) ---
    beta_l = 2 * np.pi * length_lambda  # βℓ in radians

    # --- Rotate on Γ-plane ---
    if direction == "toward_generator":
        # Phase decreases → clockwise rotation
        rotation_rad = -2 * beta_l
    else:
        # toward_load: phase increases → counter-clockwise
        rotation_rad = +2 * beta_l

    gamma_in = gamma_L * np.exp(1j * rotation_rad)

    # --- Input impedance (de-normalized) ---
    # Guard against Γ_in → 1 (open circuit at input, e.g. short-circuit load + λ/4).
    # This is a physically valid case; return a very large impedance to represent ∞.
    if abs(1 - gamma_in) < 1e-12:
        _gm = abs(gamma_L)
        return {
            "gamma_L": gamma_L,
            "gamma_in": gamma_in,
            "Zin": complex(1e18, 0.0),  # ≈ open circuit
            "gamma_magnitude": _gm,
            "VSWR": (1 + _gm) / (1 - _gm) if _gm < 1.0 else float("inf"),
            "return_loss_dB": -20 * np.log10(_gm) if _gm > 0 else float("inf"),
            "rotation_deg": np.degrees(abs(rotation_rad)),
            "arc_angles": np.linspace(np.angle(gamma_L), np.angle(gamma_L) + rotation_rad, 200),
            "angle_L": np.angle(gamma_L),
            "angle_in": np.angle(gamma_in),
        }
    Zin = Z0 * (1 + gamma_in) / (1 - gamma_in)

    # --- Derived quantities ---
    gamma_mag = abs(gamma_L)  # constant along lossless line

    if gamma_mag >= 1.0:
        VSWR = float("inf")
    else:
        VSWR = (1 + gamma_mag) / (1 - gamma_mag)

    if gamma_mag == 0:
        return_loss_dB = float("inf")
    else:
        return_loss_dB = -20 * np.log10(gamma_mag)

    rotation_deg = np.degrees(abs(rotation_rad))  # always positive degrees

    # --- Arc for visualization ---
    # Arc goes from angle_L to angle_L + rotation_rad in 200 steps
    angle_L = np.angle(gamma_L)
    angle_in = np.angle(gamma_in)
    arc_angles = np.linspace(angle_L, angle_L + rotation_rad, 200)

    return {
        "gamma_L": gamma_L,
        "gamma_in": gamma_in,
        "Zin": Zin,
        "gamma_magnitude": gamma_mag,
        "VSWR": VSWR,
        "return_loss_dB": return_loss_dB,
        "rotation_deg": rotation_deg,
        "arc_angles": arc_angles,
        "angle_L": angle_L,
        "angle_in": angle_in,
    }
