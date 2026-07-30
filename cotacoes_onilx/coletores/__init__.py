"""
Modulos de coleta de dados de cotacoes cripto e macro.

Cada coletor segue o padrao:

    def coletar() -> dict | None

Retornando None em caso de falha, sem propagar excecao para nao
derrubar quem consome. O orquestrador (agregador.py) decide como reagir
a coletas que falharam.

Cada coletor pode ser executado isolado para teste:

    python -m cotacoes_onilx.coletores.coingecko
"""
