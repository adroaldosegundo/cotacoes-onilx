"""
Coletor CoinGecko: precos, variacoes (24h/7d/30d), volume,
market cap, dominancia BTC e ETH.

API publica, sem autenticacao. Rate limit do tier free: ~30 req/min.

Endpoint principal usado: /coins/markets
Documentacao: https://docs.coingecko.com/reference/coins-markets
"""
import logging
import time
from typing import Optional

import requests

from ..config import ATIVOS, HTTP_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"

HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def coletar(extra_ativos: Optional[dict] = None) -> Optional[dict]:
    """
    Coleta cotacoes, variacoes e estrutura global de mercado.

    Estrutura de retorno:
        {
            "ativos": {
                "BTC": {
                    "preco_usd": float,
                    "preco_brl": float,
                    "volume_24h_usd": float,
                    "market_cap_usd": float,
                    "var_24h": float,        # percentual
                    "var_7d": float,         # percentual
                    "var_30d": float,        # percentual
                },
                "ETH": {...},
                "SOL": {...},
                "USDT": {...},
            },
            "global": {
                "market_cap_total_usd": float,
                "var_market_cap_24h": float,
                "dominancia_btc": float,
                "dominancia_eth": float,
            },
        }

    Retorna None se a coleta principal (ativos) falhar.
    Se apenas a coleta global falhar, retorna estrutura com global vazio.

    `extra_ativos` (mesmo formato de ATIVOS: {simbolo: {"nome", "coingecko_id"}})
    mescla ativos adicionais a esta chamada -- usado pela Carteira OnilX para
    buscar o preco da watchlist de cada assessor numa unica requisicao, sem
    duplicar chamada a API. Sem argumento, comportamento identico ao anterior
    (so o universo padrao de ATIVOS) -- e o que o Kairos ION continua usando.
    """
    resultado = {"ativos": {}, "global": {}}
    ativos_universo = {**ATIVOS, **(extra_ativos or {})}

    # -----------------------------------------------------------------------
    # 1. Cotacoes em USD com variacoes
    # -----------------------------------------------------------------------
    ids_str = ",".join(a["coingecko_id"] for a in ativos_universo.values())
    id_para_simbolo = {v["coingecko_id"]: k for k, v in ativos_universo.items()}

    max_tentativas = 3
    dados_usd = None
    for tentativa in range(1, max_tentativas + 1):
        try:
            resp = requests.get(
                f"{BASE_URL}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ids_str,
                    "price_change_percentage": "24h,7d,30d",
                    "per_page": 250,
                    "page": 1,
                },
                headers=HEADERS,
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            dados_usd = resp.json()
            break
        except (requests.RequestException, ValueError) as e:
            logger.warning(
                f"CoinGecko: falha em /coins/markets "
                f"(tentativa {tentativa}/{max_tentativas}) - {e}"
            )
            if tentativa < max_tentativas:
                time.sleep(10 * tentativa)

    if dados_usd is None:
        logger.error(f"CoinGecko: falha em /coins/markets apos {max_tentativas} tentativas")
        return None

    # -----------------------------------------------------------------------
    # 2. Cotacoes em BRL (precos apenas)
    # -----------------------------------------------------------------------
    precos_brl = {}
    try:
        resp_brl = requests.get(
            f"{BASE_URL}/simple/price",
            params={"ids": ids_str, "vs_currencies": "brl"},
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        resp_brl.raise_for_status()
        precos_brl = resp_brl.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning(
            f"CoinGecko: falha em /simple/price (BRL) - seguindo sem BRL: {e}"
        )

    # -----------------------------------------------------------------------
    # 3. Monta o dict de ativos
    # -----------------------------------------------------------------------
    for item in dados_usd:
        coingecko_id = item.get("id")
        simbolo = id_para_simbolo.get(coingecko_id)
        if not simbolo:
            continue

        resultado["ativos"][simbolo] = {
            "preco_usd": item.get("current_price"),
            "preco_brl": precos_brl.get(coingecko_id, {}).get("brl"),
            "volume_24h_usd": item.get("total_volume"),
            "market_cap_usd": item.get("market_cap"),
            "var_24h": item.get("price_change_percentage_24h"),
            "var_7d": item.get("price_change_percentage_7d_in_currency"),
            "var_30d": item.get("price_change_percentage_30d_in_currency"),
        }

    if not resultado["ativos"]:
        logger.error("CoinGecko: nenhum ativo retornado")
        return None

    # -----------------------------------------------------------------------
    # 4. Dados globais (market cap, dominancia)
    # -----------------------------------------------------------------------
    try:
        resp_global = requests.get(
            f"{BASE_URL}/global", headers=HEADERS, timeout=HTTP_TIMEOUT
        )
        resp_global.raise_for_status()
        dados_global = resp_global.json().get("data", {})

        resultado["global"] = {
            "market_cap_total_usd": (
                dados_global.get("total_market_cap", {}).get("usd")
            ),
            "var_market_cap_24h": (
                dados_global.get("market_cap_change_percentage_24h_usd")
            ),
            "dominancia_btc": (
                dados_global.get("market_cap_percentage", {}).get("btc")
            ),
            "dominancia_eth": (
                dados_global.get("market_cap_percentage", {}).get("eth")
            ),
        }
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"CoinGecko: falha em /global - seguindo sem global: {e}")

    logger.info(
        f"CoinGecko: coletados {len(resultado['ativos'])} ativos "
        f"e dados globais ({'ok' if resultado['global'] else 'vazio'})"
    )
    return resultado


def buscar_moedas(query: str, limite: int = 8) -> list[dict]:
    """Busca moedas no CoinGecko por nome/simbolo (endpoint /search), para
    a tela de watchlist da Carteira OnilX. Lista vazia em qualquer falha --
    e uma busca interativa, nao vale a pena repetir tentativas."""
    try:
        resp = requests.get(
            f"{BASE_URL}/search",
            params={"query": query},
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
        dados = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"CoinGecko: falha em /search para '{query}' - {e}")
        return []

    moedas = dados.get("coins", [])[:limite]
    return [{"id": m["id"], "symbol": m["symbol"], "name": m["name"]} for m in moedas]


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    dados = coletar()
    print(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
