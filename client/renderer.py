"""Client-side rendering (pygame)."""
import math

import pygame as pg

from core import config as C
from core.entities import Asteroid, BlackHole, Bullet, Ship, UFO, ShieldPickup, WeaponPickup
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
            WeaponPickup: self._draw_weapon_pickup,
            BlackHole: self._draw_black_hole,
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
        freeze_cd: float,
        ship: Ship | None = None,
    ) -> None:
        if state != SceneState.PLAY:
            return

        # HUD principal
        text = f"SCORE {score:06d}   LIVES {lives}   WAVE {wave}"
        label = self.font.render(text, True, self.config.WHITE)
        self.screen.blit(label, (10, 10))

        # HUD DO FREEZE (canto esquerdo abaixo do score)
        if freeze_cd <= 0:
            freeze_text = "FREEZE: READY"
            color = (100, 255, 100) if pg.time.get_ticks() % 500 < 250 else (255, 255, 255)
        else:
            freeze_text = f"FREEZE: {max(0, freeze_cd):.1f}s"
            color = self.config.WHITE

        label_freeze = self.font.render(freeze_text, True, color)
        self.screen.blit(label_freeze, (10, 40))

        # HUD do power-up de arma (canto superior direito)
        if ship is not None and ship.weapon_mode and ship.weapon_time > 0:
            mode_names = {"double": "DUPLO", "triple": "TRIPLO", "rapid": "RAPIDO"}
            name = mode_names.get(ship.weapon_mode, "")
            col = getattr(self.config, "WEAPON_PICKUP_COLOR", (255, 220, 80))

            wl = self.font.render(
                f"ARMA: {name}  {ship.weapon_time:.1f}s", True, col
            )
            self.screen.blit(wl, (self.config.WIDTH - wl.get_width() - 10, 10))

            bw = max(1, int(150 * (ship.weapon_time / self.config.WEAPON_DURATION)))
            pg.draw.rect(
                self.screen,
                col,
                (self.config.WIDTH - bw - 10, 36, bw, 4)
            )

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
        color = self.config.WHITE

        if ship.player_id == C.LOCAL_PLAYER_2_ID:
            color = self.config.BLUE

        pg.draw.polygon(self.screen, color, points, width=1)

        if ship.invuln > 0.0 and int(ship.invuln * 10) % 2 == 0:
            pg.draw.circle(
                self.screen,
                self.config.WHITE,
                (cx, cy),
                ship.r + 6,
                width=1,
            )

        # Anel dourado pulsante do power-up de arma
        if getattr(ship, "weapon_mode", None) and ship.weapon_time > 0.0:
            col = getattr(self.config, "WEAPON_PICKUP_COLOR", (255, 220, 80))
            pulse = int(ship.weapon_time * 8) % 2
            rw = ship.r + 14 + pulse * 2
            pg.draw.circle(self.screen, col, (cx, cy), rw, width=1)

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

    def _draw_weapon_pickup(self, pickup: WeaponPickup) -> None:
        if not getattr(pickup, "_draw_visible", True):
            return

        col = getattr(pickup, "_draw_color", C.WEAPON_PICKUP_COLOR)
        r = int(getattr(pickup, "r", C.WEAPON_PICKUP_RADIUS))
        cx, cy = int(pickup.pos.x), int(pickup.pos.y)

        # Losango
        pts = [
            (cx,     cy - r),
            (cx + r, cy),
            (cx,     cy + r),
            (cx - r, cy),
        ]
        pg.draw.polygon(self.screen, col, pts, width=2)

        # Label no centro
        label_map = {"double": "2x", "triple": "3x", "rapid": ">>"}
        label = label_map.get(pickup.mode, "?")
        font = pg.font.SysFont("consolas", max(8, int(r * 0.85)))
        surf_txt = font.render(label, True, col)
        rect_txt = surf_txt.get_rect(center=(cx, cy))
        self.screen.blit(surf_txt, rect_txt)

    def _draw_ufo(self, ufo: UFO) -> None:
        width = ufo.r * 2
        height = ufo.r

        body = pg.Rect(0, 0, width, height)
        body.center = (int(ufo.pos.x), int(ufo.pos.y))
        pg.draw.ellipse(self.screen, self.config.WHITE, body, width=1)

        cup = pg.Rect(0, 0, int(width * 0.5), int(height * 0.7))
        cup.center = (int(ufo.pos.x), int(ufo.pos.y - height * 0.3))
        pg.draw.ellipse(self.screen, self.config.WHITE, cup, width=1)

    def _draw_black_hole(self, black_hole: BlackHole) -> None:
        cx, cy = int(black_hole.pos.x), int(black_hole.pos.y)
        pulse = (math.sin(black_hole._pulse) + 1.0) * 0.5
        ring_radius = int(black_hole.attract_radius * (0.72 + pulse * 0.08))

        pg.draw.circle(
            self.screen,
            self.config.BLACK_HOLE_COLOR,
            (cx, cy),
            ring_radius,
            width=1,
        )
        pg.draw.circle(
            self.screen,
            self.config.BLACK_HOLE_COLOR,
            (cx, cy),
            int(black_hole.r * 1.5),
            width=2,
        )
        pg.draw.circle(
            self.screen,
            self.config.WHITE,
            (cx, cy),
            black_hole.r,
        )
        pg.draw.circle(
            self.screen,
            self.config.BLACK,
            (cx, cy),
            max(4, black_hole.r - 6),
        )
