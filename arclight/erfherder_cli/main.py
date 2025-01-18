import argparse
import rollnw
import os


def get_lower_case_extension(filename):
    _, ext = os.path.splitext(filename)
    return ext.lower()


def extract(args):
    for container in args.containers:
        ext = get_lower_case_extension(container)
        cont = None
        if ext == ".erf" or ext == ".hak" or ext == ".mod":
            cont = rollnw.Erf(container)
        elif ext == ".key":
            cont = rollnw.Key(container)
        elif ext == ".zip":
            cont = rollnw.Zip(container)

        if args.regex:
            cont.extract(args.pattern, args.output)
        else:
            cont.extract_by_glob(args.pattern, args.output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--version', action='version', version='0.1')

    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser(
        "extract", help="Extract various files by glob or regex")

    extract_parser.add_argument(
        '--regex', help='Use regex instead of Unix wildcard format', action='store_true')

    extract_parser.add_argument(
        "--output",
        type=str,
        default=".",
        help="Specify the output directory (default: current directory '.')."
    )

    extract_parser.add_argument(
        'pattern',
        type=str,
        help='Search pattern')

    extract_parser.add_argument(
        'containers', help='Containers to search.', nargs='+')

    args = parser.parse_args()
    if args.command == "extract":
        extract(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
