"""Integration tests for API endpoints."""

from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Coinbot API"
    assert data["version"] == "0.1.0"
    assert "docs" in data


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_check(client: TestClient) -> None:
    """Test readiness check endpoint."""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_get_balance(client: TestClient, mock_bitvavo_client: None) -> None:
    """Test get balance endpoint."""
    response = client.get("/api/v1/balance")
    assert response.status_code == 200
    data = response.json()
    assert "available_funds" in data
    assert "total_balance" in data
    assert "total_gains" in data


def test_get_symbols(client: TestClient, mock_bitvavo_client: None) -> None:
    """Test get symbols endpoint."""
    response = client.get("/api/v1/symbols")
    assert response.status_code == 200
    symbols = response.json()
    assert isinstance(symbols, list)
    assert len(symbols) > 0


def test_get_symbol_info(client: TestClient, mock_bitvavo_client: None) -> None:
    """Test get symbol info endpoint."""
    response = client.get("/api/v1/symbols/BTC")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"
    assert "price" in data
    assert "owned_amount" in data
    assert "change_24h" in data
    assert "volume_24h" in data
