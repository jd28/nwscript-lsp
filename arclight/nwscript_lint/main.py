#!/usr/bin/env python

import rollnw
import argparse
import os
import time


def main():
    parser = argparse.ArgumentParser(description="A linter for nwscript.")

    parser.add_argument(
        '-I', '--include',
        action='append',
        help="Include path(s).",
    )

    parser.add_argument(
        '--no-install',
        action='store_true',
        help="Disable loading game install files.",
    )

    parser.add_argument(
        '--no-user',
        action='store_true',
        help="Disable user install files.",
    )

    parser.add_argument(
        'scripts',
        metavar='scripts',
        nargs='+',
        help="List of scripts to lint.",
    )

    args = parser.parse_args()

    config = rollnw.kernel.config().options()
    config.include_install = not args.no_install
    config.include_user = not args.no_user
    rollnw.kernel.start(config)

    for file in args.scripts:
        start_time = time.perf_counter()
        ctx = rollnw.script.Context(args.include)
        nss = rollnw.script.Nss(
            file, ctx, os.path.basename(file) == "nwscript.nss")
        nss.resolve()
        elapsed_time = (time.perf_counter() - start_time) * 1000
        print(f"Processed '{file}' in {elapsed_time:.3f} ms")


if __name__ == "__main__":
    main()
