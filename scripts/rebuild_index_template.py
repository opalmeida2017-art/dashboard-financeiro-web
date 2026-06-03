# one-off script to rebuild index.html
from pathlib import Path

root = Path(__file__).resolve().parent.parent
scripts = (root / "templates/index.html").read_text(encoding="utf-8")
idx = scripts.find("{% block scripts %}")
scripts_part = scripts[idx:]
scripts_part = scripts_part.replace(
    "document.querySelector('.filters form')",
    "document.querySelector('.dash-filters form')",
)
scripts_part = scripts_part.replace(
    "btnColeta.textContent = 'Atualizando...';",
    "btnColeta.textContent = 'Atualizando…';",
)
scripts_part = scripts_part.replace(
    "btnColeta.textContent = 'Atualizar Dados';",
    "btnColeta.textContent = '↻ Atualizar SATI';",
)

content = (root / "templates/index_dashboard_content.html").read_text(encoding="utf-8")
(root / "templates/index.html").write_text(content + scripts_part, encoding="utf-8")
print("done")
