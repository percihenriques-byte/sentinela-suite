"""Credencial cifrada por fonte (auditoria 6a rodada, E1/E2).

Adiciona `secfonte.credencial_enc` (Fernet, nullable): chave de API do HIBP,
token GitHub para repos privados etc. A credencial nunca sai em resposta de
API — as rotas expoem apenas `tem_credencial: bool`.

Revision ID: 0007_secintel_credencial
Revises: 0006_secintel
Create Date: 2026-08-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0007_secintel_credencial"
down_revision: Union[str, None] = "0006_secintel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _colunas(tabela: str) -> set[str]:
    from sqlalchemy import inspect

    try:
        return {c["name"] for c in inspect(op.get_bind()).get_columns(tabela)}
    except Exception:
        return set()


def upgrade() -> None:
    if "credencial_enc" not in _colunas("secfonte"):
        op.add_column(
            "secfonte",
            sa.Column("credencial_enc", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )


def downgrade() -> None:
    if "credencial_enc" in _colunas("secfonte"):
        op.drop_column("secfonte", "credencial_enc")
