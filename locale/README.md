# Localisation tutorial

## If you are looking to create custom localisations, look no further!

#### The first step is to generate the `.pot` files, which are the templates to use for creating `.po` files, which are going to be your localised version of the template.
##### You can do this by running `regentemplate.py` in `locale\templates` under Windows, or the code in `readme.txt` if you are under a different OS, just change the parameters.

#### For the following steps, I recommend downloading [PoEdit](https://poedit.net/download), it is highly useful for editing `.po` and `.pot` files.
##### You should open up the `.pot` file you want to localize with PoEdit, then click `Create new translation`, choose your language, then create new folder in `locale` with your language's two-letter code (e.g: `en` for English), and create a sub-directory titled `LC_MESSAGES`. Save your `.po` file there with the same name as the `.pot` source-file!
##### You can now start translating! Once done, navigate to `File>Compile to MO...` and save it with the same name as the `.po` file. 
##### That's it!
