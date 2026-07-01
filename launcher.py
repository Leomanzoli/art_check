"""
ART Check – Launcher
Empacota o aplicativo Streamlit em um executável standalone.
Ao executar, inicia o servidor Streamlit e abre o navegador automaticamente.
"""

import sys
import os
import subprocess
import socket
import webbrowser
import time
import signal


def get_free_port():
    """Encontra uma porta livre."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def get_base_path():
    """Retorna o diretório base (funciona tanto em dev quanto empacotado)."""
    if getattr(sys, "frozen", False):
        # Executando como executável PyInstaller
        return sys._MEIPASS
    else:
        return os.path.dirname(os.path.abspath(__file__))


def main():
    base_path = get_base_path()
    app_path = os.path.join(base_path, "app.py")
    config_dir = os.path.join(base_path, ".streamlit")

    port = get_free_port()
    url = f"http://localhost:{port}"

    print("=" * 50)
    print("  ART Check – Análise de Risco de Tarefa")
    print("=" * 50)
    print(f"  Iniciando servidor na porta {port}...")
    print(f"  Acesse: {url}")
    print("  Pressione Ctrl+C para encerrar")
    print("=" * 50)

    env = os.environ.copy()
    env["STREAMLIT_SERVER_PORT"] = str(port)
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env["STREAMLIT_THEME_PRIMARY_COLOR"] = "#1E88E5"
    env["STREAMLIT_THEME_BACKGROUND_COLOR"] = "#FAFAFA"
    env["STREAMLIT_THEME_SECONDARY_BACKGROUND_COLOR"] = "#E3F2FD"
    env["STREAMLIT_THEME_TEXT_COLOR"] = "#212121"
    env["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] = "200"

    if getattr(sys, "frozen", False):
        # Quando empacotado, usar o streamlit embutido
        from streamlit.web import cli as stcli
        sys.argv = [
            "streamlit", "run", app_path,
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.maxUploadSize", "200",
            "--global.developmentMode", "false",
        ]

        # Abrir navegador após um curto delay
        def open_browser():
            time.sleep(3)
            webbrowser.open(url)

        import threading
        threading.Thread(target=open_browser, daemon=True).start()

        stcli.main()
    else:
        # Em desenvolvimento, usar subprocess
        cmd = [
            sys.executable, "-m", "streamlit", "run", app_path,
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ]

        proc = subprocess.Popen(cmd, env=env)

        # Abrir navegador
        time.sleep(3)
        webbrowser.open(url)

        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
