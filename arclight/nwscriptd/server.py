import argparse
import asyncio
import json
import glob
import re
import time
import uuid
import os
import rollnw
from typing import Optional, List

from lsprotocol import types as lsp

from pygls.capabilities import get_capability
from pygls.server import LanguageServer

from . import markup


def find_files_with_extension(start_path, file_extension, unique_paths=set()):
    for root, dirs, files in os.walk(start_path):
        for file in files:
            if file.endswith(file_extension):
                unique_paths.add(root)
                break

    return list(unique_paths)


class NWScriptLanguageServer(LanguageServer):
    def __init__(self, *args):
        super().__init__(*args)


SERVER = NWScriptLanguageServer("nwscriptd", "v0.6.0")


def _choose_markup(server: NWScriptLanguageServer) -> lsp.MarkupKind:
    """Returns the preferred or first of supported markup kinds."""
    markup_supported = get_capability(
        server.client_capabilities,
        "text_document.completion.completion_item.documentation_format",
        [lsp.MarkupKind.PlainText],
    )

    return markup_supported[0]


def _convert_position(position: rollnw.script.SourcePosition) -> lsp.Position:
    return lsp.Position(position.line - 1, position.column)


def _convert_range(range: rollnw.script.SourceRange) -> lsp.Range:
    return lsp.Range(_convert_position(range.start), _convert_position(range.end))


def _convert_severity(severity: rollnw.script.DiagnosticSeverity) -> lsp.DiagnosticSeverity:
    if severity == rollnw.script.DiagnosticSeverity.error:
        return lsp.DiagnosticSeverity.Error
    elif severity == rollnw.script.DiagnosticSeverity.hint:
        return lsp.DiagnosticSeverity.Hint
    elif severity == rollnw.script.DiagnosticSeverity.warning:
        return lsp.DiagnosticSeverity.Warning
    else:
        return lsp.DiagnosticSeverity.Information


def _load_nss(uri) -> rollnw.script.Nss:
    text_doc = SERVER.workspace.get_text_document(uri)
    SERVER.show_message_log(f"Parsing nwscript file: {text_doc.filename}")

    paths = find_files_with_extension(
        SERVER.workspace.root_path, ".nss", set(os.path.dirname(text_doc.path)))
    ctx = rollnw.script.Context(paths)

    nss = rollnw.script.Nss.from_string(
        text_doc.source, ctx, text_doc.filename == "nwscript.nss")
    nss.parse()
    nss.process_includes()
    nss.resolve()

    return nss, text_doc


def _validate(ls, params):
    nss, text_doc = _load_nss(params.text_document.uri)

    diagnostics = []
    error_lines = set()
    for diag in nss.diagnostics():
        if diag.severity == rollnw.script.DiagnosticSeverity.error:
            if diag.location.start.line in error_lines:
                continue
            else:
                error_lines.add(diag.location.start.line)

        d = lsp.Diagnostic(
            range=_convert_range(diag.location),
            message=diag.message,
            source=type(SERVER).__name__,
            severity=_convert_severity(diag.severity))
        diagnostics.append(d)

    ls.publish_diagnostics(params.text_document.uri, diagnostics)


def log_to_output(
    message: str, msg_type: lsp.MessageType = lsp.MessageType.Log
) -> None:
    SERVER.show_message_log(message, msg_type)


@SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: lsp.DidOpenTextDocumentParams):
    """Text document did open notification."""
    _validate(ls, params)


@SERVER.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params: lsp.DidChangeTextDocumentParams):
    """Text document did change notification."""
    _validate(ls, params)


@SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: NWScriptLanguageServer, params: lsp.DidCloseTextDocumentParams):
    """Text document did close notification."""
    server.show_message("Text Document Did Close")


def _symbol_to_doc_symbol(script, symbol):
    name = symbol.decl.identifier()
    range = symbol.decl.range()
    selection_range = symbol.decl.selection_range()

    if isinstance(symbol.decl, rollnw.script.VarDecl):
        kind = lsp.SymbolKind.Variable
        detail = "(variable)"
    elif isinstance(symbol.decl, rollnw.script.FunctionDefinition):
        kind = lsp.SymbolKind.Function
        detail = "(function)"
    elif isinstance(symbol.decl, rollnw.script.FunctionDecl):
        kind = lsp.SymbolKind.Function
        detail = "(function)"
    elif isinstance(symbol.decl, rollnw.script.StructDecl):
        kind = lsp.SymbolKind.Struct
        detail = "(struct)"

    return lsp.DocumentSymbol(name=name,
                              kind=kind,
                              range=_convert_range(range),
                              selection_range=_convert_range(selection_range),
                              detail=detail)


@SERVER.feature(
    lsp.TEXT_DOCUMENT_DOCUMENT_SYMBOL,
    lsp.DocumentSymbolOptions()
)
def text_document_document_symbol(
    server: NWScriptLanguageServer,
    params: lsp.DocumentSymbolParams
) -> [lsp.DocumentSymbol]:
    nss, text_doc = _load_nss(params.text_document.uri)
    result = [_symbol_to_doc_symbol(nss, symbol) for symbol in nss.exports()]
    return result


@SERVER.feature(lsp.TEXT_DOCUMENT_DIAGNOSTIC)
def text_document_diagnostic(params: lsp.DiagnosticOptions):
    """Returns diagnostic report."""

    _validate(SERVER, params)


def _function_to_snippet(script, function):
    id = function.identifier()

    params = []
    for i in range(len(function)):
        if function[i].init is not None:
            break

        params.append(
            f"${{{i+1}:{script.type_name(function[i])} {function[i].identifier()}}}")

    if len(params) == 0:
        return f"{id}()"

    return f"{id}({', '.join(params)})"


def _symbol_to_completion_item(script, symbol):
    label = symbol.decl.identifier()
    insert_text = None

    if symbol.kind == rollnw.script.SymbolKind.variable:
        kind = lsp.CompletionItemKind.Variable
        detail = "(variable)"
    elif symbol.kind == rollnw.script.SymbolKind.type:
        kind = lsp.CompletionItemKind.Struct
        detail = "(struct)"
    else:
        kind = lsp.CompletionItemKind.Function
        detail = "(function)"
        insert_text_format = lsp.InsertTextFormat.Snippet
        if isinstance(symbol.decl, rollnw.script.FunctionDefinition):
            insert_text = _function_to_snippet(script, symbol.decl.decl)
        else:
            insert_text = _function_to_snippet(script, symbol.decl)

    if insert_text:
        return lsp.CompletionItem(label=label,
                                  kind=kind,
                                  detail=detail,
                                  insert_text=insert_text,
                                  insert_text_format=insert_text_format)
    else:
        return lsp.CompletionItem(label=label,
                                  kind=kind,
                                  detail=detail)


@SERVER.feature(
    lsp.TEXT_DOCUMENT_COMPLETION,
    lsp.CompletionOptions(trigger_characters=["."]),
)
def completions(params: Optional[lsp.CompletionParams] = None) -> lsp.CompletionList:
    """Returns completion items."""

    if params is None:
        return lsp.CompletionList(is_incomplete=False, items=[])

    nss, text_doc = _load_nss(params.text_document.uri)

    items = []
    needle = text_doc.word_at_position(params.position)

    if text_doc.lines[params.position.line][params.position.character-1] == ".":
        nl = text_doc.lines[params.position.line][:params.position.character-1]
        word = nl.split()[-1]
        character = text_doc.lines[params.position.line].find(word)
        completions = nss.complete_dot(
            word, params.position.line + 1, character, True)
    else:
        completions = nss.complete_at(
            needle, params.position.line + 1, params.position.character, True)

    SERVER.show_message_log(str(len(completions)))
    items = [_symbol_to_completion_item(nss, item) for item in completions]

    return lsp.CompletionList(
        is_incomplete=False,
        items=items
    )


@SERVER.feature(lsp.TEXT_DOCUMENT_HOVER)
def text_document_hover(server: NWScriptLanguageServer, params: lsp.HoverParams) -> Optional[lsp.Hover]:
    nss, text_doc = _load_nss(params.text_document.uri)

    needle = text_doc.word_at_position(params.position)
    decl_info = nss.locate_symbol(
        needle, params.position.line + 1, params.position.character)

    if decl_info.decl is None:
        return

    markup_kind = _choose_markup(server)
    if isinstance(decl_info.decl, rollnw.script.VarDecl):
        return lsp.Hover(markup.hover_var_decl(decl_info, markup_kind))
    elif isinstance(decl_info.decl, rollnw.script.FunctionDecl):
        return lsp.Hover(markup.hover_func_decl(nss, decl_info, markup_kind))
    elif isinstance(decl_info.decl, rollnw.script.FunctionDefinition):
        return lsp.Hover(markup.hover_func_decl(nss, decl_info, markup_kind))
    elif isinstance(decl_info.decl, rollnw.script.StructDecl):
        return lsp.Hover(markup.hover_struct_decl(nss, decl_info, markup_kind))
    else:
        return


@SERVER.feature(lsp.TEXT_DOCUMENT_INLAY_HINT)
def inlay_hint(params: lsp.InlayHintParams) -> List[lsp.InlayHint]:
    nss, text_doc = _load_nss(params.text_document.uri)

    src_range = rollnw.script.SourceRange()
    src_range.start.line = params.range.start.line + 1
    src_range.start.column = params.range.start.character
    src_range.end.line = params.range.end.line + 1
    src_range.end.column = params.range.end.character
    hints = nss.inlay_hints(src_range)

    log_to_output(str(len(hints)))

    result = []
    for hint in hints:
        result.append(lsp.InlayHint(lsp.Position(
            hint.position.line - 1, hint.position.column),  f"{hint.message}: "))

    return result


@SERVER.feature(lsp.TEXT_DOCUMENT_SIGNATURE_HELP,
                lsp.SignatureHelpOptions(trigger_characters=["(", ","]))
def text_document_signature_help(params: lsp.SignatureHelpParams) -> Optional[lsp.SignatureHelp]:
    nss, text_doc = _load_nss(params.text_document.uri)

    sig_help = nss.signature_help(
        params.position.line + 1, params.position.character)

    if not isinstance(sig_help.expr, rollnw.script.CallExpression):
        return

    signatures = []
    markup_kind = _choose_markup(SERVER)

    if isinstance(sig_help.decl, rollnw.script.FunctionDecl):
        sig = lsp.SignatureInformation(sig_help.decl.identifier())
        sig.parameters = [lsp.ParameterInformation(
            decl.identifier(),
            markup.code_block(f"""{nss.type_name(decl)} {
                decl.identifier()}""", markup_kind)
        ) for decl in sig_help.decl]
        signatures.append(sig)
    elif isinstance(sig_help.decl, rollnw.script.FunctionDefinition):
        sig = lsp.SignatureInformation(sig_help.decl.decl.identifier())
        sig.parameters = [lsp.ParameterInformation(
            decl.identifier(),
            markup.code_block(f"""{nss.type_name(decl)} {decl.identifier()}""",
                              markup_kind)
        ) for decl in sig_help.decl.decl]
        signatures.append(sig)
    else:
        return

    return lsp.SignatureHelp(signatures, 0, sig_help.active_param)


@SERVER.feature(lsp.INITIALIZE)
def initialize(params: lsp.InitializeParams):
    rollnw.kernel.start()

    # [TODO] All client capabilities:
