"""Game scene states."""

from enum import Enum, auto


class SceneState(Enum):
    MENU = auto()
    PLAY = auto()
    GAME_OVER = auto()
