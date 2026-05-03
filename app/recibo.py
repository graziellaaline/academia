# -*- coding: utf-8 -*-
"""
Geração de recibo de pagamento em HTML.
"""

from app.version import SYSTEM_NAME


def gerar_recibo_html(aluno: dict, pagamento: dict, plano: str, modalidade: str) -> str:
    nome    = aluno.get("nome", "")
    cpf     = aluno.get("cpf") or "—"
    tel     = aluno.get("telefone") or "—"
    num_al  = f"#{aluno['id']:04d}"

    valor       = pagamento.get("valor", 0)
    forma       = pagamento.get("forma") or "—"
    dt_pag      = pagamento.get("data_pagamento") or "—"
    periodo     = pagamento.get("periodo_ref") or "—"
    pag_id      = pagamento.get("id", "")

    valor_fmt = f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Recibo #{pag_id}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6fb; padding: 30px; }}
  .recibo {{ max-width: 600px; margin: 0 auto; background: #fff;
             border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,.10);
             overflow: hidden; }}
  .header {{ background: #1e3a5f; color: #fff; padding: 24px 32px;
             display: flex; align-items: center; justify-content: space-between; }}
  .header h1 {{ font-size: 20px; font-weight: 800; letter-spacing: .5px; }}
  .header .badge {{ background: #e63946; color: #fff; border-radius: 20px;
                    padding: 4px 14px; font-size: 12px; font-weight: 700; }}
  .body {{ padding: 28px 32px; }}
  .title-recibo {{ font-size: 22px; font-weight: 800; color: #1e3a5f;
                   border-bottom: 3px solid #e63946; padding-bottom: 10px; margin-bottom: 20px; }}
  .section {{ margin-bottom: 20px; }}
  .section-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
                    color: #888; font-weight: 700; margin-bottom: 8px; }}
  .row {{ display: flex; gap: 16px; margin-bottom: 8px; }}
  .field {{ flex: 1; }}
  .field label {{ font-size: 11px; color: #999; display: block; margin-bottom: 2px; }}
  .field span {{ font-size: 14px; color: #222; font-weight: 500; }}
  .valor-box {{ background: #1e3a5f; color: #fff; border-radius: 10px;
                padding: 16px 24px; text-align: center; margin: 20px 0; }}
  .valor-box .label {{ font-size: 12px; opacity: .7; margin-bottom: 4px; }}
  .valor-box .valor {{ font-size: 32px; font-weight: 800; color: #fff; }}
  .footer {{ background: #f4f6fb; padding: 16px 32px; text-align: center;
             font-size: 11px; color: #aaa; border-top: 1px solid #eee; }}
  .assinatura {{ margin-top: 32px; border-top: 1px solid #ddd; padding-top: 16px;
                 display: flex; justify-content: space-between; }}
  .ass-box {{ text-align: center; }}
  .ass-line {{ width: 200px; border-bottom: 1px solid #333; margin-bottom: 6px; height: 32px; }}
  .ass-label {{ font-size: 11px; color: #555; }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .recibo {{ box-shadow: none; }}
  }}
</style>
</head>
<body>
<div class="recibo">
  <div class="header">
    <h1>{SYSTEM_NAME}</h1>
    <span class="badge">RECIBO #{pag_id}</span>
  </div>
  <div class="body">
    <div class="title-recibo">Recibo de Pagamento</div>

    <div class="section">
      <div class="section-title">Dados do Aluno</div>
      <div class="row">
        <div class="field"><label>Nº Aluno</label><span>{num_al}</span></div>
        <div class="field"><label>Nome</label><span>{nome}</span></div>
      </div>
      <div class="row">
        <div class="field"><label>CPF</label><span>{cpf}</span></div>
        <div class="field"><label>Telefone</label><span>{tel}</span></div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Detalhes do Plano</div>
      <div class="row">
        <div class="field"><label>Plano</label><span>{plano}</span></div>
        <div class="field"><label>Modalidade</label><span>{modalidade}</span></div>
        <div class="field"><label>Período</label><span>{periodo}</span></div>
      </div>
    </div>

    <div class="valor-box">
      <div class="label">VALOR RECEBIDO</div>
      <div class="valor">{valor_fmt}</div>
    </div>

    <div class="section">
      <div class="section-title">Pagamento</div>
      <div class="row">
        <div class="field"><label>Forma de Pagamento</label><span>{forma}</span></div>
        <div class="field"><label>Data do Pagamento</label><span>{dt_pag}</span></div>
      </div>
    </div>

    <div class="assinatura">
      <div class="ass-box">
        <div class="ass-line"></div>
        <div class="ass-label">Assinatura do Responsável</div>
      </div>
      <div class="ass-box">
        <div class="ass-line"></div>
        <div class="ass-label">Assinatura do Aluno</div>
      </div>
    </div>
  </div>
  <div class="footer">
    {SYSTEM_NAME} &mdash; Documento gerado em {dt_pag} &mdash; Recibo #{pag_id}
  </div>
</div>
<script>
  // Imprime automaticamente se aberto isolado
  if (window.opener === null) {{ window.print(); }}
</script>
</body>
</html>"""
