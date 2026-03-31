"""Build script — đóng gói thành .exe."""

import subprocess
import sys
import os

def build():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(project_dir, "assets", "icon.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "AutoCapCut",
        "--icon", icon_path,
        # Bundle customtkinter assets
        "--collect-all", "customtkinter",
        # Bundle our assets
        "--add-data", f"assets;assets",
        # Clean
        "--clean",
        "--noconfirm",
        # Entry
        "main.py",
    ]

    print(f"Building in: {project_dir}")
    print(f"Command: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=project_dir, check=True)
    print("\nBuild complete! Output: dist/AutoCapCut.exe")


if __name__ == "__main__":
    build()
