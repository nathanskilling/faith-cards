#!/usr/bin/env python3
"""AFL Manager - command line front end.

    python play.py new [--seed N] [--save NAME]   create a fresh world
    python play.py <command ...>                  run one command (see: python play.py help)
    python play.py                                interactive session
    python play.py saves                          list saved careers

The career is saved to saves/<name>/ after every command.
"""
import sys

from aflm import storage, generator
from aflm.commands import execute, cmd_clubs


def main(argv: list[str]) -> int:
    save = None
    if "--save" in argv:
        i = argv.index("--save")
        save = argv[i + 1]
        del argv[i:i + 2]
    seed = None
    if "--seed" in argv:
        i = argv.index("--seed")
        seed = int(argv[i + 1])
        del argv[i:i + 2]

    if argv and argv[0] == "saves":
        cur = storage.current_save()
        for name in storage.list_saves():
            print(("* " if name == cur else "  ") + name)
        return 0

    if argv and argv[0] == "new":
        name = save or "career"
        if name in storage.list_saves() and "--force" not in argv:
            print(f"A save called '{name}' already exists. Use --save OTHERNAME, or add --force to overwrite.")
            return 1
        game = generator.new_game(seed=seed, save_name=name)
        storage.save_game(game, name)
        print(f"New world created (seed {game.meta['seed']}), saved as '{name}'.")
        print(cmd_clubs(game, []))
        return 0

    try:
        game = storage.load_game(save)
    except FileNotFoundError as e:
        print(e)
        return 1

    if argv:                                   # one-shot command
        print(execute(game, " ".join(argv)))
        storage.save_game(game)
        return 0

    print("AFL Manager - type 'help' for commands, 'quit' to leave.")
    print(execute(game, "status" if game.user else "clubs"))
    while True:
        try:
            line = input("\nafl> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() in ("quit", "exit", "q"):
            break
        print(execute(game, line))
        storage.save_game(game)
    storage.save_game(game)
    print("Saved. See you at the next bounce.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
