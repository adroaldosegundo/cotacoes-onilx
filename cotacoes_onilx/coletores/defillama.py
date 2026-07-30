"""
Coletor DefiLlama: TVL agregado e market cap de stablecoins.

Fonte: api.llama.fi e stablecoins.llama.fi (publicas, sem autenticacao).

Coleta:
- Market cap total agregado de stablecoins (USD)
- Variacao 7d do market cap de stablecoins
- TVL total agregado em DeFi (USD)
- Variacao 7d do TVL

Documentacao: https://defillama.com/docs/api
"""
import logging
from typing import Optional

import requests

from ..config import HTTP_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

URL_STABLECOINS_CHART = "https://stablecoins.llama.fi/stablecoincharts/all"
URL_TVL_HISTORICO = "https://api.llama.fi/v2/historicalChainTvl"

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _coletar_stablecoins() -> Optional[dict]:
    """
    Market cap agregado de stablecoins.

    Retorna serie historica diaria; pegamos o ponto mais recente
    e o ponto de 7 dias atras para variacao.

    Estrutura de retorno:
        {
            "market_cap_atual_usd": float,
            "market_cap_7d_atras_usd": float,
            "var_7d_pct": float,
        }
    """
    try:
        resp = requests.get(
            URL_STABLECOINS_CHART, headers=HEADERS, timeout=HTTP_TIMEOUT
        )
        resp.raise_for_status()
        serie = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.error(f"DefiLlama [stablecoins]: falha - {e}")
        return None

    if not isinstance(serie, list) or not serie:
        logger.error("DefiLlama [stablecoins]: serie vazia ou invalida")
        return None

    try:
        # Cada item tem: {"date": "1234567890", "totalCirculatingUSD": {...}}
        # totalCirculatingUSD pode ser dict (segregado por peg) ou float
        def _extrair_total(item: dict) -> float:
            tc = item.get("totalCirculatingUSD", 0)
            if isinstance(tc, dict):
                # Soma todas as pegs (peggedUSD, peggedEUR, etc)
                return sum(float(v) for v in tc.values() if v is not None)
            return float(tc) if tc is not None else 0.0

        atual = _extrair_total(serie[-1])

        # 7 dias atras: indice -8 se houver
        if len(serie) >= 8:
            anterior = _extrair_total(serie[-8])
        else:
            anterior = _extrair_total(serie[0])

        if anterior == 0:
            var_7d = None
        else:
            var_7d = ((atual - anterior) / anterior) * 100

        return {
            "market_cap_atual_usd": atual,
            "market_cap_7d_atras_usd": anterior,
            "var_7d_pct": round(var_7d, 2) if var_7d is not None else None,
        }
    except (KeyError, ValueError, IndexError, TypeError) as e:
        logger.error(f"DefiLlama [stablecoins]: erro ao processar - {e}")
        return None


def _coletar_tvl() -> Optional[dict]:
    """
    TVL agregado total em DeFi.

    Retorna serie historica; pegamos o ponto mais recente e
    o de 7 dias atras para calcular variacao.

    Estrutura de retorno:
        {
            "tvl_atual_usd": float,
            "tvl_7d_atras_usd": float,
            "var_7d_pct": float,
        }
    """
    try:
        resp = requests.get(
            URL_TVL_HISTORICO, headers=HEADERS, timeout=HTTP_TIMEOUT
        )
        resp.raise_for_status()
        serie = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.error(f"DefiLlama [TVL]: falha - {e}")
        return None

    if not isinstance(serie, list) or not serie:
        logger.error("DefiLlama [TVL]: serie vazia ou invalida")
        return None

    try:
        atual = float(serie[-1].get("tvl", 0))
        if len(serie) >= 8:
            anterior = float(serie[-8].get("tvl", 0))
        else:
            anterior = float(serie[0].get("tvl", 0))

        if anterior == 0:
            var_7d = None
        else:
            var_7d = ((atual - anterior) / anterior) * 100

        return {
            "tvl_atual_usd": atual,
            "tvl_7d_atras_usd": anterior,
            "var_7d_pct": round(var_7d, 2) if var_7d is not None else None,
        }
    except (KeyError, ValueError, IndexError, TypeError) as e:
        logger.error(f"DefiLlama [TVL]: erro ao processar - {e}")
        return None


def coletar() -> Optional[dict]:
    """
    Coleta market cap de stablecoins e TVL DeFi agregados.

    Estrutura de retorno:
        {
            "stablecoins": {
                "market_cap_atual_usd": float,
                "market_cap_7d_atras_usd": float,
                "var_7d_pct": float,
            },
            "tvl_defi": {
                "tvl_atual_usd": float,
                "tvl_7d_atras_usd": float,
                "var_7d_pct": float,
            },
        }

    Cada subgrupo pode ser None individualmente. Retorna None se ambos falharem.
    """
    stablecoins = _coletar_stablecoins()
    tvl = _coletar_tvl()

    if stablecoins is None and tvl is None:
        return None

    logger.info(
        f"DefiLlama: stablecoins={stablecoins is not None}, "
        f"tvl={tvl is not None}"
    )

    return {
        "stablecoins": stablecoins,
        "tvl_defi": tvl,
    }


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    dados = coletar()
    print(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
