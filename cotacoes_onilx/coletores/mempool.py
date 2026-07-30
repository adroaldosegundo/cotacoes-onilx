"""
Coletor Mempool.space: dados on-chain do Bitcoin.

Fonte: mempool.space (API publica, sem autenticacao).

Coleta:
- Hashrate atual e media de 3 dias
- Fees recomendadas (rapida, media, lenta) em sat/vB
- Mempool: numero de transacoes pendentes e tamanho em MB
- Proximo ajuste de dificuldade (percentual e blocos restantes)

Documentacao: https://mempool.space/docs/api/rest
"""
import logging
from typing import Optional

import requests

from ..config import HTTP_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

_BASE_URLS = [
    "https://mempool.space/api",
    "https://mempool.emzy.de/api",
]
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
# Connect timeout curto para falhar rápido se host inacessível; read timeout normal
_TIMEOUT = (5, HTTP_TIMEOUT)


def _get(path: str) -> Optional[dict]:
    for base in _BASE_URLS:
        try:
            resp = requests.get(f"{base}{path}", headers=HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            continue
    return None


def _coletar_hashrate() -> Optional[dict]:
    """
    Hashrate atual e media de 3 dias.

    Endpoint: /v1/mining/hashrate/3d

    Retorna: {"hashrate_atual_eh": float, "hashrate_3d_eh": float}
    Valores em EH/s (exahash por segundo).
    """
    try:
        dados = _get("/v1/mining/hashrate/3d")
        if dados is None:
            raise requests.RequestException("todos os mirrors falharam")

        # API retorna em hash/s; convertemos para EH/s (1 EH = 10^18 H)
        atual_h = float(dados.get("currentHashrate", 0))
        media_h = float(dados.get("currentDifficulty", 0))  # campo varia conforme versao

        # Estrategia segura: usar hashrates da serie historica se disponivel
        hashrates = dados.get("hashrates", [])
        if hashrates:
            atual_h = float(hashrates[-1].get("avgHashrate", atual_h))
            # media de 3 dias = ultimos 3 pontos diarios, se houver
            ultimos = hashrates[-3:] if len(hashrates) >= 3 else hashrates
            soma = sum(float(p.get("avgHashrate", 0)) for p in ultimos)
            media_h = soma / len(ultimos) if ultimos else atual_h

        # Conversao para EH/s
        atual_eh = atual_h / 1e18
        media_eh = media_h / 1e18

        return {
            "hashrate_atual_eh": round(atual_eh, 2),
            "hashrate_3d_eh": round(media_eh, 2),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        logger.error(f"Mempool [hashrate]: falha - {e}")
        return None


def _coletar_fees() -> Optional[dict]:
    """
    Fees recomendadas em sat/vB.

    Endpoint: /v1/fees/recommended

    Retorna:
        {
            "rapida": int,    # fastestFee
            "media": int,     # halfHourFee
            "lenta": int,     # economyFee ou minimumFee
        }
    """
    try:
        dados = _get("/v1/fees/recommended")
        if dados is None:
            raise requests.RequestException("todos os mirrors falharam")

        return {
            "rapida": int(dados.get("fastestFee", 0)),
            "media": int(dados.get("halfHourFee", 0)),
            "lenta": int(dados.get("economyFee", dados.get("minimumFee", 0))),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        logger.error(f"Mempool [fees]: falha - {e}")
        return None


def _coletar_mempool() -> Optional[dict]:
    """
    Estado atual do mempool.

    Endpoint: /mempool

    Retorna:
        {
            "txs_pendentes": int,
            "tamanho_mb": float,
        }
    """
    try:
        dados = _get("/mempool")
        if dados is None:
            raise requests.RequestException("todos os mirrors falharam")

        # vsize esta em vbytes; convertemos para MB (vsize / 1.024.000 aprox)
        # mas o campo padrao e "size" em bytes. Usamos vsize quando disponivel.
        tamanho_bytes = dados.get("vsize", dados.get("size", 0))
        tamanho_mb = float(tamanho_bytes) / 1_000_000

        return {
            "txs_pendentes": int(dados.get("count", 0)),
            "tamanho_mb": round(tamanho_mb, 2),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        logger.error(f"Mempool [mempool]: falha - {e}")
        return None


def _coletar_dificuldade() -> Optional[dict]:
    """
    Proximo ajuste de dificuldade.

    Endpoint: /v1/difficulty-adjustment

    Retorna:
        {
            "ajuste_estimado_pct": float,  # negativo = mais facil, positivo = mais dificil
            "blocos_restantes": int,
        }
    """
    try:
        dados = _get("/v1/difficulty-adjustment")
        if dados is None:
            raise requests.RequestException("todos os mirrors falharam")

        return {
            "ajuste_estimado_pct": round(
                float(dados.get("difficultyChange", 0)), 2
            ),
            "blocos_restantes": int(dados.get("remainingBlocks", 0)),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        logger.error(f"Mempool [dificuldade]: falha - {e}")
        return None


def coletar() -> Optional[dict]:
    """
    Coleta dados on-chain do Bitcoin.

    Estrutura de retorno:
        {
            "hashrate": {
                "hashrate_atual_eh": float,
                "hashrate_3d_eh": float,
            },
            "fees_sat_vb": {
                "rapida": int,
                "media": int,
                "lenta": int,
            },
            "mempool": {
                "txs_pendentes": int,
                "tamanho_mb": float,
            },
            "dificuldade": {
                "ajuste_estimado_pct": float,
                "blocos_restantes": int,
            },
        }

    Cada subgrupo pode ser None individualmente. Retorna None apenas
    se todos os subgrupos falharem.
    """
    hashrate = _coletar_hashrate()
    fees = _coletar_fees()
    mempool = _coletar_mempool()
    dificuldade = _coletar_dificuldade()

    if all(x is None for x in [hashrate, fees, mempool, dificuldade]):
        return None

    logger.info(
        f"Mempool: hashrate={hashrate is not None}, fees={fees is not None}, "
        f"mempool={mempool is not None}, dificuldade={dificuldade is not None}"
    )

    return {
        "hashrate": hashrate,
        "fees_sat_vb": fees,
        "mempool": mempool,
        "dificuldade": dificuldade,
    }


if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    dados = coletar()
    print(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
