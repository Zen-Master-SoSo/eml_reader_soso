# eml_reader_soso

A relatively lightweight graphical .eml file reader based on PyQt

## Preview

<img width="608" height="629" alt="main-window" src="https://github.com/user-attachments/assets/f77be376-cfd0-48fa-88ea-4ebb0d98442d" />

## Install

```bash
$ pip install eml_reader_soso
$ eml-reader-soso --install
```

The "―install" option only works on XDG-compliant systems, which, AFAIK,
includes every major Linux distribution. It makes Email Reader SoSo available
from your desktop environment, such as the Gnome application menu or the Ubuntu
Unity Dash. Installation is per-user, NOT system-wide.

## Usage

Usage is straightforward. You can open a file from the command line:

```bash
$ eml-reader-soso Saved-Email.eml
```

Open the program without a file and open a file from the menu. Or click the
Open File button on the toolbar.

The "Go Previous" and "Go Next" commands go to the previous/next .eml file
found in the same directory as the one you are currently reading.

### Print

The subject, date, from, to, cc, and attachment fields are only shown on the 
first page.

<img width="698" height="268" alt="print-preview" src="https://github.com/user-attachments/assets/549c4d13-054b-4cc8-8f2f-a71227331901" />

