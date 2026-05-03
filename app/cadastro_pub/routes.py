# -*- coding: utf-8 -*-
"""
Rota pública /cadastro — formulário mobile-friendly para novos alunos.
Não requer login.
"""

from flask import Blueprint, render_template_string, request, redirect, url_for
from app.database import get_conn
from app.alunos import listar_planos, listar_modalidades

bp = Blueprint("cadastro_pub", __name__)

_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cadastro — {{ nome_academia }}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  body { background: #f4f6fb; font-family: 'Segoe UI', sans-serif; }
  .card-form { max-width: 520px; margin: 32px auto; border-radius: 16px; padding: 32px; background: #fff; box-shadow: 0 4px 24px rgba(0,0,0,0.10); }
  h4 { color: #1e3a5f; font-weight: 800; }
  .btn-enviar { background: #e63946; border-color: #e63946; font-weight: 700; }
  .badge-rv { background: #e63946; font-size: 11px; }
</style>
</head>
<body>
<div class="card-form">
  <div class="text-center mb-4">
    <span class="badge badge-rv rounded-pill px-3 py-2 text-white mb-2" style="background:#e63946">Novo Aluno</span>
    <h4>{{ nome_academia }}</h4>
    <p class="text-muted" style="font-size:13px">Preencha os dados abaixo para solicitar sua matrícula.</p>
  </div>

  {% if sucesso %}
  <div class="alert alert-success text-center">
    <strong>Cadastro enviado!</strong><br>
    Entraremos em contato em breve para confirmar sua matrícula.
  </div>
  {% else %}

  {% if erro %}
  <div class="alert alert-danger">{{ erro }}</div>
  {% endif %}

  <form method="POST">
    <div class="mb-3">
      <label class="form-label fw-semibold">Nome completo *</label>
      <input type="text" name="nome" class="form-control form-control-lg" required placeholder="Seu nome">
    </div>
    <div class="row g-2 mb-3">
      <div class="col-6">
        <label class="form-label fw-semibold">CPF</label>
        <input type="text" name="cpf" class="form-control" placeholder="000.000.000-00">
      </div>
      <div class="col-6">
        <label class="form-label fw-semibold">Nascimento</label>
        <input type="date" name="data_nascimento" class="form-control">
      </div>
    </div>
    <div class="row g-2 mb-3">
      <div class="col-6">
        <label class="form-label fw-semibold">Telefone / WhatsApp *</label>
        <input type="tel" name="telefone" class="form-control" required placeholder="(00) 00000-0000">
      </div>
      <div class="col-6">
        <label class="form-label fw-semibold">E-mail</label>
        <input type="email" name="email" class="form-control" placeholder="seu@email.com">
      </div>
    </div>
    <div class="mb-3">
      <label class="form-label fw-semibold">Plano desejado *</label>
      <select name="tipo_plano_id" class="form-select" required>
        <option value="">Selecione...</option>
        {% for p in planos %}
        <option value="{{ p.id }}">{{ p.nome }} — R$ {{ "%.2f"|format(p.valor) }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label fw-semibold">Modalidade *</label>
      <select name="modalidade_id" class="form-select" required>
        <option value="">Selecione...</option>
        {% for m in modalidades %}
        <option value="{{ m.id }}">{{ m.nome }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="mb-4">
      <label class="form-label fw-semibold">Observações</label>
      <textarea name="observacoes" class="form-control" rows="2" placeholder="Alguma informação adicional?"></textarea>
    </div>
    <button type="submit" class="btn btn-enviar text-white w-100 btn-lg">Enviar Cadastro</button>
  </form>
  {% endif %}

  <p class="text-center text-muted mt-4" style="font-size:11px">
    Suas informações são utilizadas exclusivamente pela {{ nome_academia }}.
  </p>
</div>
</body>
</html>
"""


@bp.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    from app.version import SYSTEM_NAME
    planos      = listar_planos()
    modalidades = listar_modalidades()
    erro   = None
    sucesso = False

    if request.method == "POST":
        nome     = " ".join(p.capitalize() for p in request.form.get("nome", "").strip().split())
        telefone = request.form.get("telefone", "").strip()
        if not nome or not telefone:
            erro = "Nome e telefone são obrigatórios."
        else:
            conn = get_conn()
            conn.execute("""
                INSERT INTO precadastros
                    (nome, cpf, data_nascimento, telefone, email,
                     tipo_plano_id, modalidade_id, observacoes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nome,
                request.form.get("cpf") or None,
                request.form.get("data_nascimento") or None,
                telefone,
                request.form.get("email") or None,
                request.form.get("tipo_plano_id") or None,
                request.form.get("modalidade_id") or None,
                request.form.get("observacoes") or None,
            ))
            conn.commit()
            conn.close()
            sucesso = True

    return render_template_string(
        _HTML,
        nome_academia=SYSTEM_NAME,
        planos=planos,
        modalidades=modalidades,
        erro=erro,
        sucesso=sucesso,
    )
