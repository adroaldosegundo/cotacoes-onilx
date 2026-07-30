"""
Precos de abertura mensal (candles 1M) para valorar posicoes/contratos
em relatorios de periodos passados — diferente dos coletores de
cotacoes_onilx/coletores/*.py, que trazem preco atual/live.

Extraido de Carteira_Clientes/src/precos_cripto.py (usado para valorar
contratos OnilX nos relatorios mensais De Grandi/OnilX).

Fonte: Binance (publica, sem autenticacao).
"""
import json
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

_BASE = "https://api.binance.com/api/v3/klines"
_SIMBOLO = {"BTC": "BTCBRL", "ETH": "ETHBRL", "USDT": "USDTBRL"}


@lru_cache(maxsize=16)
def _klines(simbolo: str, n: int = 30) -> list[tuple[str, float]]:
    url = f"{_BASE}?symbol={simbolo}&interval=1M&limit={n}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            candles = json.loads(r.read())
    except Exception:
        return []
    resultado = []
    for c in candles:
        dt = datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc)
        resultado.append((f"{dt.year:04d}-{dt.month:02d}", float(c[1])))
    return resultado


def precos_mensais(moeda: str) -> dict[str, float]:
    """Retorna {YYYY-MM: preco_abertura_brl} dos ultimos 30 meses."""
    simbolo = _SIMBOLO.get(moeda)
    return dict(_klines(simbolo)) if simbolo else {}


def preco_mes(moeda: str, periodo: str) -> Optional[float]:
    """Preco de abertura de `moeda` em BRL para `periodo` (YYYY-MM). None se indisponivel."""
    return precos_mensais(moeda).get(periodo)
