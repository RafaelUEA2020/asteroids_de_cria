"""Game entities (sprites)."""

import math
from random import choice, random, uniform

import pygame as pg

from core import config as C
from core.commands import PlayerCommand
from core.utils import Vec, angle_to_vec, rand_unit_vec, wrap_pos

PlayerId = int
UFO_BULLET_OWNER = -10


def rotate_vec(v: Vec, deg: float) -> Vec:
    rad = math.radians(deg)
    c = math.cos(rad)
    s = math.sin(rad)
    return Vec(v.x * c - v.y * s, v.x * s + v.y * c)


class Bullet(pg.sprite.Sprite):
    """Generic projectile."""

    def __init__(
        self,
        owner_id: PlayerId,
        pos: Vec,
        vel: Vec,
        ttl: float = C.BULLET_TTL,
    ) -> None:
        super().__init__()
        self.owner_id = owner_id
        self.pos = Vec(pos)
        self.vel = Vec(vel)
        self.ttl = float(ttl)
        self.r = int(C.BULLET_RADIUS)
        self.rect = pg.Rect(0, 0, self.r * 2, self.r * 2)

    def update(self, dt: float) -> None:
        self.pos += self.vel * dt
        self.pos = wrap_pos(self.pos)
        self.ttl -= dt
        if self.ttl <= 0.0:
            self.kill()
            return
        self.rect.center = (int(self.pos.x), int(self.pos.y))


class Asteroid(pg.sprite.Sprite):
    """Asteroid with irregular polygon shape."""

    def __init__(self, pos: Vec, vel: Vec, size: str) -> None:
        super().__init__()
        self.pos = Vec(pos)
        self.vel = Vec(vel)
        self.size = size
        self.r = int(C.AST_SIZES[size]["r"])
        self.poly = self._make_poly()
        self.rect = pg.Rect(0, 0, self.r * 2, self.r * 2)

    def _make_poly(self) -> list[Vec]:
        steps = C.AST_POLY_STEPS[self.size]
        pts: list[Vec] = []
        for i in range(steps):
            ang = i * (360 / steps)
            jitter = uniform(C.AST_POLY_JITTER_MIN, C.AST_POLY_JITTER_MAX)
            rr = self.r * jitter
            v = Vec(
                math.cos(math.radians(ang)),
                math.sin(math.radians(ang)),
            )
            pts.append(v * rr)
        return pts

    def update(self, dt: float) -> None:
        self.pos += self.vel * dt
        self.pos = wrap_pos(self.pos)
        self.rect.center = (int(self.pos.x), int(self.pos.y))


class Ship(pg.sprite.Sprite):
    """Ship controlled by command (does not read keyboard)."""

    def __init__(self, player_id: PlayerId, pos: Vec) -> None:
        super().__init__()
        self.player_id = player_id
        self.pos = Vec(pos)
        self.vel = Vec(0, 0)
        self.angle = -90.0
        self.cool = 0.0
        self.target_pos: Vec | None = None
        self.invuln = 0.0
        self.shield_timer = 0.0
        self.has_shield = False
        self.weapon_mode: str | None = None   # "double" | "triple" | "rapid" | None
        self.weapon_time: float = 0.0
        self.r = int(C.SHIP_RADIUS)
        self.rect = pg.Rect(0, 0, self.r * 2, self.r * 2)

    def apply_command(
        self,
        cmd: PlayerCommand,
        dt: float,
        bullets: pg.sprite.Group,
    ) -> "list[Bullet]":
        if cmd.rotate_left and not cmd.rotate_right:
            self.angle -= C.SHIP_TURN_SPEED * dt
        elif cmd.rotate_right and not cmd.rotate_left:
            self.angle += C.SHIP_TURN_SPEED * dt

        if cmd.thrust:
            self.vel += angle_to_vec(self.angle) * C.SHIP_THRUST * dt

        self.vel *= C.SHIP_FRICTION

        if cmd.shoot:
            return self._try_fire(bullets)

        return []

    def _try_fire(self, bullets: pg.sprite.Group) -> "list[Bullet]":
        if self.cool > 0.0:
            return []

        # Cap de balas — maior no modo rápido
        max_b = (C.WEAPON_RAPID_MAX_BULLETS
                 if self.weapon_mode == "rapid"
                 else C.MAX_BULLETS_PER_PLAYER)
        count = sum(1 for b in bullets if getattr(b, "owner_id", None) == self.player_id)
        if count >= max_b:
            return []

        fire_rate = (C.WEAPON_RAPID_FIRE_RATE
                     if self.weapon_mode == "rapid"
                     else C.SHIP_FIRE_RATE)
        self.cool = float(fire_rate)

        if self.weapon_mode == "double":
            offsets = [-C.WEAPON_DOUBLE_SPREAD / 2,
                        C.WEAPON_DOUBLE_SPREAD / 2]
        elif self.weapon_mode == "triple":
            half = C.WEAPON_TRIPLE_SPREAD / 2
            offsets = [-half, 0.0, half]
        else:
            offsets = [0.0]

        result = []
        for angle_off in offsets:
            d = angle_to_vec(self.angle + angle_off)
            pos = self.pos + d * (self.r + C.BULLET_SPAWN_OFFSET)
            vel = self.vel + d * C.SHIP_BULLET_SPEED
            result.append(Bullet(self.player_id, pos, vel, ttl=C.BULLET_TTL))
        return result

    def apply_weapon(self, mode: str) -> None:
        """Activate or refresh the weapon power-up."""
        self.weapon_mode = mode
        self.weapon_time = float(C.WEAPON_DURATION)

    def hyperspace(self) -> None:
        self.pos = Vec(uniform(0, C.WIDTH), uniform(0, C.HEIGHT))
        self.vel.xy = (0, 0)
        self.invuln = float(C.SAFE_SPAWN_TIME)

    def activate_shield(self) -> None:
        # Renova ou estende — nunca encurta um escudo já ativo
        self.shield_timer = max(self.shield_timer, float(C.SHIELD_DURATION))
        self.has_shield = True

    def update(self, dt: float) -> None:
        if self.cool > 0.0:
            self.cool = max(0.0, self.cool - dt)

        if self.invuln > 0.0:
            self.invuln = max(0.0, self.invuln - dt)

        if self.shield_timer > 0.0:
            self.shield_timer -= dt
            if self.shield_timer <= 0.0:
                self.shield_timer = 0.0
                self.has_shield = False          # expira corretamente

        if self.weapon_time > 0.0:
            self.weapon_time -= dt
            if self.weapon_time <= 0.0:
                self.weapon_mode = None
                self.weapon_time = 0.0

        self.pos += self.vel * dt
        self.pos = wrap_pos(self.pos)
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def ship_points(self) -> tuple[Vec, Vec, Vec]:
        """Return the 3 vertices of the ship triangle."""
        dirv = angle_to_vec(self.angle)
        left = angle_to_vec(self.angle + C.SHIP_NOSE_ANGLE)
        right = angle_to_vec(self.angle - C.SHIP_NOSE_ANGLE)

        p1 = self.pos + dirv * self.r
        p2 = self.pos + left * self.r * C.SHIP_NOSE_SCALE
        p3 = self.pos + right * self.r * C.SHIP_NOSE_SCALE
        return p1, p2, p3


class UFO(pg.sprite.Sprite):
    """UFO with two movement behaviors and shooting."""

    def __init__(
        self,
        pos: Vec,
        small: bool,
        target_pos: Vec | None = None,
    ) -> None:
        super().__init__()
        self.small = small
        cfg = C.UFO_SMALL if small else C.UFO_BIG
        self.r = int(cfg["r"])

        self.pos = Vec(pos)
        self.vel = Vec(0, 0)
        self.speed = float(C.UFO_SPEED_SMALL if small else C.UFO_SPEED_BIG)
        self.cool = 0.0
        self.move_dir: Vec | None = None

        self.target_pos: Vec | None = None

        if self.small:
            self._lock_small_move_dir(target_pos)

        self._setup_crossing_if_needed()
        self.rect = pg.Rect(0, 0, self.r * 2, self.r * 2)

    def _lock_small_move_dir(self, target_pos: Vec | None) -> None:
        if target_pos is None:
            ang = uniform(0.0, 360.0)
            self.move_dir = Vec(math.cos(math.radians(ang)), math.sin(math.radians(ang)))
            return

        to_target = Vec(target_pos) - self.pos
        if to_target.length_squared() < 1e-6:
            ang = uniform(0.0, 360.0)
            self.move_dir = Vec(math.cos(math.radians(ang)), math.sin(math.radians(ang)))
            return

        self.move_dir = to_target.normalize()

    def _setup_crossing_if_needed(self) -> None:
        if self.small:
            return

        mode = choice(["h", "v", "d"])
        if mode == "h":
            y = uniform(0, C.HEIGHT)
            left_to_right = uniform(0, 1) < 0.5
            self.pos = Vec(0 if left_to_right else C.WIDTH, y)
            self.vel = Vec(1 if left_to_right else -1, 0) * self.speed
            return

        if mode == "v":
            x = uniform(0, C.WIDTH)
            top_to_bottom = uniform(0, 1) < 0.5
            self.pos = Vec(x, 0 if top_to_bottom else C.HEIGHT)
            self.vel = Vec(0, 1 if top_to_bottom else -1) * self.speed
            return

        corners = [
            Vec(0, 0),
            Vec(C.WIDTH, 0),
            Vec(0, C.HEIGHT),
            Vec(C.WIDTH, C.HEIGHT),
        ]
        start = choice(corners)
        target = Vec(C.WIDTH - start.x, C.HEIGHT - start.y)
        self.pos = Vec(start)
        dirv = (target - start)
        if dirv.length_squared() > 0:
            dirv = dirv.normalize()
        self.vel = dirv * self.speed

    def update(self, dt: float) -> None:
        if self.cool > 0.0:
            self.cool = max(0.0, self.cool - dt)
        if self.small:
            self._update_pursue(dt)
        else:
            self._update_cross(dt)

        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def _update_pursue(self, dt: float) -> None:
        if self.move_dir is not None:
            self.vel = self.move_dir * self.speed

        self.pos += self.vel * dt
        self._kill_if_outside_screen()

    def _update_cross(self, dt: float) -> None:
        self.pos += self.vel * dt
        self._kill_if_outside_screen()

    def _kill_if_outside_screen(self) -> None:
        margin = self.r
        if (self.pos.x < -margin or self.pos.x > C.WIDTH + margin or
                self.pos.y < -margin or self.pos.y > C.HEIGHT + margin):
            self.kill()

    def try_fire(self) -> "Bullet | None":
        if self.cool > 0.0:
            return None

        target_pos = self.target_pos
        if target_pos is None:
            return None

        if not self.small and random() < C.UFO_BIG_MISS_CHANCE:
            ang = uniform(0.0, 360.0)
            dirv = Vec(
                math.cos(math.radians(ang)),
                math.sin(math.radians(ang)),
            )
        else:
            to_target = target_pos - self.pos
            if to_target.length_squared() < 1e-6:
                return None
            dirv = to_target.normalize()
        jitter = C.UFO_AIM_JITTER_DEG_SMALL if self.small else C.UFO_AIM_JITTER_DEG_BIG
        dirv = rotate_vec(dirv, uniform(-jitter, jitter))

        vel = dirv * C.UFO_BULLET_SPEED


        rate = C.UFO_FIRE_RATE_SMALL if self.small else C.UFO_FIRE_RATE_BIG
        self.cool = float(rate)

        return Bullet(UFO_BULLET_OWNER, self.pos, vel, ttl=float(C.UFO_BULLET_TTL))


class ShieldPickup(pg.sprite.Sprite):
    """Collectible item that grants a temporary shield."""

    def __init__(self, pos: Vec) -> None:
        super().__init__()
        self.pos = Vec(pos)
        # Drift lento em direção aleatória
        self.vel = rand_unit_vec() * uniform(18.0, 36.0)
        self._base_r = int(C.SHIELD_PICKUP_RADIUS)
        self.r = self._base_r
        self.ttl = float(C.SHIELD_PICKUP_LIFETIME)
        self._pulse = 0.0          # fase do pulso visual
        self._draw_color = C.SHIELD_COLOR
        self._draw_visible = True
        self.rect = pg.Rect(0, 0, self.r * 2, self.r * 2)
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def update(self, dt: float) -> None:
        self.pos += self.vel * dt
        self.pos = wrap_pos(self.pos)

        self._pulse = (self._pulse + dt * 3.5) % (2 * math.pi)

        self.ttl -= dt
        if self.ttl <= 0.0:
            self.kill()
            return

        warn = float(C.SHIELD_PICKUP_WARN_TIME)
        if self.ttl > warn:
            self.r = self._base_r
            self._draw_color = C.SHIELD_COLOR
            self._draw_visible = True
        else:
            urgency = 1.0 - max(0.0, self.ttl / warn)
            self.r = int(self._base_r * (1.0 - urgency * 0.4))
            blink_rate = 8.0 + urgency * 16.0
            self._draw_visible = int(self.ttl * blink_rate) % 2 == 0
            c = C.SHIELD_COLOR
            self._draw_color = (
                min(255, int(c[0] + (255 - c[0]) * urgency * 0.9)),
                min(255, int(c[1] + (255 - c[1]) * urgency * 0.4)),
                max(80,  int(c[2] * (1.0 - urgency * 0.4))),
            )

        side = max(4, self.r * 2)
        self.rect = pg.Rect(0, 0, side, side)
        self.rect.center = (int(self.pos.x), int(self.pos.y))


class WeaponPickup(pg.sprite.Sprite):
    """Collectible item that grants a temporary weapon buff."""

    MODES = ("double", "triple", "rapid")
    _LABELS = {"double": "2x", "triple": "3x", "rapid": ">>"}

    def __init__(self, pos: Vec) -> None:
        super().__init__()
        import random
        self.pos = Vec(pos)
        self.vel = rand_unit_vec() * uniform(20.0, 45.0)
        self.mode = random.choice(self.MODES)
        self._base_r = int(C.WEAPON_PICKUP_RADIUS)
        self.r = self._base_r
        self.ttl = float(C.WEAPON_PICKUP_LIFETIME)
        self._draw_color = C.WEAPON_PICKUP_COLOR
        self._draw_visible = True
        self.rect = pg.Rect(0, 0, self.r * 2, self.r * 2)
        self.rect.center = (int(self.pos.x), int(self.pos.y))

    def update(self, dt: float) -> None:
        self.pos += self.vel * dt
        self.pos = wrap_pos(self.pos)
        self.ttl -= dt
        if self.ttl <= 0.0:
            self.kill()
            return
        warn = float(C.WEAPON_PICKUP_WARN_TIME)
        if self.ttl > warn:
            self._draw_color = C.WEAPON_PICKUP_COLOR
            self._draw_visible = True
            self.r = self._base_r
        else:
            urgency = 1.0 - max(0.0, self.ttl / warn)
            self.r = int(self._base_r * (1.0 - urgency * 0.45))
            blink_rate = 10.0 + urgency * 18.0
            self._draw_visible = int(self.ttl * blink_rate) % 2 == 0
            c = C.WEAPON_PICKUP_COLOR
            self._draw_color = (
                c[0],
                min(255, int(c[1] * (1.0 - urgency * 0.5))),
                max(0,   int(c[2] * (1.0 - urgency * 0.9))),
            )
        side = max(4, self.r * 2)
        self.rect = pg.Rect(0, 0, side, side)
        self.rect.center = (int(self.pos.x), int(self.pos.y))