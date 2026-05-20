"""
Smith chart renderer.

Produces a high-quality Smith chart SVG (and PNG fallback) showing:
  1. Base Smith chart grid (resistance + reactance circles)
  2. Constant |Γ| circle
  3. Rotation arc (the transmission line path)
  4. ZL and Zin points with annotations
  5. Arrow showing direction of travel
"""

import io
import base64
from typing import Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")  # Must be before pyplot import — headless rendering
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
import matplotlib.patheffects as pe
from skrf import plotting as skrf_plot

# ── Design tokens ──────────────────────────────────────────────────────────────
PALETTE = {
    "bg": "#0f1117",
    "grid": "#1e2330",
    "grid_line": "#2a3045",
    "resistance": "#3a4a6b",
    "reactance": "#2d3d5c",
    "gamma_circle": "#4a6fa5",
    "arc": "#00c896",          # vivid teal — the movement path
    "ZL": "#ff6b6b",           # warm red — load point
    "Zin": "#4ecdc4",          # cyan — input point
    "arrow": "#ffd93d",        # amber — direction arrow
    "label_ZL": "#ff8080",
    "label_Zin": "#6eeee8",
    "text": "#e0e6f0",
    "subtitle": "#7a8aaa",
    "watermark": "#ffffff08",
}

FIG_SIZE = (9, 9)
DPI = 150


def _draw_smith_grid(ax: plt.Axes) -> None:
    """
    Draw a professional-looking Smith chart grid manually.
    We use skrf's smith() for the base circles, then style everything.
    """
    # skrf draws on whatever current axes; pass ours explicitly
    skrf_plot.smith(ax=ax, draw_labels=True, chart_type="z", ref_imm=1.0)

    # Style every line skrf drew
    for line in ax.get_lines():
        line.set_color(PALETTE["resistance"])
        line.set_linewidth(0.6)
        line.set_alpha(0.55)
        line.set_zorder(1)

    # Style text labels
    for txt in ax.texts:
        txt.set_color(PALETTE["subtitle"])
        txt.set_fontsize(7)
        txt.set_alpha(0.7)

    # Outer unit circle — draw a crisp version on top
    theta = np.linspace(0, 2 * np.pi, 500)
    ax.plot(np.cos(theta), np.sin(theta), color=PALETTE["grid_line"],
            linewidth=1.2, zorder=2, alpha=0.9)


def _annotate_point(
    ax: plt.Axes,
    gamma: complex,
    Z: complex,
    Z0: float,
    label: str,
    color: str,
    marker: str = "o",
    offset: tuple = (12, 12),
) -> None:
    """Plot and annotate an impedance point on the Γ-plane."""
    ax.plot(
        gamma.real, gamma.imag,
        marker=marker,
        color=color,
        markersize=11,
        markeredgecolor="white",
        markeredgewidth=1.2,
        zorder=10,
        clip_on=False,
    )

    # Primary label (ZL / Zin)
    ax.annotate(
        label,
        xy=(gamma.real, gamma.imag),
        xytext=offset,
        textcoords="offset points",
        fontsize=12,
        fontweight="bold",
        color=color,
        zorder=11,
        path_effects=[
            pe.withStroke(linewidth=3, foreground=PALETTE["bg"])
        ],
    )

    # Secondary label: impedance value
    sign = "+" if Z.imag >= 0 else "−"
    imag_abs = abs(Z.imag)
    z_str = f"({Z.real:.1f} {sign} j{imag_abs:.1f}) Ω"
    ax.annotate(
        z_str,
        xy=(gamma.real, gamma.imag),
        xytext=(offset[0], offset[1] - 16),
        textcoords="offset points",
        fontsize=8,
        color=PALETTE["subtitle"],
        zorder=11,
        path_effects=[
            pe.withStroke(linewidth=2, foreground=PALETTE["bg"])
        ],
    )


def _draw_direction_arrow(
    ax: plt.Axes,
    arc_angles: np.ndarray,
    gamma_mag: float,
    color: str,
) -> None:
    """Draw a small arrowhead near the midpoint of the arc."""
    n = len(arc_angles)
    mid = n // 2
    # Arrow from midpoint to midpoint+1
    x0 = gamma_mag * np.cos(arc_angles[mid])
    y0 = gamma_mag * np.sin(arc_angles[mid])
    x1 = gamma_mag * np.cos(arc_angles[mid + 1])
    y1 = gamma_mag * np.sin(arc_angles[mid + 1])

    ax.annotate(
        "",
        xy=(x1, y1),
        xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=2.0,
            mutation_scale=18,
        ),
        zorder=9,
    )


def render_smith_move(rf_result: dict, req, image_as_b64: bool = False) -> dict:
    """
    Render the Smith chart and return SVG string + PNG base64.

    Parameters
    ----------
    rf_result : dict
        Output from rf_engine.compute_tl_move().
    req : SmithMoveRequest
        Original request (for labels/title).

    Returns
    -------
    dict with 'svg' (str | None) and 'png_b64' (str | None).
    """
    gamma_L = rf_result["gamma_L"]
    gamma_in = rf_result["gamma_in"]
    gamma_mag = rf_result["gamma_magnitude"]
    arc_angles = rf_result["arc_angles"]
    ZL = complex(req.ZL.real, req.ZL.imag)
    Zin = rf_result["Zin"]
    Z0 = req.Z0

    # ── Figure setup ──────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=FIG_SIZE, facecolor=PALETTE["bg"])
    ax.set_facecolor(PALETTE["bg"])

    # ── 1. Smith chart grid ───────────────────────────────────────────────────
    _draw_smith_grid(ax)

    # ── 2. Constant |Γ| circle ────────────────────────────────────────────────
    theta = np.linspace(0, 2 * np.pi, 500)
    ax.plot(
        gamma_mag * np.cos(theta),
        gamma_mag * np.sin(theta),
        color=PALETTE["gamma_circle"],
        linewidth=1.4,
        linestyle="--",
        alpha=0.75,
        zorder=3,
        label=f"|Γ| = {gamma_mag:.3f}",
    )

    # ── 3. Rotation arc ───────────────────────────────────────────────────────
    arc_x = gamma_mag * np.cos(arc_angles)
    arc_y = gamma_mag * np.sin(arc_angles)
    ax.plot(
        arc_x, arc_y,
        color=PALETTE["arc"],
        linewidth=3.0,
        solid_capstyle="round",
        zorder=6,
        label=f"Move {req.length_lambda}λ ({rf_result['rotation_deg']:.1f}°)",
    )

    # Direction arrow near arc midpoint
    if len(arc_angles) > 3:
        _draw_direction_arrow(ax, arc_angles, gamma_mag, PALETTE["arrow"])

    # ── 4. ZL and Zin points ──────────────────────────────────────────────────
    _annotate_point(
        ax, gamma_L, ZL, Z0,
        label="ZL",
        color=PALETTE["ZL"],
        marker="o",
        offset=(10, 10),
    )
    _annotate_point(
        ax, gamma_in, Zin, Z0,
        label="Zin",
        color=PALETTE["Zin"],
        marker="s",
        offset=(10, -22),
    )

    # ── 5. Legend ─────────────────────────────────────────────────────────────
    legend_elements = [
        mpatches.Patch(color=PALETTE["ZL"], label=f"ZL = ({ZL.real:.1f} + j{ZL.imag:.1f}) Ω"),
        mpatches.Patch(color=PALETTE["Zin"], label=f"Zin = ({Zin.real:.2f} + j{Zin.imag:.2f}) Ω"),
        mpatches.Patch(color=PALETTE["gamma_circle"], label=f"|Γ| = {gamma_mag:.3f}  ·  VSWR = {rf_result['VSWR']:.2f}"),
        mpatches.Patch(color=PALETTE["arc"], label=f"{req.length_lambda}λ {req.direction.replace('_', ' ')}  ({rf_result['rotation_deg']:.1f}°)"),
    ]
    legend = ax.legend(
        handles=legend_elements,
        loc="lower left",
        fontsize=8.5,
        framealpha=0.85,
        facecolor="#141824",
        edgecolor="#2a3045",
        labelcolor=PALETTE["text"],
    )

    # ── 6. Title & decorations ────────────────────────────────────────────────
    direction_label = "→ Generator" if req.direction == "toward_generator" else "→ Load"
    ax.set_title(
        f"Smith Chart  ·  Transmission Line Move  ·  Z₀ = {Z0} Ω  ·  {direction_label}",
        fontsize=11,
        color=PALETTE["text"],
        pad=14,
        fontweight="bold",
    )

    # Return loss annotation box
    rl_text = (
        f"Return Loss = {rf_result['return_loss_dB']:.2f} dB\n"
        f"VSWR = {rf_result['VSWR']:.3f}"
    )
    ax.text(
        0.98, 0.98, rl_text,
        transform=ax.transAxes,
        fontsize=8,
        color=PALETTE["subtitle"],
        ha="right", va="top",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#141824", edgecolor="#2a3045", alpha=0.9),
    )

    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-1.15, 1.15)
    ax.set_aspect("equal")
    ax.axis("off")

    plt.tight_layout(pad=1.5)

    # ── Render SVG ────────────────────────────────────────────────────────────
    svg_buf = io.BytesIO()
    svg_str: Optional[str] = None
    try:
        fig.savefig(svg_buf, format="svg", bbox_inches="tight",
                    facecolor=PALETTE["bg"], dpi=DPI)
        svg_buf.seek(0)
        svg_str = svg_buf.read().decode("utf-8")
    except Exception:
        svg_str = None
        image_as_b64 = True  # Fallback to PNG if SVG fails

    # ── Render PNG (base64) ───────────────────────────────────────────────────
    png_b64: Optional[str] = None

    if image_as_b64:
        png_buf = io.BytesIO()
        try:
            fig.savefig(png_buf, format="png", bbox_inches="tight",
                        facecolor=PALETTE["bg"], dpi=DPI)
            png_buf.seek(0)
            png_b64 = base64.b64encode(png_buf.read()).decode("ascii")
        except Exception:
            png_b64 = None

    plt.close(fig)

    return {"svg": svg_str, "png_b64": png_b64}
