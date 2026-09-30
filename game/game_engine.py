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

        self.marble = Marble(50, 50)
        self.tilt_strength = 0.6
        self.friction = 0.02
        self.max_speed = 9

        self.walls = self._build_maze()
        self.goal_x, self.goal_y, self.goal_radius = width - 60, height - 60, 22

        self.time_limit_ms = 45000
        self.start_ticks = pygame.time.get_ticks()
        self.elapsed_ms = 0

        self.font = pygame.font.SysFont("Arial", 26)
        self.game_over = False
        self.result = None  # "solved" or "timeout"
        self.finish_time_ms = None

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
        if not self.game_over:
            return

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                self._restart_game()
            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                raise SystemExit

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
        if self.game_over:
            return

        elapsed = pygame.time.get_ticks() - self.start_ticks
        self.elapsed_ms = elapsed
        if elapsed >= self.time_limit_ms:
            self.elapsed_ms = self.time_limit_ms
            self.game_over = True
            self.result = "timeout"
            self.finish_time_ms = None
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
                bounce = 0.3
                self.marble.vx -= (1 + bounce) * velocity_into_wall * nx
                self.marble.vy -= (1 + bounce) * velocity_into_wall * ny

    def render(self, screen):
        screen.fill(DARK)

        for wall in self.walls:
            pygame.draw.rect(screen, WALL_COLOR, wall.rect())

        pygame.draw.circle(screen, GOAL_COLOR, (self.goal_x, self.goal_y), self.goal_radius)
        pygame.draw.circle(screen, WHITE, (int(self.marble.x), int(self.marble.y)), self.marble.radius)

        # timer freezes once the round ends
        seconds_left = max(0, (self.time_limit_ms - self.elapsed_ms) // 1000)
        timer_text = self.font.render(f"Time: {seconds_left}s", True, WHITE)
        screen.blit(timer_text, (10, 10))

        if self.game_over:
            # Dark translucent overlay
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            screen.blit(overlay, (0, 0))

            # Fonts
            title_font = pygame.font.SysFont("Arial", 48, bold=True)
            message_font = pygame.font.SysFont("Arial", 30)
            instruction_font = pygame.font.SysFont("Arial", 24)

            if self.result == "solved":
                title_text = "Maze Solved!"
                message_text = f"Finished in {self.finish_time_ms / 1000:.1f} seconds"
            else:
                title_text = "Time's Up!"
                message_text = "The maze was not solved."

            title_surface = title_font.render(title_text, True, WHITE)
            message_surface = message_font.render(message_text, True, WHITE)
            instruction_surface = instruction_font.render(
                "Press R, Enter, or Space to play again", True, WHITE
            )

            # Center everything on screen
            title_rect = title_surface.get_rect(
                center=(self.width // 2, self.height // 2 - 70)
            )
            message_rect = message_surface.get_rect(
                center=(self.width // 2, self.height // 2)
            )
            instruction_rect = instruction_surface.get_rect(
                center=(self.width // 2, self.height // 2 + 60)
            )

            screen.blit(title_surface, title_rect)
            screen.blit(message_surface, message_rect)
            screen.blit(instruction_surface, instruction_rect)

    def _restart_game(self):
        self.marble = Marble(50, 50)
        self.start_ticks = pygame.time.get_ticks()
        self.elapsed_ms = 0
        self.game_over = False
        self.result = None
        self.finish_time_ms = None
