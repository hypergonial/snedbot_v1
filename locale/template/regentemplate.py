import os
from pathlib import Path
import platform
if platform.system() != "Windows":
    print("Only works on Windows!")
    input()
else :
    print("Generating new .pot files...\n")
    #Note, this script will only work if you preserved the default filestructure
    #Generates .pot files from the python scripts in the project

    #Change it to your path of pygettextpy, OS and Py version specific
    pygettextpy_path = "C:\Program Files\Python39\Tools\i18n\pygettext.py"
    #Change it to your Python version (only x.x, not x.x.x)
    py_ver = 3.9
    #Script location
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    #Project folder location
    PROJECT_DIR = Path(BASE_DIR).parents[1]
    #Extensions folder location
    EXTENSIONS_DIR = Path(PROJECT_DIR, "extensions")
    os.chdir(PROJECT_DIR)
    os.system(f'cmd /c "py -{py_ver} "{pygettextpy_path}" -d "{Path(BASE_DIR, "main")}" main.py"')
    os.chdir(EXTENSIONS_DIR)
    os.system(f'cmd /c "py -{py_ver} "{pygettextpy_path}" -d "{Path(BASE_DIR, "admin_commands")}" admin_commands.py"')
    os.system(f'cmd /c "py -{py_ver} "{pygettextpy_path}" -d "{Path(BASE_DIR, "misc_commands")}" misc_commands.py"')
    os.system(f'cmd /c "py -{py_ver} "{pygettextpy_path}" -d "{Path(BASE_DIR, "matchmaking")}" matchmaking.py"')
    os.system(f'cmd /c "py -{py_ver} "{pygettextpy_path}" -d "{Path(BASE_DIR, "tags")}" tags.py"')

    #User feedback
    print("Generated .pot template files in the following locations:")
    print(f"main.pot @ {BASE_DIR}")
    print(f"admin_commands.pot @ {BASE_DIR}")
    print(f"misc_commands.pot @ {BASE_DIR}")
    print(f"matchmaking.pot @ {BASE_DIR}")
    print(f"tags.pot @ {BASE_DIR}")
    input()
