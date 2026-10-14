"""Tests of the HTTP API with services wired to fakes."""

import pytest


def test_health_docs_and_root_redirect(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/", follow_redirects=False).headers["location"] == "/docs"
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/dashboard" in paths and "/api/v1/simulations/garch/asset" in paths
    assert len(paths) == 22


def test_dashboard_returns_assets_and_macro(client):
    response = client.get("/api/v1/dashboard", params={"tickers": "PETR4.SA,XXXX9.SA"})
    assert response.status_code == 200
    assert "s-maxage=300" in response.headers["cache-control"]
    body = response.json()
    petr, missing = body["assets"]
    assert petr["ticker"] == "PETR4.SA" and len(petr["bars"]) == 250
    assert petr["last_close"] == petr["bars"][-1]["close"]
    assert petr["previous_close"] == petr["bars"][-2]["close"]
    assert missing["error_code"] == "asset_not_found" and missing["bars"] == []
    assert body["macro"]["selic"] == {"date": "2026-10-10", "value": 13.75}
    assert body["macro_error"] is None


def test_dashboard_uses_the_default_watchlist_and_survives_macro_failures(client, macro_provider):
    macro_provider.fail = True
    body = client.get("/api/v1/dashboard").json()
    assert [asset["ticker"] for asset in body["assets"]] == ["PETR4.SA", "^BVSP"]
    assert body["macro"] is None and "SGS down" in body["macro_error"]


def test_asset_routes(client):
    quote = client.get("/api/v1/assets/petr4.sa/quote")
    assert quote.status_code == 200 and quote.json()["day_change_percent"] == 1.52
    assert "s-maxage=60" in quote.headers["cache-control"]
    history = client.get("/api/v1/assets/PETR4.SA/history", params={"period": "3mo"}).json()
    assert len(history["bars"]) == 63 and history["currency"] == "BRL"
    assert client.get("/api/v1/assets/PETR4.SA/fundamentals").json()["pe_ratio"] == 5.4
    assert client.get("/api/v1/assets/PETR4.SA/technical").json()["period"] == "3mo"
    rows = client.get("/api/v1/assets/compare", params={"tickers": "PETR4.SA,XXXX9.SA"}).json()
    assert rows[0]["dividend_yield"] == 6.5 and rows[1]["error"]


@pytest.mark.parametrize(
    ("url", "status", "code"),
    [
        ("/api/v1/assets/XXXX9.SA/history", 404, "asset_not_found"),
        ("/api/v1/assets/bad%20ticker/quote", 422, "invalid_parameter"),
        ("/api/v1/assets/PETR4.SA/history?period=9y", 422, "invalid_parameter"),
        ("/api/v1/macro/brasil/series/bitcoin", 404, "series_not_found"),
        ("/api/v1/macro/brasil/expectations?indicator=IPCA", 422, "validation_error"),
        ("/api/v1/crypto/exchanges/__class__/ticker?symbol=BTC/USDT", 404, "exchange_not_found"),
    ],
)
def test_errors_use_the_uniform_body(client, url, status, code):
    response = client.get(url)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.headers["cache-control"] == "no-store"


def test_upstream_failures_are_502(client, market_provider):
    market_provider.failing.add("VALE3.SA")
    response = client.get("/api/v1/assets/VALE3.SA/quote")
    assert response.status_code == 502 and response.json()["code"] == "upstream_unavailable"


def test_unexpected_errors_are_hidden(client, market_service, monkeypatch):
    def explode(*args):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(market_service, "get_quote", explode)
    response = client.get("/api/v1/assets/PETR4.SA/quote")
    assert response.status_code == 500
    assert response.json() == {"code": "internal_error", "message": "Unexpected error. Try again later."}


def test_macro_brasil_routes(client):
    summary = client.get("/api/v1/macro/brasil/summary").json()
    assert summary["real_rate"] == pytest.approx(8.6728, abs=1e-3)
    catalog = client.get("/api/v1/macro/brasil/series").json()
    assert {"name": "selic", "code": 432, "description": "Selic target rate (% per year)", "frequency": "daily"} in catalog
    series = client.get("/api/v1/macro/brasil/series/ipca_12m", params={"start_date": "2026-01-01"}).json()
    assert series["observations"][-1] == {"date": "2026-09-01", "value": 4.58}
    assert client.get("/api/v1/macro/brasil/ptax").json()[0]["buy"] == 4.9886
    focus = client.get("/api/v1/macro/brasil/expectations", params={"indicator": "IPCA", "reference_year": 2026}).json()
    assert focus[0]["respondents"] == 144


def test_macro_global_routes(client):
    found = client.get("/api/v1/macro/global/indicators", params={"query": "inflation"}).json()
    assert found[0]["code"] == "FP.CPI.TOTL.ZG"
    values = client.get(
        "/api/v1/macro/global/indicators/FP.CPI.TOTL.ZG",
        params={"countries": "BRA,USA", "start_year": 2020, "end_year": 2023},
    ).json()
    assert len(values) == 4
    latest = client.get("/api/v1/macro/global/indicators/NY.GDP.PCAP.CD/latest", params={"countries": "BRA,USA"}).json()
    assert [item["country"] for item in latest] == ["USA", "BRA"]


def test_crypto_routes(client):
    assert client.get("/api/v1/crypto/exchanges").json() == ["binance", "kraken"]
    ticker = client.get("/api/v1/crypto/exchanges/binance/ticker", params={"symbol": "btc/usdt"})
    assert ticker.json()["symbol"] == "BTC/USDT" and "s-maxage=15" in ticker.headers["cache-control"]
    candles = client.get("/api/v1/crypto/exchanges/binance/ohlcv", params={"symbol": "BTC/USDT", "limit": 3}).json()
    assert len(candles) == 3
    book = client.get("/api/v1/crypto/exchanges/binance/order-book", params={"symbol": "BTC/USDT"}).json()
    assert book["spread"] == 1.0 and book["bids"][0] == [100.0, 1.0]


def test_asset_simulation_route(client):
    response = client.post(
        "/api/v1/simulations/garch/asset",
        json={"ticker": "PETR4.SA", "horizon_days": 21, "n_paths": 200, "seed": 4},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["dates"]) == 21 and set(body["percentiles"]) == {"p5", "p10", "p25", "p50", "p75", "p90", "p95"}
    assert body["final"]["p5"] <= body["final"]["p50"] <= body["final"]["p95"]
    assert 0 <= body["final"]["prob_above_last"] <= 1
    assert body["parameters"]["persistence"] < 1 and len(body["sample_paths"]) == 5
    invalid = client.post("/api/v1/simulations/garch/asset", json={"ticker": "PETR4.SA", "n_paths": 5})
    assert invalid.status_code == 422 and invalid.json()["code"] == "validation_error"


def test_synthetic_route_matches_the_mcp_tool(client):
    response = client.post(
        "/api/v1/simulations/garch/synthetic",
        json={"ticker": "PETR4.SA", "start_date": "2026-10-14", "n_days": 5, "n_series": 2, "seed": 1},
    )
    body = response.json()
    assert response.status_code == 200 and list(body["series"]) == ["serie_1", "serie_2"]
    assert len(body["dates"]) == 5 and body["parameters"]["alpha"] == 0.1
    bad = client.post(
        "/api/v1/simulations/garch/synthetic",
        json={"ticker": "X", "start_date": "2026-10-14", "n_days": 5, "alpha": 0.5, "beta": 0.6},
    )
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_parameter"


def test_cors_and_cache_stats(client):
    preflight = client.options(
        "/api/v1/dashboard",
        headers={"Origin": "https://finbrain.example", "Access-Control-Request-Method": "GET"},
    )
    assert preflight.headers["access-control-allow-origin"] == "https://finbrain.example"
    client.get("/api/v1/assets/PETR4.SA/quote")
    client.get("/api/v1/assets/PETR4.SA/quote")
    stats = client.get("/api/v1/cache/stats").json()
    assert stats["hits"] >= 1 and stats["entries"] >= 1
