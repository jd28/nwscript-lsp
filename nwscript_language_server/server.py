import argparse
import asyncio
import json
import re
import time
import uuid
import os
import rollnw
from typing import Optional, List

from lsprotocol import types as lsp

from pygls.server import LanguageServer

COUNT_DOWN_START_IN_SECONDS = 10
COUNT_DOWN_SLEEP_IN_SECONDS = 1


class NWScriptLanguageServer(LanguageServer):
    CMD_COUNT_DOWN_BLOCKING = "countDownBlocking"
    CMD_COUNT_DOWN_NON_BLOCKING = "countDownNonBlocking"
    CMD_PROGRESS = "progress"
    CMD_REGISTER_COMPLETIONS = "registerCompletions"
    CMD_SHOW_CONFIGURATION_ASYNC = "showConfigurationAsync"
    CMD_SHOW_CONFIGURATION_CALLBACK = "showConfigurationCallback"
    CMD_SHOW_CONFIGURATION_THREAD = "showConfigurationThread"
    CMD_UNREGISTER_COMPLETIONS = "unregisterCompletions"

    CONFIGURATION_SECTION = "pygls.nwscriptServer"

    def __init__(self, *args):
        super().__init__(*args)


SERVER = NWScriptLanguageServer("nwscript-language-server", "v0.2.0")


def _convert_position(position: rollnw.script.SourcePosition) -> lsp.Position:
    return lsp.Position(position.line - 1, position.column)


def _convert_range(range: rollnw.script.SourceRange) -> lsp.Range:
    return lsp.Range(_convert_position(range.start), _convert_position(range.end))


def _validate(ls, params):
    text_doc = ls.workspace.get_text_document(params.text_document.uri)
    ls.show_message_log(f"Parsing nwscript file: {text_doc.filename}")
    source = text_doc.source
    diagnostics = _validate_nwscript(
        source, text_doc.filename == "nwscript.nss") if source else []
    ls.publish_diagnostics(text_doc.uri, diagnostics)


def _validate_nwscript(source, command_script: bool):
    """Validates nwscript file."""
    diagnostics = []

    ctx = rollnw.script.LspContext()
    nss = rollnw.script.Nss.from_string(source, ctx, command_script)
    nss.parse()
    nss.process_includes()
    nss.resolve()

    for diag in nss.diagnostics():
        d = lsp.Diagnostic(
            range=_convert_range(diag.location),
            message=diag.message,
            source=type(SERVER).__name__,
        )
        diagnostics.append(d)

    return diagnostics


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
    text_doc = server.workspace.get_text_document(params.text_document.uri)
    source = text_doc.source
    nss = rollnw.script.Nss.from_string(
        source, rollnw.script.LspContext(), text_doc.filename == "nwscript.nss")
    nss.parse()
    nss.process_includes()
    nss.resolve()

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

    text_doc = SERVER.workspace.get_text_document(
        params.text_document.uri)
    source = text_doc.source
    nss = rollnw.script.Nss.from_string(
        source, rollnw.script.LspContext(), text_doc.filename == "nwscript.nss")
    nss.parse()
    nss.process_includes()
    nss.resolve()

    items = []
    needle = text_doc.word_at_position(params.position)

    if text_doc.lines[params.position.line][params.position.character-1] == ".":
        nl = text_doc.lines[params.position.line][:params.position.character-1]
        word = nl.split()[-1]
        character = text_doc.lines[params.position.line].find(word)
        completions = nss.complete_dot(
            word, params.position.line + 1, character)
    else:
        completions = nss.complete_at(
            needle, params.position.line + 1, params.position.character)

    SERVER.show_message_log(str(len(completions)))
    items = [_symbol_to_completion_item(nss, item) for item in completions]

    return lsp.CompletionList(
        is_incomplete=False,
        items=items
    )


@SERVER.feature(lsp.TEXT_DOCUMENT_HOVER)
def text_document_hover(server: NWScriptLanguageServer, params: lsp.HoverParams) -> Optional[lsp.Hover]:
    text_doc = server.workspace.get_text_document(
        params.text_document.uri)
    source = text_doc.source

    nss = rollnw.script.Nss.from_string(
        source, rollnw.script.LspContext(), text_doc.filename == "nwscript.nss")
    nss.parse()
    nss.process_includes()
    nss.resolve()

    needle = text_doc.word_at_position(params.position)
    decl_info = nss.locate_symbol(
        needle, params.position.line + 1, params.position.character)

    if decl_info.decl is None:
        return

    display = []
    view = f"```nwscript\n{decl_info.view}\n```"
    info = ""
    if isinstance(decl_info.decl, rollnw.script.VarDecl):
        if decl_info.kind == rollnw.script.SymbolKind.param:
            kind_str = "param"
        elif decl_info.kind == rollnw.script.SymbolKind.field:
            kind_str = "field"
        else:
            kind_str = "variable"
        display.append(
            f"### **{kind_str} `{decl_info.decl.identifier()}`**")
        display.append(f"Type: `{decl_info.type}`")
    elif isinstance(decl_info.decl, rollnw.script.FunctionDecl):
        display.append(
            f"### **function** `{decl_info.decl.identifier()}`")
        info = f"→ `{decl_info.type}`\n\n"
        if len(decl_info.decl):
            info += "Parameters\n\n"
            for i in range(len(decl_info.decl)):
                info += f"* `{nss.type_name(decl_info.decl[i])} {
                    decl_info.decl[i].identifier()}`\n\n"
    elif isinstance(decl_info.decl, rollnw.script.FunctionDefinition):
        display.append(
            f"**function** `{decl_info.decl.decl.identifier()}`")
        info = f"→ `{decl_info.type}`\n\n"
        if len(decl_info.decl.decl):
            info += "Parameters\n\n"
            for i in range(len(decl_info.decl.decl)):
                info += f"* `{nss.type_name(decl_info.decl.decl[i])} {
                    decl_info.decl.decl[i].identifier()}`\n\n"
        view = f"```nwscript\n{decl_info.view}\n```"
    elif isinstance(decl_info.decl, rollnw.script.StructDecl):
        display.append(f"### struct `{decl_info.type}`")
        view = f"```nwscript\nstruct {decl_info.type} {{}}\n```"
    else:
        return

    provider = ""
    if len(decl_info.provider):
        provider = f"Provided by `{decl_info.provider}`"

    return lsp.Hover([*display, provider, info, decl_info.comment.replace('\n', '\n\n'), view])


@SERVER.feature(lsp.TEXT_DOCUMENT_INLAY_HINT)
def inlay_hint(params: lsp.InlayHintParams) -> List[lsp.InlayHint]:

    text_doc = SERVER.workspace.get_text_document(
        params.text_document.uri)
    source = text_doc.source

    nss = rollnw.script.Nss.from_string(
        source, rollnw.script.LspContext(), text_doc.filename == "nwscript.nss")
    nss.parse()
    nss.process_includes()
    nss.resolve()

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
    log_to_output("TEXT_DOCUMENT_SIGNATURE_HELP")

    text_doc = SERVER.workspace.get_text_document(
        params.text_document.uri)
    source = text_doc.source

    nss = rollnw.script.Nss.from_string(
        source, rollnw.script.LspContext(), text_doc.filename == "nwscript.nss")
    nss.parse()
    nss.process_includes()
    nss.resolve()
    sig_help = nss.signature_help(
        params.position.line + 1, params.position.character)

    if not isinstance(sig_help.expr, rollnw.script.CallExpression):
        return

    signatures = []

    if isinstance(sig_help.decl, rollnw.script.FunctionDecl):
        sig = lsp.SignatureInformation(sig_help.decl.identifier())
        sig.parameters = [lsp.ParameterInformation(
            sig_help.decl[i].identifier(),
            lsp.MarkupContent(lsp.MarkupKind.Markdown,
                              f"""```nwscript\n{nss.type_name(sig_help.decl[i])} {
                                  sig_help.decl[i].identifier()}\n```""")
        ) for i in range(len(sig_help.decl))]
        signatures.append(sig)
    elif isinstance(sig_help.decl, rollnw.script.FunctionDefinition):
        sig = lsp.SignatureInformation(sig_help.decl.decl.identifier())
        sig.parameters = [lsp.ParameterInformation(
            sig_help.decl.decl[i].identifier()) for i in range(len(sig_help.decl.decl))]
        signatures.append(sig)
    else:
        return

    return lsp.SignatureHelp(signatures, 0, sig_help.active_param)
