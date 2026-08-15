"""Transportes REAIS das fontes de exposicao (auditoria 6a rodada, E2).

Cada fonte declara em `TRANSPORTE` a assinatura de que precisa; o runner monta
o transporte certo por fonte (despacho por tipo, em vez de um `http` unico para
assinaturas diferentes — a correcao estrutural do E2). Dois tipos:

    http_json(url, headers) -> resposta com .status_code e .json()/.text
    repo_arquivos(asset, credencial) -> list[(caminho, texto)]

So sao chamados por fonte HABILITADA (o runner barra as desligadas antes).
O cliente httpx e importado sob demanda; nos testes, tudo aqui aceita um
`http` injetado para validar parsing/limites sem rede.
"""
from __future__ import annotations

import base64
from typing import Callable, Optional

TIMEOUT_S = 20.0

# Limites da leitura de repositorio (ESPEC secao 10 + tarefa E2): o objetivo e
# procurar segredo em codigo/config, nao espelhar o repo inteiro.
MAX_ARQUIVOS = 200
MAX_BYTES_ARQUIVO = 200_000
EXTENSOES_TEXTO = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".yml", ".yaml", ".toml",
    ".ini", ".cfg", ".conf", ".env", ".sh", ".ps1", ".bat", ".rb", ".go",
    ".java", ".cs", ".php", ".sql", ".tf", ".properties", ".txt", ".xml",
}
_API_GH = "https://api.github.com"


def http_json_real(url: str, headers: Optional[dict] = None):
    """GET simples com timeout. Uso exclusivo de fonte habilitada."""
    import httpx

    return httpx.get(url, headers=headers or {}, timeout=TIMEOUT_S)


def _extensao_ok(caminho: str) -> bool:
    ca