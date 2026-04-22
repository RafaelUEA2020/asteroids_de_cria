"""Game systems (World, waves, score)."""

import math
from random import uniform
from typing import Dict

import pygame as pg

from core import config as C
from core.collisions import CollisionManager
from core.commands import PlayerCommand
from core.entities import Asteroid, BlackHole, Ship, UFO, WeaponPickup
from core.utils import Vec, rand_edge_pos

PlayerId = int


class World:
    """World state and game rules.

    Multiplayer-ready:
    - World receives commands indexed by player_id.
    - World generates events (strings) for the client (sounds/effects).
    """

    def __init__(self) -> None:
        self.ships: Dict[PlayerId, Ship] = {}
        self.bullets = pg.sprite.Group()
        self.asteroids = pg.sprite.Group()
        self.ufos = pg.sprite.Group()
        self.shields = pg.sprite.Group() 
        self.weapon_pickups = pg.sprite.Group()
        self.black_holes = pg.sprite.Group()
        self.all_sprites = pg.sprite.Group()

        self.scores: Dict[PlayerId, int] = {}
        self.lives: Dict[PlayerId, int] = {}
        self.wave = 0
        self.wave_cool = float(C.WAVE_DELAY)
        self.ufo_timer = float(C.UFO_SPAWN_EVERY)

        self.events: list[str] = []
        self._collision_mgr = CollisionManager()

        self.game_over = False
        self.shield_spawn_timer = float(C.SHIELD_SPAWN_DELAY_MIN)
        self.black_hole_spawn_timer = float(C.BLACK_HOLE_SPAWN_DELAY_MIN)
        self.spawn_player(C.LOCAL_PLAYER_ID)
        
        self.freeze_active = False
        self.freeze_timer = 0.0
        

    def begin_frame(self) -> None:
        self.events.clear()

    def reset(self) -> None:
        """Reset the world (used on Game Over)."""
        self.__init__()

    def spawn_player(self, player_id: PlayerId) -> None:
        pos = Vec(C.WIDTH / 2, C.HEIGHT / 2)
        ship = Ship(player_id, pos)
        ship.invuln = float(C.SAFE_SPAWN_TIME)

        self.ships[player_id] = ship
        self.scores[player_id] = 0
        self.lives[player_id] = C.START_LIVES
        self.all_sprites.add(ship)

    def get_ship(self, player_id: PlayerId) -> Ship | None:
        return self.ships.get(player_id)

    def start_wave(self) -> None:
        self.wave += 1
        count = C.WAVE_BASE_COUNT + self.wave

        ship_positions = [s.pos for s in self.ships.values()]

        for _ in range(count):
            pos = rand_edge_pos()
            while any(
                (pos - sp).length() < C.AST_MIN_SPAWN_DIST
                for sp in ship_positions
            ):
                pos = rand_edge_pos()

            ang = uniform(0, math.tau)
            speed = uniform(C.AST_VEL_MIN, C.AST_VEL_MAX)
            vel = Vec(math.cos(ang), math.sin(ang)) * speed
            self.spawn_asteroid(pos, vel, "L")

    def spawn_asteroid(self, pos: Vec, vel: Vec, size: str) -> None:
        ast = Asteroid(pos, vel, size)
        self.asteroids.add(ast)
        self.all_sprites.add(ast)

    def spawn_ufo(self) -> None:
        small = uniform(0, 1) < 0.5
        pos = rand_edge_pos()
        target = self._get_nearest_ship_pos(pos)
        ufo = UFO(pos, small, target_pos=target)
        self.ufos.add(ufo)

        self.all_sprites.add(ufo)

    def update(
        self,
        dt: float,
        commands_by_player_id: Dict[PlayerId, PlayerCommand],
    ) -> None:
        self.begin_frame()

        # Atualiza freeze
        if self.freeze_active:
            self.freeze_timer -= dt
            if self.freeze_timer <= 0.0:
                self.freeze_active = False
                
        if self.game_over:
            return

        self._apply_commands(dt, commands_by_player_id)
        self._apply_black_hole_gravity(dt)
        
        for sprite in self.all_sprites:
            if self.freeze_active and isinstance(sprite, Asteroid):
                continue
            sprite.update(dt)

        self._update_ufos(dt)
        self._update_timers(dt)
        self._handle_collisions()
        self._handle_black_hole_capture()
        self._maybe_start_next_wave(dt)

    def _update_timers(self, dt: float) -> None:
        # Timer do UFO
        self.ufo_timer -= dt
        if self.ufo_timer <= 0.0:
            self.spawn_ufo()
            self.ufo_timer = float(C.UFO_SPAWN_EVERY)

        # Lógica de Spawn Automático do Escudo
        if self.wave > 0: # Só spawna se a partida começou
            self.shield_spawn_timer -= dt
            if self.shield_spawn_timer <= 0.0:
                # Se ainda houver vaga no mapa (limite de 2)
                if len(self.shields) < C.SHIELD_MAX_PICKUPS:
                    self.spawn_shield_pickup()

                # Sorteia o próximo tempo baseado no seu config.py
                self.shield_spawn_timer = uniform(
                    C.SHIELD_SPAWN_DELAY_MIN, 
                    C.SHIELD_SPAWN_DELAY_MAX
                )

        if self.wave > 0:
            self.black_hole_spawn_timer -= dt
            if self.black_hole_spawn_timer <= 0.0:
                if len(self.black_holes) < C.BLACK_HOLE_MAX_ACTIVE:
                    self.spawn_black_hole()

                self.black_hole_spawn_timer = uniform(
                    C.BLACK_HOLE_SPAWN_DELAY_MIN,
                    C.BLACK_HOLE_SPAWN_DELAY_MAX,
                )

    def _apply_commands(
        self,
        dt: float,
        commands_by_player_id: Dict[PlayerId, PlayerCommand],
    ) -> None:
        for player_id, cmd in commands_by_player_id.items():
            ship = self.get_ship(player_id)
            if ship is None:
                continue

            if cmd.hyperspace:
                ship.hyperspace()
                self.scores[player_id] = max(
                    0, self.scores[player_id] - C.HYPERSPACE_COST
                )

            # fire() agora retorna lista
            new_bullets = ship.apply_command(cmd, dt, self.bullets)
            for bullet in new_bullets:
                self.bullets.add(bullet)
                self.all_sprites.add(bullet)
            if new_bullets:
                self.events.append("player_shoot")

    def _update_ufos(self, dt: float) -> None:
        for ufo in list(self.ufos):
            ufo.target_pos = self._get_nearest_ship_pos(ufo.pos)
            ufo.update(dt)
            if not ufo.alive():
                continue

            bullet = ufo.try_fire()
            if bullet is not None:
                self.bullets.add(bullet)
                self.all_sprites.add(bullet)
                self.events.append("ufo_shoot")

            if not ufo.alive():
                self.ufos.remove(ufo)

    def _apply_black_hole_gravity(self, dt: float) -> None:
        if not self.black_holes:
            return

        for ship in self.ships.values():
            strongest_pull = Vec(0, 0)
            strongest_force = 0.0

            for black_hole in self.black_holes:
                offset = black_hole.pos - ship.pos
                dist = offset.length()
                if dist <= 1e-6 or dist > black_hole.attract_radius:
                    continue

                influence = 1.0 - (dist / black_hole.attract_radius)
                force = C.BLACK_HOLE_GRAVITY * influence
                if force <= strongest_force:
                    continue

                strongest_force = force
                strongest_pull = offset.normalize() * force

            if strongest_force > 0.0:
                ship.vel += strongest_pull * dt

    def _get_nearest_ship_pos(self, from_pos: Vec) -> Vec | None:
        """Return position of the nearest living ship to from_pos."""
        nearest = None
        min_dist = float("inf")
        for ship in self.ships.values():
            d = (ship.pos - from_pos).length()
            if d < min_dist:
                min_dist = d
                nearest = ship
        return nearest.pos if nearest else None

    def _maybe_start_next_wave(self, dt: float) -> None:
        if self.asteroids:
            return

        self.wave_cool -= dt
        if self.wave_cool <= 0.0:
            self.start_wave()
            self.wave_cool = float(C.WAVE_DELAY)
    def _try_spawn_weapon_pickup(self, pos: Vec,force: bool = False) -> None:
        import random
        import random
        # Se force for True, ignora a chance aleatória
        if not force and random.random() > C.WEAPON_PICKUP_CHANCE:
            return
        
        if random.random() > C.WEAPON_PICKUP_CHANCE:
            return
        if len(self.weapon_pickups) >= C.WEAPON_MAX_PICKUPS:
            return
        for p in self.weapon_pickups:
            if (p.pos - pos).length() < C.WEAPON_PICKUP_SEPARATION:
                return
        wp = WeaponPickup(pos)
        self.weapon_pickups.add(wp)
        self.all_sprites.add(wp)

    def _handle_collisions(self) -> None:
        # Colisão com shield pickups
        for player_id, ship in self.ships.items():
            pickups_hit = pg.sprite.spritecollide(ship, self.shields, True)
            if pickups_hit:
                ship.activate_shield() 
                self.events.append("shield_up") 

        # Colisão com weapon pickups
        for player_id, ship in self.ships.items():
            wp_hit = pg.sprite.spritecollide(ship, self.weapon_pickups, True)
            for wp in wp_hit:
                ship.apply_weapon(wp.mode)
                self.events.append("shield_up")   # reutiliza som de coleta

        result = self._collision_mgr.resolve(
            self.ships, self.bullets, self.asteroids, self.ufos,
        )

        self.events.extend(result.events)

        for player_id, delta in result.score_deltas.items():
            if player_id in self.scores:
                self.scores[player_id] += delta

        for pos, vel, size in result.asteroids_to_spawn:
            self.spawn_asteroid(pos, vel, size)
            # Tenta dropar weapon pickup ao destruir fragmento L
            if size == "M":
                print(f"DEBUG: Tentando drop de arma em {pos}")
                self._try_spawn_weapon_pickup(pos)

        for player_id in result.ship_deaths:
            ship = self.get_ship(player_id)
            if ship is not None:
                self._ship_die(ship)

    def _handle_black_hole_capture(self) -> None:
        if self.game_over:
            return

        for ship in self.ships.values():
            for black_hole in self.black_holes:
                if (ship.pos - black_hole.pos).length() < (ship.r + black_hole.capture_radius):
                    self._black_hole_capture(ship)
                    return

    def _ship_die(self, ship: Ship) -> None:
        pid = ship.player_id
        self.lives[pid] -= 1
        ship.pos.xy = (C.WIDTH / 2, C.HEIGHT / 2)
        ship.vel.xy = (0, 0)
        ship.angle = -90.0
        ship.invuln = float(C.SAFE_SPAWN_TIME)

        self.events.append("ship_explosion")
        if all(v <= 0 for v in self.lives.values()):
            self.game_over = True

    def _black_hole_capture(self, ship: Ship) -> None:
        self.lives[ship.player_id] = 0
        self.events.append("ship_explosion")
        self.game_over = True

    def spawn_shield_pickup(self) -> None:
        if len(self.shields) >= C.SHIELD_MAX_PICKUPS:
            return

        # Sorteia uma posição em qualquer lugar da tela
        def get_random_pos():
            return Vec(
                uniform(60, C.WIDTH - 60), 
                uniform(60, C.HEIGHT - 60)
            )

        pos = get_random_pos()
        
        # Garante que não spawna colado no jogador
        ship_positions = [s.pos for s in self.ships.values()]
        
        # Tenta re-sortear se estiver muito perto de um jogador (limite de 10 tentativas para não travar)
        for _ in range(10):
            if any((pos - sp).length() < C.SHIELD_PICKUP_SEPARATION for sp in ship_positions):
                pos = get_random_pos()
            else:
                break

        from core.entities import ShieldPickup 
        pickup = ShieldPickup(pos)
        self.shields.add(pickup)
        self.all_sprites.add(pickup)

    def spawn_black_hole(self) -> None:
        if len(self.black_holes) >= C.BLACK_HOLE_MAX_ACTIVE:
            return

        def get_random_pos() -> Vec:
            margin = C.BLACK_HOLE_CAPTURE_RADIUS + 40
            return Vec(
                uniform(margin, C.WIDTH - margin),
                uniform(margin, C.HEIGHT - margin),
            )

        ship_positions = [s.pos for s in self.ships.values()]
        pos = get_random_pos()

        for _ in range(12):
            too_close_to_ship = any(
                (pos - ship_pos).length() < C.BLACK_HOLE_MIN_SHIP_DISTANCE
                for ship_pos in ship_positions
            )
            too_close_to_hole = any(
                (pos - black_hole.pos).length() < C.BLACK_HOLE_ATTRACT_RADIUS
                for black_hole in self.black_holes
            )
            if not too_close_to_ship and not too_close_to_hole:
                break
            pos = get_random_pos()

        black_hole = BlackHole(pos)
        self.black_holes.add(black_hole)
        self.all_sprites.add(black_hole)

    def activate_freeze(self, duration: float) -> None:
        self.freeze_active = True
        self.freeze_timer = duration