"""Lockout do PIN: contador de falhas + janela de bloqueio.

Um PIN de 4 digitos tem 10.000 combinacoes. Sem trava, um script local esgota
isso em segundos — registrar a tentativa nunca foi defesa contra a tentativa.

Revision ID: 0005_pin_lockout
Revises: 0004_sentinela
Create Date: 2026-08-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_pin_lockout"
down_revision: Union[str, None] = "0004_sentinela"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _colunas(tabela: str) -> set[str]:
    from sqlalchemy import inspect

    try:
        inspector = inspect(op.get_bind())
        if tabela not in inspector.get_table_names():
            return set()
        return {c["name"] for c in inspector.get_columns(tabela)}
    except Exception:
        return set()


def upgrade() -> None:
    existentes = _colunas("sentinelaconfig")
    if not existentes:
        return
    if "pin_falhas" not in existentes:
        op.add_column("sentinelaconfig", sa.Column("pin_falhas", sa.Integer(), nullable=True))
        op.execute("UPDATE sentinelaconfig SET pin_falhas = 0 WHERE pin_falhas IS NULL")
    if "pin_bloqueado_ate" not in existentes:
        op.add_column("sentinelaconfig", sa.Column("pin_bloqueado_ate", sa.DateTime(), nullable=True))


def downgrade() -> None:
    existentes = _colunas("sentinelaconfig")
    if "pin_bloqueado_ate" in existentes:
        op.drop_column("sentinelaconfig", "pin_bloqueado_ate")
    if "pin_falhas" in existentes:
        op.drop_column("sentinelaconfig", "pin_falhas")
