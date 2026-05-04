# ---------------------------------------------------------------------------
# Versão do sistema — ÚNICA fonte de verdade
#
# Formato: V{major}.{minor}.{patch}
#   major  — mudança estrutural incompatível (resetar minor e patch)
#   minor  — novo recurso / funcionalidade (incrementar; resetar patch)
#   patch  — correção de bug (2 dígitos: 01, 02 … 99; incrementar)
#
# Como atualizar:
#   1. Edite APENAS esta variável.
#   2. Reinicie o servidor.
#   O resto do código lê daqui — nunca escreva a versão em outro lugar.
# ---------------------------------------------------------------------------

__version__ = "V1.4.20"
SYSTEM_NAME  = "Centro de Treinamento RV"


def get_version() -> str:
    """Lê a versão diretamente do arquivo — sempre atualizada sem reiniciar."""
    import re
    from pathlib import Path
    try:
        txt = Path(__file__).read_text(encoding="utf-8")
        m = re.search(r'__version__\s*=\s*"([^"]+)"', txt)
        return m.group(1) if m else __version__
    except Exception:
        return __version__
