import os
import platform
from pathlib import Path

if platform.system() == "Windows":
    print("Initialized in Windows mode.")
    print("Generating new .pot files...\n")
    # Note, this script will only work if you preserved the default filestructure
    # Generates .pot files from the python scripts in the project

    # Change it to your path of pygettextpy, OS and Py version specific
    pygettextpy_path = "C:\Program Files\Python39\Tools\i18n\pygettext.py"
    # Script location
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # Project folder location
    PROJECT_DIR = Path(BASE_DIR).parents[1]
    # Extensions folder location
    EXTENSIONS_DIR = Path(PROJECT_DIR, "extensions")
    os.chdir(PROJECT_DIR)
    print("Generated .pot template files in the following location(s):")
    os.system(f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "main")}" main.py"')
    print(f"main.pot @ {BASE_DIR}")
    os.chdir(EXTENSIONS_DIR)
    os.system(
        f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "admin_commands")}" admin_commands.py"'
    )
    print(f"admin_commands.pot @ {BASE_DIR}")
    os.system(
        f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "misc_commands")}" misc_commands.py"'
    )
    print(f"misc_commands.pot @ {BASE_DIR}")
    os.system(
        f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "matchmaking")}" matchmaking.py"'
    )
    print(f"matchmaking.pot @ {BASE_DIR}")
    os.system(f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "tags")}" tags.py"')
    print(f"tags.pot @ {BASE_DIR}")
    os.system(
        f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "moderation")}" moderation.py"'
    )
    print(f"moderation.pot @ {BASE_DIR}")
    os.system(
        f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "timers")}" timers.py"'
    )
    print(f"timers.pot @ {BASE_DIR}")
    os.system(f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "fun")}" fun.py"')
    print(f"fun.pot @ {BASE_DIR}")
    os.system(
        f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "annoverse")}" annoverse.py"'
    )
    print(f"annoverse.pot @ {BASE_DIR}")
    os.system(f'cmd /c "py "{pygettextpy_path}" -d "{Path(BASE_DIR, "help")}" help.py"')
    print(f"help.pot @ {BASE_DIR}")

    print()
    print("Finished! Press enter to close...")
    input()
else:
    print("Initialized in Linux mode.")
    print("Generating new .pot files...\n")
    # Note, this script will only work if you preserved the default filestructure
    # Generates .pot files from the python scripts in the project

    # Change it to your path of pygettextpy, OS and Python version specific
    pygettextpy_path = "/usr/lib/python3.9/Tools/i18n/pygettext.py"
    # Script location
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    # Project folder location
    PROJECT_DIR = Path(BASE_DIR).parents[1]
    # Extensions folder location
    EXTENSIONS_DIR = Path(PROJECT_DIR, "extensions")
    os.chdir(PROJECT_DIR)
    print("Generated .pot template files in the following location(s):")
    os.system(f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "main")}" main.py')
    print(f"main.pot @ {BASE_DIR}")
    os.chdir(EXTENSIONS_DIR)
    os.system(
        f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "admin_commands")}" admin_commands.py'
    )
    print(f"admin_commands.pot @ {BASE_DIR}")
    os.system(
        f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "misc_commands")}" misc_commands.py'
    )
    print(f"misc_commands.pot @ {BASE_DIR}")
    os.system(
        f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "matchmaking")}" matchmaking.py'
    )
    print(f"matchmaking.pot @ {BASE_DIR}")
    os.system(f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "tags")}" tags.py')
    print(f"tags.pot @ {BASE_DIR}")
    os.system(
        f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "moderation")}" moderation.py'
    )
    print(f"moderation.pot @ {BASE_DIR}")
    os.system(f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "timers")}" timers.py')
    print(f"timers.pot @ {BASE_DIR}")
    os.system(f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "fun")}" fun.py')
    print(f"fun.pot @ {BASE_DIR}")
    os.system(
        f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "annoverse")}" annoverse.py'
    )
    print(f"annoverse.pot @ {BASE_DIR}")
    os.system(f'python3 "{pygettextpy_path}" -d "{Path(BASE_DIR, "help")}" help.py')
    print(f"help.pot @ {BASE_DIR}")

    print()
    print("Finished! Terminating...")
