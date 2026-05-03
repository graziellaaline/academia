# -*- coding: utf-8 -*-
"""
Conexão e criação do banco de dados SQLite.
Todas as tabelas são criadas aqui na primeira execução.
"""

import sqlite3
import hashlib
import logging
from pathlib import Path
from datetime import date, timedelta

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "academia.db"


def get_conn():
    """Retorna conexão com row_factory para acessar colunas por nome."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def criar_tabelas():
    """Cria todas as tabelas se ainda não existirem."""
    conn = get_conn()
    c = conn.cursor()

    # ── Usuários do sistema ────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nome        TEXT    NOT NULL,
            login       TEXT    NOT NULL UNIQUE,
            senha_hash  TEXT    NOT NULL,
            nivel       TEXT    NOT NULL DEFAULT 'admin',
            ativo       INTEGER NOT NULL DEFAULT 1,
            criado_em   TEXT    NOT NULL DEFAULT (date('now'))
        )
    """)

    # ── Modalidades (musculação, pilates, etc.) ────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS modalidades (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            nome  TEXT    NOT NULL UNIQUE,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Tipos de plano (mensal, trimestral, semestral) ─────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS tipos_plano (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            nome         TEXT    NOT NULL UNIQUE,
            meses        INTEGER NOT NULL,
            valor        REAL    NOT NULL,
            ativo        INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Alunos ─────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS alunos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome            TEXT    NOT NULL,
            cpf             TEXT,
            data_nascimento TEXT,
            telefone        TEXT,
            email           TEXT,
            endereco        TEXT,
            observacoes     TEXT,
            foto_path       TEXT,
            status          TEXT    NOT NULL DEFAULT 'ativo',
            origem          TEXT    NOT NULL DEFAULT 'admin',
            criado_em       TEXT    NOT NULL DEFAULT (date('now'))
        )
    """)

    # ── Matrículas (aluno + plano + modalidade + período) ─────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS matriculas (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id         INTEGER NOT NULL REFERENCES alunos(id),
            tipo_plano_id    INTEGER NOT NULL REFERENCES tipos_plano(id),
            modalidade_id    INTEGER NOT NULL REFERENCES modalidades(id),
            valor_contratado REAL,
            data_inicio      TEXT    NOT NULL,
            data_fim         TEXT    NOT NULL,
            status           TEXT    NOT NULL DEFAULT 'aguardando_pagamento',
            renovacao_auto   INTEGER NOT NULL DEFAULT 1,
            criado_em        TEXT    NOT NULL DEFAULT (date('now'))
        )
    """)
    # valor_contratado: preço travado no momento da matrícula.
    # Renovações usam este valor, não o valor atual do plano.
    # Para alterar o preço de um aluno, cancele e crie nova matrícula.
    # status possíveis: ativo | aguardando_pagamento | inadimplente | cancelado | encerrado

    # ── Pagamentos ─────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula_id    INTEGER NOT NULL REFERENCES matriculas(id),
            aluno_id        INTEGER NOT NULL REFERENCES alunos(id),
            valor           REAL    NOT NULL,
            data_vencimento TEXT    NOT NULL,
            data_pagamento  TEXT,
            forma           TEXT,
            status          TEXT    NOT NULL DEFAULT 'pendente',
            periodo_ref     TEXT,
            observacoes     TEXT,
            criado_em       TEXT    NOT NULL DEFAULT (date('now'))
        )
    """)
    # status: pendente | pago | vencido | cancelado

    # ── Pré-cadastros (link público) ───────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS precadastros (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nome            TEXT    NOT NULL,
            cpf             TEXT,
            data_nascimento TEXT,
            telefone        TEXT,
            email           TEXT,
            tipo_plano_id   INTEGER REFERENCES tipos_plano(id),
            modalidade_id   INTEGER REFERENCES modalidades(id),
            observacoes     TEXT,
            status          TEXT    NOT NULL DEFAULT 'pendente',
            criado_em       TEXT    NOT NULL DEFAULT (date('now'))
        )
    """)
    # status: pendente | aprovado | recusado

    conn.commit()
    conn.close()
    logger.info("Tabelas verificadas/criadas com sucesso.")


def migrar():
    """Aplica migrações incrementais no banco existente."""
    conn = get_conn()
    c = conn.cursor()

    # V1.0.05 — adiciona valor_contratado em matriculas (se não existir)
    cols_mat = [r[1] for r in c.execute("PRAGMA table_info(matriculas)").fetchall()]
    if "valor_contratado" not in cols_mat:
        c.execute("ALTER TABLE matriculas ADD COLUMN valor_contratado REAL")
        logger.info("Migração: coluna valor_contratado adicionada em matriculas.")

    # V1.0.10 — endereço detalhado em alunos
    cols_al = [r[1] for r in c.execute("PRAGMA table_info(alunos)").fetchall()]
    for col, tipo in [("cep", "TEXT"), ("logradouro", "TEXT"),
                      ("numero", "TEXT"), ("bairro", "TEXT"), ("cidade", "TEXT"), ("uf", "TEXT")]:
        if col not in cols_al:
            c.execute(f"ALTER TABLE alunos ADD COLUMN {col} {tipo}")
            logger.info("Migração: coluna %s adicionada em alunos.", col)

    # V1.4.00 — desconto em pagamentos
    cols_pag = [r[1] for r in c.execute("PRAGMA table_info(pagamentos)").fetchall()]
    if "desconto" not in cols_pag:
        c.execute("ALTER TABLE pagamentos ADD COLUMN desconto REAL DEFAULT 0")
        logger.info("Migração: coluna desconto adicionada em pagamentos.")

    conn.commit()
    conn.close()


def seed_inicial():
    """Insere dados iniciais se o banco estiver vazio."""
    conn = get_conn()
    c = conn.cursor()

    # Usuário admin padrão
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO usuarios (nome, login, senha_hash, nivel)
            VALUES (?, ?, ?, ?)
        """, ("Administrador", "admin", _hash("admin123"), "admin"))
        logger.info("Usuário admin criado. Login: admin / Senha: admin123")

    # Modalidades padrão
    c.execute("SELECT COUNT(*) FROM modalidades")
    if c.fetchone()[0] == 0:
        for m in ["Musculação", "Pilates", "Funcional", "Spinning", "Yoga", "Natação"]:
            c.execute("INSERT INTO modalidades (nome) VALUES (?)", (m,))

    # Tipos de plano padrão
    c.execute("SELECT COUNT(*) FROM tipos_plano")
    if c.fetchone()[0] == 0:
        planos = [
            ("Mensal",     1,  120.00),
            ("Trimestral", 3,  320.00),
            ("Semestral",  6,  580.00),
        ]
        for nome, meses, valor in planos:
            c.execute(
                "INSERT INTO tipos_plano (nome, meses, valor) VALUES (?,?,?)",
                (nome, meses, valor)
            )

    conn.commit()
    conn.close()
