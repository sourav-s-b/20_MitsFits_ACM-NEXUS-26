import unittest
from unittest.mock import patch
from model.predictor import compute_risk, get_weather_score, get_traffic_delay
from main import app
from fastapi.testclient import TestClient


class TestRiskEngine(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("model.predictor.requests.get")
    def test_weather_score(self, mock_get):
        # Mock successful OWM response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "weather": [{"main": "Thunderstorm"}]
        }

        with patch("model.predictor.OWM_KEY", "fake_key"):
            score = get_weather_score(12.97, 77.59)
            self.assertEqual(score, 0.9)

    @patch("model.predictor.requests.get")
    def test_traffic_delay_safety(self, mock_get):
        # Mock TomTom response with freeFlowSpeed = 0
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "flowSegmentData": {"freeFlowSpeed": 0, "currentSpeed": 10}
        }

        with patch("model.predictor.TOMTOM_KEY", "fake_key"):
            delay = get_traffic_delay(12.97, 77.59)
            self.assertEqual(delay, 0.0)  # Should return 0.0 instead of crashing

    def test_compute_risk_fallback(self):
        # Test without model (should use weighted formula)
        with patch("model.predictor.risk_model", None):
            result = compute_risk(
                12.97, 77.59, override={"traffic_delay": 30, "weather_score": 0.5}
            )
            # traffic: 30/60 = 0.5 * 0.5 = 0.25
            # weather: 0.5 * 0.35 = 0.175
            # time_risk: (assume 0.0 for daytime) 0.0 * 0.15 = 0
            # total: 0.425
            self.assertIn("risk_score", result)
            self.assertEqual(result["status"], "MODERATE")

    def test_sop_numeric_trigger(self):
        # Test SOP matching with weather_score > 0.7
        response = self.client.get("/sop?status=MODERATE&weather_score=0.8")
        data = response.json()
        recommendations = data["recommendations"]

        # Should match both MODERATE and weather_score > 0.7
        triggers = [r["trigger"] for r in recommendations]
        self.assertIn("MODERATE", triggers)
        self.assertIn("weather_score > 0.7", triggers)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "running"})


if __name__ == "__main__":
    unittest.main()
