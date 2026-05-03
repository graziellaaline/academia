# -*- coding: utf-8 -*-
"""
Lógica de renovação automática de matrículas.

Fluxo:
1. Todo dia (ou ao abrir o sistema), verificar_vencimentos() é chamada.
2. Matrículas ativas com data_fim <= hoje + DIAS_AVISO geram pagamento pendente
   para o próximo período (se ainda não existir).
3. Quando o pagamento é confirmado (baixar_pagamento), a matrícula tem
   data_fim estendida e status volta para 'ativo'.
4. Matrículas com pagamento vencido há mais de DIAS_TOLERANCIA viram 'inadimplente'.
"""

import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from app.database import get_conn

logger = logging.getLogger(__name__)

DIAS_AVISO      = 10   # gera cobrança X dias antes do vencimento
DIAS_TOLERANCIA = 5    # após vencimento, aguarda X dias antes de marcar inadimplente


def _hoje() -> date:
    return date.today()


def verificar_vencimentos():
    """
    Roda na inicialização e pode ser chamada a qualquer momento.
    - Gera pagamentos pendentes para renovações próximas.
    - Marca matrículas inadimplentes quando tolerância esgotada.
    - Retorna resumo do que foi feito.
    """
    hoje = _hoje()
    conn = get_conn()
    c = conn.cursor()

    gerados = 0
    inadimplentes = 0

    # ── 1. Gerar cobrança de renovação ────────────────────────────────────
    matriculas = c.execute("""
        SELECT m.*, tp.meses, tp.valor, tp.nome AS nome_plano
        FROM   matriculas m
        JOIN   tipos_plano tp ON tp.id = m.tipo_plano_id
        WHERE  m.status IN ('ativo', 'aguardando_pagamento')
          AND  m.renovacao_auto = 1
    """).fetchall()

    for mat in matriculas:
        data_fim = date.fromisoformat(mat["data_fim"])
        if data_fim - hoje > timedelta(days=DIAS_AVISO):
            continue  # ainda não está na janela de aviso

        # Calcula datas do próximo período
        proximo_inicio = data_fim + timedelta(days=1)
        proximo_fim    = proximo_inicio + relativedelta(months=mat["meses"]) - timedelta(days=1)
        periodo_ref    = f"{proximo_inicio.strftime('%m/%Y')}"

        # Verifica se já existe pagamento gerado para esse período
        ja_existe = c.execute("""
            SELECT id FROM pagamentos
            WHERE matricula_id=? AND periodo_ref=? AND status != 'cancelado'
        """, (mat["id"], periodo_ref)).fetchone()

        if ja_existe:
            continue

        # Usa valor_contratado se disponível, senão usa o valor atual do plano
        valor_renovacao = mat["valor_contratado"] if mat["valor_contratado"] else mat["valor"]

        # Gera o pagamento pendente
        c.execute("""
            INSERT INTO pagamentos
                (matricula_id, aluno_id, valor, data_vencimento, status, periodo_ref)
            VALUES (?, ?, ?, ?, 'pendente', ?)
        """, (mat["id"], mat["aluno_id"], valor_renovacao,
              data_fim.isoformat(), periodo_ref))
        gerados += 1

    # ── 2. Marcar inadimplentes ───────────────────────────────────────────
    pagamentos_vencidos = c.execute("""
        SELECT p.id, p.matricula_id, p.data_vencimento
        FROM   pagamentos p
        WHERE  p.status = 'pendente'
          AND  date(p.data_vencimento) < date('now', ? || ' days')
    """, (f"-{DIAS_TOLERANCIA}",)).fetchall()

    for pag in pagamentos_vencidos:
        c.execute("UPDATE pagamentos   SET status='vencido'      WHERE id=?", (pag["id"],))
        c.execute("UPDATE matriculas   SET status='inadimplente' WHERE id=?", (pag["matricula_id"],))
        inadimplentes += 1

    conn.commit()
    conn.close()

    logger.info("Vencimentos: %d cobranças geradas, %d inadimplentes marcados.", gerados, inadimplentes)
    return {"gerados": gerados, "inadimplentes": inadimplentes}


def baixar_pagamento(pagamento_id: int, forma: str, data_pagamento: str = None, observacoes: str = ""):
    """
    Confirma o recebimento de um pagamento.
    - Atualiza status do pagamento para 'pago'.
    - Estende data_fim da matrícula pelo período correspondente.
    - Ativa a matrícula (status = 'ativo').
    """
    hoje = _hoje()
    data_pag = data_pagamento or hoje.isoformat()

    conn = get_conn()
    c = conn.cursor()

    pag = c.execute("SELECT * FROM pagamentos WHERE id=?", (pagamento_id,)).fetchone()
    if not pag:
        conn.close()
        return False, "Pagamento não encontrado."

    if pag["status"] == "pago":
        conn.close()
        return False, "Pagamento já foi baixado."

    # Atualiza o pagamento
    c.execute("""
        UPDATE pagamentos
        SET status='pago', data_pagamento=?, forma=?, observacoes=?
        WHERE id=?
    """, (data_pag, forma, observacoes, pagamento_id))

    # Estende a matrícula
    mat = c.execute("""
        SELECT m.*, tp.meses
        FROM   matriculas m
        JOIN   tipos_plano tp ON tp.id = m.tipo_plano_id
        WHERE  m.id = ?
    """, (pag["matricula_id"],)).fetchone()

    if mat:
        data_fim_atual = date.fromisoformat(mat["data_fim"])
        # Se a matrícula já venceu, renova a partir de hoje; senão, estende do fim atual
        base = hoje if data_fim_atual < hoje else data_fim_atual
        nova_data_fim = base + relativedelta(months=mat["meses"])

        c.execute("""
            UPDATE matriculas
            SET data_fim=?, status='ativo'
            WHERE id=?
        """, (nova_data_fim.isoformat(), mat["id"]))

        # Atualiza status do aluno
        c.execute("UPDATE alunos SET status='ativo' WHERE id=?", (mat["aluno_id"],))

    conn.commit()
    conn.close()
    return True, "Pagamento confirmado e matrícula renovada."


def cancelar_pagamento(pagamento_id: int):
    conn = get_conn()
    conn.execute("UPDATE pagamentos SET status='cancelado' WHERE id=?", (pagamento_id,))
    conn.commit()
    conn.close()
    return True, "Pagamento cancelado."


def editar_pagamento(pagamento_id: int, desconto: float = None,
                     data_vencimento: str = None, data_pagamento: str = None):
    conn = get_conn()
    campos, params = [], []
    if desconto is not None:
        campos.append("desconto=?")
        params.append(max(0.0, float(desconto)))
    if data_vencimento:
        campos.append("data_vencimento=?")
        params.append(data_vencimento)
    if data_pagamento is not None:
        campos.append("data_pagamento=?")
        params.append(data_pagamento or None)
    if not campos:
        conn.close()
        return False, "Nada a alterar."
    params.append(pagamento_id)
    conn.execute(f"UPDATE pagamentos SET {', '.join(campos)} WHERE id=?", params)
    conn.commit()
    conn.close()
    return True, "Pagamento atualizado."
