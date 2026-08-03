import cotacoes_onilx.coletores.coingecko as coingecko


class _RespostaFake:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_coletar_aceita_extra_ativos_e_inclui_no_resultado(monkeypatch):
    chamadas = []

    def fake_get(url, params=None, headers=None, timeout=None):
        chamadas.append((url, params))
        if url.endswith("/coins/markets"):
            return _RespostaFake([
                {"id": "bitcoin", "current_price": 300000.0, "total_volume": 1, "market_cap": 1,
                 "price_change_percentage_24h": 1.0, "price_change_percentage_7d_in_currency": 1.0,
                 "price_change_percentage_30d_in_currency": 1.0},
                {"id": "cardano", "current_price": 2.5, "total_volume": 1, "market_cap": 1,
                 "price_change_percentage_24h": -1.0, "price_change_percentage_7d_in_currency": -1.0,
                 "price_change_percentage_30d_in_currency": -1.0},
            ])
        if url.endswith("/simple/price"):
            return _RespostaFake({"bitcoin": {"brl": 1500000.0}, "cardano": {"brl": 12.0}})
        if url.endswith("/global"):
            return _RespostaFake({"data": {}})
        raise AssertionError(f"chamada inesperada: {url}")

    monkeypatch.setattr(coingecko.requests, "get", fake_get)
    resultado = coingecko.coletar(extra_ativos={"ADA": {"nome": "Cardano", "coingecko_id": "cardano"}})

    assert resultado["ativos"]["ADA"]["preco_brl"] == 12.0
    assert "BTC" in resultado["ativos"]
    ids_chamados = next(p["ids"] for url, p in chamadas if url.endswith("/coins/markets"))
    assert "cardano" in ids_chamados


def test_coletar_sem_extra_ativos_mantem_comportamento_atual(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        if url.endswith("/coins/markets"):
            return _RespostaFake([
                {"id": "bitcoin", "current_price": 300000.0, "total_volume": 1, "market_cap": 1,
                 "price_change_percentage_24h": 1.0, "price_change_percentage_7d_in_currency": 1.0,
                 "price_change_percentage_30d_in_currency": 1.0},
            ])
        if url.endswith("/simple/price"):
            return _RespostaFake({"bitcoin": {"brl": 1500000.0}})
        if url.endswith("/global"):
            return _RespostaFake({"data": {}})
        raise AssertionError(f"chamada inesperada: {url}")

    monkeypatch.setattr(coingecko.requests, "get", fake_get)
    resultado = coingecko.coletar()
    assert "ADA" not in resultado["ativos"]
    assert "BTC" in resultado["ativos"]


def test_buscar_moedas_retorna_lista_normalizada(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert url.endswith("/search")
        assert params == {"query": "cardano"}
        return _RespostaFake({"coins": [
            {"id": "cardano", "symbol": "ada", "name": "Cardano", "market_cap_rank": 9},
            {"id": "cardano-2", "symbol": "ada2", "name": "Cardano 2"},
        ]})

    monkeypatch.setattr(coingecko.requests, "get", fake_get)
    resultado = coingecko.buscar_moedas("cardano")
    assert resultado[0] == {"id": "cardano", "symbol": "ada", "name": "Cardano"}


def test_buscar_moedas_em_falha_retorna_lista_vazia(monkeypatch):
    def fake_get(url, params=None, headers=None, timeout=None):
        raise coingecko.requests.RequestException("timeout")

    monkeypatch.setattr(coingecko.requests, "get", fake_get)
    assert coingecko.buscar_moedas("cardano") == []
