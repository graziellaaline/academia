# -*- coding: utf-8 -*-
"""
Ponto de entrada — Centro de Treinamento RV
Executa: venv/Scripts/python.exe main.py
"""

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.FileHandler("academia.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

from app.database    import criar_tabelas, migrar, seed_inicial
from app.renovacao   import verificar_vencimentos
from app.dashboard   import app as dash_app
from app.cadastro_pub.routes import bp as bp_cadastro

# Inicializa banco e dados padrão
criar_tabelas()
migrar()
seed_inicial()
verificar_vencimentos()

# Registra rotas públicas (Flask)
dash_app.server.register_blueprint(bp_cadastro)

if __name__ == "__main__":
    from waitress import serve
    from app.version import __version__, SYSTEM_NAME
    print(f"\n{'='*55}")
    print(f"  {SYSTEM_NAME}  {__version__}")
    print(f"  http://localhost:8060")
    print(f"  Cadastro público: http://localhost:8060/cadastro")
    print(f"{'='*55}\n")
    serve(dash_app.server, host="0.0.0.0", port=8060)
