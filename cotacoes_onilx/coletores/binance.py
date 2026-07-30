"""
Coletor Binance Futures: funding rate e Open Interest de BTC e ETH.

Fonte: api.binance.com (publica, sem autenticacao).

Endpoints usados:
- /fapi/v1/premiumIndex : funding rate atual e mark price
- /fapi/v1/openInterest : open interest atual em contratos

Documentacao: https://developers.binance.com/docs/derivatives/usds-margined-futures
"""
import logging
from typing import Optional

import requests

from ..config import HTTP_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

BASE_URL = "https://fapi.binance.com/fapi/v1"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _coletar_par(symbol: str) -> Optional[dict]:
    """
    Coleta funding rate e Open Interest para um par USDT-margined.

    Retorna:
        {
            "funding_rate_atual": float,       # decimal, ex: -0.000012
            "funding_rate_pct": float,         # percentual, ex: -0.0012
            "open_interest_contratos": float,
            "open_interest_usd": float,        # OI em USD
            "mark_price": float,
        }
    ou None em caso de falha.
    """
    try:
        # 1. Funding rate e mark price
        resp_fr = requests.get(
            f"{BASE_URL}/premiumIndex",
            params={"symbol": symbol},
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        resp_fr.raise_for_status()
        dados_fr = resp_fr.json()

        funding_rate = float(dados_fr["lastFundingRate"])
        mark_price = float(dados_fr["markPrice"])

        # 2. Open Interest em contratos
        resp_oi = requests.get(
            f"{BASE_URL}/openInterest",
            params={"symbol": symbol},
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        resp_oi.raise_for_status()
        dados_oi = resp_oi.json()

        oi_contratos = float(dados_oi["openInterest"])

        # Para USDT-M futures, 1 contrato representa 1 unidade do ativo base.
        # Logo, OI em USD = contratos * mark_price.
        oi_usd = oi_contratos * mark_price

        return {
            "funding_rate_atual": funding_rate,
            "funding_rate_pct": funding_rate * 100,
            "open_interest_contratos": oi_contratos,
            "open_interest_usd": oi_usd,
            "mark_price": mark_price,
        }

    except requests.RequestException as e:
        logger.error(f"Binance [{symbol}]: falha de rede - {e}")
        return None
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Binance [{symbol}]: dados inesperados - {e}")
        return None


def coletar() -> Optional[dict]:
    """
    Coleta funding rate e Open Interest de BTC e ETH na Binance.

    Estrutura de retorno:
        {
            "btc": {...},
            "eth": {...},
            "exchange": "Binance",
        }

    Retorna None apenas se ambos BTC e ETH falharem.
    """
    btc = _coletar_par("BTCUSDT")
    eth = _coletar_par("ETHUSDT")

    if btc is None and eth is None:
        return None

    logger.info(
        f"Binance: BTC={btc is not None}, ETH={eth is not None}"
    )

    return {
        "btc": btc,
        "eth": eth,
        "exchange": "Binance",
    }


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    dados = coletar()
    print(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
