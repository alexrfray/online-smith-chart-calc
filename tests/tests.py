"""
Tests for Smith Chart Service.

Run with:  pytest tests.py -v
"""

import base64
import math
import pytest
from fastapi.testclient import TestClient

from api.main import app
from smithChart.rf_engine import compute_tl_move

client = TestClient(app)

# ─── RF Engine Unit Tests ──────────────────────────────────────────────────────

class TestRFEngine:

    def test_matched_load(self):
        """ZL = Z0 → Γ = 0, Zin = Z0 at any length."""
        result = compute_tl_move(ZL=50+0j, Z0=50.0, length_lambda=0.1, direction="toward_generator")
        assert abs(result["gamma_L"]) < 1e-10
        assert abs(result["gamma_in"]) < 1e-10
        assert abs(result["Zin"] - 50) < 1e-6
        assert result["VSWR"] == pytest.approx(1.0, abs=1e-6)
        assert result["return_loss_dB"] == float("inf")

    def test_half_wave_line_is_identity(self):
        """0.5λ line maps ZL → ZL."""
        ZL = 75 + 25j
        result = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.5, direction="toward_generator")
        assert result["Zin"].real == pytest.approx(ZL.real, rel=1e-5)
        assert result["Zin"].imag == pytest.approx(ZL.imag, rel=1e-5)

    def test_quarter_wave_transformer(self):
        """λ/4 line: Zin = Z0² / ZL (for real ZL, Z0)."""
        Z0, ZL = 50.0, 100.0
        result = compute_tl_move(ZL=ZL+0j, Z0=Z0, length_lambda=0.25, direction="toward_generator")
        expected = Z0**2 / ZL  # = 25 Ω
        assert result["Zin"].real == pytest.approx(expected, rel=1e-5)
        assert abs(result["Zin"].imag) < 1e-5

    def test_open_circuit_load(self):
        """ZL → ∞ is an open circuit at the load (approximate with large R)."""
        # Use a very large impedance as an approximation for open circuit
        ZL = 1e9 + 0j
        result = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.25, direction="toward_generator")
        # λ/4 from open → short circuit at input (Zin ≈ 0)
        assert abs(result["Zin"].real) < 1e-2

    def test_short_circuit_load(self):
        """ZL = 0 → short circuit; λ/4 → open circuit at input (Γ_in = +1)."""
        ZL = 0.0 + 0j
        result = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.25, direction="toward_generator")
        # Γ_L = -1 for short circuit; after rotating 180° → Γ_in = +1 (open circuit)
        assert abs(result["gamma_L"]) == pytest.approx(1.0, abs=1e-10)
        # Zin should represent open circuit (very large)
        assert abs(result["Zin"]) > 1e10

    def test_gamma_magnitude_invariant(self):
        """|Γ| must be the same at load and input on a lossless line."""
        ZL = 30 - 60j
        result = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.15, direction="toward_generator")
        assert abs(result["gamma_L"]) == pytest.approx(abs(result["gamma_in"]), rel=1e-8)
        assert result["gamma_magnitude"] == pytest.approx(abs(result["gamma_L"]), rel=1e-8)

    def test_known_values(self):
        """Regression test with manually computed values."""
        result = compute_tl_move(ZL=75+25j, Z0=50.0, length_lambda=0.2, direction="toward_generator")
        assert result["Zin"].real == pytest.approx(36.357, rel=1e-3)
        assert result["Zin"].imag == pytest.approx(-20.490, rel=1e-3)
        assert result["gamma_magnitude"] == pytest.approx(0.2774, rel=1e-3)
        assert result["VSWR"] == pytest.approx(1.7674, rel=1e-3)

    def test_rotation_angle_toward_generator(self):
        """Rotation should be 2 * 2π * length_lambda degrees."""
        length = 0.2
        result = compute_tl_move(ZL=75+25j, Z0=50.0, length_lambda=length, direction="toward_generator")
        expected_deg = 2 * 360 * length  # = 144°
        assert result["rotation_deg"] == pytest.approx(expected_deg, rel=1e-6)

    def test_toward_load_is_counter_clockwise(self):
        """toward_load should rotate counter-clockwise (positive angle)."""
        ZL = 75 + 25j
        r_gen = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.1, direction="toward_generator")
        r_load = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.1, direction="toward_load")
        # They should give different Zin values
        assert abs(r_gen["Zin"] - r_load["Zin"]) > 1e-3
        # gamma_mag same in both
        assert r_gen["gamma_magnitude"] == pytest.approx(r_load["gamma_magnitude"], rel=1e-8)

    def test_return_loss_formula(self):
        """RL = -20 log10(|Γ|)."""
        ZL = 75 + 25j
        result = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.1, direction="toward_generator")
        expected_rl = -20 * math.log10(result["gamma_magnitude"])
        assert result["return_loss_dB"] == pytest.approx(expected_rl, rel=1e-6)

    def test_vswr_formula(self):
        """VSWR = (1+|Γ|)/(1-|Γ|)."""
        ZL = 100 + 0j
        result = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.05, direction="toward_generator")
        gamma = result["gamma_magnitude"]
        expected_vswr = (1 + gamma) / (1 - gamma)
        assert result["VSWR"] == pytest.approx(expected_vswr, rel=1e-8)

    def test_invalid_negative_Z0(self):
        with pytest.raises(ValueError, match="Z0 must be positive"):
            compute_tl_move(ZL=50+0j, Z0=-10.0, length_lambda=0.1, direction="toward_generator")

    def test_invalid_length_too_large(self):
        with pytest.raises(ValueError, match="length_lambda"):
            compute_tl_move(ZL=50+0j, Z0=50.0, length_lambda=0.6, direction="toward_generator")

    def test_zero_length(self):
        """0λ → Zin = ZL."""
        ZL = 33 - 47j
        result = compute_tl_move(ZL=ZL, Z0=50.0, length_lambda=0.0, direction="toward_generator")
        assert result["Zin"].real == pytest.approx(ZL.real, rel=1e-5)
        assert result["Zin"].imag == pytest.approx(ZL.imag, rel=1e-5)


# ─── API Integration Tests ────────────────────────────────────────────────────

class TestAPI:

    VALID_PAYLOAD = {
        "ZL": {"real": 75, "imag": 25},
        "Z0": 50,
        "length_lambda": 0.2,
        "direction": "toward_generator",
    }

    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_smith_move_status_200(self):
        r = client.post("/smith/move", json=self.VALID_PAYLOAD)
        assert r.status_code == 200

    def test_smith_move_response_fields(self):
        r = client.post("/smith/move", json=self.VALID_PAYLOAD)
        data = r.json()
        required = ["ZL", "Zin", "Z0", "gamma_L", "gamma_in",
                    "gamma_magnitude", "VSWR", "return_loss_dB",
                    "rotation_deg", "chart_svg", "chart_png_b64"]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_smith_move_zin_values(self):
        r = client.post("/smith/move", json=self.VALID_PAYLOAD)
        data = r.json()
        assert data["Zin"]["real"] == pytest.approx(36.357, rel=1e-3)
        assert data["Zin"]["imag"] == pytest.approx(-20.490, rel=1e-3)

    def test_smith_move_echoes_inputs(self):
        r = client.post("/smith/move", json=self.VALID_PAYLOAD)
        data = r.json()
        assert data["Z0"] == 50
        assert data["length_lambda"] == 0.2
        assert data["direction"] == "toward_generator"

    def test_chart_svg_is_string(self):
        r = client.post("/smith/move", json=self.VALID_PAYLOAD)
        svg = r.json()["chart_svg"]
        assert isinstance(svg, str)
        assert svg.strip().startswith("<")  # SVG/XML starts with <

    # ONLY SUPPORTING SVG NOW, PNG generation is fallback for rendering errors. So this test is not valid anymore.
    # def test_chart_png_b64_decodeable(self):
    #     r = client.post("/smith/move", json=self.VALID_PAYLOAD)
    #     b64 = r.json()["chart_png_b64"]
    #     assert isinstance(b64, str)
    #     raw = base64.b64decode(b64)
    #     assert raw[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes

    def test_toward_load_direction(self):
        payload = {**self.VALID_PAYLOAD, "direction": "toward_load"}
        r = client.post("/smith/move", json=payload)
        assert r.status_code == 200

    def test_pure_resistive_load(self):
        payload = {**self.VALID_PAYLOAD, "ZL": {"real": 100, "imag": 0}}
        r = client.post("/smith/move", json=payload)
        assert r.status_code == 200

    def test_matched_load_api(self):
        payload = {**self.VALID_PAYLOAD, "ZL": {"real": 50, "imag": 0}}
        r = client.post("/smith/move", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["VSWR"] == pytest.approx(1.0, abs=1e-4)

    def test_validation_negative_resistance(self):
        payload = {**self.VALID_PAYLOAD, "ZL": {"real": -10, "imag": 0}}
        r = client.post("/smith/move", json=payload)
        assert r.status_code == 422

    def test_validation_length_out_of_range(self):
        payload = {**self.VALID_PAYLOAD, "length_lambda": 0.7}
        r = client.post("/smith/move", json=payload)
        assert r.status_code == 422

    def test_validation_invalid_direction(self):
        payload = {**self.VALID_PAYLOAD, "direction": "sideways"}
        r = client.post("/smith/move", json=payload)
        assert r.status_code == 422

    def test_validation_negative_Z0(self):
        payload = {**self.VALID_PAYLOAD, "Z0": -50}
        r = client.post("/smith/move", json=payload)
        assert r.status_code == 422

    def test_zero_length_identity(self):
        payload = {**self.VALID_PAYLOAD, "length_lambda": 0.0}
        r = client.post("/smith/move", json=payload)
        data = r.json()
        assert data["Zin"]["real"] == pytest.approx(75.0, rel=1e-4)
        assert data["Zin"]["imag"] == pytest.approx(25.0, rel=1e-4)

    def test_half_wave_identity(self):
        payload = {**self.VALID_PAYLOAD, "length_lambda": 0.5}
        r = client.post("/smith/move", json=payload)
        data = r.json()
        assert data["Zin"]["real"] == pytest.approx(75.0, rel=1e-3)
        assert data["Zin"]["imag"] == pytest.approx(25.0, rel=1e-3)

    def test_openapi_schema_available(self):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert "/smith/move" in schema["paths"]
