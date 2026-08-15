"""Modulo Seguranca (Security Intelligence Engine) — M0.

Cria as tabelas do ESPEC-SEGURANCA.md secao 3: ativos autorizados, fontes com
consentimento, eventos normalizados, achados de exposicao, incidentes com
linha do tempo e a trilha de auditoria do proprio modulo.

Nenhum segredo em claro: identificador de ativo cifrado + hash + mascarado;
achados guardam apenas o indicador mascarado e um fingerprint.

Revision ID: 0006_secintel
Revises: 0005_pin_lockout
Create Date: 2026-08-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "0006_secintel"
down_revision: Union[str, None] = "0005_pin_lockout"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tabelas() -> set[str]:
    from sqlalchemy import inspect

    try:
        return set(inspect(op.get_bind()).get_table_names())
    except Exception:
        return set()


def _base_cols() -> list[sa.Column]:
    return [
        sa.Column("id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    existentes = _tabelas()

    if "secasset" not in existentes:
        op.create_table(
            "secasset",
            *_base_cols(),
            sa.Column("workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("tipo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("identificador_enc", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("identificador_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("identificador_mascarado", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("titular", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("nivel_autorizacao", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("verificado_em", sa.DateTime(), nullable=True),
            sa.Column("fonte_cadastro", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("ativo", sa.Boolean(), nullable=True),
            sa.Column("ultima_verificacao", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_secasset_id", "secasset", ["id"])
        op.create_index("ix_secasset_deleted_at", "secasset", ["deleted_at"])
        op.create_index("ix_secasset_workspace_id", "secasset", ["workspace_id"])
        op.create_index("ix_secasset_tipo", "secasset", ["tipo"])
        op.create_index("ix_secasset_identificador_hash", "secasset", ["identificador_hash"])
        op.create_index("ix_secasset_ativo", "secasset", ["ativo"])

    if "secfonte" not in existentes:
        op.create_table(
            "secfonte",
            *_base_cols(),
            sa.Column("nome", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("habilitada", sa.Boolean(), nullable=False),
            sa.Column("requer_nivel", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("descricao_egresso", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("consentida_em", sa.DateTime(), nullable=True),
            sa.Column("consentida_por", sqlmodel.sql.sqltypes.GUID(), nullable=True),
            sa.Column("ultima_consulta", sa.DateTime(), nullable=True),
            sa.Column("estado", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("erro_msg", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.ForeignKeyConstraint(["consentida_por"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_secfonte_id", "secfonte", ["id"])
        op.create_index("ix_secfonte_deleted_at", "secfonte", ["deleted_at"])
        op.create_index("ix_secfonte_nome", "secfonte", ["nome"], unique=True)

    if "secevento" not in existentes:
        op.create_table(
            "secevento",
            *_base_cols(),
            sa.Column("workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("origem", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("tipo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("ts", sa.DateTime(), nullable=False),
            sa.Column("ip", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("usuario", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("dispositivo_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("sessao", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("endpoint", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("atributos", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_secevento_id", "secevento", ["id"])
        op.create_index("ix_secevento_deleted_at", "secevento", ["deleted_at"])
        op.create_index("ix_secevento_workspace_id", "secevento", ["workspace_id"])
        op.create_index("ix_secevento_origem", "secevento", ["origem"])
        op.create_index("ix_secevento_tipo", "secevento", ["tipo"])
        op.create_index("ix_secevento_ts", "secevento", ["ts"])
        op.create_index("ix_secevento_ip", "secevento", ["ip"])
        op.create_index("ix_secevento_usuario", "secevento", ["usuario"])
        op.create_index("ix_secevento_ws_ts", "secevento", ["workspace_id", "ts"])

    if "secincidente" not in existentes:
        op.create_table(
            "secincidente",
            *_base_cols(),
            sa.Column("workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("titulo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("cenario", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("severidade", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("confianca", sa.Float(), nullable=False),
            sa.Column("estado", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("primeiro_visto", sa.DateTime(), nullable=False),
            sa.Column("ultimo_visto", sa.DateTime(), nullable=False),
            sa.Column("ocorrencias", sa.Integer(), nullable=False),
            sa.Column("resumo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("recomendacoes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_secincidente_id", "secincidente", ["id"])
        op.create_index("ix_secincidente_deleted_at", "secincidente", ["deleted_at"])
        op.create_index("ix_secincidente_workspace_id", "secincidente", ["workspace_id"])
        op.create_index("ix_secincidente_cenario", "secincidente", ["cenario"])
        op.create_index("ix_secincidente_severidade", "secincidente", ["severidade"])
        op.create_index("ix_secincidente_estado", "secincidente", ["estado"])
        op.create_index("ix_secincidente_fingerprint", "secincidente", ["fingerprint"])
        op.create_index(
            "ux_secincidente_ws_fingerprint", "secincidente",
            ["workspace_id", "fingerprint"], unique=True,
        )

    if "secachado" not in existentes:
        op.create_table(
            "secachado",
            *_base_cols(),
            sa.Column("workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("asset_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
            sa.Column("fonte", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("tipo_exposicao", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("classificacao", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("confianca", sa.Float(), nullable=False),
            sa.Column("severidade", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("indicador_mascarado", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("evidencia_resumo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("descoberto_em", sa.DateTime(), nullable=False),
            sa.Column("exposto_em_estimado", sa.DateTime(), nullable=True),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("motivo_fp", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("incidente_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
            sa.ForeignKeyConstraint(["asset_id"], ["secasset.id"]),
            sa.ForeignKeyConstraint(["incidente_id"], ["secincidente.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_secachado_id", "secachado", ["id"])
        op.create_index("ix_secachado_deleted_at", "secachado", ["deleted_at"])
        op.create_index("ix_secachado_workspace_id", "secachado", ["workspace_id"])
        op.create_index("ix_secachado_asset_id", "secachado", ["asset_id"])
        op.create_index("ix_secachado_fonte", "secachado", ["fonte"])
        op.create_index("ix_secachado_tipo_exposicao", "secachado", ["tipo_exposicao"])
        op.create_index("ix_secachado_severidade", "secachado", ["severidade"])
        op.create_index("ix_secachado_status", "secachado", ["status"])
        op.create_index("ix_secachado_fingerprint", "secachado", ["fingerprint"])
        op.create_index("ix_secachado_incidente_id", "secachado", ["incidente_id"])
        op.create_index(
            "ux_secachado_ws_fingerprint", "secachado",
            ["workspace_id", "fingerprint"], unique=True,
        )
        op.create_index(
            "ix_secachado_ws_status_sev", "secachado",
            ["workspace_id", "status", "severidade"],
        )

    if "secincidenteitem" not in existentes:
        op.create_table(
            "secincidenteitem",
            *_base_cols(),
            sa.Column("incidente_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("ref_tipo", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("ref_id", sqlmodel.sql.sqltypes.GUID(), nullable=True),
            sa.Column("nota", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("ts", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["incidente_id"], ["secincidente.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_secincidenteitem_id", "secincidenteitem", ["id"])
        op.create_index("ix_secincidenteitem_deleted_at", "secincidenteitem", ["deleted_at"])
        op.create_index("ix_secincidenteitem_incidente_id", "secincidenteitem", ["incidente_id"])

    if "secauditoria" not in existentes:
        op.create_table(
            "secauditoria",
            *_base_cols(),
            sa.Column("workspace_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("user_id", sqlmodel.sql.sqltypes.GUID(), nullable=False),
            sa.Column("acao", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("detalhe", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
            sa.Column("ts", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["workspace_id"], ["workspace.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_secauditoria_id", "secauditoria", ["id"])
        op.create_index("ix_secauditoria_deleted_at", "secauditoria", ["deleted_at"])
        op.create_index("ix_secauditoria_workspace_id", "secauditoria", ["workspace_id"])
        op.create_index("ix_secauditoria_user_id", "secauditoria", ["user_id"])
        op.create_index("ix_secauditoria_acao", "secauditoria", ["acao"])
        op.create_index("ix_secauditoria_ts", "secauditoria", ["ts"])


def downgrade() -> None:
    existentes = _tabelas()
    # ordem inversa das FKs: quem referencia cai antes de quem e referenciado
    for tabela in (
        "secauditoria",
        "secincidenteitem",
        "secachado",
        "secincidente",
        "secevento",
        "secfonte",
        "secasset",
    ):
        if tabela in existentes:
            op.drop_table(tabela)
