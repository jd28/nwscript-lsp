# nwscriptd

The LSP is built on [pygls](https://github.com/openlawlibrary/pygls) and [rollnw](https://github.com/jd28/rollnw).  It is derived from the [Pygls Playground](https://github.com/openlawlibrary/pygls/tree/main/examples/vscode-playground) and aims, at this point, only to be a tested bed for implementing LSP features.  A more robust implementation will come later maybe integrating with [nasher.cfg](https://github.com/squattingmonk/nasher#nashercfg).  For now only the current document path will be added to the include path of the script context resman.

That the testbed extension is for vscode is out of simplicity, obviously plugins for any LSP client emacs, (neo)vim, etc will be supported.

Currently, it implements:
* Completions
* Hover
* Workspace Diagnostics
* Document Symbols
* Signature Help

## Setup - Neovim

1. Install required package
   ```
   python -m pip install rollnw
   ```

2. Install the language server
   ```
   python -m pip install nwscriptd
   ```

Note: Sometimes "--break-system-packages" is needed to install
   ```
    python -m pip install --break-system-packages rollnw
    python -m pip install --break-system-packages nwscriptd
   ```

3. Make sure ``nwscriptd`` is on your PATH!

4. Setup neovim config - Obviously people's tastes will differ here.
   ```lua
   require("config.lazy")

   vim.api.nvim_exec(
   [[
   autocmd FileType nwscript setlocal lsp
   ]],
   false
   )

   local lspconfig = require("lspconfig")
   local configs = require("lspconfig.configs")

   if not configs.nwscript_language_server then
   configs.nwscript_language_server = {
      default_config = {
         cmd = { "nwscriptd" },
         filetypes = { "nwscript" },
         root_dir = lspconfig.util.root_pattern(".git", "nasher.cfg"),
      },
   }
   end

   lspconfig.nwscript_language_server.setup({
   on_attach = function(client, bufnr)
      -- Custom on_attach function (optional)
      print("nwscript language server attached!")

      require("lsp_signature").on_attach({
         bind = true, -- This is mandatory, otherwise border config won't get registered.
         handler_opts = {
         border = "rounded",
         },
      }, bufnr)

      -- Enable snippet support (if your completion plugin supports snippets)
      vim.bo[bufnr].expandtab = false
      vim.bo[bufnr].shiftwidth = 4
   end,
   settings = {
      ["nwscriptd"] = {
         disableSnippets = "on",
      },
   },
   })

   -- Global mappings.
   -- See `:help vim.diagnostic.*` for documentation on any of the below functions
   vim.keymap.set("n", "<space>e", vim.diagnostic.open_float)
   vim.keymap.set("n", "[d", vim.diagnostic.goto_prev)
   vim.keymap.set("n", "]d", vim.diagnostic.goto_next)
   vim.keymap.set("n", "<space>q", vim.diagnostic.setloclist)

   -- Use LspAttach autocommand to only map the following keys
   -- after the language server attaches to the current buffer
   vim.api.nvim_create_autocmd("LspAttach", {
   group = vim.api.nvim_create_augroup("UserLspConfig", {}),
   callback = function(ev)
      -- Enable completion triggered by <c-x><c-o>
      vim.bo[ev.buf].omnifunc = "v:lua.vim.lsp.omnifunc"

      -- Buffer local mappings.
      -- See `:help vim.lsp.*` for documentation on any of the below functions
      local opts = { buffer = ev.buf }
      vim.keymap.set("n", "gD", vim.lsp.buf.declaration, opts)
      vim.keymap.set("n", "gd", vim.lsp.buf.definition, opts)
      vim.keymap.set("n", "K", vim.lsp.buf.hover, opts)
      vim.keymap.set("n", "gi", vim.lsp.buf.implementation, opts)
      vim.keymap.set("n", "<C-k>", vim.lsp.buf.signature_help, opts)
      vim.keymap.set("n", "<space>wa", vim.lsp.buf.add_workspace_folder, opts)
      vim.keymap.set("n", "<space>wr", vim.lsp.buf.remove_workspace_folder, opts)
      vim.keymap.set("n", "<space>wl", function()
         print(vim.inspect(vim.lsp.buf.list_workspace_folders()))
      end, opts)
      vim.keymap.set("n", "<space>D", vim.lsp.buf.type_definition, opts)
      vim.keymap.set("n", "<space>rn", vim.lsp.buf.rename, opts)
      vim.keymap.set({ "n", "v" }, "<space>ca", vim.lsp.buf.code_action, opts)
      vim.keymap.set("n", "gr", vim.lsp.buf.references, opts)
      vim.keymap.set("n", "<space>f", function()
         vim.lsp.buf.format({ async = true })
      end, opts)
   end,
   })
   ```
