"""
cotacoes_onilx — base compartilhada de coleta de cotacoes cripto e macro.

Extraido de kairos_ion/coletores/*.py para ser a fonte unica usada tanto
pelo pipeline diario do Kairos ION quanto pelo InformeMensalOnilX v2.0.

Cada coletor segue o padrao:

    def coletar() -> dict | None

Uso tipico:

    from cotacoes_onilx.agregador import coletar_todas
    dados = coletar_todas()
"""
