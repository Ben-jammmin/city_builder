"""
main.py — Application entry point.

Starts pygame, shows the main menu, and then repeatedly runs the game loop
until the player quits. If the player returns to the main menu (e.g. by
pressing Escape), the loop brings the menu back instead of exiting.
"""

import sys

import pygame

from citybuilder.game import Game
from citybuilder.menu import run_main_menu


def main() -> None:
    pygame.init()

    # Keep looping so the player can return to the menu after a game session.
    while True:
        # run_main_menu returns a GameConfig (new/load game) or None (quit).
        config = run_main_menu()
        if config is None:  # player chose Quit from main menu
            break

        game = Game(config)
        # game.run() returns True if the player closed the window entirely,
        # False if they just pressed Escape back to the menu.
        quit_to_desktop = game.run()

        if quit_to_desktop:  # player closed the window — respect that
            break

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
