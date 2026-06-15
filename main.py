import sys

import pygame

from citybuilder.game import Game
from citybuilder.menu import run_main_menu


def main() -> None:
    pygame.init()

    while True:
        config = run_main_menu()
        if config is None:  # player chose Quit from main menu
            break

        game = Game(config)
        quit_to_desktop = game.run()

        if quit_to_desktop:  # player closed the window — respect that
            break

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
