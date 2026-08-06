"""Modulo Sentinela: registro de supervisao + configuracao.

Cria `sentinelaevent` (uma linha por tentativa observada, com o texto da busca
cifrado) e `sentinelaconfig` (linha unica: token de ingestao, sensibilidade,
PIN, retencao).

Nao ha workspace_id de proposito: o registro parental pertence a maquina, nao
a um espaco de trabalho comercial.

Revision ID: 0004_sentinela
Revises: 0003_taglink_unique
Create Date: 2026-08-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0004_sentinela"
down_revision: Union[str, None] = "0003_taglink_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelas() -> set[str]:
    from sqlalchemy import inspect

    try:
        return set(inspect(op.get_bind()).get_table_names())
    except Exception:
        return set()


def upgrade() -> None:
    existentes = _tabelas()

    if "sentinelaevent" not in existentes:
        op.create_table(
            "sentinelaevent",
            sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("ocorrido_em", sa.DateTime(), nullable=False),
            sa.Column("busca_enc", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("origem", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("dispositivo", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("tema", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("confianca", sa.Float(), nullable=True),
            sa.Column("bloqueado", sa.Boolean(), nullable=True),
            sa.Column("sinais", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sentinelaevent_id", "sentinelaevent", ["id"])
        op.create_index("ix_sentinelaevent_deleted_at", "sentinelaevent", ["deleted_at"])
        op.create_index("ix_sentinelaevent_ocorrido_em", "sentinelaevent", ["ocorrido_em"])
        op.create_index("ix_sentinelaevent_origem", "sentinelaevent", ["origem"])
        op.create_index("ix_sentinelaevent_dispositivo", "sentinelaevent", ["dispositivo"])
        op.create_index("ix_sentinelaevent_tema", "sentinelaevent", ["tema"])
        op.create_index("ix_sentinelaevent_bloqueado", "sentinelaevent", ["bloqueado"])

    if "sentinelaconfig" not in existentes:
        op.create_table(
            "sentinelaconfig",
            sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("ativo", sa.Boolean(), nullable=True),
            sa.Column("sensibilidade", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("token_ingestao", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("pin_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("retencao_dias", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_sentinelaconfig_id", "sentinelaconfig", ["id"])
        op.create_index("ix_sentinelaconfig_deleted_at", "sentinelaconfig", ["deleted_at"])


def downgrade() -> None:
    existentes = _tabelas()
    if "sentinelaconfig" in existentes:
        op.drop_table("sentinelaconfig")
    if "sentinelaevent" in existentes:
        op.drop_table("sentinelaevent")
