# -*- coding: utf-8 -*-
"""
Dashboard principal — Centro de Treinamento RV
"""

import logging
import re
from datetime import date, timedelta
from urllib.parse import parse_qs, urlencode

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback_context, no_update, ALL
from dash.exceptions import PreventUpdate

from app.version import SYSTEM_NAME, get_version
import app.auth    as auth_mod
import app.alunos  as alunos_mod
import app.renovacao as renov_mod
from app.database import get_conn

logger = logging.getLogger(__name__)

# ── Inicialização ──────────────────────────────────────────────────────────
from pathlib import Path as _Path
app = dash.Dash(
    __name__,
    assets_folder=str(_Path(__file__).resolve().parent.parent / "assets"),
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    ],
    suppress_callback_exceptions=True,
    title=SYSTEM_NAME,
)
server = app.server


# ── Cores / tema ───────────────────────────────────────────────────────────
COR_PRIMARIA  = "#1e3a5f"
COR_ACENTO    = "#e63946"
COR_FUNDO     = "#f4f6fb"
COR_CARD      = "#ffffff"

MOTIVO_MATRICULA_LABELS = {
    "financeiro": "Financeiro",
    "mudanca_de_plano": "Mudança de plano",
    "cancelamento_de_plano": "Cancelamento de plano",
}

TAB_ITENS = [
    ("bi-speedometer2", "dashboard", "Dashboard", "/"),
    ("bi-people-fill", "alunos", "Alunos", "/alunos"),
    ("bi-calendar-check", "pagamentos", "Pagamentos", "/pagamentos"),
    ("bi-person-plus", "precadastros", "Pré-cadastros", "/precadastros"),
    ("bi-card-list", "planos", "Planos e Modalidades", "/planos"),
    ("bi-people", "usuarios", "Usuários", "/usuarios"),
]


def _path_para_tab(pathname):
    pathname = pathname or "/"
    for _, tab, _, path in TAB_ITENS:
        if path != "/" and pathname.startswith(path):
            return tab
    return "dashboard"


def _rota_aluno(pathname):
    if (pathname or "") == "/alunos/novo":
        return "novo", None
    m = re.fullmatch(r"/alunos/(\d+)/(ver|editar)", pathname or "")
    if not m:
        return None, None
    return m.group(2), int(m.group(1))


def _params_alunos(search):
    qs = parse_qs((search or "").lstrip("?"))
    busca = (qs.get("busca") or [""])[0]
    status = (qs.get("status") or ["ativo"])[0] or "ativo"
    return busca, status


def _url_alunos(pathname, busca="", status="ativo"):
    params = {}
    if busca:
        params["busca"] = busca
    if status:
        params["status"] = status
    query = urlencode(params)
    return f"{pathname}?{query}" if query else pathname


def _estado_modal_aluno(pathname):
    hoje = date.today().isoformat()
    estado = {
        "is_open": False,
        "titulo": None,
        "aluno_id": None,
        "nome": "",
        "cpf": "",
        "nasc": "",
        "tel": "",
        "email": "",
        "cep": "",
        "logradouro": "",
        "numero": "",
        "bairro": "",
        "cidade": "",
        "uf": "",
        "obs": "",
        "plano":   None,
        "modal":   None,
        "inicio":  hoje,
        "datafim": None,
        "renovacao": True,
        "erro": "",
        "btn_inativar": None,
    }
    acao, aluno_id = _rota_aluno(pathname)
    if acao == "novo":
        estado["is_open"] = True
        estado["titulo"] = "Novo Aluno"
        return estado
    if acao != "editar" or not aluno_id:
        return estado

    a = alunos_mod.buscar_aluno(aluno_id)
    if not a:
        return estado
    mat_atual = alunos_mod.buscar_matricula_corrente(a["id"])
    estado.update({
        "is_open": True,
        "titulo": f"#{a['id']:04d} — {a['nome']}",
        "aluno_id": a["id"],
        "nome": a["nome"] or "",
        "cpf": a["cpf"] or "",
        "nasc": a["data_nascimento"] or "",
        "tel": a["telefone"] or "",
        "email": a["email"] or "",
        "cep": a.get("cep") or "",
        "logradouro": a.get("logradouro") or "",
        "numero": a.get("numero") or "",
        "bairro": a.get("bairro") or "",
        "cidade": a.get("cidade") or "",
        "uf": a.get("uf") or "",
        "obs": a["observacoes"] or "",
        "plano":   mat_atual["tipo_plano_id"] if mat_atual else None,
        "modal":   mat_atual["modalidade_id"] if mat_atual else None,
        "inicio":  mat_atual["data_inicio"]   if mat_atual else hoje,
        "datafim": mat_atual["data_fim"]      if mat_atual else None,
        "renovacao": bool(mat_atual["renovacao_auto"]) if mat_atual else True,
        "btn_inativar": dbc.Button(
            [html.I(className="bi bi-person-x me-1"), "Inativar"],
            id="btn-abrir-inativar", n_clicks=0,
            color="danger", outline=True, className="me-auto",
        ) if a["status"] == "ativo" else None,
    })
    return estado


def _estado_modal_ver(pathname):
    estado = {"is_open": False, "titulo": None, "corpo": None}
    acao, aluno_id = _rota_aluno(pathname)
    if acao != "ver" or not aluno_id:
        return estado

    a = alunos_mod.buscar_aluno(aluno_id)
    if not a:
        return estado
    matriculas = alunos_mod.listar_matriculas_aluno(aluno_id)
    pagamentos = alunos_mod.listar_pagamentos(aluno_id=aluno_id)

    info = dbc.Row([
        dbc.Col([
            html.Div([
                html.Span(f"#{a['id']:04d}", style={"fontWeight": "700", "color": COR_ACENTO, "fontSize": "18px", "marginRight": "10px"}),
                html.Span(a["nome"], style={"fontWeight": "700", "fontSize": "18px"}),
                html.Span(_badge_status(a["status"]), className="ms-2"),
            ]),
            html.Small([
                html.Span(a["cpf"] or "", className="me-3"),
                html.Span(a["telefone"] or "", className="me-3"),
                html.Span(a["email"] or ""),
            ], className="text-muted"),
        ]),
    ], className="mb-3")

    if matriculas:
        rows_mat = [html.Tr([
            html.Td(m["plano"]), html.Td(m["modalidade"]),
            html.Td(_fmt_brl(m["valor_contratado"] or m["valor"])),
            html.Td(_fmt_data(m["data_inicio"])), html.Td(_fmt_data(m["data_fim"])), html.Td(_badge_status(m["status"])),
        ]) for m in matriculas]
        tabela_mat = dbc.Table([
            html.Thead(html.Tr([html.Th("Plano"), html.Th("Modalidade"), html.Th("Valor"), html.Th("Início"), html.Th("Fim"), html.Th("Status")])),
            html.Tbody(rows_mat),
        ], bordered=True, size="sm", responsive=True, className="mb-0")
    else:
        tabela_mat = html.P("Nenhuma matrícula encontrada.", className="text-muted")

    if pagamentos:
        rows_pag = [html.Tr([
            html.Td(p["periodo_ref"] or "—"), html.Td(p["plano"]), html.Td(_fmt_brl(p["valor"])),
            html.Td(_fmt_data(p["data_vencimento"])), html.Td(_fmt_data(p["data_pagamento"])), html.Td(p["forma"] or "—"), html.Td(_badge_status(p["status"])),
        ]) for p in pagamentos]
        tabela_pag = dbc.Table([
            html.Thead(html.Tr([html.Th("Período"), html.Th("Plano"), html.Th("Valor"), html.Th("Vencimento"), html.Th("Pago em"), html.Th("Forma"), html.Th("Status")])),
            html.Tbody(rows_pag),
        ], bordered=True, size="sm", responsive=True, className="mb-0")
    else:
        tabela_pag = html.P("Nenhum pagamento encontrado.", className="text-muted")

    estado.update({
        "is_open": True,
        "titulo": f"#{a['id']:04d} — {a['nome']}",
        "corpo": html.Div([
            info,
            html.H6("Matrículas", className="fw-bold mt-2 mb-1", style={"color": COR_PRIMARIA}),
            tabela_mat,
            html.H6("Histórico de Pagamentos", className="fw-bold mt-3 mb-1", style={"color": COR_PRIMARIA}),
            tabela_pag,
        ]),
    })
    return estado


# ── Helpers visuais ────────────────────────────────────────────────────────

def _kpi_card(card_id, titulo, valor, subtitulo, icone, cor):
    return dbc.Col(
        dbc.Button(
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Div(titulo, style={"fontSize": "11px", "color": "#6c757d", "fontWeight": "600", "textTransform": "uppercase", "letterSpacing": "0.5px"}),
                            html.Div(str(valor), style={"fontSize": "28px", "fontWeight": "800", "color": COR_PRIMARIA, "lineHeight": "1.1"}),
                            html.Div(subtitulo, style={"fontSize": "11px", "color": "#aaa", "marginTop": "2px"}),
                        ], style={"flex": 1, "textAlign": "left"}),
                        html.Div(
                            html.I(className=f"bi {icone}", style={"fontSize": "28px", "color": cor, "opacity": "0.85"}),
                            style={"alignSelf": "center"}
                        ),
                    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start"}),
                ])
            ], style={"borderRadius": "12px", "border": f"1px solid {cor}22", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)", "background": COR_CARD}),
            id=f"card-{card_id}",
            n_clicks=0,
            color="link",
            title="Clique para ver os detalhes",
            style={"padding": 0, "border": "none", "width": "100%", "textDecoration": "none"},
        ),
        md=2, xs=6, className="mb-3",
    )


def _tabela_dashboard(colunas, linhas, vazio):
    if not linhas:
        return html.Div(vazio, className="text-muted")
    return dbc.Table(
        [html.Thead(html.Tr([html.Th(c) for c in colunas])), html.Tbody(linhas)],
        bordered=True, hover=True, size="sm", responsive=True, className="mb-0"
    )


def _detalhes_dashboard(card_id, dias=7, busca_inadimplente="", ordenacao_inadimplente="vencimento"):
    hoje_dt = date.today()
    hoje = hoje_dt.isoformat()
    conn = get_conn()
    titulo = "Detalhes"
    subtitulo = ""
    corpo = None
    vazio = "Nenhum registro encontrado."

    if card_id == "ativos":
        titulo = "Alunos Ativos"
        subtitulo = "Cadastros ativos no momento"
        alunos = alunos_mod.listar_alunos(status="ativo")[:15]
        corpo = _tabela_dashboard(["Nº", "Nome", "Telefone", "Plano / Modalidade"], [html.Tr([
            html.Td(f"#{a['id']:04d}"),
            html.Td(a["nome"]),
            html.Td(a["telefone"] or "—"),
            html.Td(a.get("plano_ativo") or "—"),
        ]) for a in alunos], vazio)
    elif card_id == "inadimplentes":
        if busca_inadimplente:
            titulo = "Busca de Alunos"
            subtitulo = "Resultado da busca — clique em Receber para registrar pagamento pendente"
            matched = alunos_mod.listar_alunos(status="ativo", busca=busca_inadimplente)[:20]
            linhas = []
            for a in matched:
                pag = conn.execute("""
                    SELECT p.id, p.valor, p.data_vencimento,
                           COALESCE(tp.nome || ' / ' || mod.nome, '—') AS plano
                    FROM pagamentos p
                    JOIN matriculas m ON m.id = p.matricula_id
                    LEFT JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
                    LEFT JOIN modalidades mod ON mod.id = m.modalidade_id
                    WHERE p.aluno_id = ? AND p.status IN ('pendente','vencido')
                    ORDER BY date(p.data_vencimento), p.id LIMIT 1
                """, (a["id"],)).fetchone()
                if pag:
                    pag = dict(pag)
                    linhas.append(html.Tr([
                        html.Td(f"#{a['id']:04d}"),
                        html.Td(a["nome"]),
                        html.Td(a.get("telefone") or "—"),
                        html.Td(pag["plano"]),
                        html.Td(_fmt_data(pag["data_vencimento"])),
                        html.Td(_fmt_brl(pag["valor"])),
                        html.Td(dbc.Button(
                            [html.I(className="bi bi-cash-coin me-1"), "Receber"],
                            id={"type": "btn-baixar-pag", "index": pag["id"]},
                            color="success", size="sm", outline=True,
                        )),
                    ]))
                else:
                    linhas.append(html.Tr([
                        html.Td(f"#{a['id']:04d}"),
                        html.Td(a["nome"]),
                        html.Td(a.get("telefone") or "—"),
                        html.Td(a.get("plano_ativo") or "—"),
                        html.Td("—"),
                        html.Td("—"),
                        html.Td(_badge_status("ativo")),
                    ]))
            corpo = _tabela_dashboard(
                ["Nº", "Nome", "Telefone", "Plano", "Vencimento", "Valor", ""],
                linhas, vazio
            )
        else:
            titulo = "Inadimplentes"
            subtitulo = "Busque o aluno e registre o pagamento como atalho"
            rows = conn.execute("""
                SELECT p.id, a.id AS aluno_id, a.nome, a.telefone,
                       COALESCE(tp.nome || ' / ' || mod.nome, '—') AS plano,
                       p.valor, p.data_vencimento, p.status
                FROM pagamentos p
                JOIN alunos a ON a.id = p.aluno_id
                JOIN matriculas m ON m.id = p.matricula_id
                LEFT JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
                LEFT JOIN modalidades mod ON mod.id = m.modalidade_id
                WHERE m.status = 'inadimplente'
                  AND p.status IN ('pendente', 'vencido')
                ORDER BY a.nome, date(p.data_vencimento), p.id
            """).fetchall()
            lista = [dict(r) for r in rows]
            if ordenacao_inadimplente == "nome":
                lista.sort(key=lambda r: ((r["nome"] or "").casefold(), r.get("data_vencimento") or "", r["id"]))
            elif ordenacao_inadimplente == "valor_desc":
                lista.sort(key=lambda r: (float(r["valor"] or 0), (r["nome"] or "").casefold()), reverse=True)
            else:
                lista.sort(key=lambda r: (r.get("data_vencimento") or "9999-12-31", (r["nome"] or "").casefold(), r["id"]))
            lista = lista[:15]
            corpo = _tabela_dashboard(["Nº", "Nome", "Telefone", "Plano", "Vencimento", "Valor", ""], [html.Tr([
                    html.Td(f"#{r['aluno_id']:04d}"),
                    html.Td(r["nome"]),
                    html.Td(r["telefone"] or "—"),
                    html.Td(r["plano"]),
                    html.Td(_fmt_data(r["data_vencimento"])),
                    html.Td(_fmt_brl(r["valor"])),
                    html.Td(dbc.Button(
                        [html.I(className="bi bi-cash-coin me-1"), "Receber"],
                        id={"type": "btn-baixar-pag", "index": r["id"]},
                        color="success", size="sm", outline=True,
                    )),
                ]) for r in lista], vazio)
    elif card_id == "vencendo":
        dias = max(int(dias or 7), 1)
        fim = (hoje_dt + timedelta(days=dias)).isoformat()
        titulo = "Vencimentos Configuráveis"
        subtitulo = f"Matrículas ativas vencendo nos próximos {dias} dias"
        rows = conn.execute("""
            SELECT a.nome, COALESCE(tp.nome || ' / ' || mod.nome, '—') AS plano, m.data_fim
            FROM matriculas m
            JOIN alunos a ON a.id = m.aluno_id
            LEFT JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
            LEFT JOIN modalidades mod ON mod.id = m.modalidade_id
            WHERE m.status = 'ativo'
              AND date(m.data_fim) BETWEEN date(?) AND date(?)
            ORDER BY date(m.data_fim), a.nome
            LIMIT 15
        """, (hoje, fim)).fetchall()
        corpo = _tabela_dashboard(["Aluno", "Plano / Modalidade", "Vencimento"], [html.Tr([
            html.Td(r["nome"]), html.Td(r["plano"]), html.Td(_fmt_data(r["data_fim"]))
        ]) for r in rows], vazio)
    elif card_id == "receita_mes":
        titulo = "Receita do Mês"
        subtitulo = "Pagamentos recebidos no mês atual"
        rows = conn.execute("""
            SELECT p.data_pagamento, a.nome AS aluno_nome, p.plano, p.valor
            FROM pagamentos p
            LEFT JOIN alunos a ON a.id = p.aluno_id
            WHERE p.status = 'pago'
              AND strftime('%Y-%m', p.data_pagamento) = strftime('%Y-%m', 'now')
            ORDER BY p.data_pagamento DESC, p.id DESC
            LIMIT 15
        """).fetchall()
        corpo = _tabela_dashboard(["Pago em", "Aluno", "Plano", "Valor"], [html.Tr([
            html.Td(_fmt_data(r["data_pagamento"])), html.Td(r["aluno_nome"] or "—"), html.Td(r["plano"] or "—"), html.Td(_fmt_brl(r["valor"]))
        ]) for r in rows], vazio)
    elif card_id == "a_receber_mes":
        titulo = "A Receber"
        subtitulo = "Pagamentos pendentes ou vencidos do mês atual"
        rows = conn.execute("""
            SELECT a.nome AS aluno_nome, p.plano, p.data_vencimento, p.valor, p.status
            FROM pagamentos p
            LEFT JOIN alunos a ON a.id = p.aluno_id
            WHERE p.status IN ('pendente','vencido')
              AND strftime('%Y-%m', p.data_vencimento) = strftime('%Y-%m', 'now')
            ORDER BY date(p.data_vencimento), p.id DESC
            LIMIT 15
        """).fetchall()
        corpo = _tabela_dashboard(["Aluno", "Plano", "Vencimento", "Valor", "Status"], [html.Tr([
            html.Td(r["aluno_nome"] or "—"), html.Td(r["plano"] or "—"), html.Td(_fmt_data(r["data_vencimento"])), html.Td(_fmt_brl(r["valor"])), html.Td(_badge_status(r["status"]))
        ]) for r in rows], vazio)
    elif card_id == "precadastros":
        titulo = "Pré-cadastros Pendentes"
        subtitulo = "Cadastros aguardando aprovação"
        precads = alunos_mod.listar_precadastros("pendente")[:15]
        corpo = _tabela_dashboard(["Nome", "Telefone", "Plano", "Modalidade"], [html.Tr([
            html.Td(p["nome"]), html.Td(p.get("telefone") or "—"), html.Td(p.get("plano") or "—"), html.Td(p.get("modalidade") or "—")
        ]) for p in precads], vazio)

    conn.close()
    return dbc.Card([
        dbc.CardHeader([
            html.Strong(titulo, style={"color": COR_PRIMARIA}),
            html.Span(subtitulo, className="text-muted ms-2", style={"fontSize": "12px"}),
        ]),
        dbc.CardBody(corpo or html.Div(vazio, className="text-muted")),
    ], className="shadow-sm mb-4")


def _badge_status(status):
    mapa = {
        "ativo":               ("Ativo",              "success"),
        "inadimplente":        ("Inadimplente",       "danger"),
        "aguardando_pagamento":("Aguard. Pagamento",  "warning"),
        "cancelado":           ("Cancelado",          "secondary"),
        "encerrado":           ("Encerrado",          "dark"),
        "pendente":            ("Pendente",           "warning"),
        "pago":                ("Pago",               "success"),
        "vencido":             ("Vencido",            "danger"),
    }
    label, cor = mapa.get(status, (status, "secondary"))
    return dbc.Badge(label, color=cor, className="me-1")


def _fmt_brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def _fmt_data(valor):
    if not valor:
        return "—"
    texto = str(valor).strip()
    if len(texto) >= 10:
        texto = texto[:10]
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return valor


def _id_mais_recente(ids, timestamps):
    pares = [
        (ts or -1, item_id)
        for item_id, ts in zip(ids or [], timestamps or [])
        if item_id
    ]
    if not pares:
        return None
    ts, item_id = max(pares, key=lambda p: p[0])
    return item_id if ts >= 0 else None


def _acao_mais_recente(acoes):
    validas = [(ts or -1, nome) for nome, ts in acoes]
    ts, nome = max(validas, key=lambda p: p[0])
    return nome if ts >= 0 else None


# ── Layout principal ───────────────────────────────────────────────────────

def _navbar():
    return dbc.Navbar(
        dbc.Container([
            html.Span([
                html.Img(src="/assets/logo.jpeg", height="38px",
                         style={"borderRadius": "4px", "marginRight": "10px"}),
                dbc.Badge(get_version(), color="secondary", className="ms-1", style={"fontSize": "10px"}),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div(id="navbar-usuario", style={"color": "#ccc", "fontSize": "12px"}),
        ], fluid=True),
        color=COR_PRIMARIA, dark=True, className="mb-0 py-2",
    )


def _sidebar(pathname):
    links = []
    tab_ativa = _path_para_tab(pathname)
    for icone, tab, label, href in TAB_ITENS:
        ativo = tab == tab_ativa
        links.append(
            dcc.Link(
                html.Div(
                    [html.I(className=f"bi {icone} me-2"), label],
                    style={
                        "padding": "10px 16px", "borderRadius": "8px",
                        "cursor": "pointer",
                        "color": "#fff" if ativo else "#ccc",
                        "background": "rgba(255,255,255,0.12)" if ativo else "transparent",
                        "fontSize": "13px", "fontWeight": "500",
                        "marginBottom": "2px",
                        "transition": "all 0.15s",
                    },
                    className="sidebar-link",
                ),
                href=href,
                refresh=False,
                style={"textDecoration": "none"},
            )
        )
    return html.Div([
        html.Div(
            html.Img(src="/assets/logo.jpeg",
                     style={"width": "160px", "borderRadius": "6px", "margin": "12px auto", "display": "block"}),
        ),
        html.Hr(style={"borderColor": "#333", "margin": "0 8px 8px"}),
        html.Div("MENU", style={"fontSize": "10px", "color": "#666", "fontWeight": "700",
                                "letterSpacing": "1px", "padding": "8px 16px 8px"}),
        *links,
        html.Hr(style={"borderColor": "#333", "margin": "12px 8px"}),
        html.Div(
            [html.I(className="bi bi-box-arrow-right me-2"), "Sair"],
            id="btn-logout",
            n_clicks=0,
            style={"padding": "10px 16px", "cursor": "pointer", "color": "#e63946",
                   "fontSize": "13px", "fontWeight": "500"},
        ),
    ], style={
        "width": "200px", "minHeight": "100vh", "background": "#1a2840",
        "position": "fixed", "top": "52px", "left": 0, "zIndex": 100,
        "overflowY": "auto",
    })


app.layout = html.Div([
    dcc.Store(id="store-sessao",    storage_type="session"),
    dcc.Store(id="store-tab-ativa", data="dashboard"),
    dcc.Store(id="store-login-erro", data=""),
    dcc.Location(id="url"),
    dcc.Interval(id="interval-vencimentos", interval=15 * 60 * 1000, n_intervals=0),  # 15min

    html.Div(id="conteudo-raiz"),
], style={"fontFamily": "'Inter', 'Segoe UI', sans-serif", "background": COR_FUNDO, "minHeight": "100vh"})


# ── Roteamento principal ───────────────────────────────────────────────────

@app.callback(
    Output("conteudo-raiz", "children"),
    Input("store-sessao", "data"),
    Input("url", "pathname"),
    Input("url", "search"),
)
def rotear(sessao, pathname, search):
    if not sessao or not sessao.get("usuario_id"):
        return _layout_login()
    return _layout_app(sessao, pathname, search)


def _layout_login():
    return html.Div([
        html.Div([
            html.Div([
                html.Img(src="/assets/logo.jpeg",
                         style={"maxWidth": "280px", "width": "100%",
                                "borderRadius": "8px", "marginBottom": "24px"}),
            ], className="text-center"),

            dbc.Input(id="login-usuario", placeholder="Usuário", type="text",
                      className="mb-3", size="lg"),
            dbc.Input(id="login-senha",   placeholder="Senha",   type="password",
                      className="mb-3", size="lg"),
            dbc.Button("Entrar", id="btn-login", color="danger", className="w-100 fw-bold",
                       size="lg", style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
            html.Div(id="login-erro", className="mt-3 text-center text-danger", style={"fontSize": "13px"}),
        ], style={
            "maxWidth": "380px", "margin": "80px auto", "background": "white",
            "borderRadius": "16px", "padding": "40px",
            "boxShadow": "0 4px 24px rgba(0,0,0,0.10)",
        }),
    ], style={"background": COR_PRIMARIA, "minHeight": "100vh"})


def _layout_app(sessao, pathname, search):
    tab_ativa = _path_para_tab(pathname)
    return html.Div([
        _navbar(),
        _sidebar(pathname),
        html.Div([
            html.Div(id="conteudo-aba", children=_renderizar_aba(tab_ativa, sessao, pathname, search), style={"padding": "24px"}),
        ], style={"marginLeft": "200px", "marginTop": "52px", "minHeight": "calc(100vh - 52px)"}),
    ])


# ── Login / Logout ─────────────────────────────────────────────────────────
# Separados em dois callbacks porque btn-logout só existe após login
# e btn-login/login-erro só existem na tela de login.

@app.callback(
    Output("store-sessao",  "data",     allow_duplicate=True),
    Output("store-login-erro", "data"),
    Input("btn-login",      "n_clicks"),
    State("login-usuario",  "value"),
    State("login-senha",    "value"),
    prevent_initial_call=True,
)
def fazer_login(n, usuario, senha):
    if not n:
        raise PreventUpdate
    if not usuario or not senha:
        return no_update, "Preencha usuário e senha."
    usr = auth_mod.autenticar(usuario, senha)
    if not usr:
        return no_update, "Usuário ou senha incorretos."
    return {"usuario_id": usr["id"], "nome": usr["nome"], "nivel": usr["nivel"]}, ""


@app.callback(
    Output("login-erro", "children"),
    Input("store-login-erro", "data"),
)
def exibir_erro_login(msg):
    return msg or ""


@app.callback(
    Output("store-sessao", "data", allow_duplicate=True),
    Input("btn-logout",    "n_clicks"),
    prevent_initial_call=True,
)
def fazer_logout(n):
    if not n:
        raise PreventUpdate
    return None


@app.callback(
    Output("navbar-usuario", "children"),
    Input("store-sessao", "data"),
)
def atualizar_navbar(sessao):
    if not sessao:
        return ""
    return [
        html.I(className="bi bi-person-circle me-1"),
        f"{sessao.get('nome','')} ",
        dbc.Badge(sessao.get("nivel", ""), color="secondary", style={"fontSize": "9px"}),
    ]


# ── Navegação entre abas ───────────────────────────────────────────────────

@app.callback(
    Output("store-tab-ativa", "data"),
    Input("url", "pathname"),
)
def trocar_aba(pathname):
    return _path_para_tab(pathname)


def _renderizar_aba(tab, sessao, pathname=None, search=None):
    if not sessao:
        raise PreventUpdate
    if tab == "dashboard":
        return _aba_dashboard()
    if tab == "alunos":
        m_perfil = re.fullmatch(r"/alunos/(\d+)$", pathname or "")
        if m_perfil:
            return _aba_perfil_aluno(int(m_perfil.group(1)))
        return _aba_alunos(pathname, search)
    if tab == "pagamentos":
        return _aba_pagamentos()
    if tab == "precadastros":
        return _aba_precadastros()
    if tab == "planos":
        return _aba_planos()
    if tab == "usuarios":
        return _aba_usuarios(sessao)
    return html.P("Aba não encontrada.")


@app.callback(
    Output("conteudo-aba", "children"),
    Input("store-tab-ativa", "data"),
    Input("store-sessao",    "data"),
    Input("url",             "pathname"),
    Input("url",             "search"),
)
def renderizar_aba(tab, sessao, pathname, search):
    return _renderizar_aba(tab, sessao, pathname, search)


# ── Verificar vencimentos periodicamente ──────────────────────────────────

@app.callback(
    Output("interval-vencimentos", "disabled"),
    Input("interval-vencimentos", "n_intervals"),
    State("store-sessao", "data"),
    prevent_initial_call=False,
)
def tick_vencimentos(n, sessao):
    if sessao:
        renov_mod.verificar_vencimentos()
    return False


@app.callback(
    Output("store-dashboard-card", "data"),
    Input("card-ativos", "n_clicks"),
    Input("card-inadimplentes", "n_clicks"),
    Input("card-receita_mes", "n_clicks"),
    Input("card-a_receber_mes", "n_clicks"),
    Input("card-precadastros", "n_clicks"),
    prevent_initial_call=True,
)
def selecionar_card_dashboard(n_ativos, n_inad, n_receita, n_receber, n_precad):
    tid = callback_context.triggered_id
    mapa = {
        "card-ativos": "ativos",
        "card-inadimplentes": "inadimplentes",
        "card-receita_mes": "receita_mes",
        "card-a_receber_mes": "a_receber_mes",
        "card-precadastros": "precadastros",
    }
    if tid in mapa:
        return mapa[tid]
    raise PreventUpdate


@app.callback(
    Output("dashboard-detalhes", "children"),
    Input("store-dashboard-card", "data"),
    Input("dash-inadimplentes-busca", "value"),
    Input("dash-inadimplentes-ordenacao", "value"),
)
def atualizar_detalhes_dashboard(card_id, busca_inadimplente, ordenacao_inadimplente):
    return _detalhes_dashboard(card_id or "inadimplentes", 7, busca_inadimplente or "", ordenacao_inadimplente or "vencimento")


@app.callback(
    Output("dash-inadimplentes-busca-wrap", "style"),
    Input("store-dashboard-card", "data"),
)
def toggle_busca_inadimplente(card_id):
    return {"display": "block"} if (card_id or "inadimplentes") == "inadimplentes" else {"display": "none"}


# ══════════════════════════════════════════════════════════════════════════
# ABA: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════

def _aba_dashboard():
    k    = alunos_mod.kpis()
    hoje = date.today()
    from datetime import timedelta

    # ── KPI cards ────────────────────────────────────────────────────────
    cards = dbc.Row([
        _kpi_card("ativos",         "Alunos Ativos",     k["ativos"],                   "cadastros ativos",     "bi-people-fill",        "#0d6efd"),
        _kpi_card("inadimplentes",  "Inadimplentes",     k["inadimplentes"],            "pagamento em atraso",   "bi-exclamation-circle", "#dc3545"),
        _kpi_card("receita_mes",    "Receita do Mês",    _fmt_brl(k["receita_mes"]),    "pagamentos recebidos",  "bi-cash-coin",          "#198754"),
        _kpi_card("a_receber_mes",  "A Receber",         _fmt_brl(k["a_receber_mes"]),  "vencimentos do mês",    "bi-wallet2",            "#6f42c1"),
        _kpi_card("precadastros",   "Pré-cadastros",     k["precadastros_pendentes"],   "aguardando aprovação",  "bi-person-plus",        "#20c997"),
    ], className="g-3 mb-4")

    # ── Linha 2: Novos cadastros | Cancelamentos | Modalidades ───────────
    def _mini_card(titulo, valor, subtitulo, icone, cor):
        return dbc.Card(dbc.CardBody([
            html.Div([
                html.I(className=f"bi {icone} me-2", style={"color": cor, "fontSize": "22px"}),
                html.Span(titulo, style={"fontSize": "12px", "color": "#888", "fontWeight": "600"}),
            ], className="d-flex align-items-center mb-1"),
            html.Div(str(valor), style={"fontSize": "28px", "fontWeight": "800", "color": cor}),
            html.Div(subtitulo, style={"fontSize": "11px", "color": "#aaa"}),
        ]), style={"borderLeft": f"4px solid {cor}", "borderRadius": "10px"})

    linha2 = dbc.Row([
        dbc.Col(_mini_card("Novos este mês",       k["novos_mes"],
                           "novos cadastros",      "bi-person-check", "#0d6efd"), md=3),
        dbc.Col(_mini_card("Cancelamentos",         k["cancelamentos_mes"],
                           "inativados este mês",  "bi-person-x",     "#dc3545"), md=3),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.Div([
                html.I(className="bi bi-bar-chart-fill me-2",
                       style={"color": COR_PRIMARIA, "fontSize": "22px"}),
                html.Span("Alunos por Modalidade",
                          style={"fontSize": "12px", "color": "#888", "fontWeight": "600"}),
            ], className="d-flex align-items-center mb-2"),
            *([
                html.Div([
                    html.Div([
                        html.Span(m["modalidade"], style={"fontSize": "12px"}),
                        html.Span(str(m["total"]),
                                  style={"fontWeight": "700", "color": COR_PRIMARIA,
                                         "fontSize": "13px", "float": "right"}),
                    ], style={"display": "flex", "justifyContent": "space-between",
                              "marginBottom": "4px"}),
                    dbc.Progress(
                        value=round(m["total"] / max(k["ativos"], 1) * 100),
                        color="danger", style={"height": "6px", "marginBottom": "6px"},
                    ),
                ]) for m in k["por_modalidade"]
            ] if k["por_modalidade"] else [html.P("Sem dados", className="text-muted")])
        ]), style={"borderRadius": "10px"}), md=6),
    ], className="g-3 mb-4")

    # ── Novos cadastros últimos 30 dias ───────────────────────────────────
    novos30 = k["novos_30d"]
    if novos30:
        barras = html.Div([
            html.Div([
                html.Div(style={
                    "width": f"{round(n['total'] / max(x['total'] for x in novos30) * 100)}%",
                    "height": "100%", "background": COR_ACENTO, "borderRadius": "2px",
                }),
            ], style={"height": "28px", "background": "#f0f0f0", "borderRadius": "4px",
                      "marginBottom": "4px", "overflow": "hidden"})
            for n in novos30
        ], style={"display": "grid", "gridTemplateColumns": f"repeat({len(novos30)}, 1fr)",
                  "gap": "3px", "height": "80px"})
        legenda = html.Div([
            html.Span(n["dia"], style={"fontSize": "9px", "color": "#aaa",
                                       "textAlign": "center", "display": "block"})
            for n in novos30
        ], style={"display": "grid",
                  "gridTemplateColumns": f"repeat({len(novos30)}, 1fr)", "gap": "3px"})
        grafico_novos = html.Div([barras, legenda])
    else:
        grafico_novos = html.P("Sem cadastros nos últimos 30 dias.", className="text-muted")

    # ── Vencimentos próximos 7 dias ───────────────────────────────────────
    pags_semana = alunos_mod.listar_pagamentos(status="pendente")
    pags_semana = [p for p in pags_semana
                   if p["data_vencimento"] and
                   date.fromisoformat(p["data_vencimento"]) <= hoje + timedelta(days=7)][:10]

    tabela_venc = dbc.Table([
        html.Thead(html.Tr([html.Th("Aluno"), html.Th("Plano"), html.Th("Vencimento"),
                             html.Th("Valor"), html.Th("Status")])),
        html.Tbody([html.Tr([
            html.Td(p["aluno_nome"]),
            html.Td(p["plano"]),
            html.Td(_fmt_data(p["data_vencimento"])),
            html.Td(_fmt_brl(p["valor"])),
            html.Td(_badge_status(p["status"])),
        ]) for p in pags_semana]) if pags_semana
        else html.Tbody(html.Tr(html.Td(
            "Nenhum vencimento próximo.", colSpan=5,
            className="text-center text-muted py-3")))
    ], bordered=True, hover=True, size="sm", responsive=True)

    # ── Recebidos nos últimos 30 dias ─────────────────────────────────────
    conn_dash = get_conn()
    recebidos_30d = conn_dash.execute("""
        SELECT p.data_pagamento, a.nome AS aluno_nome,
               tp.nome AS plano, mod.nome AS modalidade,
               p.valor, p.forma
        FROM pagamentos p
        JOIN alunos a       ON a.id  = p.aluno_id
        JOIN matriculas m   ON m.id  = p.matricula_id
        JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
        JOIN modalidades mod ON mod.id = m.modalidade_id
        WHERE p.status = 'pago'
          AND date(p.data_pagamento) >= date('now', '-29 days')
        ORDER BY date(p.data_pagamento) DESC, p.id DESC
    """).fetchall()
    total_30d = conn_dash.execute("""
        SELECT COALESCE(SUM(valor), 0) FROM pagamentos
        WHERE status = 'pago' AND date(data_pagamento) >= date('now', '-29 days')
    """).fetchone()[0]
    conn_dash.close()

    if recebidos_30d:
        rows_rec = [html.Tr([
            html.Td(_fmt_data(r["data_pagamento"]), style={"whiteSpace": "nowrap"}),
            html.Td(r["aluno_nome"]),
            html.Td(f"{r['plano']} / {r['modalidade']}", style={"fontSize": "12px", "color": "#555"}),
            html.Td(_fmt_brl(r["valor"]), style={"fontWeight": "600", "textAlign": "right"}),
            html.Td(r["forma"] or "—", style={"fontSize": "12px"}),
        ]) for r in recebidos_30d]
        tabela_recebidos = dbc.Table(
            [html.Thead(html.Tr([
                html.Th("Data"), html.Th("Aluno"), html.Th("Plano"),
                html.Th("Valor", style={"textAlign": "right"}), html.Th("Forma"),
            ])),
             html.Tbody(rows_rec)],
            bordered=True, hover=True, size="sm", responsive=True, className="mb-0"
        )
    else:
        tabela_recebidos = html.P("Nenhum recebimento nos últimos 30 dias.", className="text-muted")

    card_recebidos = dbc.Card([
        dbc.CardHeader([
            html.Strong("Recebimentos — últimos 30 dias", style={"color": COR_PRIMARIA}),
            html.Span(
                f"  Total: {_fmt_brl(total_30d)}",
                style={"fontWeight": "700", "color": "#198754", "fontSize": "14px", "float": "right"},
            ),
        ]),
        dbc.CardBody(tabela_recebidos, style={"maxHeight": "320px", "overflowY": "auto", "padding": "0.5rem"}),
    ], className="shadow-sm")

    return html.Div([
        dcc.Store(id="store-pag-id"),
        dcc.Download(id="download-recibo"),
        html.H5([html.I(className="bi bi-speedometer2 me-2"), "Dashboard"],
                className="fw-bold mb-3", style={"color": COR_PRIMARIA}),
        cards,
        linha2,
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader(html.Strong("Novos cadastros — últimos 30 dias")),
                dbc.CardBody(grafico_novos),
            ], className="shadow-sm h-100"), md=4),
            dbc.Col(dbc.Card([
                dbc.CardHeader(html.Strong("Vencimentos nos próximos 7 dias")),
                dbc.CardBody(tabela_venc),
            ], className="shadow-sm h-100"), md=8),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(card_recebidos, md=12),
        ], className="g-3"),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="bi bi-cash-coin me-2", style={"color": COR_ACENTO}),
                "Registrar Pagamento",
            ])),
            dbc.ModalBody([
                html.Div(id="modal-pag-info", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Forma de pagamento *"),
                        dbc.Select(id="inp-pag-forma",
                                   options=[{"label": "PIX", "value": "pix"},
                                            {"label": "Dinheiro", "value": "dinheiro"},
                                            {"label": "Cartão", "value": "cartao"},
                                            {"label": "Transferência", "value": "transferencia"}]),
                    ], md=6),
                    dbc.Col([
                        dbc.Label("Data do pagamento"),
                        dbc.Input(id="inp-pag-data", type="date", value=hoje.isoformat()),
                    ], md=6),
                ], className="mb-2"),
                dbc.Label("Observações"),
                dbc.Textarea(id="inp-pag-obs", rows=2),
                html.Div(id="modal-pag-erro", className="text-danger mt-2", style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-modal-pag-cancel", color="secondary", outline=True),
                dbc.Button([html.I(className="bi bi-check-lg me-1"), "Confirmar"], id="btn-modal-pag-confirmar", color="success"),
            ]),
        ], id="modal-pag", is_open=False),
    ])


# ══════════════════════════════════════════════════════════════════════════
# ABA: ALUNOS
# ══════════════════════════════════════════════════════════════════════════

def _aba_alunos(pathname=None, search=None):
    estado_modal = _estado_modal_aluno(pathname)
    estado_ver = _estado_modal_ver(pathname)
    busca_atual, status_atual = _params_alunos(search)
    return html.Div([
        dcc.Download(id="download-alunos-xlsx"),
        dcc.Download(id="download-modelo-xlsx"),
        html.Div([
            html.H5([html.I(className="bi bi-people-fill me-2"), "Alunos"],
                    className="fw-bold mb-0", style={"color": COR_PRIMARIA}),
            html.Div([
                dcc.Upload(
                    dbc.Button([html.I(className="bi bi-upload me-1"), "Importar Excel"],
                               color="secondary", size="sm", outline=True),
                    id="upload-alunos", accept=".xlsx,.xls", multiple=False,
                ),
                dbc.Button([html.I(className="bi bi-download me-1"), "Exportar Excel"],
                           id="btn-export-alunos", color="secondary", size="sm",
                           outline=True, className="ms-1"),
                dbc.Button([html.I(className="bi bi-file-earmark-arrow-down me-1"), "Modelo"],
                           id="btn-modelo-alunos", color="secondary", size="sm",
                           outline=True, className="ms-1"),
                dcc.Link(
                    dbc.Button([html.I(className="bi bi-plus-lg me-1"), "Novo Aluno"],
                               color="danger", size="sm", className="ms-2",
                               style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
                    href=_url_alunos("/alunos/novo", busca_atual, status_atual),
                    refresh=False,
                ),
            ], className="d-flex align-items-center"),
        ], className="d-flex justify-content-between align-items-center mb-3"),
        html.Div(id="alerta-importacao"),

        dbc.Row([
            dbc.Col(dbc.Input(id="busca-aluno", placeholder="Buscar por nome, CPF ou telefone...",
                              debounce=True, value=busca_atual), md=5),
            dbc.Col(dbc.Select(id="filtro-status-aluno",
                               options=[{"label": "Todos", "value": ""},
                                        {"label": "Ativos", "value": "ativo"},
                                         {"label": "Inativos", "value": "inativo"}],
                               value=status_atual), md=3),
        ], className="mb-3"),

        html.Div(id="tabela-alunos"),

        # Modal cadastro/edição de aluno
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-aluno-titulo", children=estado_modal["titulo"])),
            dbc.ModalBody([
                dcc.Store(id="store-aluno-id", data=estado_modal["aluno_id"]),
                dbc.Row([
                    dbc.Col([dbc.Label("Nome *"), dbc.Input(id="inp-aluno-nome", value=estado_modal["nome"])], md=8),
                    dbc.Col([dbc.Label("CPF"),    dbc.Input(id="inp-aluno-cpf", placeholder="000.000.000-00", value=estado_modal["cpf"])], md=4),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Nascimento"), dbc.Input(id="inp-aluno-nasc", type="date", value=estado_modal["nasc"])], md=4),
                    dbc.Col([dbc.Label("Telefone"),   dbc.Input(id="inp-aluno-tel",  placeholder="(00) 00000-0000", value=estado_modal["tel"])], md=4),
                    dbc.Col([dbc.Label("E-mail"),     dbc.Input(id="inp-aluno-email",type="email", value=estado_modal["email"])], md=4),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("CEP"), dbc.Input(id="inp-aluno-cep", placeholder="00000-000", maxLength=9, value=estado_modal["cep"])], md=3),
                    dbc.Col([dbc.Label("Logradouro"), dbc.Input(id="inp-aluno-logradouro", placeholder="Rua / Av. / etc.", value=estado_modal["logradouro"])], md=7),
                    dbc.Col([dbc.Label("Número"), dbc.Input(id="inp-aluno-numero", value=estado_modal["numero"])], md=2),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Bairro"), dbc.Input(id="inp-aluno-bairro", value=estado_modal["bairro"])], md=4),
                    dbc.Col([dbc.Label("Cidade"), dbc.Input(id="inp-aluno-cidade", value=estado_modal["cidade"])], md=5),
                    dbc.Col([dbc.Label("UF"), dbc.Input(id="inp-aluno-uf", maxLength=2, value=estado_modal["uf"])], md=3),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Observações"), dbc.Textarea(id="inp-aluno-obs", rows=2, value=estado_modal["obs"])], md=12),
                ], className="mb-3"),
                html.Hr(),
                html.Div([
                    html.Span("Matrícula", className="fw-bold me-2"),
                    html.Small("(obrigatório para novos alunos)", className="text-danger"),
                ], className="mb-2"),
                dbc.Row([
                    dbc.Col([dbc.Label("Plano *"),
                             dbc.Select(id="inp-mat-plano",
                                         options=[{"label": p["nome"], "value": p["id"]}
                                                  for p in alunos_mod.listar_planos()], value=estado_modal["plano"])], md=4),
                    dbc.Col([dbc.Label("Modalidade *"),
                             dbc.Select(id="inp-mat-modal",
                                         options=[{"label": m["nome"], "value": m["id"]}
                                                  for m in alunos_mod.listar_modalidades()], value=estado_modal["modal"])], md=4),
                    dbc.Col([dbc.Label("Início"),
                             dbc.Input(id="inp-mat-inicio", type="date",
                                       value=estado_modal["inicio"])], md=4),
                ], className="mb-2"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Vencimento final da matrícula atual"),
                        dbc.Input(id="inp-mat-datafim", type="date",
                                  value=estado_modal["datafim"],
                                  placeholder="Deixe vazio para calcular automaticamente"),
                    ], md=6),
                ], className="mb-2"),
                html.Small(
                    "Ao salvar, o sistema atualiza a matrícula atual do aluno em vez de criar uma nova.",
                    className="text-muted d-block mb-2",
                ),
                dbc.Checkbox(id="inp-mat-renovacao", label="Renovação automática", value=estado_modal["renovacao"], className="mb-2"),
                html.Div(id="modal-aluno-erro", children=estado_modal["erro"], className="text-danger mt-2", style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-modal-aluno-cancel", color="secondary", outline=True),
                html.Div(id="btn-inativar-wrapper", children=estado_modal["btn_inativar"]),   # botão inativar aparece só na edição
                dbc.Button("Salvar",   id="btn-modal-aluno-salvar", color="danger",
                           style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
            ]),
        ], id="modal-aluno", size="xl", scrollable=True, is_open=estado_modal["is_open"]),

        # Modal detalhes do aluno (olhinho)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-ver-titulo", children=estado_ver["titulo"])),
            dbc.ModalBody(id="modal-ver-corpo", children=estado_ver["corpo"]),
            dbc.ModalFooter(
                dbc.Button("Fechar", id="btn-modal-ver-fechar", color="secondary", outline=True)
            ),
        ], id="modal-ver-aluno", size="xl", scrollable=True, is_open=estado_ver["is_open"]),

        # Store + Download para recibo
        dcc.Store(id="store-novo-pagamento"),
        dcc.Download(id="download-recibo"),

        # Modal recebimento imediato
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="bi bi-cash-coin me-2", style={"color": COR_ACENTO}),
                "Confirmar Pagamento",
            ])),
            dbc.ModalBody([
                dbc.Alert(
                    "Matrícula criada! Deseja registrar o pagamento agora?",
                    color="info", className="mb-3",
                ),
                html.Div(id="receb-info", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Forma de pagamento *"),
                        dbc.Select(id="receb-forma",
                                   options=[
                                       {"label": "PIX",         "value": "pix"},
                                       {"label": "Cartão",      "value": "cartao"},
                                       {"label": "Dinheiro",    "value": "dinheiro"},
                                       {"label": "Transferência","value": "transferencia"},
                                   ]),
                    ], md=6),
                    dbc.Col([
                        dbc.Label("Data do pagamento"),
                        dbc.Input(id="receb-data", type="date",
                                  value=date.today().isoformat()),
                    ], md=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("E-mail para envio do recibo"),
                        dbc.Input(id="receb-email", type="email",
                                  placeholder="deixe em branco para não enviar"),
                    ], md=12),
                ], className="mb-2"),
                dbc.Input(id="receb-obs", placeholder="Observações (opcional)", className="mb-2"),
                html.Div(id="receb-erro", className="text-danger", style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Agora não", id="btn-receb-fechar",
                           color="secondary", outline=True, className="me-auto"),
                dbc.Button([html.I(className="bi bi-receipt me-1"), "Receber e Gerar Recibo"],
                           id="btn-receb-confirmar", color="danger",
                           style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
            ]),
        ], id="modal-recebimento", size="lg", is_open=False),

        # Modal confirmação de inativação
        dcc.Store(id="store-inativar-id"),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="bi bi-person-x me-2", style={"color": "#dc3545"}),
                "Inativar Aluno",
            ])),
            dbc.ModalBody([
                html.Div(id="inativar-info", className="mb-3"),
                dbc.Alert([
                    html.I(className="bi bi-exclamation-triangle me-2"),
                    "Esta ação encerrará todas as matrículas ativas do aluno.",
                ], color="warning", className="mb-3"),
                dbc.Checkbox(
                    id="inativar-cancelar-pendencias",
                    label="Cancelar também as mensalidades em aberto (somem do Contas a Receber)",
                    value=True,
                ),
            ]),
            dbc.ModalFooter([
                dbc.Button("Voltar", id="btn-inativar-cancel",
                           color="secondary", outline=True),
                dbc.Button([html.I(className="bi bi-person-x me-1"), "Confirmar Inativação"],
                           id="btn-inativar-confirmar", color="danger"),
            ]),
        ], id="modal-inativar", is_open=False),
    ])


@app.callback(
    Output("tabela-alunos", "children"),
    Input("busca-aluno",         "value"),
    Input("filtro-status-aluno", "value"),
    Input("store-tab-ativa",     "data"),
)
def atualizar_tabela_alunos(busca, status, tab):
    if tab != "alunos":
        raise PreventUpdate
    lista = alunos_mod.listar_alunos(status=status or None, busca=busca)
    if not lista:
        return dbc.Alert("Nenhum aluno encontrado.", color="light")

    rows = []
    for a in lista:
        plano_txt = a.get("plano_ativo") or "—"
        url_perfil = f"/alunos/{a['id']}"
        url_editar = _url_alunos(f"/alunos/{a['id']}/editar", busca or "", status or "")
        rows.append(html.Tr([
            html.Td(f"#{a['id']:04d}", style={"fontWeight": "600", "color": COR_ACENTO, "whiteSpace": "nowrap"}),
            html.Td(a["nome"]),
            html.Td(a["telefone"] or "—"),
            html.Td(html.Small(plano_txt, style={"color": "#555"})),
            html.Td(_badge_status(a["status"])),
            html.Td([
                dcc.Link(
                    dbc.Button(html.I(className="bi bi-person-lines-fill"),
                               color="primary", size="sm", outline=True,
                               className="me-1", title="Ver perfil"),
                    href=url_perfil, refresh=False,
                ),
                dcc.Link(
                    dbc.Button(html.I(className="bi bi-pencil"),
                               color="warning", size="sm", outline=True,
                               title="Editar"),
                    href=url_editar, refresh=False,
                ),
            ]),
        ]))

    return dbc.Table(
        [html.Thead(html.Tr([html.Th("Nº"), html.Th("Nome"), html.Th("Telefone"),
                              html.Th("Plano / Modalidade"), html.Th("Status"), html.Th("")])),
         html.Tbody(rows)],
        bordered=True, hover=True, size="sm", responsive=True
    )


@app.callback(
    Output("modal-aluno",          "is_open"),
    Output("modal-aluno-titulo",   "children"),
    Output("store-aluno-id",       "data"),
    Output("inp-aluno-nome",       "value"),
    Output("inp-aluno-cpf",        "value"),
    Output("inp-aluno-nasc",       "value"),
    Output("inp-aluno-tel",        "value"),
    Output("inp-aluno-email",      "value"),
    Output("inp-aluno-cep",        "value"),
    Output("inp-aluno-logradouro", "value"),
    Output("inp-aluno-numero",     "value"),
    Output("inp-aluno-bairro",     "value"),
    Output("inp-aluno-cidade",     "value"),
    Output("inp-aluno-uf",         "value"),
    Output("inp-aluno-obs",        "value"),
    Output("inp-mat-plano",        "value"),
    Output("inp-mat-modal",        "value"),
    Output("inp-mat-inicio",       "value"),
    Output("inp-mat-datafim",      "value"),
    Output("modal-aluno-erro",     "children"),
    Output("store-novo-pagamento", "data"),
    Output("btn-inativar-wrapper", "children"),
    Output("url",                  "pathname", allow_duplicate=True),
    Output("url",                  "search", allow_duplicate=True),
    Input("btn-modal-aluno-cancel",      "n_clicks"),
    Input("btn-modal-aluno-salvar",      "n_clicks"),
    State("url",                  "pathname"),
    State("url",                  "search"),
    State("store-aluno-id",       "data"),
    State("inp-aluno-nome",       "value"),
    State("inp-aluno-cpf",        "value"),
    State("inp-aluno-nasc",       "value"),
    State("inp-aluno-tel",        "value"),
    State("inp-aluno-email",      "value"),
    State("inp-aluno-cep",        "value"),
    State("inp-aluno-logradouro", "value"),
    State("inp-aluno-numero",     "value"),
    State("inp-aluno-bairro",     "value"),
    State("inp-aluno-cidade",     "value"),
    State("inp-aluno-uf",         "value"),
    State("inp-aluno-obs",        "value"),
    State("inp-mat-plano",        "value"),
    State("inp-mat-modal",        "value"),
    State("inp-mat-inicio",       "value"),
    State("inp-mat-datafim",      "value"),
    State("inp-mat-renovacao",    "value"),
    prevent_initial_call=True,
)
def controlar_modal_aluno(n_cancel, n_salvar, pathname, search,
                           aluno_id, nome, cpf, nasc, tel, email,
                           cep, logradouro, numero, bairro, cidade, uf, obs,
                           plano_id, modal_id, inicio, datafim, renovacao):
    tid = callback_context.triggered_id
    hoje = date.today().isoformat()
    _vazio = ("", "", "", "", "", "", "", "", "", "", "", "", None, None, hoje, None, "", None, None)

    def _retorno_erro(msg):
        retorno = [no_update] * 24
        retorno[19] = msg
        return tuple(retorno)

    if tid == "btn-modal-aluno-cancel":
        if not n_cancel:
            raise PreventUpdate
        return (False, no_update, no_update) + _vazio + ("/alunos", search or "")

    if tid == "btn-modal-aluno-salvar":
        if not n_salvar:
            raise PreventUpdate
        if not nome:
            raise PreventUpdate
        if not aluno_id and (not plano_id or not modal_id):
            return _retorno_erro("Selecione o plano e a modalidade para continuar.")
        dados = {
            "nome": nome, "cpf": cpf or "", "data_nascimento": nasc or "",
            "telefone": tel or "", "email": email or "",
            "cep": cep or "", "logradouro": logradouro or "",
            "numero": numero or "", "bairro": bairro or "",
            "cidade": cidade or "", "uf": uf or "",
            "endereco": logradouro or "",
            "observacoes": obs or "", "origem": "admin",
        }

        from app.database import get_conn as _get_conn
        pag_id = None

        if aluno_id:
            alunos_mod.atualizar_aluno(aluno_id, dados)
            if plano_id and modal_id:
                mat_atual = alunos_mod.buscar_matricula_corrente(aluno_id)
                if mat_atual:
                    df = datafim or mat_atual["data_fim"]
                    alunos_mod.alterar_matricula_ativa(
                        aluno_id, int(plano_id), int(modal_id), df,
                        data_inicio=inicio or mat_atual["data_inicio"],
                        renovacao_auto=bool(renovacao),
                    )
                else:
                    alunos_mod.criar_matricula(aluno_id, int(plano_id), int(modal_id),
                                               data_inicio=inicio, renovacao_auto=bool(renovacao))
                    conn = _get_conn()
                    row = conn.execute(
                        "SELECT id FROM pagamentos WHERE aluno_id=? AND status='pendente' ORDER BY id DESC LIMIT 1",
                        (aluno_id,)).fetchone()
                    conn.close()
                    pag_id = row["id"] if row else None
        else:
            novo_id = alunos_mod.criar_aluno(dados)
            alunos_mod.criar_matricula(novo_id, int(plano_id), int(modal_id),
                                       data_inicio=inicio, renovacao_auto=bool(renovacao))
            conn = _get_conn()
            row = conn.execute(
                "SELECT id FROM pagamentos WHERE aluno_id=? AND status='pendente' ORDER BY id DESC LIMIT 1",
                (novo_id,)).fetchone()
            conn.close()
            pag_id = row["id"] if row else None

        return (False, no_update, no_update) + _vazio[:17] + (pag_id, None, "/alunos", search or "")

    raise PreventUpdate


@app.callback(
    Output("inp-aluno-logradouro", "value", allow_duplicate=True),
    Output("inp-aluno-bairro",     "value", allow_duplicate=True),
    Output("inp-aluno-cidade",     "value", allow_duplicate=True),
    Output("inp-aluno-uf",         "value", allow_duplicate=True),
    Input("inp-aluno-cep",  "n_blur"),
    State("inp-aluno-cep",  "value"),
    prevent_initial_call=True,
)
def buscar_cep(_, cep_raw):
    import re, urllib.request, json as _json
    if not cep_raw:
        raise PreventUpdate
    digits = re.sub(r"\D", "", cep_raw or "")
    if len(digits) != 8:
        raise PreventUpdate
    try:
        with urllib.request.urlopen(
            f"https://viacep.com.br/ws/{digits}/json/", timeout=4
        ) as resp:
            data = _json.loads(resp.read())
        if data.get("erro"):
            raise PreventUpdate
        return (data.get("logradouro", ""), data.get("bairro", ""),
                data.get("localidade", ""), data.get("uf", ""))
    except Exception:
        raise PreventUpdate


@app.callback(
    Output("inp-aluno-cpf", "value", allow_duplicate=True),
    Input("inp-aluno-cpf",  "n_blur"),
    State("inp-aluno-cpf",  "value"),
    prevent_initial_call=True,
)
def formatar_cpf(_, cpf_raw):
    import re
    if not cpf_raw:
        raise PreventUpdate
    digits = re.sub(r"\D", "", cpf_raw)
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return cpf_raw


@app.callback(
    Output("modal-ver-aluno",  "is_open"),
    Output("modal-ver-titulo", "children"),
    Output("modal-ver-corpo",  "children"),
    Output("url",              "pathname", allow_duplicate=True),
    Output("url",              "search", allow_duplicate=True),
    Input("btn-modal-ver-fechar", "n_clicks"),
    State("url",               "pathname"),
    State("url",               "search"),
    prevent_initial_call=True,
)
def ver_aluno(n_fechar, pathname, search):
    if n_fechar and n_fechar > 0:
        return False, no_update, no_update, "/alunos", search or ""
    raise PreventUpdate


# ══════════════════════════════════════════════════════════════════════════
# INATIVAÇÃO DE ALUNO
# ══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("modal-inativar",   "is_open"),
    Output("store-inativar-id","data"),
    Output("inativar-info",    "children"),
    Input("btn-abrir-inativar",   "n_clicks"),
    Input("btn-inativar-cancel",  "n_clicks"),
    Input("btn-inativar-confirmar","n_clicks"),
    State("store-aluno-id",       "data"),
    prevent_initial_call=True,
)
def abrir_modal_inativar(n_abrir, n_cancel, n_confirmar, aluno_id):
    tid = callback_context.triggered_id
    if tid in ("btn-inativar-cancel", "btn-inativar-confirmar"):
        return False, no_update, no_update
    if not n_abrir or not aluno_id:
        raise PreventUpdate
    a = alunos_mod.buscar_aluno(aluno_id)
    if not a:
        raise PreventUpdate
    info = html.Div([
        html.Span(f"#{a['id']:04d} ", style={"color": COR_ACENTO, "fontWeight": "700"}),
        html.Strong(a["nome"]),
        html.Span(f" — {a['telefone'] or ''}", className="text-muted ms-2"),
    ])
    return True, aluno_id, info


@app.callback(
    Output("modal-inativar",      "is_open", allow_duplicate=True),
    Output("modal-aluno",         "is_open", allow_duplicate=True),
    Output("tabela-alunos",       "children", allow_duplicate=True),
    Input("btn-inativar-confirmar","n_clicks"),
    State("store-inativar-id",    "data"),
    State("inativar-cancelar-pendencias","value"),
    State("filtro-status-aluno",  "value"),
    prevent_initial_call=True,
)
def confirmar_inativacao(n, aluno_id, cancelar_pendencias, status_filtro):
    if not n or not aluno_id:
        raise PreventUpdate

    from app.database import get_conn as _gc
    conn = _gc()
    conn.execute("UPDATE alunos SET status='inativo' WHERE id=?", (aluno_id,))
    conn.execute(
        "UPDATE matriculas SET status='cancelado' WHERE aluno_id=? AND status NOT IN ('encerrado','cancelado')",
        (aluno_id,)
    )
    if cancelar_pendencias:
        conn.execute(
            "UPDATE pagamentos SET status='cancelado' WHERE aluno_id=? AND status IN ('pendente','vencido')",
            (aluno_id,)
        )
    conn.commit()
    conn.close()

    # Rebuild tabela
    lista = alunos_mod.listar_alunos(status=status_filtro or None)
    rows = []
    for a in lista:
        plano_txt = a.get("plano_ativo") or "—"
        url_ver = _url_alunos(f"/alunos/{a['id']}/ver", "", status_filtro or "")
        url_editar = _url_alunos(f"/alunos/{a['id']}/editar", "", status_filtro or "")
        rows.append(html.Tr([
            html.Td(f"#{a['id']:04d}", style={"fontWeight": "600", "color": COR_ACENTO, "whiteSpace": "nowrap"}),
            html.Td(a["nome"]),
            html.Td(a["telefone"] or "—"),
            html.Td(html.Small(plano_txt, style={"color": "#555"})),
            html.Td(_badge_status(a["status"])),
            html.Td([
                dcc.Link(
                    dbc.Button(html.I(className="bi bi-eye"),
                               color="primary", size="sm", outline=True, className="me-1"),
                    href=url_ver, refresh=False,
                ),
                dcc.Link(
                    dbc.Button(html.I(className="bi bi-pencil"),
                               color="warning", size="sm", outline=True),
                    href=url_editar, refresh=False,
                ),
            ]),
        ]))
    tabela = dbc.Table(
        [html.Thead(html.Tr([html.Th("Nº"), html.Th("Nome"), html.Th("Telefone"),
                              html.Th("Plano / Modalidade"), html.Th("Status"), html.Th("")])),
         html.Tbody(rows)],
        bordered=True, hover=True, size="sm", responsive=True
    ) if lista else dbc.Alert("Nenhum aluno encontrado.", color="light")

    return False, False, tabela


# ══════════════════════════════════════════════════════════════════════════
# RECEBIMENTO IMEDIATO + RECIBO
# ══════════════════════════════════════════════════════════════════════════

@app.callback(
    Output("modal-recebimento", "is_open"),
    Output("receb-info",        "children"),
    Output("receb-email",       "value"),
    Input("store-novo-pagamento", "data"),
    Input("btn-receb-fechar",     "n_clicks"),
    Input("btn-receb-confirmar",  "n_clicks"),
    prevent_initial_call=True,
)
def abrir_modal_recebimento(pag_id, n_fechar, n_confirmar):
    tid = callback_context.triggered_id
    if tid in ("btn-receb-fechar", "btn-receb-confirmar"):
        return False, no_update, no_update
    if not pag_id:
        raise PreventUpdate
    from app.database import get_conn as _gc
    conn = _gc()
    pag = conn.execute("""
        SELECT p.*, a.nome AS aluno_nome, a.email AS aluno_email,
               tp.nome AS plano, mod.nome AS modalidade
        FROM pagamentos p
        JOIN alunos a       ON a.id  = p.aluno_id
        JOIN matriculas m   ON m.id  = p.matricula_id
        JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
        JOIN modalidades mod ON mod.id = m.modalidade_id
        WHERE p.id = ?
    """, (pag_id,)).fetchone()
    conn.close()
    if not pag:
        raise PreventUpdate
    info = dbc.Card(dbc.CardBody([
        dbc.Row([
            dbc.Col([html.Small("Aluno", className="text-muted d-block"),
                     html.Strong(pag["aluno_nome"])], md=6),
            dbc.Col([html.Small("Plano", className="text-muted d-block"),
                     html.Span(f"{pag['plano']} / {pag['modalidade']}")], md=6),
        ], className="mb-2"),
        dbc.Row([
            dbc.Col([html.Small("Valor", className="text-muted d-block"),
                     html.Strong(_fmt_brl(pag["valor"]),
                                 style={"fontSize": "20px", "color": COR_ACENTO})], md=6),
            dbc.Col([html.Small("Período", className="text-muted d-block"),
                     html.Span(pag["periodo_ref"] or "—")], md=6),
        ]),
    ]), className="mb-3 border-0 bg-light")
    return True, info, (pag["aluno_email"] or "")


@app.callback(
    Output("download-recibo",       "data"),
    Output("receb-erro",            "children"),
    Output("modal-recebimento",     "is_open", allow_duplicate=True),
    Input("btn-receb-confirmar",    "n_clicks"),
    State("store-novo-pagamento",   "data"),
    State("receb-forma",            "value"),
    State("receb-data",             "value"),
    State("receb-email",            "value"),
    State("receb-obs",              "value"),
    prevent_initial_call=True,
)
def confirmar_recebimento(n, pag_id, forma, dt_pag, email, obs):
    if not n or not pag_id:
        raise PreventUpdate
    if not forma:
        return no_update, "Selecione a forma de pagamento.", no_update

    from app.renovacao import baixar_pagamento
    from app.database import get_conn as _gc
    from app.recibo import gerar_recibo_html
    import smtplib, email as email_lib

    baixar_pagamento(pag_id, forma, dt_pag or date.today().isoformat(), obs or "")

    conn = _gc()
    pag = conn.execute("""
        SELECT p.*, a.nome AS aluno_nome, a.email AS aluno_email,
               a.cpf, a.telefone, a.id AS aluno_id,
               tp.nome AS plano, mod.nome AS modalidade
        FROM pagamentos p
        JOIN alunos a       ON a.id  = p.aluno_id
        JOIN matriculas m   ON m.id  = p.matricula_id
        JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
        JOIN modalidades mod ON mod.id = m.modalidade_id
        WHERE p.id = ?
    """, (pag_id,)).fetchone()
    conn.close()

    if not pag:
        return no_update, "Erro ao gerar recibo.", no_update

    aluno_dict = {"id": pag["aluno_id"], "nome": pag["aluno_nome"],
                  "cpf": pag["cpf"], "telefone": pag["telefone"]}
    html_str = gerar_recibo_html(aluno_dict, dict(pag), pag["plano"], pag["modalidade"])

    # Envio por e-mail se informado
    erro_email = ""
    if email and email.strip():
        try:
            _enviar_recibo_email(email.strip(), pag["aluno_nome"], html_str)
        except Exception as ex:
            erro_email = f" (falha no e-mail: {ex})"

    download = dcc.send_string(html_str, filename=f"recibo_{pag_id}.html",
                               type="text/html")
    return download, erro_email, False


def _enviar_recibo_email(destinatario: str, nome_aluno: str, html_body: str):
    """Envia recibo por e-mail via SMTP. Configurar variáveis de ambiente ou academia.cfg."""
    import os, smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user:
        raise ValueError("SMTP não configurado (defina SMTP_USER e SMTP_PASS)")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Recibo de Pagamento — {nome_aluno}"
    msg["From"]    = smtp_user
    msg["To"]      = destinatario
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, destinatario, msg.as_string())


# ══════════════════════════════════════════════════════════════════════════
# ABA: PAGAMENTOS / CONTAS A RECEBER
# ══════════════════════════════════════════════════════════════════════════

def _aba_pagamentos():
    hoje = date.today()
    return html.Div([
        dcc.Download(id="download-pagamentos-xlsx"),
        dcc.Store(id="store-pag-id"),
        dcc.Store(id="store-pag-edit-id"),
        dcc.Store(id="store-refresh-pag", data=0),

        dbc.Row([
            # ── Lista principal ──────────────────────────────────────────
            dbc.Col([
                # Cabeçalho estilo referência
                html.Div([
                    html.Div(
                        "Cobranças",
                        style={"background": COR_PRIMARIA, "color": "white",
                               "padding": "10px 18px", "fontWeight": "700",
                               "fontSize": "14px", "letterSpacing": ".5px"},
                    ),
                    html.Div([
                        dbc.Input(
                            id="filtro-pag-busca",
                            placeholder="🔍  Filtrar por aluno...",
                            size="sm", debounce=False,
                            style={"border": "none", "background": "transparent",
                                   "maxWidth": "260px", "outline": "none",
                                   "boxShadow": "none"},
                        ),
                        html.Div([
                            dbc.Button(
                                html.I(className="bi bi-download"),
                                id="btn-export-pagamentos",
                                color="secondary", size="sm", outline=True,
                                title="Exportar Excel", className="ms-1",
                            ),
                        ], className="ms-auto d-flex"),
                    ], className="d-flex align-items-center px-3 py-2 border-bottom bg-white"),
                    html.Div(id="tabela-pagamentos"),
                ], style={"border": "1px solid #ddd", "borderRadius": "8px",
                          "overflow": "hidden", "background": "white"}),
            ], md=9),

            # ── Painel lateral de filtros ────────────────────────────────
            dbc.Col([
                html.Div([
                    html.Div(
                        html.Strong("Filtro Avançado",
                                    style={"color": "white", "fontSize": "13px"}),
                        style={"background": "#1565c0", "padding": "12px 16px",
                               "borderRadius": "8px 8px 0 0"},
                    ),
                    html.Div([
                        # Status
                        html.Div("Status", style={"fontSize": "11px", "color": "#888",
                                                   "fontWeight": "700",
                                                   "textTransform": "uppercase",
                                                   "marginBottom": "6px"}),
                        dbc.RadioItems(
                            id="filtro-pag-status",
                            options=[
                                {"label": "Todas",   "value": "aberto"},
                                {"label": "Vencidas","value": "vencido"},
                                {"label": "Futuras", "value": "futuras"},
                                {"label": "Pagas",   "value": "pago"},
                            ],
                            value="aberto", className="mb-3",
                            inputStyle={"marginRight": "6px"},
                        ),
                        html.Hr(className="my-2"),
                        # Período
                        html.Div("Período", style={"fontSize": "11px", "color": "#888",
                                                    "fontWeight": "700",
                                                    "textTransform": "uppercase",
                                                    "marginBottom": "6px"}),
                        dbc.RadioItems(
                            id="filtro-pag-periodo",
                            options=[
                                {"label": "Todos",         "value": ""},
                                {"label": "Este Mês",      "value": "mes"},
                                {"label": "Hoje",          "value": "hoje"},
                                {"label": "Outro Período", "value": "custom"},
                            ],
                            value="", className="mb-2",
                            inputStyle={"marginRight": "6px"},
                        ),
                        dbc.Row([
                            dbc.Col(dbc.Input(id="filtro-pag-ini", type="date",
                                              size="sm"), md=6),
                            dbc.Col(dbc.Input(id="filtro-pag-fim", type="date",
                                              value=hoje.isoformat(), size="sm"), md=6),
                        ], id="filtro-pag-datas", className="mb-3",
                           style={"display": "none"}),
                        dbc.Row([
                            dbc.Col(dbc.Button(
                                [html.I(className="bi bi-check-lg me-1"), "Filtrar"],
                                id="btn-pag-filtrar", color="success", size="sm",
                                className="w-100",
                            ), md=6),
                            dbc.Col(dbc.Button(
                                [html.I(className="bi bi-x-lg me-1"), "Limpar"],
                                id="btn-pag-limpar", color="danger", size="sm",
                                outline=True, className="w-100",
                            ), md=6),
                        ], className="mb-3 g-1"),
                        html.Hr(className="my-2"),
                        html.Div(id="totais-pag"),
                    ], style={"padding": "14px 16px"}),
                ], style={"border": "1px solid #ddd", "borderRadius": "8px",
                          "overflow": "hidden", "position": "sticky", "top": "70px",
                          "background": "white"}),
            ], md=3),
        ]),

        # Modal detalhes / baixa de pagamento (cifrão verde)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="bi bi-cash-coin me-2", style={"color": "#198754"}),
                "Detalhes do Pagamento",
            ])),
            dbc.ModalBody([
                html.Div(id="modal-pag-info", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Forma de pagamento *"),
                        dbc.Select(id="inp-pag-forma",
                                   options=[{"label": "PIX",          "value": "pix"},
                                            {"label": "Dinheiro",     "value": "dinheiro"},
                                            {"label": "Cartão",       "value": "cartao"},
                                            {"label": "Transferência","value": "transferencia"}]),
                    ], md=6),
                    dbc.Col([
                        dbc.Label("Data do pagamento"),
                        dbc.Input(id="inp-pag-data", type="date", value=hoje.isoformat()),
                    ], md=6),
                ], className="mb-2", id="pag-form-row"),
                dbc.Label("Observações"),
                dbc.Textarea(id="inp-pag-obs", rows=2),
                html.Div(id="modal-pag-erro", className="text-danger mt-2",
                         style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Fechar", id="btn-modal-pag-cancel",
                           color="secondary", outline=True),
                dbc.Button([html.I(className="bi bi-check-lg me-1"), "Confirmar Pagamento"],
                           id="btn-modal-pag-confirmar", color="success"),
            ]),
        ], id="modal-pag", is_open=False),

        # Modal editar pagamento (lápis laranja)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="bi bi-pencil me-2", style={"color": "#fd7e14"}),
                "Editar Pagamento",
            ])),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Desconto (R$)"),
                        dbc.Input(id="inp-pag-edit-desconto", type="number",
                                  min=0, step=0.01, placeholder="0,00"),
                    ], md=6),
                    dbc.Col([
                        dbc.Label("Data de Vencimento"),
                        dbc.Input(id="inp-pag-edit-venc", type="date"),
                    ], md=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Data de Pagamento"),
                        dbc.Input(id="inp-pag-edit-dtpag", type="date"),
                    ], md=6),
                ]),
                html.Div(id="modal-pag-edit-erro", className="text-danger mt-2",
                         style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-pag-edit-cancel",
                           color="secondary", outline=True),
                dbc.Button([html.I(className="bi bi-save me-1"), "Salvar"],
                           id="btn-pag-edit-salvar", color="warning"),
            ]),
        ], id="modal-pag-edit", is_open=False),
    ])


@app.callback(
    Output("filtro-pag-datas", "style"),
    Input("filtro-pag-periodo", "value"),
)
def toggle_datas_custom(periodo):
    return {"display": "flex"} if periodo == "custom" else {"display": "none"}


@app.callback(
    Output("filtro-pag-status",  "value"),
    Output("filtro-pag-periodo", "value"),
    Output("filtro-pag-busca",   "value"),
    Output("filtro-pag-ini",     "value"),
    Output("filtro-pag-fim",     "value"),
    Input("btn-pag-limpar",      "n_clicks"),
    prevent_initial_call=True,
)
def limpar_filtros_pag(n):
    if not n:
        raise PreventUpdate
    return "aberto", "", "", None, None


@app.callback(
    Output("tabela-pagamentos", "children"),
    Output("totais-pag",        "children"),
    Input("filtro-pag-status",  "value"),
    Input("filtro-pag-periodo", "value"),
    Input("filtro-pag-ini",     "value"),
    Input("filtro-pag-fim",     "value"),
    Input("filtro-pag-busca",   "value"),
    Input("btn-pag-filtrar",    "n_clicks"),
    Input("store-tab-ativa",    "data"),
    Input("store-refresh-pag",  "data"),
)
def atualizar_tabela_pag(status, periodo, dt_ini, dt_fim, busca, _filtrar, tab, _refresh):
    if tab != "pagamentos":
        raise PreventUpdate

    from app.database import get_conn as _gc
    hoje = date.today()

    # Monta filtro de datas
    if periodo == "hoje":
        dt_ini = dt_fim = hoje.isoformat()
    elif periodo == "mes":
        import calendar as _cal
        dt_ini = hoje.replace(day=1).isoformat()
        ultimo = _cal.monthrange(hoje.year, hoje.month)[1]
        dt_fim = hoje.replace(day=ultimo).isoformat()
    elif periodo == "":
        dt_ini = dt_fim = None   # sem filtro de data
    # custom: usa dt_ini e dt_fim dos inputs

    # Status filter
    futuras_only = False
    if status == "aberto":
        status_list = ("pendente", "vencido")
    elif status == "futuras":
        status_list = ("pendente",)
        futuras_only = True
    elif status:
        status_list = (status,)
    else:
        status_list = None

    conn = _gc()
    sql = """
        SELECT p.*, a.nome AS aluno_nome, a.id AS aluno_id,
               tp.nome AS plano, mod.nome AS modalidade,
               m.data_inicio AS mat_inicio, m.data_fim AS mat_fim
        FROM pagamentos p
        JOIN alunos a        ON a.id  = p.aluno_id
        JOIN matriculas m    ON m.id  = p.matricula_id
        JOIN tipos_plano tp  ON tp.id = m.tipo_plano_id
        JOIN modalidades mod ON mod.id = m.modalidade_id
        WHERE 1=1
    """
    params = []
    if status_list:
        sql += f" AND p.status IN ({','.join('?'*len(status_list))})"
        params += list(status_list)
    if dt_ini:
        sql += " AND p.data_vencimento >= ?"
        params.append(dt_ini)
    if dt_fim:
        sql += " AND p.data_vencimento <= ?"
        params.append(dt_fim)
    if futuras_only:
        sql += " AND p.data_vencimento > date('now')"
    sql += " ORDER BY p.data_vencimento ASC"
    rows_db = conn.execute(sql, params).fetchall()

    # Totalizadores
    tot_sql = """
        SELECT
          COALESCE(SUM(CASE WHEN p.status='vencido' THEN p.valor ELSE 0 END),0) AS vencidas,
          COALESCE(SUM(CASE WHEN p.status='pendente' AND p.data_vencimento > date('now') THEN p.valor ELSE 0 END),0) AS futuras,
          COALESCE(SUM(CASE WHEN p.status='pago' THEN p.valor ELSE 0 END),0) AS recebido
        FROM pagamentos p WHERE 1=1
    """
    t_params = []
    if dt_ini:
        tot_sql += " AND p.data_vencimento >= ?"; t_params.append(dt_ini)
    if dt_fim:
        tot_sql += " AND p.data_vencimento <= ?"; t_params.append(dt_fim)
    tot = dict(conn.execute(tot_sql, t_params).fetchone())
    conn.close()

    lista = [dict(r) for r in rows_db]
    if busca:
        lista = [p for p in lista if busca.lower() in p["aluno_nome"].lower()]

    # Totalizadores UI
    totais = html.Div([
        html.Div([
            html.Div("Vencidas",  style={"fontSize": "11px", "color": "#888"}),
            html.Div(_fmt_brl(tot["vencidas"]), style={"fontWeight": "700", "color": "#dc3545"}),
        ], className="d-flex justify-content-between mb-1"),
        html.Div([
            html.Div("Futuras",   style={"fontSize": "11px", "color": "#888"}),
            html.Div(_fmt_brl(tot["futuras"]),  style={"fontWeight": "700", "color": "#0d6efd"}),
        ], className="d-flex justify-content-between mb-1"),
        html.Div([
            html.Div("Recebido",  style={"fontSize": "11px", "color": "#888"}),
            html.Div(_fmt_brl(tot["recebido"]), style={"fontWeight": "700", "color": "#198754"}),
        ], className="d-flex justify-content-between mb-2"),
        html.Hr(className="my-1"),
        html.Div([
            html.Div("Total a receber", style={"fontSize": "12px", "fontWeight": "700"}),
            html.Div(_fmt_brl(tot["vencidas"] + tot["futuras"]),
                     style={"fontWeight": "800", "fontSize": "16px", "color": COR_PRIMARIA}),
        ], className="d-flex justify-content-between"),
    ])

    if not lista:
        return dbc.Alert("Nenhum registro encontrado.", color="light"), totais

    _th = {"fontSize": "11px", "color": "#888", "fontWeight": "700",
           "textTransform": "uppercase", "padding": "10px 14px",
           "borderBottom": "2px solid #e0e0e0", "background": "#fafafa"}

    rows = []
    for p in lista:
        is_vencido = (p["status"] == "vencido" or
                      (p["status"] == "pendente" and
                       p["data_vencimento"] < hoje.isoformat()))
        desconto = float(p.get("desconto") or 0)
        valor_liq = float(p["valor"]) - desconto

        btn_ver = dbc.Button(
            html.I(className="bi bi-cash-coin"),
            id={"type": "btn-ver-pag", "index": p["id"]},
            size="sm", title="Ver / Receber",
            style={"background": "#198754", "border": "none",
                   "color": "white", "padding": "3px 8px", "marginRight": "4px",
                   "borderRadius": "4px"},
        )
        btn_edit = dbc.Button(
            html.I(className="bi bi-pencil"),
            id={"type": "btn-edit-pag", "index": p["id"]},
            size="sm", title="Editar",
            style={"background": "#fd7e14", "border": "none",
                   "color": "white", "padding": "3px 8px", "borderRadius": "4px"},
        )

        rows.append(html.Tr([
            html.Td(
                _fmt_data(p["data_vencimento"]),
                style={"whiteSpace": "nowrap", "padding": "10px 14px",
                       "color": "#dc3545" if is_vencido else "#555",
                       "fontWeight": "500", "width": "115px"},
            ),
            html.Td([
                html.Div(f"{p['aluno_nome']} ({p['aluno_id']})",
                         style={"color": "#0d6efd", "fontWeight": "500"}),
                html.Small(
                    f"{p['plano']}  ·  {_fmt_data(p.get('mat_inicio'))} a {_fmt_data(p.get('mat_fim'))}",
                    style={"color": "#888"},
                ),
            ], style={"padding": "10px 14px"}),
            html.Td(
                _fmt_brl(valor_liq),
                style={"textAlign": "right", "fontWeight": "700",
                       "color": "#0d6efd", "whiteSpace": "nowrap",
                       "padding": "10px 14px", "width": "110px"},
            ),
            html.Td(
                [btn_ver, btn_edit],
                style={"textAlign": "right", "whiteSpace": "nowrap",
                       "padding": "8px 14px", "width": "90px"},
            ),
        ], style={"borderBottom": "1px solid #f0f0f0",
                  "backgroundColor": "#fff8f8" if is_vencido else "white"}))

    cabecalho = html.Tr([
        html.Th("Vencimento", style=_th),
        html.Th("Aluno ou Consumidor", style=_th),
        html.Th("Valor", style={**_th, "textAlign": "right"}),
        html.Th("", style={**_th, "width": "90px"}),
    ])
    tabela = html.Table(
        [html.Thead(cabecalho), html.Tbody(rows)],
        style={"width": "100%", "borderCollapse": "collapse"},
    )
    return tabela, totais


@app.callback(
    Output("modal-pag",               "is_open"),
    Output("store-pag-id",            "data"),
    Output("modal-pag-info",          "children"),
    Output("modal-pag-erro",          "children"),
    Output("store-refresh-pag",       "data"),
    Output("btn-modal-pag-confirmar", "style"),
    Output("pag-form-row",            "style"),
    Output("inp-pag-data",            "value"),
    Input({"type": "btn-baixar-pag",  "index": ALL}, "n_clicks"),
    Input({"type": "btn-ver-pag",     "index": ALL}, "n_clicks"),
    Input("btn-modal-pag-cancel",     "n_clicks"),
    Input("btn-modal-pag-confirmar",  "n_clicks"),
    State("store-pag-id",    "data"),
    State("inp-pag-forma",   "value"),
    State("inp-pag-data",    "value"),
    State("inp-pag-obs",     "value"),
    State("store-refresh-pag", "data"),
    prevent_initial_call=True,
)
def controlar_modal_pag(baixar_clicks, ver_clicks, n_cancel, n_confirmar,
                        pag_id, forma, data_pag, obs, refresh_val):
    tid = callback_context.triggered_id
    valor_clicado = (callback_context.triggered[0].get("value") or 0) if callback_context.triggered else 0

    if tid == "btn-modal-pag-cancel":
        if not n_cancel:
            raise PreventUpdate
        return False, no_update, no_update, "", no_update, no_update, no_update, no_update

    if isinstance(tid, dict) and tid.get("type") in ("btn-baixar-pag", "btn-ver-pag"):
        if valor_clicado <= 0:
            raise PreventUpdate
        pid = tid["index"]
        conn = get_conn()
        p = conn.execute("""
            SELECT p.*, a.nome AS aluno_nome, tp.nome AS plano, mod.nome AS modalidade
            FROM pagamentos p
            JOIN alunos a ON a.id = p.aluno_id
            JOIN matriculas m ON m.id = p.matricula_id
            JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
            JOIN modalidades mod ON mod.id = m.modalidade_id
            WHERE p.id = ?
        """, (pid,)).fetchone()
        conn.close()
        if not p:
            raise PreventUpdate
        p = dict(p)
        desconto = float(p.get("desconto") or 0)
        valor_liq = float(p["valor"]) - desconto
        data_sugerida = p.get("data_vencimento") or date.today().isoformat()

        info_items = [
            html.Strong(p["aluno_nome"]), html.Br(),
            html.Span(f"{p['plano']} / {p['modalidade']}", style={"color": "#555"}),
            "  |  Venc.: ", _fmt_data(p["data_vencimento"]), html.Br(),
            "Valor: ", html.Strong(_fmt_brl(p["valor"])),
        ]
        if desconto:
            info_items += [
                "  |  Desconto: ",
                html.Strong(_fmt_brl(desconto), style={"color": "#198754"}),
                "  |  A pagar: ",
                html.Strong(_fmt_brl(valor_liq), style={"color": COR_ACENTO}),
            ]
        if p["status"] == "pago":
            info_items += [html.Br(), "Pago em: ", _fmt_data(p["data_pagamento"]),
                           "  |  Forma: ", p.get("forma") or "—"]
            data_sugerida = p.get("data_pagamento") or data_sugerida
        info = dbc.Alert(info_items, color="info")
        hide = {"display": "none"} if p["status"] == "pago" else {}
        return True, pid, info, "", no_update, hide, hide, data_sugerida

    if tid == "btn-modal-pag-confirmar":
        if not n_confirmar:
            raise PreventUpdate
        if not pag_id or not forma:
            return no_update, no_update, no_update, "Selecione a forma de pagamento.", no_update, no_update, no_update, no_update
        ok, msg = renov_mod.baixar_pagamento(pag_id, forma, data_pag, obs or "")
        if ok:
            return False, None, "", "", (refresh_val or 0) + 1, {}, {}, no_update
        return no_update, no_update, no_update, msg, no_update, no_update, no_update, no_update

    raise PreventUpdate


@app.callback(
    Output("modal-pag-edit",          "is_open"),
    Output("store-pag-edit-id",       "data"),
    Output("inp-pag-edit-desconto",   "value"),
    Output("inp-pag-edit-venc",       "value"),
    Output("inp-pag-edit-dtpag",      "value"),
    Output("modal-pag-edit-erro",     "children"),
    Output("store-refresh-pag",       "data", allow_duplicate=True),
    Input({"type": "btn-edit-pag",    "index": ALL}, "n_clicks"),
    Input("btn-pag-edit-cancel",      "n_clicks"),
    Input("btn-pag-edit-salvar",      "n_clicks"),
    State("store-pag-edit-id",        "data"),
    State("inp-pag-edit-desconto",    "value"),
    State("inp-pag-edit-venc",        "value"),
    State("inp-pag-edit-dtpag",       "value"),
    State("store-refresh-pag",        "data"),
    prevent_initial_call=True,
)
def controlar_modal_pag_edit(edit_clicks, n_cancel, n_salvar,
                              pag_id, desconto, venc, dtpag, refresh):
    tid = callback_context.triggered_id
    valor = (callback_context.triggered[0].get("value") or 0) if callback_context.triggered else 0

    if tid == "btn-pag-edit-cancel":
        if not n_cancel:
            raise PreventUpdate
        return False, no_update, no_update, no_update, no_update, "", no_update

    if isinstance(tid, dict) and tid.get("type") == "btn-edit-pag":
        if valor <= 0:
            raise PreventUpdate
        pid = tid["index"]
        conn = get_conn()
        p = conn.execute("SELECT * FROM pagamentos WHERE id=?", (pid,)).fetchone()
        conn.close()
        if not p:
            raise PreventUpdate
        p = dict(p)
        return (True, pid,
                p.get("desconto") or 0,
                p.get("data_vencimento") or "",
                p.get("data_pagamento") or "",
                "", no_update)

    if tid == "btn-pag-edit-salvar":
        if not n_salvar:
            raise PreventUpdate
        if not pag_id:
            return no_update, no_update, no_update, no_update, no_update, "Erro interno.", no_update
        ok, msg = renov_mod.editar_pagamento(
            pag_id,
            desconto=float(desconto) if desconto else 0.0,
            data_vencimento=venc or None,
            data_pagamento=dtpag or None,
        )
        if ok:
            return False, None, no_update, no_update, no_update, "", (refresh or 0) + 1
        return no_update, no_update, no_update, no_update, no_update, msg, no_update

    raise PreventUpdate


# ══════════════════════════════════════════════════════════════════════════
# ABA: PERFIL DO ALUNO
# ══════════════════════════════════════════════════════════════════════════

def _perfil_tab_btn(tab_id, label, ativa):
    return html.Button(
        label,
        id={"type": "btn-perfil-tab", "index": tab_id},
        className="perfil-tab-btn",
        n_clicks=0,
        style=_perfil_tab_style(ativa),
    )


def _perfil_tab_style(ativa):
    return {
        "background": "#ffffff" if ativa else COR_PRIMARIA,
        "color": COR_PRIMARIA if ativa else "#cbd5e1",
        "border": "none", "padding": "12px 22px",
        "fontWeight": "700", "fontSize": "12px", "cursor": "pointer",
        "borderBottom": "3px solid #ffffff" if ativa else "3px solid transparent",
        "letterSpacing": ".5px",
        "borderRadius": "8px 8px 0 0" if ativa else "0",
        "boxShadow": "0 -1px 0 rgba(255,255,255,.12), 0 8px 18px rgba(15,23,42,.18)" if ativa else "none",
        "transform": "translateY(-1px)" if ativa else "none",
        "transition": "all .18s ease",
    }


def _perfil_tab_bar(tab_ativa):
    return html.Div([
        _perfil_tab_btn("financeiro", "FINANCEIRO", tab_ativa == "financeiro"),
        _perfil_tab_btn("matriculas", "MATRÍCULAS", tab_ativa == "matriculas"),
        html.Span("TREINOS", style={
            "color": "#aaa", "padding": "12px 22px", "fontSize": "12px",
            "fontWeight": "700", "letterSpacing": ".5px", "cursor": "default",
        }),
        html.Span("AVALIAÇÕES", style={
            "color": "#aaa", "padding": "12px 22px", "fontSize": "12px",
            "fontWeight": "700", "letterSpacing": ".5px", "cursor": "default",
        }),
    ], style={"background": COR_PRIMARIA, "display": "flex",
              "borderRadius": "8px 8px 0 0", "overflow": "hidden"})


def _perfil_tab_financeiro(aluno_id):
    hoje = date.today().isoformat()
    return html.Div([
        dcc.Store(id="store-perfil-fin-tipo",   data="cobrancas"),
        dcc.Store(id="store-perfil-fin-filtro", data="abertas"),
        html.Div([
            html.Div([
                dbc.RadioItems(
                    id="perfil-fin-tipo",
                    options=[{"label": "Cobranças",    "value": "cobrancas"},
                             {"label": "Recebimentos", "value": "recebimentos"}],
                    value="cobrancas", inline=True, className="me-4 perfil-radio-items",
                    inputStyle={"marginRight": "4px"},
                ),
                html.Span(style={"borderLeft": "1px solid #ddd", "margin": "0 12px"}),
                dbc.RadioItems(
                    id="perfil-fin-filtro",
                    options=[{"label": "Abertas",    "value": "abertas"},
                             {"label": "Canceladas", "value": "canceladas"},
                             {"label": "Todas",      "value": "todas"}],
                    value="abertas", inline=True, className="perfil-radio-items",
                    inputStyle={"marginRight": "4px"},
                ),
            ], className="d-flex align-items-center", style={"flexWrap": "wrap", "gap": "8px"}),
            dbc.Button(
                [html.I(className="bi bi-cash-stack me-1"), "Receber selecionadas"],
                id="btn-perfil-pag-lote",
                color="success",
                outline=True,
                size="sm",
                className="ms-auto",
            ),
        ], className="d-flex align-items-center p-3 border-bottom",
           style={"flexWrap": "wrap", "gap": "8px"}),
        html.Div(id="perfil-fin-tabela"),
        html.Div(id="perfil-fin-total", className="text-end p-3 border-top fw-bold"),
    ])


def _perfil_tab_matriculas(aluno_id):
    return html.Div([
        dcc.Store(id="store-perfil-mat-filtro", data="ativas"),
        html.Div([
            dbc.RadioItems(
                id="perfil-mat-filtro",
                options=[{"label": "Ativas e Pendentes", "value": "ativas"},
                         {"label": "Canceladas",         "value": "canceladas"},
                         {"label": "Finalizadas",        "value": "finalizadas"},
                         {"label": "Todas",              "value": "todas"}],
                value="ativas", inline=True, className="perfil-radio-items",
                inputStyle={"marginRight": "4px"},
            ),
            dbc.Button([html.I(className="bi bi-plus-circle me-1"), "Matrícula"],
                       id="btn-perfil-nova-mat", color="success", size="sm",
                       outline=True, className="ms-auto"),
        ], className="d-flex align-items-center p-3 border-bottom"),
        html.Div(id="perfil-mat-tabela"),
    ])


def _aba_perfil_aluno(aluno_id: int):
    a = alunos_mod.buscar_aluno(aluno_id)
    if not a:
        return dbc.Alert("Aluno não encontrado.", color="danger")

    hoje = date.today()
    matriculas = alunos_mod.listar_matriculas_aluno(aluno_id)
    mat_ativas = [m for m in matriculas
                  if m["status"] in ("ativo", "inadimplente", "aguardando_pagamento")]

    conn = get_conn()
    total_vencido = conn.execute("""
        SELECT COALESCE(SUM(p.valor - COALESCE(p.desconto, 0)), 0)
        FROM pagamentos p
        JOIN matriculas m ON m.id = p.matricula_id
        WHERE m.aluno_id = ? AND p.status IN ('pendente','vencido')
    """, (aluno_id,)).fetchone()[0]
    conn.close()

    iniciais = "".join(w[0].upper() for w in (a["nome"] or "?").split()[:2])

    # ── Painel esquerdo ──────────────────────────────────────────────────
    painel_esq = dbc.Card([
        dbc.CardBody([
            html.Div(iniciais, style={
                "width": "80px", "height": "80px", "borderRadius": "50%",
                "background": COR_PRIMARIA, "color": "#fff",
                "display": "flex", "alignItems": "center", "justifyContent": "center",
                "fontSize": "28px", "fontWeight": "800", "margin": "0 auto 12px",
            }),
            html.Div(a["nome"], className="fw-bold text-center", style={"fontSize": "15px"}),
            html.Div(f"#{aluno_id:04d}", className="text-center mb-2",
                    style={"color": COR_ACENTO, "fontWeight": "700", "fontSize": "13px"}),
            html.Div(_badge_status(a["status"]), className="text-center mb-3"),
            html.Hr(className="my-2"),
            html.Small("INFORMAÇÕES", className="text-muted fw-semibold d-block mb-1",
                       style={"fontSize": "10px"}),
            html.Div("E-MAIL", style={"fontSize": "10px", "color": "#aaa", "marginTop": "6px"}),
            html.Div(a.get("email") or "—", style={"fontSize": "13px"}),
            html.Div("TELEFONE", style={"fontSize": "10px", "color": "#aaa", "marginTop": "6px"}),
            html.Div(a.get("telefone") or "—", style={"fontSize": "13px"}),
            html.Hr(className="my-2"),
            dcc.Link(
                dbc.Button([html.I(className="bi bi-pencil me-1"), "Editar"],
                           color="secondary", size="sm", outline=True, className="w-100"),
                href=f"/alunos/{aluno_id}/editar", refresh=False,
            ),
        ]),
    ], className="shadow-sm")

    # ── Barra de resumo ─────────────────────────────────────────────────
    cor_vencido = "#dc3545" if total_vencido > 0 else "#198754"
    barra = html.Div([
        html.Div([
            html.I(className="bi bi-check-circle-fill me-2",
                   style={"color": "#198754", "fontSize": "22px"}),
            html.Div([
                html.Div(a["status"].capitalize(),
                         style={"color": "#198754", "fontWeight": "700", "lineHeight": "1.1"}),
                html.Div(f"{len(mat_ativas)} Matrícula",
                         style={"fontSize": "11px", "color": "#888"}),
            ]),
        ], className="d-flex align-items-center me-4"),
        html.Div([
            html.I(className="bi bi-exclamation-triangle-fill me-2",
                   style={"color": cor_vencido, "fontSize": "22px"}),
            html.Div([
                html.Div(_fmt_brl(total_vencido),
                         style={"color": cor_vencido, "fontWeight": "700", "lineHeight": "1.1"}),
                html.Div("Total Vencido", style={"fontSize": "11px", "color": "#888"}),
            ]),
        ], className="d-flex align-items-center me-4"),
        html.Div([
            html.I(className="bi bi-coin me-2",
                   style={"color": "#0d6efd", "fontSize": "22px"}),
            html.Div([
                html.Div(_fmt_brl(0),
                         style={"color": "#0d6efd", "fontWeight": "700", "lineHeight": "1.1"}),
                html.Div("Crédito Disponível", style={"fontSize": "11px", "color": "#888"}),
            ]),
        ], className="d-flex align-items-center"),
    ], className="d-flex align-items-center p-3 mb-3",
       style={"background": "#fff", "borderRadius": "10px",
              "boxShadow": "0 2px 8px rgba(0,0,0,.07)"})

    # ── Aba nav + conteúdo ───────────────────────────────────────────────
    planos     = alunos_mod.listar_planos()
    modalids   = alunos_mod.listar_modalidades()
    tab_panel = html.Div([
        dcc.Store(id="store-perfil-tab",      data="financeiro"),
        dcc.Store(id="store-perfil-aluno-id", data=aluno_id),
        dcc.Store(id="store-perfil-refresh",  data=0),
        dcc.Store(id="store-perfil-pag-id"),
        dcc.Store(id="store-perfil-edit-id"),
        dcc.Store(id="store-perfil-acao-mat"),
        # Tab buttons
        html.Div(id="perfil-tabs-topo", children=_perfil_tab_bar("financeiro")),
        # Tab content
        html.Div(id="perfil-conteudo-tab",
                 children=_perfil_tab_financeiro(aluno_id),
                 style={"background": "#fff", "borderRadius": "0 0 8px 8px",
                        "border": "1px solid #e0e0e0", "borderTop": "none"}),
        # Modals
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-perfil-pag-titulo", children=[
                html.I(className="bi bi-cash-coin me-2", style={"color": "#198754"}),
                "Detalhes do Pagamento",
            ])),
            dbc.ModalBody([
                html.Div(id="modal-perfil-pag-info", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Forma de pagamento *"),
                        dbc.Select(id="inp-perfil-pag-forma",
                                   options=[{"label": "PIX",          "value": "pix"},
                                            {"label": "Dinheiro",     "value": "dinheiro"},
                                            {"label": "Cartão",       "value": "cartao"},
                                            {"label": "Transferência","value": "transferencia"}]),
                    ], md=6),
                    dbc.Col([
                        dbc.Label("Data do pagamento"),
                        dbc.Input(id="inp-perfil-pag-data", type="date",
                                  value=hoje.isoformat()),
                    ], md=6),
                ], className="mb-2", id="perfil-pag-form-row"),
                dbc.Textarea(id="inp-perfil-pag-obs", rows=2, placeholder="Observações"),
                html.Div(id="modal-perfil-pag-erro", className="text-danger mt-2",
                         style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Fechar", id="btn-perfil-pag-cancel",
                           color="secondary", outline=True),
                dbc.Button([html.I(className="bi bi-check-lg me-1"), "Confirmar"],
                           id="btn-perfil-pag-confirmar", color="success"),
            ]),
        ], id="modal-perfil-pag", is_open=False),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="bi bi-pencil me-2", style={"color": "#fd7e14"}),
                "Editar Pagamento",
            ])),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Desconto (R$)"),
                        dbc.Input(id="inp-perfil-edit-desconto", type="number",
                                  min=0, step=0.01, placeholder="0,00"),
                    ], md=6),
                    dbc.Col([
                        dbc.Label("Data de Vencimento"),
                        dbc.Input(id="inp-perfil-edit-venc", type="date"),
                    ], md=6),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Data de Pagamento"),
                        dbc.Input(id="inp-perfil-edit-dtpag", type="date"),
                    ], md=6),
                ]),
                html.Div(id="modal-perfil-edit-erro", className="text-danger mt-2",
                         style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-perfil-edit-cancel",
                           color="secondary", outline=True),
                dbc.Button([html.I(className="bi bi-save me-1"), "Salvar"],
                           id="btn-perfil-edit-salvar", color="warning"),
            ]),
        ], id="modal-perfil-edit-pag", is_open=False),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle([
                html.I(className="bi bi-plus-circle me-2", style={"color": "#198754"}),
                "Nova Matrícula",
            ])),
            dbc.ModalBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Plano *"),
                        dbc.Select(id="inp-perfil-mat-plano",
                                   options=[{
                                       "label": (f"{p['nome']} — {_fmt_brl(p['valor'])}" +
                                                 (f" ({p['modalidade_nome']})" if p.get("modalidade_nome") else "")),
                                       "value": p["id"],
                                   } for p in planos]),
                    ], md=12),
                ], className="mb-3"),
                html.Div([
                    dbc.Label("Modalidade *"),
                    dbc.Select(id="inp-perfil-mat-modal",
                               options=[{"label": m["nome"], "value": m["id"]}
                                        for m in modalids]),
                ], id="perfil-mat-modal-row", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Data de início"),
                        dbc.Input(id="inp-perfil-mat-inicio", type="date",
                                  value=hoje.isoformat()),
                    ], md=6),
                ]),
                html.Div(id="modal-perfil-mat-erro", className="text-danger mt-2",
                         style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-perfil-mat-cancel",
                           color="secondary", outline=True),
                dbc.Button([html.I(className="bi bi-check-lg me-1"), "Matricular"],
                           id="btn-perfil-mat-confirmar", color="success"),
            ]),
        ], id="modal-perfil-nova-mat", is_open=False),
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-perfil-acao-titulo")),
            dbc.ModalBody([
                dbc.Alert(id="modal-perfil-acao-info", color="info", className="mb-3"),
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Motivo *"),
                        dbc.Select(
                            id="inp-perfil-acao-motivo",
                            options=[
                                {"label": MOTIVO_MATRICULA_LABELS[m], "value": m}
                                for m in alunos_mod.MOTIVOS_MATRICULA
                            ],
                            value="mudanca_de_plano",
                        ),
                    ], md=6),
                    dbc.Col([
                        dbc.Label("Data da mudança *"),
                        dbc.Input(id="inp-perfil-acao-data", type="date", value=hoje.isoformat()),
                    ], md=6),
                ], className="mb-3"),
                html.Div(id="perfil-acao-novo-plano-wrap", children=[
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("Novo plano *"),
                            dbc.Select(id="inp-perfil-acao-plano",
                                       options=[{
                                           "label": (f"{p['nome']} — {_fmt_brl(p['valor'])}" +
                                                     (f" ({p['modalidade_nome']})" if p.get("modalidade_nome") else "")),
                                           "value": p["id"],
                                       } for p in planos]),
                        ], md=12),
                    ], className="mb-3"),
                    html.Div([
                        dbc.Label("Nova modalidade *"),
                        dbc.Select(id="inp-perfil-acao-modal",
                                   options=[{"label": m["nome"], "value": m["id"]}
                                            for m in modalids]),
                    ], id="perfil-acao-modal-row", className="mb-3"),
                ]),
                dbc.Checkbox(id="inp-perfil-acao-renovacao", label="Renovação automática no novo plano", value=True, className="mb-2"),
                html.Div(id="modal-perfil-acao-erro", className="text-danger mt-2",
                         style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-perfil-acao-cancel",
                           color="secondary", outline=True),
                dbc.Button(id="btn-perfil-acao-confirmar", color="primary"),
            ]),
        ], id="modal-perfil-acao-mat", is_open=False),
    ], style={"boxShadow": "0 2px 8px rgba(0,0,0,.07)"})

    return html.Div([
        # Barra de busca rápida de aluno
        html.Div([
            html.Div([
                html.I(className="bi bi-search me-2",
                       style={"color": "#999", "fontSize": "14px"}),
                dbc.Input(
                    id="perfil-busca-aluno",
                    placeholder="Buscar outro aluno por nome ou telefone...",
                    debounce=False, size="sm",
                    style={"border": "none", "outline": "none",
                           "background": "transparent", "boxShadow": "none",
                           "fontSize": "14px", "color": "#333"},
                ),
            ], className="d-flex align-items-center px-3 py-2",
               style={"background": "white", "borderRadius": "8px",
                      "boxShadow": "0 2px 8px rgba(0,0,0,.08)"}),
            html.Div(id="perfil-busca-resultados",
                     style={"position": "absolute", "width": "100%", "zIndex": "1000"}),
        ], style={"position": "relative", "marginBottom": "12px"}),

        # Breadcrumb
        html.Div([
            dcc.Link("← Alunos", href="/alunos",
                     style={"color": COR_PRIMARIA, "textDecoration": "none",
                            "fontWeight": "600", "fontSize": "13px"}),
            html.Span(" > Perfil", style={"color": "#aaa", "fontSize": "13px"}),
        ], className="mb-3"),
        dbc.Row([
            dbc.Col(painel_esq, md=3),
            dbc.Col([barra, tab_panel], md=9),
        ], className="g-3"),
    ])


# ── Perfil: troca de tab ───────────────────────────────────────────────────

@app.callback(
    Output("store-perfil-tab", "data"),
    Input({"type": "btn-perfil-tab", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def trocar_perfil_tab(n_clicks):
    tid = callback_context.triggered_id
    valor = (callback_context.triggered[0].get("value") or 0) if callback_context.triggered else 0
    if isinstance(tid, dict) and tid.get("type") == "btn-perfil-tab" and valor > 0:
        return tid["index"]
    raise PreventUpdate


@app.callback(
    Output("perfil-tabs-topo", "children"),
    Input("store-perfil-tab", "data"),
)
def estilizar_tabs_perfil(tab_ativa):
    return _perfil_tab_bar(tab_ativa or "financeiro")


@app.callback(
    Output("perfil-conteudo-tab", "children"),
    Input("store-perfil-tab",     "data"),
    Input("store-perfil-refresh", "data"),
    State("store-perfil-aluno-id","data"),
)
def renderizar_perfil_tab(tab, _refresh, aluno_id):
    if not aluno_id:
        raise PreventUpdate
    if tab == "matriculas":
        return _perfil_tab_matriculas(aluno_id)
    return _perfil_tab_financeiro(aluno_id)


def _pagamentos_marcados(ids_componentes, valores_componentes):
    selecionados = []
    for comp_id, valor in zip(ids_componentes or [], valores_componentes or []):
        if valor:
            selecionados.append(int(comp_id["index"]))
    return selecionados


# ── Perfil: tabela financeiro ─────────────────────────────────────────────

@app.callback(
    Output("perfil-fin-tabela", "children"),
    Output("perfil-fin-total",  "children"),
    Input("perfil-fin-tipo",    "value"),
    Input("perfil-fin-filtro",  "value"),
    Input("store-perfil-refresh", "data"),
    State("store-perfil-aluno-id","data"),
)
def atualizar_perfil_financeiro(tipo, filtro, _refresh, aluno_id):
    if not aluno_id:
        raise PreventUpdate
    hoje = date.today().isoformat()
    if tipo == "recebimentos":
        status_filter = ("pago",)
    elif filtro == "canceladas":
        status_filter = ("cancelado",)
    elif filtro == "todas":
        status_filter = ("pendente", "vencido", "pago", "cancelado")
    else:
        status_filter = ("pendente", "vencido")

    conn = get_conn()
    ph = ",".join("?" * len(status_filter))
    rows_db = conn.execute(f"""
        SELECT p.*, tp.nome AS plano_nome, mod.nome AS modalidade_nome,
               m.data_inicio AS mat_inicio, m.data_fim AS mat_fim
        FROM pagamentos p
        JOIN matriculas m ON m.id = p.matricula_id
        JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
        JOIN modalidades mod ON mod.id = m.modalidade_id
        WHERE p.aluno_id = ? AND p.status IN ({ph})
        ORDER BY p.data_vencimento DESC
    """, (aluno_id,) + status_filter).fetchall()
    conn.close()

    rows_db = [dict(r) for r in rows_db]
    total = sum(float(r["valor"]) - float(r.get("desconto") or 0)
                for r in rows_db if r["status"] not in ("cancelado",))
    linhas = []
    for p in rows_db:
        desconto = float(p.get("desconto") or 0)
        valor_liq = float(p["valor"]) - desconto
        is_venc = (p["status"] == "vencido" or
                   (p["status"] == "pendente" and (p["data_vencimento"] or "") < hoje))
        periodo_ref = (f"{_fmt_data(p.get('mat_inicio'))} a {_fmt_data(p.get('mat_fim'))}"
                       if p.get("mat_inicio") else _fmt_data(p["data_vencimento"]))
        referencia = f"Mensalidade {periodo_ref} — {p['plano_nome']}"
        btn_ver = dbc.Button(
            html.I(className="bi bi-cash-coin"),
            id={"type": "btn-perfil-ver-pag", "index": p["id"]},
            size="sm", title="Ver / Receber",
            style={"backgroundColor": "#198754", "borderColor": "#198754",
                   "color": "white", "padding": "2px 7px", "marginRight": "4px"},
        )
        btn_edit = dbc.Button(
            html.I(className="bi bi-pencil"),
            id={"type": "btn-perfil-edit-pag", "index": p["id"]},
            size="sm", title="Editar",
            style={"backgroundColor": "#fd7e14", "borderColor": "#fd7e14",
                   "color": "white", "padding": "2px 7px"},
        )
        chk = ""
        if tipo == "cobrancas" and p["status"] in ("pendente", "vencido"):
            chk = dcc.Checklist(
                id={"type": "chk-perfil-pag", "index": p["id"]},
                options=[{"label": "", "value": p["id"]}],
                value=[],
                inputStyle={"marginRight": "0"},
                style={"display": "flex", "justifyContent": "center"},
            )
        linhas.append(html.Tr([
            html.Td(chk, style={"textAlign": "center", "width": "42px"}),
            html.Td(_fmt_data(p["data_vencimento"]),
                   style={"color": "#dc3545" if is_venc else "#333",
                          "fontWeight": "600", "whiteSpace": "nowrap"}),
            html.Td(referencia, style={"color": "#0d6efd"}),
            html.Td([
                html.Span(_fmt_brl(valor_liq),
                         style={"fontWeight": "700", "color": COR_PRIMARIA}),
                *([html.Br(),
                   html.Small(_fmt_brl(p["valor"]),
                              style={"textDecoration": "line-through", "color": "#aaa",
                                     "fontSize": "10px"})]
                  if desconto > 0 else []),
            ], style={"textAlign": "right"}),
            html.Td([btn_ver, btn_edit],
                    style={"textAlign": "right", "whiteSpace": "nowrap"}),
        ], style={"backgroundColor": "#fff5f5" if is_venc else ""}))

    if not linhas:
        tabela = html.Div("Nenhum registro encontrado.", className="text-muted p-3")
    else:
        tabela = dbc.Table(
            [html.Thead(html.Tr([
                html.Th("", style={"width": "42px"}),
                html.Th("VENCIMENTO",
                        style={"fontSize": "11px", "color": "#888", "fontWeight": "700"}),
                html.Th("REFERÊNCIA",
                        style={"fontSize": "11px", "color": "#888", "fontWeight": "700"}),
                html.Th("VALOR",
                        style={"fontSize": "11px", "color": "#888", "fontWeight": "700",
                               "textAlign": "right"}),
                html.Th("", style={"fontSize": "11px"}),
            ])),
             html.Tbody(linhas)],
            bordered=False, hover=True, size="sm", responsive=True,
        )
    total_txt = ["Total  ",
                 html.Span(_fmt_brl(total),
                           style={"color": COR_PRIMARIA, "fontSize": "18px",
                                  "fontWeight": "800"})]
    return tabela, total_txt


# ── Perfil: tabela matrículas ─────────────────────────────────────────────

@app.callback(
    Output("perfil-mat-tabela",   "children"),
    Input("perfil-mat-filtro",    "value"),
    Input("store-perfil-refresh", "data"),
    State("store-perfil-aluno-id","data"),
)
def atualizar_perfil_matriculas(filtro, _refresh, aluno_id):
    if not aluno_id:
        raise PreventUpdate
    matriculas = alunos_mod.listar_matriculas_aluno(aluno_id)
    hoje = date.today()

    if filtro == "ativas":
        matriculas = [m for m in matriculas
                      if m["status"] in ("ativo","inadimplente","aguardando_pagamento")]
    elif filtro == "canceladas":
        matriculas = [m for m in matriculas if m["status"] == "cancelado"]
    elif filtro == "finalizadas":
        matriculas = [m for m in matriculas if m["status"] == "encerrado"]

    # Carrega pagamentos pendentes do aluno de uma só vez
    conn = get_conn()
    pags_pendentes = conn.execute("""
        SELECT matricula_id, MIN(id) AS pag_id
        FROM pagamentos
        WHERE aluno_id = ? AND status IN ('pendente','vencido')
        GROUP BY matricula_id
    """, (aluno_id,)).fetchall()
    conn.close()
    pag_map = {r["matricula_id"]: r["pag_id"] for r in pags_pendentes}

    _th = {"fontSize": "11px", "color": "#888", "fontWeight": "700",
           "textTransform": "uppercase", "padding": "10px 14px",
           "borderBottom": "2px solid #e0e0e0"}

    linhas = []
    for m in matriculas:
        data_fim = date.fromisoformat(m["data_fim"]) if m.get("data_fim") else None
        vence_txt = f"Vence dia {data_fim.day}" if data_fim else "—"
        vigencia_txt = f"{_fmt_data(m['data_inicio'])} até {_fmt_data(m['data_fim'])}"
        periodo = "Mensal" if m.get("meses") == 1 else (
            f"{m['meses']} meses" if m.get("meses") else "—")
        motivo_txt = MOTIVO_MATRICULA_LABELS.get(m.get("motivo_encerramento") or "", "")
        data_enc_txt = _fmt_data(m.get("data_encerramento")) if m.get("data_encerramento") else None

        # Ícone de status
        if m["status"] == "ativo":
            icone = html.I(className="bi bi-check-circle-fill",
                           style={"color": "#198754", "fontSize": "16px"})
        elif m["status"] == "aguardando_pagamento":
            icone = html.I(className="bi bi-clock-fill",
                           style={"color": "#fd7e14", "fontSize": "16px"})
        else:
            icone = html.I(className="bi bi-x-circle-fill",
                           style={"color": "#aaa", "fontSize": "16px"})

        # Botão de recebimento se houver pagamento pendente
        pag_id = pag_map.get(m["id"])
        btn_receber = None
        if pag_id:
            btn_receber = dbc.Button(
                [html.I(className="bi bi-cash-coin me-1"), "Receber"],
                id={"type": "btn-perfil-ver-pag", "index": pag_id},
                size="sm",
                style={"backgroundColor": "#198754", "border": "none",
                       "color": "white", "fontSize": "11px",
                       "padding": "3px 10px", "borderRadius": "4px"},
            )

        botoes_acao = []
        if m["status"] in ("ativo", "aguardando_pagamento", "inadimplente"):
            botoes_acao.append(dbc.Button(
                [html.I(className="bi bi-arrow-left-right me-1"), "Mudar plano"],
                id={"type": "btn-perfil-mudar-plano", "index": m["id"]},
                size="sm", color="primary", outline=True,
                className="me-1",
            ))
            botoes_acao.append(dbc.Button(
                [html.I(className="bi bi-x-circle me-1"), "Cancelar"],
                id={"type": "btn-perfil-cancelar-mat", "index": m["id"]},
                size="sm", color="danger", outline=True,
            ))

        linhas.append(html.Tr([
            html.Td([
                html.Div(m["plano"], style={"color": "#0d6efd", "fontWeight": "600"}),
                html.Small(m["modalidade"], style={"color": "#888"}),
            ], style={"padding": "10px 14px"}),
            html.Td([
                html.Div(_fmt_data(m["data_inicio"])),
                html.Small(vence_txt, style={"color": "#888"}),
                html.Br(),
                html.Small("Vigência", style={"color": "#888", "display": "block", "marginTop": "4px"}),
                html.Small(vigencia_txt, style={"color": "#0d6efd", "fontWeight": "600"}),
                *( [html.Br(), html.Small(f"Encerrada em {data_enc_txt}", style={"color": "#888"})] if data_enc_txt else [] ),
            ], style={"padding": "10px 14px"}),
            html.Td(periodo, style={"padding": "10px 14px"}),
            html.Td(_fmt_brl(m.get("valor_contratado") or m.get("valor")),
                    style={"textAlign": "right", "fontWeight": "700",
                           "color": COR_PRIMARIA, "padding": "10px 14px"}),
            html.Td(
                [
                    html.Div([
                        icone, html.Span(" "), _badge_status(m["status"]),
                        *( [html.Span(f"  {motivo_txt}", style={"color": "#888", "fontSize": "11px"})] if motivo_txt else [] ),
                    ], className="mb-1" if (btn_receber or botoes_acao) else ""),
                    *( [html.Div(btn_receber, className="mb-1")] if btn_receber else [] ),
                    *( [html.Div(botoes_acao, style={"display": "flex", "justifyContent": "flex-end", "gap": "4px", "flexWrap": "wrap"})] if botoes_acao else [] ),
                ],
                style={"textAlign": "right", "whiteSpace": "nowrap",
                        "padding": "8px 14px"},
            ),
        ], style={"borderBottom": "1px solid #f0f0f0"}))

    if not linhas:
        return html.Div("Nenhuma matrícula encontrada.", className="text-muted p-3")

    return html.Table(
        [html.Thead(html.Tr([
            html.Th("Plano e Modalidade", style=_th),
            html.Th("Matrícula / Vigência", style=_th),
            html.Th("Periodicidade", style=_th),
            html.Th("Valor", style={**_th, "textAlign": "right"}),
            html.Th("", style={**_th, "width": "180px"}),
        ])),
         html.Tbody(linhas)],
        style={"width": "100%", "borderCollapse": "collapse"},
    )


# ── Perfil: modal cifrão ──────────────────────────────────────────────────

@app.callback(
    Output("modal-perfil-pag",          "is_open"),
    Output("modal-perfil-pag-titulo",   "children"),
    Output("store-perfil-pag-id",       "data"),
    Output("modal-perfil-pag-info",     "children"),
    Output("modal-perfil-pag-erro",     "children"),
    Output("btn-perfil-pag-confirmar",  "style"),
    Output("perfil-pag-form-row",       "style"),
    Output("store-perfil-refresh",      "data", allow_duplicate=True),
    Output("inp-perfil-pag-data",       "value"),
    Input({"type": "btn-perfil-ver-pag","index": ALL}, "n_clicks"),
    Input("btn-perfil-pag-lote",        "n_clicks"),
    Input("btn-perfil-pag-cancel",      "n_clicks"),
    Input("btn-perfil-pag-confirmar",   "n_clicks"),
    State("store-perfil-pag-id",        "data"),
    State("inp-perfil-pag-forma",       "value"),
    State("inp-perfil-pag-data",        "value"),
    State("inp-perfil-pag-obs",         "value"),
    State({"type": "chk-perfil-pag",  "index": ALL}, "id"),
    State({"type": "chk-perfil-pag",  "index": ALL}, "value"),
    State("store-perfil-refresh",       "data"),
    prevent_initial_call=True,
)
def controlar_modal_perfil_pag(ver_clicks, n_lote, n_cancel, n_confirmar,
                                pag_store, forma, data_pag, obs,
                                chk_ids, chk_vals, refresh):
    tid = callback_context.triggered_id
    valor = (callback_context.triggered[0].get("value") or 0) if callback_context.triggered else 0
    titulo_padrao = [html.I(className="bi bi-cash-coin me-2", style={"color": "#198754"}), "Detalhes do Pagamento"]

    if tid == "btn-perfil-pag-cancel":
        if not n_cancel:
            raise PreventUpdate
        return False, titulo_padrao, no_update, no_update, "", no_update, no_update, no_update, no_update

    if isinstance(tid, dict) and tid.get("type") == "btn-perfil-ver-pag":
        if valor <= 0:
            raise PreventUpdate
        pid = tid["index"]
        conn = get_conn()
        p = conn.execute("""
            SELECT p.*, a.nome AS aluno_nome, tp.nome AS plano, mod.nome AS modalidade
            FROM pagamentos p
            JOIN alunos a ON a.id = p.aluno_id
            JOIN matriculas m ON m.id = p.matricula_id
            JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
            JOIN modalidades mod ON mod.id = m.modalidade_id
            WHERE p.id = ?
        """, (pid,)).fetchone()
        conn.close()
        if not p:
            raise PreventUpdate
        p = dict(p)
        desconto = float(p.get("desconto") or 0)
        valor_liq = float(p["valor"]) - desconto
        data_sugerida = p.get("data_vencimento") or date.today().isoformat()
        if p["status"] == "pago":
            data_sugerida = p.get("data_pagamento") or data_sugerida
        info_items = [
            html.Strong(p["aluno_nome"]), html.Br(),
            html.Span(f"{p['plano']} / {p['modalidade']}", style={"color": "#555"}),
            "  |  Venc.: ", _fmt_data(p["data_vencimento"]), html.Br(),
            "Valor: ", html.Strong(_fmt_brl(p["valor"])),
        ]
        if desconto:
            info_items += [
                "  |  Desconto: ", html.Strong(_fmt_brl(desconto), style={"color": "#198754"}),
                "  |  A pagar: ", html.Strong(_fmt_brl(valor_liq), style={"color": COR_ACENTO}),
            ]
        if p["status"] == "pago":
            info_items += [html.Br(), "Pago em: ", _fmt_data(p["data_pagamento"]),
                           "  |  Forma: ", p.get("forma") or "—"]
        info = dbc.Alert(info_items, color="info")
        hide = {"display": "none"} if p["status"] == "pago" else {}
        return True, titulo_padrao, {"ids": [pid], "modo": "unico"}, info, "", hide, hide, no_update, data_sugerida

    if tid == "btn-perfil-pag-lote":
        if not n_lote:
            raise PreventUpdate
        selecionados = _pagamentos_marcados(chk_ids, chk_vals)
        if not selecionados:
            return True, [html.I(className="bi bi-cash-stack me-2", style={"color": "#198754"}), "Receber Selecionadas"], None, dbc.Alert("Selecione ao menos uma mensalidade em aberto.", color="warning"), "", {}, {}, no_update, date.today().isoformat()

        conn = get_conn()
        placeholders = ",".join("?" * len(selecionados))
        rows = conn.execute(f"""
            SELECT p.*, a.nome AS aluno_nome, tp.nome AS plano, mod.nome AS modalidade
            FROM pagamentos p
            JOIN alunos a ON a.id = p.aluno_id
            JOIN matriculas m ON m.id = p.matricula_id
            JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
            JOIN modalidades mod ON mod.id = m.modalidade_id
            WHERE p.id IN ({placeholders})
            ORDER BY date(p.data_vencimento), p.id
        """, tuple(selecionados)).fetchall()
        conn.close()
        rows = [dict(r) for r in rows if r["status"] in ("pendente", "vencido")]
        if not rows:
            return True, [html.I(className="bi bi-cash-stack me-2", style={"color": "#198754"}), "Receber Selecionadas"], None, dbc.Alert("Nenhuma mensalidade selecionada pode ser recebida agora.", color="warning"), "", {}, {}, no_update, date.today().isoformat()

        total = sum(float(r["valor"]) - float(r.get("desconto") or 0) for r in rows)
        info = dbc.Alert([
            html.Strong(rows[0]["aluno_nome"]), html.Br(),
            html.Span(f"{len(rows)} mensalidade(s) selecionada(s)"), html.Br(),
            html.Ul([
                html.Li(f"{_fmt_data(r['data_vencimento'])} — {r['plano']} / {r['modalidade']} — {_fmt_brl(float(r['valor']) - float(r.get('desconto') or 0))}")
                for r in rows
            ], className="mb-2 mt-2"),
            html.Span("Total: "), html.Strong(_fmt_brl(total)),
        ], color="info")
        return True, [html.I(className="bi bi-cash-stack me-2", style={"color": "#198754"}), "Receber Selecionadas"], {"ids": [r["id"] for r in rows], "modo": "lote"}, info, "", {}, {}, no_update, date.today().isoformat()

    if tid == "btn-perfil-pag-confirmar":
        if not n_confirmar:
            raise PreventUpdate
        if not pag_store or not pag_store.get("ids") or not forma:
            return no_update, no_update, no_update, no_update, "Selecione a forma de pagamento.", no_update, no_update, no_update, no_update
        if len(pag_store["ids"]) > 1:
            ok, msg = renov_mod.baixar_pagamentos_lote(pag_store["ids"], forma, data_pag, obs or "")
        else:
            ok, msg = renov_mod.baixar_pagamento(pag_store["ids"][0], forma, data_pag, obs or "")
        if ok:
            return False, titulo_padrao, None, "", "", {}, {}, (refresh or 0) + 1, no_update
        return no_update, no_update, no_update, no_update, msg, no_update, no_update, no_update, no_update

    raise PreventUpdate


# ── Perfil: modal lápis ───────────────────────────────────────────────────

@app.callback(
    Output("modal-perfil-edit-pag",         "is_open"),
    Output("store-perfil-edit-id",          "data"),
    Output("inp-perfil-edit-desconto",      "value"),
    Output("inp-perfil-edit-venc",          "value"),
    Output("inp-perfil-edit-dtpag",         "value"),
    Output("modal-perfil-edit-erro",        "children"),
    Output("store-perfil-refresh",          "data", allow_duplicate=True),
    Input({"type": "btn-perfil-edit-pag",   "index": ALL}, "n_clicks"),
    Input("btn-perfil-edit-cancel",         "n_clicks"),
    Input("btn-perfil-edit-salvar",         "n_clicks"),
    State("store-perfil-edit-id",           "data"),
    State("inp-perfil-edit-desconto",       "value"),
    State("inp-perfil-edit-venc",           "value"),
    State("inp-perfil-edit-dtpag",          "value"),
    State("store-perfil-refresh",           "data"),
    prevent_initial_call=True,
)
def controlar_modal_perfil_edit(edit_clicks, n_cancel, n_salvar,
                                  pag_id, desconto, venc, dtpag, refresh):
    tid = callback_context.triggered_id
    valor = (callback_context.triggered[0].get("value") or 0) if callback_context.triggered else 0

    if tid == "btn-perfil-edit-cancel":
        if not n_cancel:
            raise PreventUpdate
        return False, no_update, no_update, no_update, no_update, "", no_update

    if isinstance(tid, dict) and tid.get("type") == "btn-perfil-edit-pag":
        if valor <= 0:
            raise PreventUpdate
        pid = tid["index"]
        conn = get_conn()
        p = conn.execute("SELECT * FROM pagamentos WHERE id=?", (pid,)).fetchone()
        conn.close()
        if not p:
            raise PreventUpdate
        p = dict(p)
        return (True, pid, p.get("desconto") or 0,
                p.get("data_vencimento") or "", p.get("data_pagamento") or "",
                "", no_update)

    if tid == "btn-perfil-edit-salvar":
        if not n_salvar:
            raise PreventUpdate
        if not pag_id:
            return no_update, no_update, no_update, no_update, no_update, "Erro.", no_update
        ok, msg = renov_mod.editar_pagamento(
            pag_id,
            desconto=float(desconto) if desconto else 0.0,
            data_vencimento=venc or None,
            data_pagamento=dtpag or None,
        )
        if ok:
            return False, None, no_update, no_update, no_update, "", (refresh or 0) + 1
        return no_update, no_update, no_update, no_update, no_update, msg, no_update

    raise PreventUpdate


# ── Perfil: busca rápida de aluno ─────────────────────────────────────────────

@app.callback(
    Output("perfil-busca-resultados", "children"),
    Input("perfil-busca-aluno",        "value"),
)
def buscar_aluno_no_perfil(busca):
    if not busca or len(busca) < 2:
        return None
    lista = alunos_mod.listar_alunos(busca=busca)[:8]
    if not lista:
        return html.Div("Nenhum aluno encontrado.",
                        className="px-3 py-2 text-muted",
                        style={"background": "white", "borderRadius": "8px",
                               "boxShadow": "0 4px 16px rgba(0,0,0,.12)",
                               "marginTop": "4px"})
    return html.Div([
        dcc.Link(
            html.Div([
                html.Span(f"#{a['id']:04d} ",
                          style={"color": COR_ACENTO, "fontWeight": "700", "fontSize": "12px"}),
                html.Span(a["nome"], style={"fontWeight": "500"}),
                html.Span(f"  {a.get('telefone') or ''}",
                          style={"color": "#aaa", "fontSize": "12px"}),
                html.Span(" ", className="ms-2"),
                _badge_status(a["status"]),
            ], className="px-3 py-2 d-flex align-items-center",
               style={"borderBottom": "1px solid #f0f0f0", "cursor": "pointer"}),
            href=f"/alunos/{a['id']}",
            style={"textDecoration": "none", "color": "#333", "display": "block"},
            refresh=False,
        )
        for a in lista
    ], style={"background": "white", "borderRadius": "8px",
              "boxShadow": "0 4px 16px rgba(0,0,0,.15)",
              "marginTop": "4px", "overflow": "hidden"})


# ── Perfil: esconde Modalidade quando plano já tem uma ──────────────────────

@app.callback(
    Output("perfil-mat-modal-row", "style"),
    Output("inp-perfil-mat-modal", "value"),
    Input("inp-perfil-mat-plano",  "value"),
)
def toggle_perfil_modalidade_field(plano_id):
    if not plano_id:
        return {}, None
    conn = get_conn()
    p = conn.execute(
        "SELECT modalidade_id FROM tipos_plano WHERE id=?", (int(plano_id),)
    ).fetchone()
    conn.close()
    if p and p["modalidade_id"]:
        return {"display": "none"}, str(p["modalidade_id"])
    return {}, None


@app.callback(
    Output("perfil-acao-modal-row", "style"),
    Output("inp-perfil-acao-modal", "value"),
    Input("inp-perfil-acao-plano", "value"),
)
def toggle_perfil_acao_modalidade_field(plano_id):
    if not plano_id:
        return {}, None
    conn = get_conn()
    p = conn.execute(
        "SELECT modalidade_id FROM tipos_plano WHERE id=?", (int(plano_id),)
    ).fetchone()
    conn.close()
    if p and p["modalidade_id"]:
        return {"display": "none"}, str(p["modalidade_id"])
    return {}, None


# ── Perfil: modal nova matrícula ──────────────────────────────────────────

@app.callback(
    Output("modal-perfil-nova-mat",      "is_open"),
    Output("modal-perfil-mat-erro",      "children"),
    Output("store-perfil-refresh",       "data", allow_duplicate=True),
    Input("btn-perfil-nova-mat",         "n_clicks"),
    Input("btn-perfil-mat-cancel",       "n_clicks"),
    Input("btn-perfil-mat-confirmar",    "n_clicks"),
    State("inp-perfil-mat-plano",        "value"),
    State("inp-perfil-mat-modal",        "value"),
    State("inp-perfil-mat-inicio",       "value"),
    State("store-perfil-aluno-id",       "data"),
    State("store-perfil-refresh",        "data"),
    prevent_initial_call=True,
)
def controlar_modal_perfil_mat(n_abrir, n_cancel, n_confirmar,
                                plano_id, modal_id, inicio, aluno_id, refresh):
    tid = callback_context.triggered_id
    if tid == "btn-perfil-nova-mat":
        if not n_abrir:
            raise PreventUpdate
        return True, "", no_update
    if tid == "btn-perfil-mat-cancel":
        if not n_cancel:
            raise PreventUpdate
        return False, "", no_update
    if tid == "btn-perfil-mat-confirmar":
        if not n_confirmar:
            raise PreventUpdate
        if not aluno_id or not plano_id or not modal_id:
            return no_update, "Selecione plano e modalidade.", no_update
        _, msg = alunos_mod.criar_matricula(
            aluno_id, int(plano_id), int(modal_id), inicio
        )
        return False, "", (refresh or 0) + 1
    raise PreventUpdate


@app.callback(
    Output("modal-perfil-acao-mat", "is_open"),
    Output("modal-perfil-acao-titulo", "children"),
    Output("modal-perfil-acao-info", "children"),
    Output("store-perfil-acao-mat", "data"),
    Output("inp-perfil-acao-motivo", "value"),
    Output("inp-perfil-acao-data", "value"),
    Output("perfil-acao-novo-plano-wrap", "style"),
    Output("inp-perfil-acao-plano", "value"),
    Output("inp-perfil-acao-modal", "value"),
    Output("inp-perfil-acao-renovacao", "value"),
    Output("inp-perfil-acao-renovacao", "style"),
    Output("btn-perfil-acao-confirmar", "children"),
    Output("btn-perfil-acao-confirmar", "color"),
    Output("modal-perfil-acao-erro", "children"),
    Output("store-perfil-refresh", "data", allow_duplicate=True),
    Input({"type": "btn-perfil-mudar-plano", "index": ALL}, "n_clicks"),
    Input({"type": "btn-perfil-cancelar-mat", "index": ALL}, "n_clicks"),
    Input("btn-perfil-acao-cancel", "n_clicks"),
    Input("btn-perfil-acao-confirmar", "n_clicks"),
    State("store-perfil-acao-mat", "data"),
    State("inp-perfil-acao-motivo", "value"),
    State("inp-perfil-acao-data", "value"),
    State("inp-perfil-acao-plano", "value"),
    State("inp-perfil-acao-modal", "value"),
    State("inp-perfil-acao-renovacao", "value"),
    State("store-perfil-refresh", "data"),
    prevent_initial_call=True,
)
def controlar_modal_acao_matricula(mudar_clicks, cancelar_clicks, n_cancel, n_confirmar,
                                   acao_store, motivo, data_mudanca, plano_id,
                                   modal_id, renovacao, refresh):
    tid = callback_context.triggered_id
    valor = (callback_context.triggered[0].get("value") or 0) if callback_context.triggered else 0
    oculto = {"display": "none"}
    visivel = {"display": "block"}

    if tid == "btn-perfil-acao-cancel":
        if not n_cancel:
            raise PreventUpdate
        return False, no_update, no_update, None, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, "", no_update

    if isinstance(tid, dict) and tid.get("type") in ("btn-perfil-mudar-plano", "btn-perfil-cancelar-mat"):
        if valor <= 0:
            raise PreventUpdate
        mat_id = tid["index"]
        conn = get_conn()
        mat = conn.execute("""
            SELECT m.*, a.nome AS aluno_nome, tp.nome AS plano_nome, mod.nome AS modalidade_nome
            FROM matriculas m
            JOIN alunos a ON a.id = m.aluno_id
            JOIN tipos_plano tp ON tp.id = m.tipo_plano_id
            JOIN modalidades mod ON mod.id = m.modalidade_id
            WHERE m.id=?
        """, (mat_id,)).fetchone()
        conn.close()
        if not mat:
            raise PreventUpdate
        mat = dict(mat)
        tipo_acao = "mudanca" if tid.get("type") == "btn-perfil-mudar-plano" else "cancelamento"
        info = [
            html.Strong(mat["aluno_nome"]), html.Br(),
            html.Span(f"Plano atual: {mat['plano_nome']} / {mat['modalidade_nome']}"), html.Br(),
            html.Span(f"Início: {_fmt_data(mat['data_inicio'])}  |  Fim atual: {_fmt_data(mat['data_fim'])}"),
        ]
        return (
            True,
            "Mudar Plano" if tipo_acao == "mudanca" else "Cancelar Matrícula",
            info,
            {"matricula_id": mat_id, "acao": tipo_acao},
            "mudanca_de_plano" if tipo_acao == "mudanca" else "cancelamento_de_plano",
            date.today().isoformat(),
            visivel if tipo_acao == "mudanca" else oculto,
            None,
            None,
            True,
            visivel if tipo_acao == "mudanca" else oculto,
            [html.I(className="bi bi-arrow-left-right me-1"), "Confirmar mudança"] if tipo_acao == "mudanca" else [html.I(className="bi bi-x-circle me-1"), "Confirmar cancelamento"],
            "primary" if tipo_acao == "mudanca" else "danger",
            "",
            no_update,
        )

    if tid == "btn-perfil-acao-confirmar":
        if not n_confirmar:
            raise PreventUpdate
        if not acao_store or not acao_store.get("matricula_id"):
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, "Selecione a matrícula novamente.", no_update
        if not motivo or not data_mudanca:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, "Informe o motivo e a data da mudança.", no_update

        if acao_store.get("acao") == "mudanca":
            if not plano_id or not modal_id:
                return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, "Selecione o novo plano e a nova modalidade.", no_update
            ok, msg, _ = alunos_mod.trocar_plano_matricula(
                acao_store["matricula_id"],
                int(plano_id),
                int(modal_id),
                data_mudanca,
                motivo=motivo,
                renovacao_auto=bool(renovacao),
            )
        else:
            ok, msg = alunos_mod.encerrar_matricula(
                acao_store["matricula_id"],
                data_mudanca=data_mudanca,
                motivo=motivo,
                status_destino="cancelado",
            )

        if ok:
            return False, no_update, no_update, None, no_update, no_update, no_update, None, None, True, no_update, no_update, no_update, "", (refresh or 0) + 1
        return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, msg, no_update

    raise PreventUpdate


# ══════════════════════════════════════════════════════════════════════════
# ABA: PRÉ-CADASTROS
# ══════════════════════════════════════════════════════════════════════════

def _aba_precadastros():
    return html.Div([
        html.H5([html.I(className="bi bi-person-plus me-2"), "Pré-cadastros (Link Público)"],
                className="fw-bold mb-3", style={"color": COR_PRIMARIA}),

        dbc.Alert([
            html.I(className="bi bi-link-45deg me-2"),
            "Link para novos alunos: ",
            html.Strong("/cadastro", id="link-cadastro"),
            " — compartilhe este endereço com interessados.",
        ], color="info", className="mb-3"),

        html.Div(id="tabela-precadastros"),

        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Aprovar Pré-cadastro")),
            dbc.ModalBody([
                dcc.Store(id="store-pre-id"),
                html.Div(id="modal-pre-info", className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Plano *"),
                             dbc.Select(id="inp-pre-plano",
                                        options=[{"label": p["nome"], "value": p["id"]}
                                                 for p in alunos_mod.listar_planos()])], md=6),
                    dbc.Col([dbc.Label("Modalidade *"),
                             dbc.Select(id="inp-pre-modal",
                                        options=[{"label": m["nome"], "value": m["id"]}
                                                 for m in alunos_mod.listar_modalidades()])], md=6),
                ]),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-modal-pre-cancel", color="secondary", outline=True),
                dbc.Button("Aprovar e Cadastrar", id="btn-modal-pre-aprovar", color="success"),
            ]),
        ], id="modal-pre", is_open=False),
    ])


@app.callback(
    Output("tabela-precadastros", "children"),
    Input("store-tab-ativa", "data"),
)
def atualizar_precadastros(tab):
    if tab != "precadastros":
        raise PreventUpdate
    lista = alunos_mod.listar_precadastros()
    if not lista:
        return dbc.Alert("Nenhum pré-cadastro pendente.", color="success")
    rows = [html.Tr([
        html.Td(p["nome"]),
        html.Td(p["telefone"] or "—"),
        html.Td(p["email"] or "—"),
        html.Td(p["plano"] or "—"),
        html.Td(p["modalidade"] or "—"),
        html.Td(_fmt_data(p["criado_em"])),
        html.Td(dbc.Button([html.I(className="bi bi-check-lg me-1"), "Aprovar"],
                           id={"type": "btn-aprovar-pre", "index": p["id"]},
                           color="success", size="sm")),
    ]) for p in lista]
    return dbc.Table(
        [html.Thead(html.Tr([html.Th("Nome"), html.Th("Telefone"), html.Th("E-mail"),
                              html.Th("Plano"), html.Th("Modalidade"), html.Th("Data"), html.Th("")])),
         html.Tbody(rows)],
        bordered=True, hover=True, size="sm", responsive=True
    )


@app.callback(
    Output("modal-pre",       "is_open"),
    Output("store-pre-id",    "data"),
    Output("modal-pre-info",  "children"),
    Input({"type": "btn-aprovar-pre", "index": ALL}, "n_clicks"),
    Input("btn-modal-pre-cancel",     "n_clicks"),
    Input("btn-modal-pre-aprovar",    "n_clicks"),
    State("store-pre-id",   "data"),
    State("inp-pre-plano",  "value"),
    State("inp-pre-modal",  "value"),
    prevent_initial_call=True,
)
def controlar_modal_pre(aprovar_clicks, n_cancel, n_confirmar, pre_id, plano_id, modal_id):
    tid = callback_context.triggered_id
    if tid == "btn-modal-pre-cancel":
        return False, no_update, no_update
    if isinstance(tid, dict) and tid.get("type") == "btn-aprovar-pre":
        pid = tid["index"]
        lista = alunos_mod.listar_precadastros()
        p = next((x for x in lista if x["id"] == pid), None)
        if not p:
            raise PreventUpdate
        info = dbc.Alert([html.Strong(p["nome"]), html.Br(),
                          f"Tel: {p['telefone'] or '—'}  |  E-mail: {p['email'] or '—'}"], color="info")
        return True, pid, info
    if tid == "btn-modal-pre-aprovar":
        if not pre_id or not plano_id or not modal_id:
            raise PreventUpdate
        alunos_mod.aprovar_precadastro(pre_id, int(plano_id), int(modal_id))
        return False, None, ""
    raise PreventUpdate


# ══════════════════════════════════════════════════════════════════════════
# ABA: PLANOS E MODALIDADES
# ══════════════════════════════════════════════════════════════════════════

def _aba_planos():
    planos      = alunos_mod.listar_planos(apenas_ativos=False)
    modalidades = alunos_mod.listar_modalidades(apenas_ativas=False)

    def _row_plano(p):
        btn_toggle = dbc.Button(
            "Desativar" if p["ativo"] else "Ativar",
            id={"type": "btn-toggle-plano", "index": p["id"]},
            color="danger" if p["ativo"] else "success",
            size="sm", outline=True, className="me-1",
        )
        btn_edit = dbc.Button(
            html.I(className="bi bi-pencil"),
            id={"type": "btn-edit-plano", "index": p["id"]},
            color="warning", size="sm", outline=True,
        )
        mod_txt = p.get("modalidade_nome") or "—"
        return html.Tr([
            html.Td(p["nome"]),
            html.Td(html.Small(mod_txt, style={"color": "#0d6efd" if mod_txt != "—" else "#aaa"})),
            html.Td(f"{p['meses']} mês(es)"),
            html.Td(_fmt_brl(p["valor"])),
            html.Td(_badge_status("ativo" if p["ativo"] else "cancelado")),
            html.Td([btn_edit, btn_toggle]),
        ])

    def _row_modal(m):
        acoes = [
            dbc.Button(html.I(className="bi bi-pencil"),
                       id={"type": "btn-edit-modal", "index": m["id"]},
                       color="warning", size="sm", outline=True, className="me-1"),
            dbc.Button("Desativar" if m["ativo"] else "Ativar",
                       id={"type": "btn-toggle-modal", "index": m["id"]},
                       color="danger" if m["ativo"] else "success",
                       size="sm", outline=True, className="me-1"),
        ]
        if not m["ativo"]:
            acoes.append(
                dbc.Button(html.I(className="bi bi-trash"),
                           id={"type": "btn-del-modal", "index": m["id"]},
                           color="danger", size="sm", title="Excluir permanentemente")
            )
        return html.Tr([
            html.Td(m["nome"]),
            html.Td(_badge_status("ativo" if m["ativo"] else "cancelado")),
            html.Td(acoes),
        ])

    return html.Div([
        html.H5([html.I(className="bi bi-card-list me-2"), "Planos e Modalidades"],
                className="fw-bold mb-3", style={"color": COR_PRIMARIA}),

        html.Div(id="planos-conteudo", children=[
            dbc.Row([
                # ── Planos ──────────────────────────────────────────────
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.Strong("Tipos de Plano"),
                            dbc.Button([html.I(className="bi bi-plus-lg me-1"), "Novo Plano"],
                                       id="btn-novo-plano", color="danger", size="sm",
                                       className="float-end",
                                       style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
                        ]),
                        dbc.CardBody(
                            dbc.Table([
                                html.Thead(html.Tr([
                                    html.Th("Nome"), html.Th("Modalidade"),
                                    html.Th("Duração"), html.Th("Valor"),
                                    html.Th("Status"), html.Th(""),
                                ])),
                                html.Tbody([_row_plano(p) for p in planos]),
                            ], bordered=True, hover=True, size="sm", responsive=True)
                        ),
                    ], className="shadow-sm"),
                ], md=7),

                # ── Modalidades ──────────────────────────────────────────
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            html.Strong("Modalidades"),
                            dbc.Button([html.I(className="bi bi-plus-lg me-1"), "Nova Modalidade"],
                                       id="btn-nova-modal", color="danger", size="sm",
                                       className="float-end",
                                       style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
                        ]),
                        dbc.CardBody(
                            dbc.Table([
                                html.Thead(html.Tr([html.Th("Nome"), html.Th("Status"), html.Th("")])),
                                html.Tbody([_row_modal(m) for m in modalidades]),
                            ], bordered=True, hover=True, size="sm", responsive=True)
                        ),
                    ], className="shadow-sm"),
                ], md=5),
            ]),
        ]),

        # ── Modal: Plano ─────────────────────────────────────────────────
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-plano-titulo")),
            dbc.ModalBody([
                dcc.Store(id="store-plano-id"),
                dbc.Row([
                    dbc.Col([dbc.Label("Nome do plano *"), dbc.Input(id="inp-plano-nome")], md=8),
                    dbc.Col([dbc.Label("Duração (meses) *"),
                             dbc.Select(id="inp-plano-meses",
                                        options=[{"label": "1 mês (Mensal)",       "value": "1"},
                                                 {"label": "3 meses (Trimestral)", "value": "3"},
                                                 {"label": "6 meses (Semestral)",  "value": "6"},
                                                 {"label": "12 meses (Anual)",     "value": "12"}])], md=4),
                ], className="mb-3"),
                dbc.Row([
                    dbc.Col([dbc.Label("Valor (R$) *"),
                             dbc.Input(id="inp-plano-valor", type="number", min=0, step=0.01)], md=6),
                    dbc.Col([
                        dbc.Label("Modalidade (embutida no plano)"),
                        dbc.Select(id="inp-plano-modal-id",
                                   options=[{"label": "— Nenhuma (genérico) —", "value": ""}] +
                                           [{"label": m["nome"], "value": str(m["id"])}
                                            for m in alunos_mod.listar_modalidades()]),
                        html.Small("Se preenchida, o aluno não precisará escolher modalidade na matrícula.",
                                   className="text-muted", style={"fontSize": "11px"}),
                    ], md=6),
                ], className="mb-3"),
                # Opções de atualização — só aparecem ao editar (não ao criar)
                html.Div(id="plano-opcoes-atualizacao", children=[
                    html.Hr(),
                    html.P("Se o valor mudou, o que deseja atualizar?",
                           className="fw-semibold mb-2", style={"fontSize": "13px"}),
                    dbc.Checkbox(id="inp-plano-atualizar-vigentes",
                                 label="Atualizar valor das matrículas ativas (próximas renovações usarão o novo valor)",
                                 value=False, className="mb-1"),
                    dbc.Checkbox(id="inp-plano-atualizar-pendentes",
                                 label="Atualizar também cobranças pendentes em aberto",
                                 value=False, className="mb-1"),
                    dbc.Alert([
                        html.I(className="bi bi-shield-check me-1"),
                        "Pagamentos já confirmados nunca são alterados — o histórico é preservado."
                    ], color="success", className="mt-2 py-2", style={"fontSize": "12px"}),
                ], style={"display": "none"}),
                html.Div(id="modal-plano-erro", className="text-danger mt-2", style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-modal-plano-cancel", color="secondary", outline=True),
                dbc.Button("Salvar",   id="btn-modal-plano-salvar", color="danger",
                           style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
            ]),
        ], id="modal-plano", is_open=False),

        # ── Modal: Modalidade ─────────────────────────────────────────────
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-modalidade-titulo")),
            dbc.ModalBody([
                dcc.Store(id="store-modal-id"),
                # Seção: criar nova
                html.Div(id="div-nova-modalidade", children=[
                    dbc.Label("Nome da nova modalidade", className="fw-semibold"),
                    dbc.Input(id="inp-modalidade-nome", placeholder="Ex: Boxe, CrossFit...",
                              className="mb-1"),
                    html.Small("Existentes: " + ", ".join(
                        m["nome"] for m in alunos_mod.listar_modalidades(apenas_ativas=False)
                    ), className="text-muted d-block mb-3", style={"fontSize": "11px"}),
                ]),
                html.Div(id="modal-modalidade-erro", className="text-danger mt-1",
                         style={"fontSize": "13px"}),
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancelar", id="btn-modal-modalidade-cancel", color="secondary", outline=True),
                dbc.Button("Salvar",   id="btn-modal-modalidade-salvar", color="danger",
                           style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
            ]),
        ], id="modal-modalidade", is_open=False),
    ])


# ── Callbacks: Planos ──────────────────────────────────────────────────────

@app.callback(
    Output("modal-plano",                  "is_open"),
    Output("modal-plano-titulo",           "children"),
    Output("store-plano-id",               "data"),
    Output("inp-plano-nome",               "value"),
    Output("inp-plano-meses",              "value"),
    Output("inp-plano-valor",              "value"),
    Output("modal-plano-erro",             "children"),
    Output("planos-conteudo",              "children", allow_duplicate=True),
    Output("plano-opcoes-atualizacao",     "style"),
    Output("inp-plano-modal-id",           "value"),
    Input("btn-novo-plano",                            "n_clicks"),
    Input({"type": "btn-edit-plano",   "index": ALL},  "n_clicks"),
    Input({"type": "btn-toggle-plano", "index": ALL},  "n_clicks"),
    Input("btn-modal-plano-cancel",                    "n_clicks"),
    Input("btn-modal-plano-salvar",                    "n_clicks"),
    State("store-plano-id",                "data"),
    State("inp-plano-nome",                "value"),
    State("inp-plano-meses",               "value"),
    State("inp-plano-valor",               "value"),
    State("inp-plano-modal-id",            "value"),
    State("inp-plano-atualizar-vigentes",  "value"),
    State("inp-plano-atualizar-pendentes", "value"),
    prevent_initial_call=True,
)
def gerenciar_planos(n_novo, n_edit, n_toggle, n_cancel, n_salvar,
                     plano_id, nome, meses, valor, modal_id,
                     atualizar_vigentes, atualizar_pendentes):
    ctx = callback_context
    valor_clicado = ctx.triggered[0].get("value") or 0
    tid = ctx.triggered_id
    if tid not in ("btn-modal-plano-cancel", "btn-modal-plano-salvar"):
        if valor_clicado <= 0:
            raise PreventUpdate

    _oculto  = {"display": "none"}
    _visivel = {"display": "block"}

    if tid == "btn-novo-plano":
        return True, "Novo Plano", None, "", "1", None, "", no_update, _oculto, ""

    if isinstance(tid, dict) and tid.get("type") == "btn-edit-plano":
        from app.database import get_conn as _gc
        c = _gc()
        p = dict(c.execute("SELECT * FROM tipos_plano WHERE id=?", (tid["index"],)).fetchone())
        c.close()
        if not p:
            raise PreventUpdate
        return (True, f"Editar — {p['nome']}", p["id"],
                p["nome"], str(p["meses"]), p["valor"], "", no_update, _visivel,
                str(p.get("modalidade_id") or ""))

    if isinstance(tid, dict) and tid.get("type") == "btn-toggle-plano":
        from app.database import get_conn as _gc
        c = _gc()
        p = c.execute("SELECT ativo FROM tipos_plano WHERE id=?", (tid["index"],)).fetchone()
        novo = 0 if p["ativo"] else 1
        c.execute("UPDATE tipos_plano SET ativo=? WHERE id=?", (novo, tid["index"]))
        c.commit(); c.close()
        return False, no_update, no_update, no_update, no_update, no_update, "", _rebuild_planos(), no_update, no_update

    if tid == "btn-modal-plano-cancel":
        return False, no_update, no_update, "", None, None, "", no_update, _oculto, ""

    if tid == "btn-modal-plano-salvar":
        if not nome or not meses or valor is None:
            return no_update, no_update, no_update, no_update, no_update, no_update, \
                   "Preencha todos os campos obrigatórios.", no_update, no_update, no_update
        from app.database import get_conn as _gc
        try:
            c = _gc()
            nome_fmt = nome.strip()
            mid = int(modal_id) if modal_id else None
            if plano_id:
                c.execute(
                    "UPDATE tipos_plano SET nome=?, meses=?, valor=?, modalidade_id=? WHERE id=?",
                    (nome_fmt, int(meses), float(valor), mid, int(plano_id))
                )
                if atualizar_vigentes:
                    c.execute("""
                        UPDATE matriculas SET valor_contratado=?
                        WHERE tipo_plano_id=?
                          AND status IN ('ativo','aguardando_pagamento','inadimplente')
                    """, (float(valor), int(plano_id)))
                if atualizar_pendentes:
                    c.execute("""
                        UPDATE pagamentos SET valor=?
                        WHERE matricula_id IN (
                            SELECT id FROM matriculas
                            WHERE tipo_plano_id=?
                              AND status IN ('ativo','aguardando_pagamento','inadimplente')
                        ) AND status IN ('pendente','vencido')
                    """, (float(valor), int(plano_id)))
            else:
                c.execute(
                    "INSERT INTO tipos_plano (nome, meses, valor, modalidade_id) VALUES (?,?,?,?)",
                    (nome_fmt, int(meses), float(valor), mid)
                )
            c.commit()
            c.close()
        except Exception as e:
            logger.error("Erro ao salvar plano: %s", e)
            return no_update, no_update, no_update, no_update, no_update, no_update, \
                   f"Erro: {e}", no_update, no_update, no_update
        try:
            novo_conteudo = _rebuild_planos()
        except Exception as e:
            logger.error("Erro ao reconstruir planos: %s", e)
            novo_conteudo = no_update
        return False, no_update, no_update, "", "1", None, "", novo_conteudo, _oculto, ""

    raise PreventUpdate


def _rebuild_planos():
    """Reconstrói o conteúdo do div planos-conteudo após qualquer alteração."""
    planos      = alunos_mod.listar_planos(apenas_ativos=False)
    modalidades = alunos_mod.listar_modalidades(apenas_ativas=False)

    def _row_p(p):
        mod_txt = p.get("modalidade_nome") or "—"
        return html.Tr([
            html.Td(p["nome"]),
            html.Td(html.Small(mod_txt, style={"color": "#0d6efd" if mod_txt != "—" else "#aaa"})),
            html.Td(f"{p['meses']} mês(es)"),
            html.Td(_fmt_brl(p["valor"])),
            html.Td(_badge_status("ativo" if p["ativo"] else "cancelado")),
            html.Td([
                dbc.Button(html.I(className="bi bi-pencil"),
                           id={"type": "btn-edit-plano", "index": p["id"]},
                           color="warning", size="sm", outline=True, className="me-1"),
                dbc.Button("Desativar" if p["ativo"] else "Ativar",
                           id={"type": "btn-toggle-plano", "index": p["id"]},
                           color="danger" if p["ativo"] else "success", size="sm", outline=True),
            ]),
        ])

    def _row_m(m):
        acoes = [
            dbc.Button(html.I(className="bi bi-pencil"),
                       id={"type": "btn-edit-modal", "index": m["id"]},
                       color="warning", size="sm", outline=True, className="me-1"),
            dbc.Button("Desativar" if m["ativo"] else "Ativar",
                       id={"type": "btn-toggle-modal", "index": m["id"]},
                       color="danger" if m["ativo"] else "success", size="sm", outline=True,
                       className="me-1"),
        ]
        # Botão excluir só aparece para modalidades inativas (canceladas)
        if not m["ativo"]:
            acoes.append(
                dbc.Button(html.I(className="bi bi-trash"),
                           id={"type": "btn-del-modal", "index": m["id"]},
                           color="danger", size="sm", className="ms-1",
                           title="Excluir permanentemente")
            )
        return html.Tr([
            html.Td(m["nome"]),
            html.Td(_badge_status("ativo" if m["ativo"] else "cancelado")),
            html.Td(acoes),
        ])

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.Strong("Tipos de Plano"),
                    dbc.Button([html.I(className="bi bi-plus-lg me-1"), "Novo Plano"],
                               id="btn-novo-plano", color="danger", size="sm",
                               className="float-end",
                               style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
                ]),
                dbc.CardBody(dbc.Table([
                    html.Thead(html.Tr([
                        html.Th("Nome"), html.Th("Modalidade"),
                        html.Th("Duração"), html.Th("Valor"),
                        html.Th("Status"), html.Th(""),
                    ])),
                    html.Tbody([_row_p(p) for p in planos]),
                ], bordered=True, hover=True, size="sm", responsive=True)),
            ], className="shadow-sm"),
        ], md=7),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.Strong("Modalidades"),
                    dbc.Button([html.I(className="bi bi-plus-lg me-1"), "Nova Modalidade"],
                               id="btn-nova-modal", color="danger", size="sm",
                               className="float-end",
                               style={"backgroundColor": COR_ACENTO, "borderColor": COR_ACENTO}),
                ]),
                dbc.CardBody(dbc.Table([
                    html.Thead(html.Tr([html.Th("Nome"), html.Th("Status"), html.Th("")])),
                    html.Tbody([_row_m(m) for m in modalidades]),
                ], bordered=True, hover=True, size="sm", responsive=True)),
            ], className="shadow-sm"),
        ], md=5),
    ])


# ── Callbacks: Modalidades ─────────────────────────────────────────────────

@app.callback(
    Output("modal-modalidade",        "is_open"),
    Output("modal-modalidade-titulo", "children"),
    Output("store-modal-id",          "data"),
    Output("inp-modalidade-nome",     "value"),
    Output("modal-modalidade-erro",   "children"),
    Output("planos-conteudo",         "children", allow_duplicate=True),
    Input("btn-nova-modal",                            "n_clicks"),
    Input({"type": "btn-edit-modal",   "index": ALL}, "n_clicks"),
    Input({"type": "btn-toggle-modal", "index": ALL}, "n_clicks"),
    Input("btn-modal-modalidade-cancel",               "n_clicks"),
    Input("btn-modal-modalidade-salvar",               "n_clicks"),
    State("store-modal-id",       "data"),
    State("inp-modalidade-nome",  "value"),
    prevent_initial_call=True,
)
def gerenciar_modalidades(n_nova, n_edit, n_toggle, n_cancel, n_salvar, modal_id, nome):
    ctx = callback_context
    # Guard: ignora disparos de componentes recriados (n_clicks=0)
    valor = ctx.triggered[0].get("value") or 0
    tid   = ctx.triggered_id
    # Salvar e Cancelar não têm valor numérico — só aplicar guard em cliques de botões de ação
    if tid not in ("btn-modal-modalidade-cancel", "btn-modal-modalidade-salvar"):
        if valor <= 0:
            raise PreventUpdate

    if tid == "btn-nova-modal":
        return True, "Nova Modalidade", None, "", "", no_update

    if isinstance(tid, dict) and tid.get("type") == "btn-edit-modal":
        from app.database import get_conn as _gc
        c = _gc()
        m = c.execute("SELECT * FROM modalidades WHERE id=?", (tid["index"],)).fetchone()
        c.close()
        if not m:
            raise PreventUpdate
        return True, f"Renomear — {m['nome']}", m["id"], m["nome"], "", no_update

    if isinstance(tid, dict) and tid.get("type") == "btn-toggle-modal":
        from app.database import get_conn as _gc
        c = _gc()
        m = c.execute("SELECT ativo FROM modalidades WHERE id=?", (tid["index"],)).fetchone()
        novo = 0 if m["ativo"] else 1
        c.execute("UPDATE modalidades SET ativo=? WHERE id=?", (novo, tid["index"]))
        c.commit(); c.close()
        return False, no_update, no_update, no_update, "", _rebuild_planos()

    if tid == "btn-modal-modalidade-cancel":
        return False, no_update, no_update, "", "", no_update

    if tid == "btn-modal-modalidade-salvar":
        nome_val = (nome or "").strip().upper()
        if not nome_val:
            return no_update, no_update, no_update, no_update, "Selecione ou digite o nome.", no_update
        from app.database import get_conn as _gc
        c = _gc()
        try:
            if modal_id:
                # Renomear existente
                c.execute("UPDATE modalidades SET nome=? WHERE id=?", (nome_val, modal_id))
            else:
                # Criar nova — verifica se já existe (mesmo nome, qualquer status)
                existe = c.execute(
                    "SELECT id FROM modalidades WHERE upper(nome)=upper(?)", (nome_val,)
                ).fetchone()
                if existe:
                    c.close()
                    return (no_update, no_update, no_update, no_update,
                            f"'{nome_val}' já existe. Use o lápis para editar ou escolha outro nome.", no_update)
                c.execute("INSERT INTO modalidades (nome) VALUES (?)", (nome_val,))
            c.commit()
        except Exception as e:
            c.close()
            return no_update, no_update, no_update, no_update, f"Erro: {e}", no_update
        c.close()
        return False, no_update, no_update, "", "", _rebuild_planos()

    raise PreventUpdate


# ── Callback: Excluir modalidade ───────────────────────────────────────────

@app.callback(
    Output("planos-conteudo", "children", allow_duplicate=True),
    Input({"type": "btn-del-modal", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def excluir_modalidade(clicks):
    ctx = callback_context
    if not ctx.triggered or not any(v for v in clicks if v):
        raise PreventUpdate
    tid = ctx.triggered_id
    if not isinstance(tid, dict) or tid.get("type") != "btn-del-modal":
        raise PreventUpdate

    modal_id = tid["index"]
    from app.database import get_conn as _gc
    c = _gc()
    # Verifica se há matrículas usando esta modalidade
    em_uso = c.execute(
        "SELECT COUNT(*) FROM matriculas WHERE modalidade_id=?", (modal_id,)
    ).fetchone()[0]
    if em_uso:
        c.close()
        # Não exclui — retorna tabela sem alteração mas com aviso
        # (por limitação do Dash, apenas reconstruímos sem excluir)
        logger.warning("Tentativa de excluir modalidade %s em uso (%d matrículas).", modal_id, em_uso)
        raise PreventUpdate
    c.execute("DELETE FROM modalidades WHERE id=?", (modal_id,))
    c.commit()
    c.close()
    return _rebuild_planos()


# ══════════════════════════════════════════════════════════════════════════
# EXCEL: EXPORTAÇÃO / IMPORTAÇÃO
# ══════════════════════════════════════════════════════════════════════════

import base64 as _b64
from app.excel_io import (exportar_alunos, exportar_pagamentos,
                           importar_alunos, gerar_modelo_importacao)


@app.callback(
    Output("download-alunos-xlsx", "data"),
    Input("btn-export-alunos", "n_clicks"),
    prevent_initial_call=True,
)
def exportar_alunos_cb(n):
    conteudo = exportar_alunos()
    return dcc.send_bytes(conteudo, filename=f"alunos_{date.today()}.xlsx")


@app.callback(
    Output("download-modelo-xlsx", "data"),
    Input("btn-modelo-alunos", "n_clicks"),
    prevent_initial_call=True,
)
def baixar_modelo_cb(n):
    conteudo = gerar_modelo_importacao()
    return dcc.send_bytes(conteudo, filename="modelo_importacao_alunos.xlsx")


@app.callback(
    Output("alerta-importacao",  "children"),
    Output("tabela-alunos",      "children", allow_duplicate=True),
    Input("upload-alunos",       "contents"),
    State("upload-alunos",       "filename"),
    State("filtro-status-aluno", "value"),
    prevent_initial_call=True,
)
def importar_alunos_cb(contents, filename, status_filtro):
    if not contents:
        raise PreventUpdate
    _, b64 = contents.split(",", 1)
    dados_bytes = _b64.b64decode(b64)
    resultado = importar_alunos(dados_bytes)

    inseridos = resultado["inseridos"]
    erros     = resultado["erros"]

    if erros and not inseridos:
        alerta = dbc.Alert([html.B("Erro na importação: "), erros[0]], color="danger", dismissable=True)
    elif erros:
        alerta = dbc.Alert([
            html.B(f"{inseridos} aluno(s) importado(s) com avisos. "),
            html.Br(),
            *[html.Div(e, style={"fontSize": "12px"}) for e in erros[:5]],
        ], color="warning", dismissable=True)
    else:
        primeiro = resultado.get("primeiro", "—")
        ultimo   = resultado.get("ultimo",   "—")
        alerta = dbc.Alert([
            html.B(f"{inseridos} aluno(s) importado(s) com sucesso! "),
            html.Span(f"Numerados de {primeiro} a {ultimo}.", style={"fontSize": "13px"}),
        ], color="success", dismissable=True)

    from app.alunos import listar_alunos
    lista = listar_alunos(status=status_filtro or None)
    # rebuild tabela inline
    from dash import html as _html
    rows = []
    for a in lista:
        plano_txt = a.get("plano_ativo") or "—"
        rows.append(html.Tr([
            html.Td(f"#{a['id']:04d}", style={"fontWeight": "600", "color": COR_ACENTO, "whiteSpace": "nowrap"}),
            html.Td(a["nome"]),
            html.Td(a["telefone"] or "—"),
            html.Td(html.Small(plano_txt, style={"color": "#555"})),
            html.Td(_badge_status(a["status"])),
            html.Td(dbc.Button(html.I(className="bi bi-pencil"),
                               id={"type": "btn-edit-aluno", "index": a["id"]},
                               color="warning", size="sm", outline=True)),
        ]))
    tabela = dbc.Table(
        [html.Thead(html.Tr([html.Th("Nº"), html.Th("Nome"), html.Th("Telefone"),
                              html.Th("Plano / Modalidade"), html.Th("Status"), html.Th("")])),
         html.Tbody(rows)],
        bordered=True, hover=True, size="sm", responsive=True
    ) if lista else dbc.Alert("Nenhum aluno encontrado.", color="light")

    return alerta, tabela


@app.callback(
    Output("download-pagamentos-xlsx", "data"),
    Input("btn-export-pagamentos", "n_clicks"),
    State("filtro-pag-periodo", "value"),
    State("filtro-pag-ini",     "value"),
    State("filtro-pag-fim",     "value"),
    prevent_initial_call=True,
)
def exportar_pagamentos_cb(n, periodo, dt_ini, dt_fim):
    hoje = date.today()
    if periodo == "hoje":
        mes, ano = hoje.month, hoje.year
    elif periodo == "mes":
        mes, ano = hoje.month, hoje.year
    else:
        mes, ano = None, None
    conteudo = exportar_pagamentos(mes=mes, ano=ano)
    sufixo = f"{str(mes or '').zfill(2)}_{ano}" if mes and ano else str(hoje)
    return dcc.send_bytes(conteudo, filename=f"pagamentos_{sufixo}.xlsx")


# ══════════════════════════════════════════════════════════════════════════
# ABA: USUÁRIOS
# ══════════════════════════════════════════════════════════════════════════

def _aba_usuarios(sessao):
    if sessao.get("nivel") != "admin":
        return dbc.Alert("Acesso restrito a administradores.", color="danger")

    usuarios = auth_mod.listar_usuarios()

    rows = [html.Tr([
        html.Td(u["nome"]),
        html.Td(u["login"]),
        html.Td(dbc.Badge(u["nivel"], color="primary")),
        html.Td(_badge_status("ativo" if u["ativo"] else "cancelado")),
        html.Td(_fmt_data(u["criado_em"])),
    ]) for u in usuarios]

    return html.Div([
        html.H5([html.I(className="bi bi-people me-2"), "Usuários do Sistema"],
                className="fw-bold mb-3", style={"color": COR_PRIMARIA}),
        dbc.Table([
            html.Thead(html.Tr([html.Th("Nome"), html.Th("Login"),
                                 html.Th("Nível"), html.Th("Status"), html.Th("Criado em")])),
            html.Tbody(rows),
        ], bordered=True, hover=True, size="sm", responsive=True),
        dbc.Alert("Gerenciamento de usuários — em breve: criação, alteração de senha e desativação.", color="info", className="mt-3"),
    ])
