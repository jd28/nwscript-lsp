# nwscript-lsp

The LSP is built on [pygls](https://github.com/openlawlibrary/pygls) and [rollnw](https://github.com/jd28/rollnw).  It is derived from the [Pygls Playground](https://github.com/openlawlibrary/pygls/tree/main/examples/vscode-playground) and aims, at this point, only to be a tested bed for implementing LSP features.  A more robust implementation will come later maybe integrating with [nasher.cfg](https://github.com/squattingmonk/nasher#nashercfg).

That the testbed extension is for vscode is out of simplicity, obviously plugins for any LSP client emacs, (neo)vim, etc will be supported.

Currently, it implements:
* Completions
* Hover
* Workspace Diagnostics
* Document Symbos

## Setup

### Install Server Dependencies

Open a terminal in the repository's root directory

1. Create a virtual environment
   ```
   python -m venv env
   ```

1. Install pygls
   ```
   python -m pip install -r requirements.txt
   ```

### Install Client Dependencies

Open terminal in the same directory as this file and execute following commands:

1. Install node dependencies

   ```
   npm install
   ```
1. Compile the extension

   ```
   npm run compile
   ```
   Alternatively you can run `npm run watch` if you are going to be actively working on the extension itself.

### Run Extension

1. Open this directory in VS Code

1. The playground relies on the [Python extension for VSCode](https://marketplace.visualstudio.com/items?itemName=ms-python.python) for choosing the appropriate Python environment in which to run the example language servers.
   If you haven't already, you will need to install it and reload the window.

1. Open the Run and Debug view (`ctrl + shift + D`)

1. Select `Launch Client` and press `F5`, this will open a second VSCode window with the `vscode-playground` extension enabled.

1. You will need to make sure that VSCode is using a virtual environment that contains an installation of `pygls`.
   The `Python: Select Interpreter` command can be used to pick the correct one.

   Alternatively, you can set the `pygls.server.pythonPath` option in the `.vscode/settings.json` file
