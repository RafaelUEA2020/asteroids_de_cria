"""Client-side rendering (pygame)."""
import math

import pygame as pg

from core import config as C
from core.entities import Asteroid, Bullet, Ship, UFO, ShieldPickup
from core.scene import SceneState


class Renderer:
    """Draws scenes and entities without coupling game rules to Game."""

    def __init__(
        self,
        screen: pg.Surface,
        config: object = C,
        fonts: dict[str, pg.font.Font] | None = None,
    ) -> None:
        self.screen = screen
        self.config = config
        safe_fonts = fonts or {}
        self.font = safe_fonts["font"]
        self.big = safe_fonts["big"]

        self._draw_dispatch: dict[type, callable] = {
            Bullet: self._draw_bullet,
            Asteroid: self._draw_asteroid,
            Ship: self._draw_ship,
            UFO: self._draw_ufo,
            ShieldPickup: self._draw_shield_pickup,
        }

    def clear(self) -> None:
        self.screen.fill(self.config.BLACK)

    def draw_world(self, world: object) -> None:
        sprites = getattr(world, "all_sprites", [])
        for sprite in sprites:
            drawer = self._draw_dispatch.get(type(sprite))
            if drawer is not None:
                drawer(sprite)

    def draw_hud(
        self,
        score: int,
        lives: int,
        wave: int,
        state: SceneState,
    ) -> None:
        if state != SceneState.PLAY:
            return

        text = f"SCORE {score:06d}   LIVES {lives}   WAVE {wave}"
        label = self.font.render(text, True, self.config.WHITE)
        self.screen.blit(label, (10, 10))

    def draw_menu(self) -> None:
        self._draw_text(
            self.big,
            "ASTEROIDS",
            self.config.WIDTH // 2 - 170,
            200,
        )
        self._draw_text(
            self.font,
            "Press any key",
            self.config.WIDTH // 2 - 170,
            350,
        )

    def draw_game_over(self) -> None:
        self._draw_text(
            self.big,
            "GAME OVER",
            self.config.WIDTH // 2 - 170,
            260,
        )
        self._draw_text(
            self.font,
            "Press any key",
            self.config.WIDTH // 2 - 170,
            340,
        )

    def _draw_text(
        self,
        font: pg.font.Font,
        text: str,
        x: int,
        y: int,
    ) -> None:
        label = font.render(text, True, self.config.WHITE)
        self.screen.blit(label, (x, y))

    def _draw_bullet(self, bullet: Bullet) -> None:
        center = (int(bullet.pos.x), int(bullet.pos.y))
        pg.draw.circle(
            self.screen,
            self.config.WHITE,
            center,
            bullet.r,
            width=1,
        )

    def _draw_asteroid(self, asteroid: Asteroid) -> None:
        points = [
            (int(asteroid.pos.x + p.x), int(asteroid.pos.y + p.y))
            for p in asteroid.poly
        ]
        pg.draw.polygon(self.screen, self.config.WHITE, points, width=1)

    def _draw_ship(self, ship: Ship) -> None:
        cx, cy = int(ship.pos.x), int(ship.pos.y)

        # Escudo ativo: anel duplo pulsante
        if getattr(ship, "has_shield", False):
            col = getattr(self.config, "SHIELD_COLOR", (120, 220, 255))
            pulse = int(ship.shield_timer * 12) % 2
            ro = ship.r + 8 + pulse * 3
            pg.draw.circle(self.screen, col, (cx, cy), ro, width=2)
            pg.draw.circle(self.screen, col, (cx, cy), ro + 6, width=1)

        # Corpo da nave
        p1, p2, p3 = ship.ship_points()
        points = [(int(p.x), int(p.y)) for p in (p1, p2, p3)]
        pg.draw.polygon(self.screen, self.config.WHITE, points, width=1)

        if ship.invuln > 0.0 and int(ship.invuln * 10) % 2 == 0:
            pg.draw.circle(
                self.screen,
                self.config.WHITE,
                (cx, cy),
                ship.r + 6,
                width=1,
            )

    def _draw_shield_pickup(self, pickup: ShieldPickup) -> None:
    
        if not getattr(pickup, "_draw_visible", True):
            return

        col = getattr(pickup, "_draw_color", C.SHIELD_COLOR)
        r = getattr(pickup, "r", C.SHIELD_PICKUP_RADIUS)
        pulse = getattr(pickup, "_pulse", 0.0)
        cx, cy = int(pickup.pos.x), int(pickup.pos.y)

        # Anel externo
        line_w = 2 if pickup.ttl > C.SHIELD_PICKUP_WARN_TIME else 1
        pg.draw.circle(self.screen, col, (cx, cy), r, width=max(1, line_w))

        # Cruz interna
        arm = int(r * 0.55)
        pg.draw.line(self.screen, col, (cx - arm, cy), (cx + arm, cy), max(1, line_w))
        pg.draw.line(self.screen, col, (cx, cy - arm), (cx, cy + arm), max(1, line_w))

        # Ponto central pulsante
        dot_r = max(1, int(1.5 + 1.5 * (math.sin(pulse) + 1) / 2))
        pg.draw.circle(self.screen, col, (cx, cy), dot_r)

    def _draw_ufo(self, ufo: UFO) -> None:
        width = ufo.r * 2
        height = ufo.r

        body = pg.Rect(0, 0, width, height)
        body.center = (int(ufo.pos.x), int(ufo.pos.y))
        pg.draw.ellipse(self.screen, self.config.WHITE, body, width=1)

        cup = pg.Rect(0, 0, int(width * 0.5), int(height * 0.7))
        cup.center = (int(ufo.pos.x), int(ufo.pos.y - height * 0.3))
        pg.draw.ellipse(self.screen, self.config.WHITE, cup, width=1)
