# -*- coding: utf-8 -*-
"""
CRUD de alunos, matrículas e consultas agregadas.
"""

import logging
import unicodedata
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from app.database import get_conn

logger = logging.getLogger(__name__)

STATUS_MATRICULA_ABERTOS = ("ativo", "aguardando_pagamento", "inadimplente")
MOTIVOS_MATRICULA = (
    "financeiro",
    "mudanca_de_plano",
    "cancelamento_de_plano",
)


# ── Alunos ─────────────────────────────────────────────────────────────────

def listar_alunos(status=None, busca=None):
    conn = get_conn()
    sql  = """
        SELECT a.*,
               (SELECT COUNT(*) FROM matriculas m WHERE m.aluno_id=a.id AND m.status='ativo') AS matriculas_ativas,
               (SELECT tp.nome || ' / ' || mod.nome
                FROM matriculas m
                JOIN tipos_plano tp  ON tp.id  = m.tipo_plano_id
                JOIN modalidades mod ON mod.id = m.modalidade_id
                WHERE m.aluno_id = a.id AND m.status = 'ativo'
                ORDER BY m.criado_em DESC LIMIT 1) AS plano_ativo
        FROM alunos a WHERE 1=1"""
    params = []
    if status:
        sql += " AND a.status=?"
        params.append(status)
    sql += " ORDER BY a.nome"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    lista = [dict(r) for r in rows]
    if not busca:
        return lista

    termo = _normalizar_busca(busca)
    return [a for a in lista if termo in _texto_busca_aluno(a)]


def buscar_aluno(aluno_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM alunos WHERE id=?", (aluno_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _fmt_nome_aluno(nome: str) -> str:
    """Primeira letra de cada palavra maiúscula, demais minúsculas."""
    return " ".join(p.capitalize() for p in nome.strip().split()) if nome else ""


def _normalizar_busca(texto: str) -> str:
    texto = "".join(
        c for c in unicodedata.normalize("NFKD", texto or "")
        if not unicodedata.combining(c)
    )
    return " ".join(texto.casefold().split())


def _texto_busca_aluno(aluno: dict) -> str:
    partes = [
        aluno.get("nome", ""),
        aluno.get("cpf", ""),
        aluno.get("telefone", ""),
        aluno.get("email", ""),
        aluno.get("plano_ativo", ""),
    ]
    return _normalizar_busca(" ".join(p for p in partes if p))


def _fmt_cpf(cpf: str) -> str:
    digits = "".join(c for c in (cpf or "") if c.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return cpf or ""


def criar_aluno(dados: dict):
    dados = dict(dados)
    dados["nome"] = _fmt_nome_aluno(dados.get("nome", ""))
    dados["cpf"]  = _fmt_cpf(dados.get("cpf", ""))
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO alunos (nome, cpf, data_nascimento, telefone, email,
                            endereco, cep, logradouro, numero, bairro, cidade, uf,
                            observacoes, origem)
        VALUES (:nome, :cpf, :data_nascimento, :telefone, :email,
                :endereco, :cep, :logradouro, :numero, :bairro, :cidade, :uf,
                :observacoes, :origem)
    """, dados)
    aluno_id = c.lastrowid
    conn.commit()
    conn.close()
    return aluno_id


def atualizar_aluno(aluno_id: int, dados: dict):
    dados = dict(dados)
    dados["nome"] = _fmt_nome_aluno(dados.get("nome", ""))
    dados["cpf"]  = _fmt_cpf(dados.get("cpf", ""))
    conn = get_conn()
    conn.execute("""
        UPDATE alunos
        SET nome=:nome, cpf=:cpf, data_nascimento=:data_nascimento,
            telefone=:telefone, email=:email, endereco=:endereco,
            cep=:cep, logradouro=:logradouro, numero=:numero,
            bairro=:bairro, cidade=:cidade, uf=:uf,
            observacoes=:observacoes
        WHERE id=:id
    """, {**dados, "id": aluno_id})
    conn.commit()
    conn.close()


def inativar_aluno(aluno_id: int):
    conn = get_conn()
    conn.execute("UPDATE alunos SET status='inativo' WHERE id=?", (aluno_id,))
    conn.execute("UPDATE matriculas SET status='cancelado' WHERE aluno_id=? AND status NOT IN ('encerrado','cancelado')", (aluno_id,))
    conn.commit()
    conn.close()


# ── Matrículas ─────────────────────────────────────────────────────────────

def listar_matriculas_aluno(aluno_id: int):
    conn = get_conn()
    rows = conn.execute("""
        SELECT m.*, tp.nome AS plano, tp.meses, tp.valor,
               mod.nome AS modalidade
        FROM   matriculas m
        JOIN   tipos_plano tp  ON tp.id  = m.tipo_plano_id
        JOIN   modalidades mod ON mod.id = m.modalidade_id
        WHERE  m.aluno_id = ?
        ORDER  BY m.criado_em DESC
    """, (aluno_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def buscar_matricula_corrente(aluno_id: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT m.*, tp.nome AS plano, tp.meses, tp.valor,
               mod.nome AS modalidade
        FROM   matriculas m
        JOIN   tipos_plano tp  ON tp.id  = m.tipo_plano_id
        JOIN   modalidades mod ON mod.id = m.modalidade_id
        WHERE  m.aluno_id = ?
          AND  m.status IN (?, ?, ?)
        ORDER  BY CASE m.status
                    WHEN 'ativo' THEN 0
                    WHEN 'aguardando_pagamento' THEN 1
                    ELSE 2
                  END,
                  date(COALESCE(m.data_inicio, m.criado_em)) DESC,
                  m.id DESC
        LIMIT 1
    """, (aluno_id, *STATUS_MATRICULA_ABERTOS)).fetchone()
    conn.close()
    return dict(row) if row else None


def _normalizar_data_mudanca(data_mudanca: str, data_inicio_atual: str) -> tuple[str, str]:
    data_ref = date.fromisoformat(data_mudanca)
    data_inicio = date.fromisoformat(data_inicio_atual)
    data_fim = max(data_inicio, data_ref - timedelta(days=1))
    return data_ref.isoformat(), data_fim.isoformat()


def criar_matricula(aluno_id: int, tipo_plano_id: int, modalidade_id: int = None,
                    data_inicio: str = None, renovacao_auto: bool = True,
                    valor_override: float = None):
    """
    Cria matrícula e gera o primeiro pagamento.
    modalidade_id: se None, usa a modalidade embutida no plano.
    valor_override: se informado, usa esse valor em vez do preço atual do plano.
    """
    hoje = date.today()
    inicio = date.fromisoformat(data_inicio) if data_inicio else hoje

    conn = get_conn()
    plano = conn.execute("SELECT * FROM tipos_plano WHERE id=?", (tipo_plano_id,)).fetchone()
    if not plano:
        conn.close()
        return None, "Plano não encontrado."

    # Prioridade: modalidade_id passado > modalidade embutida no plano > primeiro ativo
    effective_mod = modalidade_id or dict(plano).get("modalidade_id")
    if not effective_mod:
        first_mod = conn.execute(
            "SELECT id FROM modalidades WHERE ativo=1 ORDER BY id LIMIT 1"
        ).fetchone()
        effective_mod = first_mod["id"] if first_mod else 1
    modalidade_id = effective_mod

    valor = valor_override if valor_override is not None else plano["valor"]
    fim   = inicio + relativedelta(months=plano["meses"]) - timedelta(days=1)

    c = conn.cursor()
    c.execute("""
        INSERT INTO matriculas (aluno_id, tipo_plano_id, modalidade_id,
                                valor_contratado, data_inicio, data_fim,
                                status, renovacao_auto)
        VALUES (?, ?, ?, ?, ?, ?, 'aguardando_pagamento', ?)
    """, (aluno_id, tipo_plano_id, modalidade_id,
          valor, inicio.isoformat(), fim.isoformat(), 1 if renovacao_auto else 0))
    mat_id = c.lastrowid

    # Gera o primeiro pagamento com o valor travado
    c.execute("""
        INSERT INTO pagamentos (matricula_id, aluno_id, valor, data_vencimento, status, periodo_ref)
        VALUES (?, ?, ?, ?, 'pendente', ?)
    """, (mat_id, aluno_id, valor, inicio.isoformat(), inicio.strftime("%m/%Y")))

    conn.commit()
    conn.close()
    return mat_id, "Matrícula criada. Aguardando pagamento."


def alterar_matricula_ativa(aluno_id: int, tipo_plano_id: int, modalidade_id: int,
                            data_fim: str, data_inicio: str = None,
                            renovacao_auto: bool = None,
                            valor_override: float = None):
    """
    Atualiza a matrícula aberta mais recente do aluno.
    Ajusta o valor dos pagamentos pendentes quando o plano muda.
    """
    conn = get_conn()
    mat = conn.execute(
        """
        SELECT * FROM matriculas
        WHERE aluno_id=?
          AND status IN (?, ?, ?)
        ORDER BY CASE status
                    WHEN 'ativo' THEN 0
                    WHEN 'aguardando_pagamento' THEN 1
                    ELSE 2
                 END,
                 date(COALESCE(data_inicio, criado_em)) DESC,
                 id DESC
        LIMIT 1
        """,
        (aluno_id, *STATUS_MATRICULA_ABERTOS)
    ).fetchone()
    if not mat:
        conn.close()
        return False, "Nenhuma matrícula aberta encontrada."

    plano = conn.execute("SELECT * FROM tipos_plano WHERE id=?", (tipo_plano_id,)).fetchone()
    if not plano:
        conn.close()
        return False, "Plano não encontrado."

    valor = valor_override if valor_override is not None else plano["valor"]
    plano_mudou = mat["tipo_plano_id"] != tipo_plano_id

    campos = [
        "tipo_plano_id=?",
        "modalidade_id=?",
        "data_fim=?",
        "valor_contratado=?",
    ]
    params = [tipo_plano_id, modalidade_id, data_fim, valor]

    if data_inicio:
        campos.append("data_inicio=?")
        params.append(data_inicio)
    if renovacao_auto is not None:
        campos.append("renovacao_auto=?")
        params.append(1 if renovacao_auto else 0)

    params.append(mat["id"])

    conn.execute(
        f"UPDATE matriculas SET {', '.join(campos)} WHERE id=?",
        params,
    )

    if plano_mudou:
        conn.execute("""
            UPDATE pagamentos SET valor=?
            WHERE matricula_id=? AND status IN ('pendente', 'vencido')
        """, (valor, mat["id"]))

    if data_inicio and mat["status"] == "aguardando_pagamento":
        periodo_ref = date.fromisoformat(data_inicio).strftime("%m/%Y")
        conn.execute("""
            UPDATE pagamentos
            SET data_vencimento=?, periodo_ref=?
            WHERE id = (
                SELECT id FROM pagamentos
                WHERE matricula_id=? AND status IN ('pendente', 'vencido')
                ORDER BY id
                LIMIT 1
            )
        """, (data_inicio, periodo_ref, mat["id"]))

    conn.commit()
    conn.close()
    return True, "Matrícula atualizada."


def cancelar_matricula(matricula_id: int):
    conn = get_conn()
    conn.execute("UPDATE matriculas SET status='cancelado' WHERE id=?", (matricula_id,))
    conn.execute(
        "UPDATE pagamentos SET status='cancelado' WHERE matricula_id=? AND status='pendente'",
        (matricula_id,)
    )
    conn.commit()
    conn.close()


def encerrar_matricula(matricula_id: int, data_mudanca: str, motivo: str,
                      status_destino: str = "cancelado"):
    if status_destino not in ("cancelado", "encerrado"):
        return False, "Status de encerramento inválido."
    if motivo not in MOTIVOS_MATRICULA:
        return False, "Motivo inválido para a matrícula."

    conn = get_conn()
    mat = conn.execute("SELECT * FROM matriculas WHERE id=?", (matricula_id,)).fetchone()
    if not mat:
        conn.close()
        return False, "Matrícula não encontrada."

    data_ref, data_fim = _normalizar_data_mudanca(data_mudanca, mat["data_inicio"])
    conn.execute("""
        UPDATE matriculas
        SET status=?,
            renovacao_auto=0,
            data_fim=?,
            data_encerramento=?,
            motivo_encerramento=?
        WHERE id=?
    """, (status_destino, data_fim, data_ref, motivo, matricula_id))
    conn.execute("""
        UPDATE pagamentos
        SET status='cancelado'
        WHERE matricula_id=? AND status IN ('pendente', 'vencido')
    """, (matricula_id,))
    conn.commit()
    conn.close()
    return True, "Matrícula encerrada."


def trocar_plano_matricula(matricula_id: int, novo_plano_id: int, nova_modalidade_id: int,
                           data_mudanca: str, motivo: str = "mudanca_de_plano",
                           renovacao_auto: bool = True):
    conn = get_conn()
    mat = conn.execute("SELECT * FROM matriculas WHERE id=?", (matricula_id,)).fetchone()
    conn.close()
    if not mat:
        return False, "Matrícula não encontrada.", None

    ok, msg = encerrar_matricula(
        matricula_id,
        data_mudanca=data_mudanca,
        motivo=motivo,
        status_destino="encerrado",
    )
    if not ok:
        return False, msg, None

    nova_matricula_id, msg_nova = criar_matricula(
        mat["aluno_id"],
        novo_plano_id,
        nova_modalidade_id,
        data_inicio=data_mudanca,
        renovacao_auto=renovacao_auto,
    )
    return True, msg_nova, nova_matricula_id


# ── Pagamentos ─────────────────────────────────────────────────────────────

def listar_pagamentos(aluno_id=None, status=None, mes=None, ano=None):
    conn = get_conn()
    sql = """
        SELECT p.*, a.nome AS aluno_nome,
               tp.nome AS plano, mod.nome AS modalidade
        FROM   pagamentos p
        JOIN   alunos a       ON a.id   = p.aluno_id
        JOIN   matriculas m   ON m.id   = p.matricula_id
        JOIN   tipos_plano tp ON tp.id  = m.tipo_plano_id
        JOIN   modalidades mod ON mod.id = m.modalidade_id
        WHERE  1=1
    """
    params = []
    if aluno_id:
        sql += " AND p.aluno_id=?"; params.append(aluno_id)
    if status:
        sql += " AND p.status=?";   params.append(status)
    if mes and ano:
        sql += " AND strftime('%m/%Y', p.data_vencimento)=?"
        params.append(f"{str(mes).zfill(2)}/{ano}")
    sql += " ORDER BY p.data_vencimento DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Dashboard KPIs ─────────────────────────────────────────────────────────

def kpis():
    conn = get_conn()
    hoje = date.today().isoformat()
    r = {}
    r["ativos"]        = conn.execute("SELECT COUNT(*) FROM alunos WHERE status='ativo'").fetchone()[0]
    r["inadimplentes"] = conn.execute("SELECT COUNT(DISTINCT aluno_id) FROM matriculas WHERE status='inadimplente'").fetchone()[0]
    r["vencendo_7d"]   = conn.execute(
        "SELECT COUNT(*) FROM matriculas WHERE status='ativo' AND date(data_fim) BETWEEN date(?) AND date(?, '+7 days')",
        (hoje, hoje)
    ).fetchone()[0]
    r["receita_mes"]   = conn.execute(
        "SELECT COALESCE(SUM(valor),0) FROM pagamentos WHERE status='pago' AND strftime('%Y-%m', data_pagamento)=strftime('%Y-%m','now')"
    ).fetchone()[0]
    r["a_receber_mes"] = conn.execute(
        "SELECT COALESCE(SUM(valor),0) FROM pagamentos WHERE status IN ('pendente','vencido') AND strftime('%Y-%m', data_vencimento)=strftime('%Y-%m','now')"
    ).fetchone()[0]
    r["precadastros_pendentes"] = conn.execute(
        "SELECT COUNT(*) FROM precadastros WHERE status='pendente'"
    ).fetchone()[0]

    # Novos cadastros este mês
    r["novos_mes"] = conn.execute(
        "SELECT COUNT(*) FROM alunos WHERE strftime('%Y-%m', criado_em)=strftime('%Y-%m','now')"
    ).fetchone()[0]

    # Cancelamentos este mês
    r["cancelamentos_mes"] = conn.execute(
        "SELECT COUNT(*) FROM alunos WHERE status='inativo' AND strftime('%Y-%m', criado_em)=strftime('%Y-%m','now')"
    ).fetchone()[0]

    # Alunos por modalidade (matrículas ativas)
    rows_mod = conn.execute("""
        SELECT mod.nome AS modalidade, COUNT(DISTINCT m.aluno_id) AS total
        FROM matriculas m
        JOIN modalidades mod ON mod.id = m.modalidade_id
        WHERE m.status = 'ativo'
        GROUP BY mod.nome
        ORDER BY total DESC
    """).fetchall()
    r["por_modalidade"] = [dict(row) for row in rows_mod]

    # Novos cadastros últimos 30 dias (para gráfico)
    rows_novos = conn.execute("""
        SELECT strftime('%d/%m', criado_em) AS dia, COUNT(*) AS total
        FROM alunos
        WHERE criado_em >= date('now', '-29 days')
        GROUP BY strftime('%Y-%m-%d', criado_em)
        ORDER BY criado_em
    """).fetchall()
    r["novos_30d"] = [dict(row) for row in rows_novos]

    conn.close()
    return r


# ── Planos e modalidades ───────────────────────────────────────────────────

def listar_planos(apenas_ativos=True):
    conn = get_conn()
    sql = """
        SELECT tp.*, mod.nome AS modalidade_nome
        FROM tipos_plano tp
        LEFT JOIN modalidades mod ON mod.id = tp.modalidade_id
    """
    if apenas_ativos:
        sql += " WHERE tp.ativo=1"
    sql += " ORDER BY tp.nome COLLATE NOCASE"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def atualizar_valor_plano(tipo_plano_id: int, novo_valor: float,
                          atualizar_vigentes: bool = False,
                          atualizar_pendentes: bool = False):
    """
    Atualiza o valor de um tipo de plano.

    atualizar_vigentes:  se True, atualiza valor_contratado das matrículas
                         ativas/aguardando com esse plano (futuras renovações
                         passam a usar o novo valor).
    atualizar_pendentes: se True, atualiza também o valor dos pagamentos
                         ainda pendentes vinculados a essas matrículas.

    Pagamentos já pagos NUNCA são alterados — o histórico é sempre preservado.
    """
    conn = get_conn()
    c = conn.cursor()

    # Atualiza o preço do plano
    c.execute("UPDATE tipos_plano SET valor=? WHERE id=?", (novo_valor, tipo_plano_id))

    afetadas = 0
    if atualizar_vigentes:
        # Matrículas ativas ou aguardando pagamento com esse plano
        c.execute("""
            UPDATE matriculas
            SET valor_contratado = ?
            WHERE tipo_plano_id = ?
              AND status IN ('ativo', 'aguardando_pagamento', 'inadimplente')
        """, (novo_valor, tipo_plano_id))
        afetadas = c.rowcount

    if atualizar_pendentes and afetadas:
        # Pagamentos pendentes/vencidos ligados às matrículas do plano
        c.execute("""
            UPDATE pagamentos
            SET valor = ?
            WHERE matricula_id IN (
                SELECT id FROM matriculas
                WHERE tipo_plano_id = ?
                  AND status IN ('ativo', 'aguardando_pagamento', 'inadimplente')
            )
            AND status IN ('pendente', 'vencido')
        """, (novo_valor, tipo_plano_id))

    conn.commit()
    conn.close()
    return afetadas


def listar_modalidades(apenas_ativas=True):
    conn = get_conn()
    sql = "SELECT * FROM modalidades"
    if apenas_ativas:
        sql += " WHERE ativo=1"
    sql += " ORDER BY nome"
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Pré-cadastros ──────────────────────────────────────────────────────────

def listar_precadastros(status="pendente"):
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*, tp.nome AS plano, mod.nome AS modalidade
        FROM   precadastros p
        LEFT JOIN tipos_plano tp  ON tp.id  = p.tipo_plano_id
        LEFT JOIN modalidades mod ON mod.id = p.modalidade_id
        WHERE  p.status=?
        ORDER  BY p.criado_em DESC
    """, (status,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def aprovar_precadastro(precadastro_id: int, tipo_plano_id: int, modalidade_id: int):
    conn = get_conn()
    pre = conn.execute("SELECT * FROM precadastros WHERE id=?", (precadastro_id,)).fetchone()
    conn.close()
    if not pre:
        return None, "Pré-cadastro não encontrado."

    aluno_id = criar_aluno({
        "nome":            pre["nome"],
        "cpf":             pre["cpf"],
        "data_nascimento": pre["data_nascimento"],
        "telefone":        pre["telefone"],
        "email":           pre["email"],
        "endereco":        "",
        "observacoes":     pre["observacoes"] or "",
        "origem":          "link_publico",
    })

    mat_id, msg = criar_matricula(aluno_id, tipo_plano_id, modalidade_id)

    conn2 = get_conn()
    conn2.execute("UPDATE precadastros SET status='aprovado' WHERE id=?", (precadastro_id,))
    conn2.commit()
    conn2.close()

    return aluno_id, f"Aluno cadastrado. {msg}"
