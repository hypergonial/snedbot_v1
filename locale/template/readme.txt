These are the template files you can use to update/create your own localisations!
Do not change these files directly!
If you wish to regenerate the .pot files from code, run the included script!

####

If the script does not work for you, you can use these commands manually.

Execute this in folder of main.py in cmd to generate a pot file for main.py
py -3.9 "C:\Program Files\Python39\Tools\i18n\pygettext.py" -d main main.py

To compile a .po file into a .mo file, use this (poedit has this functionality built-in):
py -3.9 "C:\Program Files\Python39\Tools\i18n\msgfmt.py" -o main.mo main