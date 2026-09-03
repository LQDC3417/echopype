from pathlib import Path


def test_gui_launcher_uses_project_python():
    launcher = Path(__file__).parents[1] / "start_gui.bat"

    assert '"D:\\Program Files\\Anaconda\\python.exe" -m src.app' in launcher.read_text(
        encoding="utf-8"
    )
