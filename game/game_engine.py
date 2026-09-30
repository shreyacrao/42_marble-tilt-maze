import math
import array

import pygame
from .marble import Marble
from .wall import Wall

# Game Engine

WHITE = (255, 255, 255)
DARK = (40, 40, 50)
WALL_COLOR = (90, 90, 110)
GOAL_COLOR = (60, 200, 120)


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        pygame.mixer.init()
        self._load_sounds()

        self.marble = Marble(50, 50)

        self.difficulty = None

        self.difficulty_settings = {
            "Easy": {
                "tilt_strength": 0.4,
                "friction": 0.04,
                "time_limit_ms": 60000
            },
            "Medium": {
                "tilt_strength": 0.6,
                "friction": 0.02,
                "time_limit_ms": 45000
            },
            "Hard": {
                "tilt_strength": 0.9,
                "friction": 0.01,
                "time_limit_ms": 30000
            }
        }

        self.tilt_strength = 0.6
        self.friction = 0.02
        self.max_speed = 9

        self.walls = self._build_maze()
        self.goal_x, self.goal_y, self.goal_radius = width - 60, height - 60, 22

        self.time_limit_ms = 45000
        self.start_ticks = pygame.time.get_ticks()

        self.font = pygame.font.SysFont("Arial", 26)
        self.game_over = False
        self.result = None  # "solved" or "timeout"
        self.finish_time_ms = None
        self.show_difficulty_screen = False

        # Bounce sound cooldown (ms) so sliding along a wall doesn't spam
        self.last_bounce_sound = 0
        self.bounce_sound_cooldown = 80

    def _load_sounds(self):
        """
        Create simple sound effects programmatically.
        No external sound files are required.
        """

        # Match whatever the mixer was actually initialised with
        # (pygame.init() usually starts it in stereo).
        sample_rate, _, channels = pygame.mixer.get_init()

        def make_tone(frequency, duration, volume=0.3):
            samples = int(sample_rate * duration)
            buffer = array.array("h")

            for i in range(samples):
                t = i / sample_rate

                # Fade out toward the end to avoid clicks
                fade = 1.0 - (i / samples)

                value = (
                    math.sin(2 * math.pi * frequency * t)
                    * volume
                    * fade
                )

                # One copy of the sample per channel (mono or stereo)
                for _ in range(channels):
                    buffer.append(int(value * 32767))

            return pygame.mixer.Sound(buffer=buffer)

        # Wall bounce: short, low "thump"
        self.bounce_sound = make_tone(
            180,
            0.08,
            0.35
        )

        # Goal: higher, longer tone
        self.goal_sound = make_tone(
            700,
            0.30,
            0.35
        )

        # Timeout: lower tone
        self.timeout_sound = make_tone(
            120,
            0.45,
            0.35
        )

    def _build_maze(self):
        walls = []
        t = 16  # wall thickness

        # outer boundary
        walls.append(Wall(0, 0, self.width, t))
        walls.append(Wall(0, self.height - t, self.width, t))
        walls.append(Wall(0, 0, t, self.height))
        walls.append(Wall(self.width - t, 0, t, self.height))

        # a few internal walls forming a simple winding path
        walls.append(Wall(0, 140, self.width - 140, t))
        walls.append(Wall(140, 260, self.width - 140, t))
        walls.append(Wall(0, 380, self.width - 140, t))

        return walls

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        # Difficulty selection screen
        if self.show_difficulty_screen:
            if event.key == pygame.K_1:
                self._start_new_game("Easy")

            elif event.key == pygame.K_2:
                self._start_new_game("Medium")

            elif event.key == pygame.K_3:
                self._start_new_game("Hard")

            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                raise SystemExit

            return

        # End screen
        if self.game_over:
            if event.key in (
                pygame.K_r,
                pygame.K_RETURN,
                pygame.K_SPACE
            ):
                self.show_difficulty_screen = True

            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                raise SystemExit

    def _start_new_game(self, difficulty):
        settings = self.difficulty_settings[difficulty]

        self.difficulty = difficulty

        self.tilt_strength = settings["tilt_strength"]
        self.friction = settings["friction"]
        self.time_limit_ms = settings["time_limit_ms"]

        # Reset marble
        self.marble = Marble(50, 50)

        # Reset game state
        self.game_over = False
        self.result = None
        self.finish_time_ms = None

        # Hide difficulty screen
        self.show_difficulty_screen = False

        # Restart timer
        self.start_ticks = pygame.time.get_ticks()

    def handle_input(self):
        if self.game_over:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = mouse_x - self.width // 2
        dy = mouse_y - self.height // 2
        dist = max(1, (dx ** 2 + dy ** 2) ** 0.5)
        ax = (dx / dist) * self.tilt_strength
        ay = (dy / dist) * self.tilt_strength
        self.marble.vx += ax
        self.marble.vy += ay

    def update(self):
        if self.game_over or self.show_difficulty_screen:
            return

        elapsed = pygame.time.get_ticks() - self.start_ticks
        if elapsed >= self.time_limit_ms:
            self.game_over = True
            self.result = "timeout"
            self.finish_time_ms = None

            self.timeout_sound.play()

            return

        self.marble.vx *= (1 - self.friction)
        self.marble.vy *= (1 - self.friction)

        speed = (self.marble.vx ** 2 + self.marble.vy ** 2) ** 0.5
        if speed > self.max_speed:
            scale = self.max_speed / speed
            self.marble.vx *= scale
            self.marble.vy *= scale

        self.marble.x += self.marble.vx
        self.marble.y += self.marble.vy

        self._resolve_wall_collisions()

        gx = self.goal_x - self.marble.x
        gy = self.goal_y - self.marble.y
        if (gx ** 2 + gy ** 2) ** 0.5 <= self.goal_radius:
            self.game_over = True
            self.result = "solved"
            self.finish_time_ms = elapsed

            self.goal_sound.play()

    def _resolve_wall_collisions(self):
        for wall in self.walls:
            wall_rect = wall.rect()

            # Marble center
            cx = self.marble.x
            cy = self.marble.y
            r = self.marble.radius

            # Find the closest point on the rectangle to the marble center
            closest_x = max(wall_rect.left, min(cx, wall_rect.right))
            closest_y = max(wall_rect.top, min(cy, wall_rect.bottom))

            dx = cx - closest_x
            dy = cy - closest_y

            distance_squared = dx * dx + dy * dy

            # No collision: the actual circular marble does not touch the wall
            if distance_squared > r * r:
                continue

            # Determine collision normal
            if distance_squared > 0:
                # Normal from wall toward marble
                distance = distance_squared ** 0.5
                nx = dx / distance
                ny = dy / distance
            else:
                # Marble center is inside the wall rectangle.
                # Find the nearest wall face and push the marble out.
                distances = [
                    (abs(cx - wall_rect.left), -1, 0),
                    (abs(wall_rect.right - cx), 1, 0),
                    (abs(cy - wall_rect.top), 0, -1),
                    (abs(wall_rect.bottom - cy), 0, 1),
                ]
                _, nx, ny = min(distances, key=lambda item: item[0])

            # Push marble out of the wall
            if distance_squared > 0:
                penetration = r - distance
                if penetration > 0:
                    self.marble.x += nx * penetration
                    self.marble.y += ny * penetration
            else:
                # Center was inside the wall: move to the nearest valid position.
                if nx != 0:
                    self.marble.x = (
                        wall_rect.left - r if nx < 0 else wall_rect.right + r
                    )
                else:
                    self.marble.y = (
                        wall_rect.top - r if ny < 0 else wall_rect.bottom + r
                    )

            # Bounce only if moving INTO the wall
            velocity_into_wall = self.marble.vx * nx + self.marble.vy * ny

            if velocity_into_wall < 0:
                # Play the bounce sound (with cooldown)
                now = pygame.time.get_ticks()

                if now - self.last_bounce_sound >= self.bounce_sound_cooldown:
                    self.bounce_sound.play()
                    self.last_bounce_sound = now

                bounce = 0.3
                self.marble.vx -= (1 + bounce) * velocity_into_wall * nx
                self.marble.vy -= (1 + bounce) * velocity_into_wall * ny

    def render(self, screen):
        screen.fill(DARK)

        # Draw maze
        for wall in self.walls:
            pygame.draw.rect(screen, WALL_COLOR, wall.rect())

        # Draw goal
        pygame.draw.circle(
            screen,
            GOAL_COLOR,
            (self.goal_x, self.goal_y),
            self.goal_radius
        )

        # Draw marble
        pygame.draw.circle(
            screen,
            WHITE,
            (int(self.marble.x), int(self.marble.y)),
            self.marble.radius
        )

        # Draw timer only while playing
        if not self.game_over and not self.show_difficulty_screen:
            elapsed = pygame.time.get_ticks() - self.start_ticks
            seconds_left = max(
                0,
                (self.time_limit_ms - elapsed) // 1000
            )

            timer_text = self.font.render(
                f"Time: {seconds_left}s",
                True,
                WHITE
            )

            screen.blit(timer_text, (10, 10))

            # Show current difficulty
            difficulty_text = self.font.render(
                f"Difficulty: {self.difficulty or 'Medium'}",
                True,
                WHITE
            )

            screen.blit(
                difficulty_text,
                (10, 45)
            )

        # Difficulty selection screen
        if self.show_difficulty_screen:
            self._render_difficulty_screen(screen)

        # Game-over screen
        elif self.game_over:
            self._render_game_over_screen(screen)

    def _render_game_over_screen(self, screen):
        overlay = pygame.Surface(
            (self.width, self.height),
            pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))

        title_font = pygame.font.SysFont(
            "Arial",
            48,
            bold=True
        )

        message_font = pygame.font.SysFont(
            "Arial",
            30
        )

        instruction_font = pygame.font.SysFont(
            "Arial",
            24
        )

        if self.result == "solved":
            title_text = "Maze Solved!"
            message_text = (
                f"Finished in "
                f"{self.finish_time_ms / 1000:.1f} seconds"
            )
        else:
            title_text = "Time's Up!"
            message_text = "The maze was not solved."

        title_surface = title_font.render(
            title_text,
            True,
            WHITE
        )

        message_surface = message_font.render(
            message_text,
            True,
            WHITE
        )

        instruction_surface = instruction_font.render(
            "Press R, Enter, or Space to continue",
            True,
            WHITE
        )

        screen.blit(
            title_surface,
            title_surface.get_rect(
                center=(
                    self.width // 2,
                    self.height // 2 - 70
                )
            )
        )

        screen.blit(
            message_surface,
            message_surface.get_rect(
                center=(
                    self.width // 2,
                    self.height // 2
                )
            )
        )

        screen.blit(
            instruction_surface,
            instruction_surface.get_rect(
                center=(
                    self.width // 2,
                    self.height // 2 + 60
                )
            )
        )

    def _render_difficulty_screen(self, screen):
        overlay = pygame.Surface(
            (self.width, self.height),
            pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 210))
        screen.blit(overlay, (0, 0))

        title_font = pygame.font.SysFont(
            "Arial",
            44,
            bold=True
        )

        option_font = pygame.font.SysFont(
            "Arial",
            30
        )

        instruction_font = pygame.font.SysFont(
            "Arial",
            22
        )

        title_surface = title_font.render(
            "Choose Difficulty",
            True,
            WHITE
        )

        screen.blit(
            title_surface,
            title_surface.get_rect(
                center=(
                    self.width // 2,
                    self.height // 2 - 120
                )
            )
        )

        options = [
            ("1", "Easy", "60 seconds"),
            ("2", "Medium", "45 seconds"),
            ("3", "Hard", "30 seconds"),
        ]

        start_y = self.height // 2 - 50

        for i, (key, name, time_limit) in enumerate(options):
            text = f"{key} - {name}   ({time_limit})"

            surface = option_font.render(
                text,
                True,
                WHITE
            )

            screen.blit(
                surface,
                surface.get_rect(
                    center=(
                        self.width // 2,
                        start_y + i * 55
                    )
                )
            )

        instruction = instruction_font.render(
            "Press 1, 2, or 3 to start    |    Esc to exit",
            True,
            WHITE
        )

        screen.blit(
            instruction,
            instruction.get_rect(
                center=(
                    self.width // 2,
                    self.height // 2 + 130
                )
            )
        )
