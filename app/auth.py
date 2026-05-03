# -*- coding: utf-8 -*-
"""
Autenticação e controle de sessão.
"""

import hashlib
import logging
from typing import Optional, Dict

from app.database import get_conn

logger = logging.getLogger(__name__)

NIVEIS = {
    "admin":      {"label": "Administrador", "cor": "#dc3545"},
    "gerente":    {"label": "Gerente",        "cor": "#fd7e14"},
    "recepcao":   {"label": "Recepção",       "cor": "#0d6efd"},
}


def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def autenticar(login: str, senha: str) -> Optional[Dict]:
    """Retorna dict do usuário se credenciais válidas, None caso contrário."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE login=? AND ativo=1", (login.strip(),)
    ).fetchone()
    conn.close()
    if row and row["senha_hash"] == _hash(senha):
        return dict(row)
    return None


def listar_usuarios():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM usuarios ORDER BY nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def criar_usuario(nome, login, senha, nivel="recepcao"):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO usuarios (nome, login, senha_hash, nivel) VALUES (?,?,?,?)",
            (nome.strip(), login.strip(), _hash(senha), nivel)
        )
        conn.commit()
        return True, "Usuário criado com sucesso."
    except Exception as e:
        return False, f"Erro: {e}"
    finally:
        conn.close()


def alterar_senha(usuario_id, nova_senha):
    conn = get_conn()
    conn.execute(
        "UPDATE usuarios SET senha_hash=? WHERE id=?", (_hash(nova_senha), usuario_id)
    )
    conn.commit()
    conn.close()


def desativar_usuario(usuario_id):
    conn = get_conn()
    conn.execute("UPDATE usuarios SET ativo=0 WHERE id=?", (usuario_id,))
    conn.commit()
    conn.close()
