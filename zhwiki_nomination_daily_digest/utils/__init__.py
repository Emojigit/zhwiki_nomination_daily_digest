"""Common code for command-line utilities."""


from typing import Callable


def util_run(argv: list[str], func_map: dict[str, Callable[[list[str]], int]]) -> int:
    if len(argv) <= 1:
        print("Invalid usage: Subcommand name not supplied. List of subcommands:")
        print("\n".join(func_map.keys()))
        return 1

    if argv[1] not in func_map:
        print("Invalid usage: Invalid subcommand. List of subcommands:")
        print("\n".join(func_map.keys()))
        return 1

    return func_map[argv[1]](argv)
