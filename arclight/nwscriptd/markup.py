from lsprotocol import types as lsp
import rollnw.script as nws


def code_block(string: str, markup_kind: lsp.MarkupKind) -> lsp.MarkupContent:
    if markup_kind == lsp.MarkupKind.Markdown:
        string = f"```nwscript\n{string}\n```"
    else:
        # Force plain text if we don't know how to handle a markup kind
        markup_kind = lsp.MarkupKind.PlainText

    return lsp.MarkupContent(markup_kind, string)


def hover_func_decl(nss: nws.Nss, symbol: nws.Symbol, markup_kind: lsp.MarkupKind) -> lsp.MarkupContent:
    lines = []

    if isinstance(symbol.decl, nws.FunctionDefinition):
        d = symbol.decl.decl
    else:
        d = symbol.decl

    if markup_kind == lsp.MarkupKind.Markdown:
        lines.append(f"**function `{d.identifier()}` → `{symbol.type}`**")
        if symbol.provider is not None:
            lines.append(f"\n* Provided by `{symbol.provider.name()}`")

        if len(d):
            lines.append("\n\nParameters")
            for i in range(len(d)):
                lines.append(
                    f"\n* `{nss.type_name(d[i])} {d[i].identifier()}`")

        if len(symbol.comment):
            lines.append(
                "\n\n```nwscript\n//" +
                symbol.comment.replace('\n', '\n//') +
                "\n```"
            )

        lines.append(f"\n```nwscript\n{symbol.view}\n```")

        return lsp.MarkupContent(markup_kind, ''.join(lines))
    else:
        # Force plain text if we don't know how to handle a markup kind
        markup_kind = lsp.MarkupKind.PlainText
        lines.append(f"**function {d.identifier()} -> {symbol.type}**")
        if symbol.provider is not None:
            lines.append(f"\n* Provided by '{symbol.provider.name()}'")

        if len(d):
            lines.append("\n\nParameters")
            for i in range(len(d)):
                lines.append(
                    f"\n* {nss.type_name(d[i])} {d[i].identifier()}")

        if len(symbol.comment):
            lines.append(
                "\n\n//" +
                symbol.comment.replace('\n', '\n//') +
                "\n"
            )

        lines.append(f"\n{symbol.view}")

        return lsp.MarkupContent(markup_kind, ''.join(lines))


def hover_struct_decl(nss: nws.Nss, symbol: nws.Symbol, markup_kind: lsp.MarkupKind) -> lsp.MarkupContent:
    lines = []

    if markup_kind == lsp.MarkupKind.Markdown:
        lines.append(f"**struct `{symbol.type}`**")

        if symbol.provider is not None:
            lines.append(f"\n* Provided by `{symbol.provider.name()}`")

        if len(symbol.comment):
            lines.append(
                "\n\n```nwscript\n//" +
                symbol.comment.replace('\n', '\n//') +
                "\n```"
            )

        lines.append(f"\n\n```nwscript\nstruct {symbol.type} {{}}\n```")
    else:
        # Force plain text if we don't know how to handle a markup kind
        markup_kind = lsp.MarkupKind.PlainText
        lines.append(f"**struct {symbol.type}**")

        if symbol.provider is not None:
            lines.append(f"\n* Provided by '{symbol.provider.name()}'")

        if len(symbol.comment):
            lines.append(
                "\n\n//" +
                symbol.comment.replace('\n', '\n//') +
                "\n"
            )

        lines.append(f"struct {symbol.type} {{}}")

    return lsp.MarkupContent(markup_kind, ''.join(lines))


def hover_var_decl(symbol: nws.Symbol, markup_kind: lsp.MarkupKind) -> lsp.MarkupContent:
    lines = []

    if symbol.kind == nws.SymbolKind.param:
        kind_str = "param"
    elif symbol.kind == nws.SymbolKind.field:
        kind_str = "field"
    else:
        kind_str = "variable"

    if markup_kind == lsp.MarkupKind.Markdown:
        header = f"**{kind_str} `{symbol.decl.identifier()}`: `{symbol.type}`**"
        lines.append(header)

        if symbol.provider is not None:
            lines.append(f"\n* Provided by `{symbol.provider.name()}`")

        if len(symbol.comment):
            lines.append(
                "\n\n```nwscript\n//" +
                symbol.comment.replace('\n', '\n//') +
                "\n```"
            )

        lines.append(f"\n\n```nwscript\n{symbol.view}\n```")

        return lsp.MarkupContent(markup_kind, ''.join(lines))
    else:
        # Force plain text if we don't know how to handle a markup kind
        markup_kind = lsp.MarkupKind.PlainText
        lines.append(
            f"<{kind_str}> {symbol.decl.identifier()}: {symbol.type}")
        if symbol.provider is not None:
            lines.append(f"\n* Provided by '{symbol.provider.name()}'")
        lines.append(symbol.comment)
        lines.append(f"{symbol.view}")
        return lsp.MarkupContent(markup_kind, ''.join(lines))
