"""Input system supporting keyboard and joystick."""

import pygame as pg

from core.commands import PlayerCommand
from core import config as C

class InputMapper:

    def __init__(
        self,
        left=None,
        right=None,
        thrust=None,
        shoot=None,
        hyperspace=None,
        freeze=None,
        joystick=None,
    ):
        self.left = left
        self.right = right
        self.thrust = thrust
        self.shoot = shoot
        self.hyperspace = hyperspace
        self.freeze = freeze

        self.joystick = joystick

        self._freeze_pressed = False

    def handle_event(self, event: pg.event.Event) -> None:

        if event.type != pg.KEYDOWN:
            return

        if self.freeze is not None and event.key == self.freeze:
            self._freeze_pressed = True

    def build_command(self, keys: pg.key.ScancodeWrapper) -> PlayerCommand:
        # =========================
        # KEYBOARD INPUT
        # =========================

        rotate_left = False
        rotate_right = False
        thrust = False
        shoot = False
        hyperspace = False

        if self.joystick is None:

            rotate_left = keys[self.left]
            rotate_right = keys[self.right]
            thrust = keys[self.thrust]
            shoot = keys[self.shoot]
            hyperspace = keys[self.hyperspace]

        # =========================
        # JOYSTICK INPUT
        # =========================

        else:

            axis_x = self.joystick.get_axis(0)

            rotate_left = axis_x < - C.JOYSTICK_DEADZONE
            rotate_right = axis_x > C.JOYSTICK_DEADZONE

            thrust = self.joystick.get_button(0)

            shoot = self.joystick.get_button(1)

            hyperspace = self.joystick.get_button(2)

        return PlayerCommand(
            rotate_left=rotate_left,
            rotate_right=rotate_right,
            thrust=thrust,
            shoot=shoot,
            hyperspace=hyperspace,
        )

    def consume_freeze(self) -> bool:
        pressed = self._freeze_pressed
        self._freeze_pressed = False
        return pressed