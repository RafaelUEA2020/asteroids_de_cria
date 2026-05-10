"""Game loop and scenes (menu, play, game over).

- InputMapper converts keyboard input into PlayerCommand.
- World updates the simulation and generates events (strings) for Game.
- Game handles audio and screen transitions (low coupling).
"""

import sys
import os
import pygame as pg

from core import config as C
from core.scene import SceneState
from client.audio import load_sounds
from client.audio_manager import AudioManager
from client.controls import InputMapper
from client.renderer import Renderer
from core.world import World
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'core')))

class Game:
    """Orchestrates input -> update -> draw."""

    def __init__(self) -> None:
        pg.mixer.pre_init(C.AUDIO_FREQUENCY, C.AUDIO_SIZE, C.AUDIO_CHANNELS, C.AUDIO_BUFFER)
        pg.init()
        pg.mixer.init()

        self.screen = pg.display.set_mode((C.WIDTH, C.HEIGHT))
        pg.display.set_caption("Asteroids")
        
        # detectar os controles
        pg.joystick.init()
        self.joysticks = []

        for i in range(pg.joystick.get_count()):
            joy = pg.joystick.Joystick(i)
            joy.init()
            self.joysticks.append(joy)
        print(f"Controles detectados: {len(self.joysticks)}")
        
        # =========================
        # PLAYER 1 -> teclado
        # =========================

        self.input1 = InputMapper(
            left=pg.K_a,
            right=pg.K_d,
            thrust=pg.K_w,
            shoot=pg.K_SPACE,
            hyperspace=pg.K_LSHIFT,
            freeze=pg.K_f,
        )
        
        # =========================
        # PLAYER 2
        # controle se existir
        # senão teclado
        # =========================

        if len(self.joysticks) > 0:
        
            print("Player 2 usando controle")

            self.input2 = InputMapper(
                joystick=self.joysticks[0]
            )

        else:
        
            print("Player 2 usando teclado")

            self.input2 = InputMapper(
                left=pg.K_LEFT,
                right=pg.K_RIGHT,
                thrust=pg.K_UP,
                shoot=pg.K_RETURN,
                hyperspace=pg.K_RSHIFT,
            )
            
        self.clock = pg.time.Clock()
        self.running = True

        self.font = pg.font.SysFont(C.FONT_NAME, C.FONT_SIZE_SMALL)
        self.big = pg.font.SysFont(C.FONT_NAME, C.FONT_SIZE_LARGE)
        self.renderer = Renderer(
            self.screen,
            config=C,
            fonts={"font": self.font, "big": self.big},
        )

        self.scene = SceneState.MENU
        self.world = World()

        self.sounds = load_sounds(C.SOUND_PATH)
        self.audio = AudioManager(self.sounds)
        
        self.freeze_cooldown = C.FREEZE_COOLDOWN
        self.freeze_duration = C.FREEZE_DURATION
        self.freeze_cd_timer = 0.0

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(C.FPS) / 1000.0
            self._handle_events()
            self._update(dt)
            self._draw()

        pg.quit()

    def _handle_events(self) -> None:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self._quit()

            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self._quit()

            if self.scene == SceneState.MENU:
                if event.type == pg.KEYDOWN:
                    self.scene = SceneState.PLAY
                continue

            if self.scene == SceneState.GAME_OVER:
                if event.type == pg.KEYDOWN:
                    self.world.reset()
                    self.scene = SceneState.PLAY
                continue

            if self.scene == SceneState.PLAY:
                self.input1.handle_event(event)
                self.input2.handle_event(event)

    def _update(self, dt: float) -> None:
        if self.scene != SceneState.PLAY:
            return

        keys = pg.key.get_pressed()
        cmd1 = self.input1.build_command(keys)
        cmd2 = self.input2.build_command(keys)

        commands = {
            C.LOCAL_PLAYER_ID: cmd1,
            C.LOCAL_PLAYER_2_ID: cmd2,
        }
        
        self.world.update(dt, commands)

        if self.world.game_over:
            self.audio.stop_all()
            self.scene = SceneState.GAME_OVER
            return

        self.audio.update_thrust(
            cmd1.thrust or cmd2.thrust
        )
        
        self.audio.update_ufo_siren(list(self.world.ufos))
        self.audio.play_events(self.world.events)
        
        # cooldown
        if self.freeze_cd_timer > 0:
            self.freeze_cd_timer -= dt

        # input freeze (CORRETO)
        if self.input1.consume_freeze() and self.freeze_cd_timer <= 0:
            self.world.activate_freeze(self.freeze_duration)
            self.freeze_cd_timer = self.freeze_cooldown

    def _draw(self) -> None:
        self.renderer.clear()

        if self.scene == SceneState.MENU:
            self.renderer.draw_menu()
            pg.display.flip()
            return

        if self.scene == SceneState.GAME_OVER:
            self.renderer.draw_game_over()
            pg.display.flip()
            return

        self.renderer.draw_world(self.world)
        self.renderer.draw_hud(
            self.world.scores.get(C.LOCAL_PLAYER_ID, 0),
            self.world.lives.get(C.LOCAL_PLAYER_ID, 0),
            self.world.wave,
            self.scene,
            self.freeze_cd_timer,
            score_p2=self.world.scores.get(C.LOCAL_PLAYER_2_ID, 0),
            lives_p2=self.world.lives.get(C.LOCAL_PLAYER_2_ID, 0),
        )
        pg.display.flip()

    def _quit(self) -> None:
        self.running = False
        pg.quit()
        sys.exit(0)
