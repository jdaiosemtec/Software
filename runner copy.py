"""
Mini endless runner (cleaned-up runner.py).

This is a corrected, top-level implementation of the prototype. Key
behaviour preserved:
- Hold-to-jump (Space)
- Crouch (Down) to avoid low obstacles
- Coins and bottles (bottles restore 1 HP)
- Mask-based collectible pickup
- Pause (Enter) and runtime re-import of `assets/child.png` (I key)

Run with: python runner.py
"""
import math
import os
import random
import pygame
from pygame import Rect

# --- Config ---
ASSETS_DIR = os.path.join(os.path.dirname(__file__), 'assets')
CHILD_IMG = os.path.join(ASSETS_DIR, 'child.png')
BLUEBERRY_IMG = os.path.join(ASSETS_DIR, 'blueberry.png')   # 蓝莓护盾
BUGI_SOUND  = os.path.join(ASSETS_DIR, 'bugi.wav') #音效
LOVE_SOUND  = os.path.join(ASSETS_DIR, 'love.wav') #音效
SHIELD_SOUND  = os.path.join(ASSETS_DIR, 'shield.wav') #音效
BROKE_SOUND  = os.path.join(ASSETS_DIR, 'broke.wav') #音效
HIT_SOUND = os.path.join(ASSETS_DIR, 'hit.wav')
METEOR_IMG  = os.path.join(ASSETS_DIR, 'meteor.png')   # 流星图片

SCREEN_W = 900
SCREEN_H = 500
GROUND_Y = SCREEN_H - 90
FPS = 60

BG_SCROLL_FACTOR = 0.28

def play_hit_sound():
    if os.path.exists(HIT_SOUND):
        pygame.mixer.Sound(HIT_SOUND).play()

def play_broke_sound():
    if os.path.exists(BROKE_SOUND):
        pygame.mixer.Sound(BROKE_SOUND).play()

def play_bugi_sound():
    if os.path.exists(BUGI_SOUND):
        pygame.mixer.Sound(BUGI_SOUND).play()

def play_shield_sound():
    if os.path.exists(SHIELD_SOUND):
        pygame.mixer.Sound(SHIELD_SOUND).play()

def play_love_sound():
    if os.path.exists(LOVE_SOUND):
        pygame.mixer.Sound(LOVE_SOUND).play()

def load_image(path):
    try:
        return pygame.image.load(path).convert_alpha()
    except Exception:
        return None


def make_transparent(surf, bg_color=(255, 255, 255), tol=12):
    """Return a copy of surf with pixels close to bg_color made transparent.

    This is intentionally simple and robust for a wide range of photos.
    """
    if surf is None:
        return None
    surf = surf.convert_alpha()
    w, h = surf.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(w):
        for y in range(h):
            r, g, b, a = surf.get_at((x, y))
            if abs(r - bg_color[0]) <= tol and abs(g - bg_color[1]) <= tol and abs(b - bg_color[2]) <= tol:
                out.set_at((x, y), (255, 255, 255, 0))
            else:
                out.set_at((x, y), (r, g, b, a))
    return out


class Player(pygame.sprite.Sprite):
    def __init__(self, child_surf=None):
        super().__init__()
        self.child_surf = make_transparent(child_surf) if child_surf is not None else None
        self.crouching = False
        self.space_holding = False
        self.vy = 0.0
        self.on_ground = True
        self.shield = False   # ← 新增在这
        self.image = pygame.Surface((96, 128), pygame.SRCALPHA)
        self.update_image()
        self.rect = self.image.get_rect()
        self.rect.left = 120
        self.rect.bottom = GROUND_Y
        self.mask = pygame.mask.from_surface(self.image)

    def update_image(self):
        self.image.fill((0, 0, 0, 0))
        if self.child_surf:
            cs_w = int(self.image.get_width())
            # crouch reduces child's height visually
            cs_h = cs_w if not self.crouching else int(cs_w * 0.66)
            cs_h = min(cs_h, self.image.get_height())
            cs = pygame.transform.smoothscale(self.child_surf, (cs_w, cs_h))
            y_child = self.image.get_height() - cs.get_height()
            x_child = max(0, (self.image.get_width() - cs.get_width()) // 2)
            self.image.blit(cs, (x_child, y_child))
        try:
            self.mask = pygame.mask.from_surface(self.image)
        except Exception:
            self.mask = None
        # 护盾外观：淡蓝圈
        if self.shield:
            cx, cy = self.image.get_width()//2, self.image.get_height()//2
            # 外层光晕
            pygame.draw.circle(self.image, (220, 215, 255, 160), (cx, cy), 58, 2)

    def update(self, dt):
        # gravity when not holding upward
        if not self.on_ground and not getattr(self, 'space_holding', False):
            self.vy += 1500 * dt
        self.rect.y += int(self.vy * dt)
        if self.rect.bottom >= GROUND_Y:
            self.rect.bottom = GROUND_Y
            self.vy = 0
            self.on_ground = True

    def start_crouch(self):
        if not self.crouching and self.on_ground:
            self.crouching = True
            old_bottom = self.rect.bottom
            self.image.fill((0,0,0,0))   # 清空
            self.update_image()          # 重画小孩+护盾（画在self.image）
            self.rect = self.image.get_rect()
            self.rect.left = 120
            self.rect.bottom = old_bottom

    def end_crouch(self):
        if self.crouching:
            self.crouching = False
            old_bottom = self.rect.bottom
            self.image.fill((0,0,0,0))   # 清空
            self.update_image()          # 重画小孩+护盾
            self.rect = self.image.get_rect()
            self.rect.left = 120
            self.rect.bottom = old_bottom


class Obstacle(pygame.sprite.Sprite):
    def __init__(self, x, w, h):
        super().__init__()
        self.image = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (120, 80, 40), Rect(0, 0, w, h))
        self.rect = self.image.get_rect()
        self.rect.left = x
        self.low = False
        self.rect.bottom = GROUND_Y

    def update(self, dx):
        # dx is expected to be a number (pixels to move left)
        try:
            self.rect.x -= int(dx)
        except Exception:
            pass

    def set_low(self):
        self.low = True
        base_h = random.randint(72, 200)
        new_h = base_h * 2
        old_left = self.rect.left
        w = max(60, self.rect.width)
        self.image = pygame.Surface((w, new_h), pygame.SRCALPHA)
        pygame.draw.rect(self.image, (120, 80, 40), Rect(0, 0, w, new_h))
        self.rect = self.image.get_rect()
        self.rect.left = old_left
        self.rect.bottom = GROUND_Y - 72


class Collectible(pygame.sprite.Sprite):
    def __init__(self, x, y, typ='coin'):
        super().__init__()
        self.typ = typ
        self.image = pygame.Surface((22, 28), pygame.SRCALPHA)
        if typ == 'coin':
            self._coin_front = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(self._coin_front, (255, 215, 0), (16, 16), 14)  # 亮黄
            self._coin_back = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(self._coin_back, (184, 134, 11), (16, 16), 14)  # 暗黄

            self._angle = 0          # 0° 正面，180° 反面
            self.image = self._coin_front
            self.rect = self.image.get_rect(center=(x, y))
        elif typ == 'bottle':
            # 奶瓶绘制开始
            body_rect = Rect(4, 6, 14, 16)
            # 奶瓶绘制结束
            pygame.draw.rect(self.image, (245, 245, 245), body_rect, border_radius=6)
            pygame.draw.rect(self.image, (200, 200, 200), body_rect, width=1, border_radius=6)
            neck_rect = Rect(8, 0, 6, 8)
            pygame.draw.rect(self.image, (245, 245, 245), neck_rect, border_radius=3)
            pygame.draw.rect(self.image, (200, 200, 200), neck_rect, width=1, border_radius=3)
            cap_rect = Rect(7, -2, 8, 4)
            pygame.draw.rect(self.image, (200, 220, 255), cap_rect, border_radius=2)
            pygame.draw.rect(self.image, (160, 180, 200), cap_rect, width=1, border_radius=2)
            pygame.draw.line(self.image, (255, 255, 255), (7, 9), (7, 18), 1)
            self.rect = self.image.get_rect(center=(x, y))
        elif typ == 'blueberry':                                    # 蓝莓绘制
            berry_surf = load_image(BLUEBERRY_IMG)
            if berry_surf:
                berry_surf = make_transparent(berry_surf, bg_color=(255,255,255), tol=20)
                # 裁成正方形再缩放
                w, h = berry_surf.get_size()
                side = min(w, h)
                crop = pygame.Rect((w-side)//2, (h-side)//2, side, side)
                berry_surf = berry_surf.subsurface(crop)
                self.image = pygame.transform.smoothscale(berry_surf, (24, 24))
            else:          # 无图时画蓝色圆
                self.image = pygame.Surface((20, 24), pygame.SRCALPHA)
                pygame.draw.circle(self.image, (50,120,255), (10, 12), 10)
                pygame.draw.circle(self.image, (30, 90, 200), (10, 12), 10, 2)
            self.rect = self.image.get_rect(center=(x, y))
        try:
            self.mask = pygame.mask.from_surface(self.image)
        except Exception:
            self.mask = None

    def update(self, dx): # 金币旋转
        self.rect.x -= int(dx)
        if self.typ == 'coin':
            self._angle = (self._angle + 6) % 360      # 每帧 6°，可调

            # 计算透视宽度
            rad = math.radians(self._angle)
            persp_width = max(1, int(32 * abs(math.cos(rad))))
            src = self._coin_front if abs(self._angle) < 180 else self._coin_back
            # 水平压缩 -> 3D 翻转
            self.image = pygame.transform.scale(src, (persp_width, 32))
            # 保持中心不变
            center = self.rect.center
            self.rect = self.image.get_rect(center=center)
            self.mask = pygame.mask.from_surface(self.image)


def game_over(screen, font, score):
    clock = pygame.time.Clock()
    overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    return True
                elif ev.key == pygame.K_ESCAPE:
                    return False
        screen.blit(overlay, (0, 0))
        txt1 = font.render('GAME OVER', True, (255, 255, 255))
        txt2 = font.render(f'Score: {score}', True, (255, 255, 255))
        txt3 = font.render('Press Enter to restart or Esc to quit', True, (220, 220, 220))
        screen.blit(txt1, (SCREEN_W // 2 - txt1.get_width() // 2, SCREEN_H // 2 - 40))
        screen.blit(txt2, (SCREEN_W // 2 - txt2.get_width() // 2, SCREEN_H // 2 - 8))
        screen.blit(txt3, (SCREEN_W // 2 - txt3.get_width() // 2, SCREEN_H // 2 + 24))
        pygame.display.flip()
        clock.tick(15)


def main():
    pygame.init()
    pygame.mixer.init()    
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption('Crazy Mason')
    clock = pygame.time.Clock()

    # assets
    child_img = load_image(CHILD_IMG)
    backgrounds = []
    bund_path = os.path.join(ASSETS_DIR, 'bund.jpg')
    if os.path.exists(bund_path):
        surf = load_image(bund_path)
        if surf:
           bg = pygame.transform.smoothscale(surf, (SCREEN_W, SCREEN_H))
    # 设置 80 % 不透明
           bg.set_alpha(155)          # 255 * 0.8 ≈ 204
           backgrounds.append(bg)

    # entities
    player = Player(child_surf=child_img)
    ########## STEP 2 开始：飘字组 ##########
    all_sprites = pygame.sprite.Group()
    ########## STEP 2 结束 ##########
    obstacles = pygame.sprite.Group()
    meteors = pygame.sprite.Group()
    collects = pygame.sprite.Group()

    # re-apply child if present
    if child_img:
        player.child_surf = make_transparent(child_img)
        player.update_image()

    paused = False
    score = 0
    speed = 280
    difficulty_timer = 0.0
    max_hp = 5
    hp = max_hp
    invuln_timer = 0.0

    bg_x1 = 0
    bg_w = backgrounds[0].get_width() if backgrounds else SCREEN_W

    space_charging_start = None
    max_charge = 0.7  # user's requested value
    base_jump = 650
    jump_mult_min = 2.0 / 3.0
    jump_mult_max = max(jump_mult_min, 1.06 / 3.0)

    obstacle_timer = 0.0
    collect_timer = 0.0
    font = pygame.font.SysFont('Arial', 20)
    coin_count = 0

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_RETURN:
                    paused = not paused
                    if paused:
                        player.space_holding = False
                        space_charging_start = None
                elif ev.key == pygame.K_i:
                    child_img = load_image(CHILD_IMG)
                    if child_img:
                        player.child_surf = make_transparent(child_img)
                        player.update_image()
                elif ev.key == pygame.K_SPACE:
                    if not paused and space_charging_start is None and player.on_ground:
                        space_charging_start = pygame.time.get_ticks()
                        player.space_holding = True
                        player.on_ground = False
                elif ev.key == pygame.K_DOWN:
                    if not paused:
                        player.start_crouch()
            elif ev.type == pygame.KEYUP:
                if ev.key == pygame.K_DOWN:
                    player.end_crouch()
                elif ev.key == pygame.K_SPACE:
                    player.space_holding = False
                    space_charging_start = None

        if paused:
            global sleep_surf
            # 第一次暂停时加载 sleep.jpg
            if 'sleep_surf' not in globals():
                sleep_path = os.path.join(ASSETS_DIR, 'sleep.jpg')
                sleep_surf = load_image(sleep_path)
                if sleep_surf:
                    sleep_surf = pygame.transform.smoothscale(sleep_surf, (SCREEN_W, SCREEN_H))
            # 画 sleep 图，没有则 fallback
            if sleep_surf:
                screen.blit(sleep_surf, (0, 0))
            else:
                screen.fill((135, 206, 250))
            pygame.display.flip()
            continue

        # spawn obstacles
        obstacle_timer -= dt
        if obstacle_timer <= 0:
            obstacle_w = random.randint(28, 62)
            obstacle_h = random.randint(28, 70)
            x = SCREEN_W + random.randint(10, 80)
            max_tries = 12
            tries = 0
            placed = False
            obs = None
            while tries < max_tries and not placed:
                obs = Obstacle(x, obstacle_w, obstacle_h)
                if random.random() < 0.22:
                    obs.set_low()
                conflict = False
                gap = int(player.rect.width * 0.2)
                for c in collects:
                    if obs.rect.inflate(gap, 0).colliderect(c.rect):
                        conflict = True
                        break
                if conflict:
                    x += random.randint(40, 100)
                    tries += 1
                    continue
                placed = True
            if obs:
                obstacles.add(obs)
            # increase obstacle spawn interval by 10%
            base_interval = max(0.85, 1.7 - (score / 4000.0))
            obstacle_timer = base_interval * 1.08

        # spawn collectibles
        collect_timer -= dt
        if collect_timer <= 0:
            cx = SCREEN_W + random.randint(40, 220)
            cy = GROUND_Y - random.randint(80, 160)
            r = random.random()
            if r < 0.04:                    # 4 % 奶瓶
                typ = 'bottle'
            elif r < 0.08:                  # 另外 8 % 蓝莓
                typ = 'blueberry'
            else:
                typ = 'coin'
            c = Collectible(cx, cy, typ=typ)
            gap = int(player.rect.width * 0.2)
            tries = 0
            placed = False
            while tries < 12 and not placed:
                crect = c.image.get_rect(center=(cx, cy))
                conflict = False
                for ob in obstacles:
                    if crect.colliderect(ob.rect.inflate(gap, 0)):
                        conflict = True
                        break
                if conflict:
                    cx += random.randint(40, 100)
                    tries += 1
                    continue
                placed = True
            c.rect = c.image.get_rect(center=(cx, cy))
            collects.add(c)
            collect_timer = random.uniform(1.2, 3.0)

        # difficulty
        difficulty_timer += dt
        if difficulty_timer > 5.0:
            difficulty_timer = 0.0
            speed += 6

        # hold-to-jump handling
        if space_charging_start is not None and getattr(player, 'space_holding', False):
            held_ms = pygame.time.get_ticks() - space_charging_start
            held_s = held_ms / 1000.0
            if held_s >= max_charge:
                player.space_holding = False
                space_charging_start = None
                player.vy = 0
            else:
                t = held_s / max_charge if max_charge > 0 else 1.0
                mult = jump_mult_min + (jump_mult_max - jump_mult_min) * t
                player.vy = -int(base_jump * mult)
                player.on_ground = False

        # update
        player.update(dt)
        ########## STEP 4-1 开始：更新飘字 ##########
        all_sprites.update(dt)
########## STEP 4-1 结束 ##########
        # 更新陨石
        meteors.update(dt)
        for m in list(meteors):
            if m.rect.top > SCREEN_H + 100:
                m.kill()
        for o in list(obstacles):
            o.update(speed * dt)
            if o.rect.right < -50:
                o.kill()
        for c in list(collects):
            c.update(speed * dt)
            if c.rect.right < -50:
                c.kill()

        # collisions: obstacles
        if invuln_timer > 0:
            invuln_timer -= dt
        hit = None
        for o in obstacles:
            if not o.rect.colliderect(player.rect):
                continue
            if getattr(o, 'low', False):
                head_h = max(8, int(player.rect.height * 0.35))
                head_rect = Rect(player.rect.left, player.rect.top, player.rect.width, head_h)
                if head_rect.colliderect(o.rect):
                    hit = o
                    break
                else:
                    continue
            else:
                hit = o
                break

        if hit:
            if getattr(hit, 'low', False) and player.crouching:
                pass
            else: #掉血逻辑
                if player.shield:
                    player.shield = False
                    play_broke_sound()
                    player.update_image()
                    hit.kill()
                    all_sprites.add(FloatText(player.rect.centerx, player.rect.top - 10,
                                              'Blocked!', (160, 0, 220)))
                else:
                    hp -= 1
                    play_hit_sound()
                invuln_timer = 1.0
                try:
                    hit.kill()
                except Exception:
                    pass
                if hp <= 0:
                    restart = game_over(screen, font, score)
                    if restart:
                        # reset state
                        obstacles.empty()
                        collects.empty()
                        player = Player(child_surf=child_img)
                        score = 0
                        speed = 280
                        coin_count = 0
                        difficulty_timer = 0.0
                        obstacle_timer = 0.0
                        collect_timer = 0.0
                        hp = max_hp
                        invuln_timer = 0.0
                        continue
                    else:
                        break

        # collectibles (mask-based)
        ########## STEP 3 开始：冒字 ##########
        collected = pygame.sprite.spritecollide(player, collects, dokill=True,
                                                collided=pygame.sprite.collide_mask)
        if collected:
            for item in collected:
                if item.typ == 'coin':
                    play_bugi_sound()
                    coin_count += 1
                    score += 100
                    # 白色 +100
                    all_sprites.add(FloatText(player.rect.centerx, player.rect.top - 10,
                                              '+100', (255, 215, 0)))
                elif item.typ == 'bottle':
                    play_love_sound()
                    hp = min(max_hp, hp + 1)
                    # 红色 +1
                    all_sprites.add(FloatText(player.rect.centerx, player.rect.top - 10,
                                              '+1', (255, 0, 0)))
                elif item.typ == 'blueberry': 
                    play_shield_sound()                      # 捡到蓝莓
                    player.shield = True
                    all_sprites.add(FloatText(player.rect.centerx, player.rect.top - 10,
                                              '+1', (160, 0, 220)))   # 紫色 +1
        score += int(speed * dt * 0.1)
        # 每 500 分触发一次陨石雨
        new_milestone = score // 500
        old_milestone = getattr(player, '_last_milestone', -1)
        if new_milestone > old_milestone:
            player._last_milestone = new_milestone
            for _ in range(new_milestone):
                x = random.randint(80, SCREEN_W - 80)
                meteors.add(Meteor(x))
        # 陨石碰撞
        for m in pygame.sprite.spritecollide(player, meteors, dokill=True):
            if player.shield:
                player.shield = False
                play_broke_sound()
                player.update_image()
                all_sprites.add(FloatText(player.rect.centerx, player.rect.top - 10,
                                          'Blocked!', (0, 200, 255)))
            else:
                hp -= 1
                play_hit_sound()
                invuln_timer = 1.0
                all_sprites.add(FloatText(player.rect.centerx, player.rect.top - 10,
                                          '-1', (255, 100, 0)))
                        # ===== 新增：统一检查致死 =====
            if hp <= 0:
                restart = game_over(screen, font, score)
                if restart:
                    obstacles.empty(); collects.empty(); meteors.empty()
                    player = Player(child_surf=child_img)
                    score = 0; speed = 280; difficulty_timer = 0.0
                    obstacle_timer = 0.0; collect_timer = 0.0
                    coin_count = 0
                    hp = max_hp; invuln_timer = 0.0
                    continue
                else:
                    break
        # ------------------------------

        # draw
        if backgrounds:
            bg_x1 -= speed * dt * BG_SCROLL_FACTOR
            if bg_x1 <= -bg_w:
                bg_x1 += bg_w
            # 画两张图，实现无缝循环
            screen.blit(backgrounds[0], (bg_x1, 0))
            screen.blit(backgrounds[0], (bg_x1 + bg_w, 0))
        else:
            screen.fill((135, 206, 250))
        # 开始画地面
        gh = SCREEN_H - GROUND_Y
        grass = pygame.Surface((SCREEN_W, gh), pygame.SRCALPHA)

        # 底色
        grass.fill((60, 160, 80))

        # 小草
        for _ in range(SCREEN_W // 60):        # 每 60 像素一株
            x = random.randint(0, SCREEN_W - 1)
            h = random.randint(10, 30)          # 草高
            y0 = gh - h                        # 从地面底部长出
            # 叶子
            for dx, dy in [(-3, -h), (0, -h*0.9), (3, -h)]:
                leaf = pygame.Rect(x + dx, y0 + int(dy), 4, h//2)
                pygame.draw.ellipse(grass, (40, 140, 60), leaf)
        grass.set_alpha(230) 
        screen.blit(grass, (0, GROUND_Y))
        screen.blit(player.image, player.rect)
                # 护盾圆环（盖在人物之上）
        if player.shield:
            cx, cy = player.rect.center
            pygame.draw.circle(screen,(220, 215, 255, 160), (cx, cy), 58, 2)  # 单圈 2 像素
        for o in obstacles:
            screen.blit(o.image, o.rect)
        for c in collects:
            screen.blit(c.image, c.rect)
        for m in meteors:
            screen.blit(m.image, m.rect)
########## STEP 4-2 开始：绘制飘字 ##########
        all_sprites.draw(screen)
########## STEP 4-2 结束 ##########
        # HUD
        scr_surf = font.render(f'Score: {score}', True, (30, 30, 30))
        screen.blit(scr_surf, (12, 12))
        coin_surf = font.render(f'Coins: {coin_count}', True, (30, 30, 30))
        screen.blit(coin_surf, (12, 36))
        for i in range(max_hp):
            cx = SCREEN_W - 20 - i * 28          # 爱心中心 x
            cy = 15 + 6                            # 中心 y
            col = (255, 20, 20) if i < hp else (120, 120, 120)
            # 标准 12×12 爱心坐标（cx,cy 为中心）
            heart = [
                (cx - 6, cy - 2), (cx - 4, cy - 6), (cx - 2, cy - 6),
                (cx, cy - 4), (cx + 2, cy - 6), (cx + 4, cy - 6),
                (cx + 6, cy - 2), (cx + 6, cy), (cx + 3, cy + 4),
                (cx, cy + 6), (cx - 3, cy + 4), (cx - 6, cy)
            ]
            pygame.draw.polygon(screen, col, heart)

        pygame.display.flip()

    pygame.quit()
########## STEP 1 开始：飘字类 ##########
class FloatText(pygame.sprite.Sprite):
    """向上飘的字符，生命周期 0.8 秒"""
    def __init__(self, x, y, text, color):
        super().__init__()
        self.image = pygame.font.SysFont('Arial', 22, bold=True).render(text, True, color)
        self.rect  = self.image.get_rect(center=(x, y))
        self.life  = 0.8
        self.vy    = -50          # 像素/秒

    def update(self, dt):
        self.life -= dt
        self.rect.y += int(self.vy * dt)
        if self.life <= 0:
            self.kill()
########## STEP 1 结束 ##########
class Meteor(pygame.sprite.Sprite):
    """从天而降的陨石，旋转下落，碰玩家 -1 HP"""
    _image = None

    @classmethod
    def _load_image(cls):
        if cls._image is None:
            cls._image = pygame.Surface((46, 46), pygame.SRCALPHA)
            pygame.draw.circle(cls._image, (60, 50, 50), (23, 23), 20)
            pygame.draw.circle(cls._image, (120, 100, 100), (23, 23), 20, 3)
            pygame.draw.circle(cls._image, (180, 160, 140), (15, 15), 5)

    def __init__(self, x):
        super().__init__()
        self._load_image()
        self.image = self._image.copy()
        self.rect = self.image.get_rect(midtop=(x, -60))
        self.vy = random.uniform(280, 380)
        self.vx = random.uniform(-40, 40)
        self.angle = 0
        self.rot_speed = random.uniform(-180, 180)

    def update(self, dt):
        self.angle += self.rot_speed * dt
        self.image = pygame.transform.rotate(self._image, self.angle)
        self.rect.x += int(self.vx * dt)
        self.rect.y += int(self.vy * dt)
if __name__ == '__main__':
    main()