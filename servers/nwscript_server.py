import argparse
import asyncio
import json
import re
import time
import uuid
import os
import rollnw
from typing import Optional

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


nwscript_server = NWScriptLanguageServer("nwscript-lsp", "v0.1.0")


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
            range=_convert_range(diag.location.range),
            message=diag.message,
            source=type(nwscript_server).__name__,
        )
        diagnostics.append(d)

    return diagnostics


def log_to_output(
    message: str, msg_type: lsp.MessageType = lsp.MessageType.Log
) -> None:
    nwscript_server.show_message_log(message, msg_type)


@nwscript_server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: lsp.DidOpenTextDocumentParams):
    """Text document did open notification."""
    _validate(ls, params)


@nwscript_server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params: lsp.DidChangeTextDocumentParams):
    """Text document did change notification."""
    _validate(ls, params)


@nwscript_server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
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


@nwscript_server.feature(
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


@nwscript_server.feature(lsp.WORKSPACE_DIAGNOSTIC)
def workspace_diagnostic(
    params: lsp.WorkspaceDiagnosticParams,
) -> lsp.WorkspaceDiagnosticReport:
    """Returns diagnostic report."""
    documents = nwscript_server.workspace.text_documents.keys()

    items = []

    if len(documents) > 0:
        for d in documents:
            document = nwscript_server.workspace.get_text_document(d)
            nwscript_server.show_message_log(
                f"Parsing nwscript file: {document.filename}")
            items.append(
                lsp.WorkspaceFullDocumentDiagnosticReport(
                    uri=document.uri,
                    version=document.version,
                    items=_validate_nwscript(
                        document.source, document.filename == "nswcript.nss"),
                    kind=lsp.DocumentDiagnosticReportKind.Full,
                )
            )

    return lsp.WorkspaceDiagnosticReport(items=items)


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


@nwscript_server.feature(
    lsp.TEXT_DOCUMENT_COMPLETION,
    lsp.CompletionOptions(trigger_characters=["."]),
)
def completions(params: Optional[lsp.CompletionParams] = None) -> lsp.CompletionList:
    """Returns completion items."""

    if params is None:
        return lsp.CompletionList(is_incomplete=False, items=[])

    text_doc = nwscript_server.workspace.get_text_document(
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

    nwscript_server.show_message_log(str(len(completions)))
    items = [_symbol_to_completion_item(nss, item) for item in completions]

    return lsp.CompletionList(
        is_incomplete=False,
        items=items
    )


@nwscript_server.feature(lsp.TEXT_DOCUMENT_HOVER)
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
                info += f"* `{nss.type_name(decl_info.decl[i])} {decl_info.decl[i].identifier()}`\n\n"
    elif isinstance(decl_info.decl, rollnw.script.FunctionDefinition):
        display.append(
            f"**function** `{decl_info.decl.decl.identifier()}`")
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


def add_arguments(parser):
    parser.description = "simple nwscript server"

    parser.add_argument("--tcp", action="store_true", help="Use TCP server")
    parser.add_argument("--ws", action="store_true",
                        help="Use WebSocket server")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Bind to this address")
    parser.add_argument("--port", type=int, default=2087,
                        help="Bind to this port")


def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()

    rollnw.kernel.start()

    if args.tcp:
        nwscript_server.start_tcp(args.host, args.port)
    elif args.ws:
        nwscript_server.start_ws(args.host, args.port)
    else:
        nwscript_server.start_io()


if __name__ == "__main__":
    main()
