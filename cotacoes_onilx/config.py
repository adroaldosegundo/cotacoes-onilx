"""
Constantes usadas pelos coletores. Subconjunto do config.py do kairos_ion
(so o que os coletores de fato importam) para o pacote nao depender do
projeto que o consome.
"""
import os

ATIVOS = {
    "BTC": {
        "nome": "Bitcoin",
        "coingecko_id": "bitcoin",
    },
    "ETH": {
        "nome": "Ethereum",
        "coingecko_id": "ethereum",
    },
    "SOL": {
        "nome": "Solana",
        "coingecko_id": "solana",
    },
    "XRP": {
        "nome": "XRP",
        "coingecko_id": "ripple",
    },
    "USDT": {
        "nome": "Tether",
        "coingecko_id": "tether",
    },
}

HTTP_TIMEOUT = int(os.getenv("COTACOES_ONILX_HTTP_TIMEOUT", "15"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
