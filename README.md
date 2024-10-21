[![PyPI version](https://badge.fury.io/py/arclight.svg)](https://badge.fury.io/py/arclight)

# Arclight.py

These are tools related to the Arclight project

## Installation

Ideally, create and activate a Python venv.

```
pip install arclight
```

To uninstall delete the venv created above.

## [nwscriptd](arclight/nwscriptd/README.md)

A language server for nwscript. See the [README](arclight/nwscriptd/README.md).

## nwscript-lint

A wrapper around the script parser and resolver

```
usage: nwscript-lint [-h] [-I INCLUDE] [--no-install] [--no-user] scripts [scripts ...]

A linter for nwscript.

positional arguments:
  scripts               List of scripts to lint.

options:
  -h, --help            show this help message and exit
  -I INCLUDE, --include INCLUDE
                        Include path(s).
  --no-install          Disable loading game install files.
  --no-user             Disable user install files.
```

Sample output:

![output](screenshots/nwscript-lint-2024-10-21.png)
