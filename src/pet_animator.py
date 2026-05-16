# 完整文件：强制右跑，取消呼吸偏移，保持现有动作逻辑
import math
import random
from src.pet_state import PetAction, PetMood


class PetAnimator:
    def __init__(self):
        self.frame = 0
        self.blink_timer = 0
        self.is_blinking = False
        self.blink_duration = 0
        self.auto_action_timer = random.uniform(5, 15)
        self.action_timer = 0
        self.walk_speed = 1.5
        # 强制始终向右（使用右向素材）
        self.walk_direction = 1
        self.facing = 1
        self.breathe_frame = 0
        self.squash = 1.0
        self.special_action = None
        self.special_timer = 0

    def update(self, dt, state):
        self.frame += 1
        self.breathe_frame += 1

        if self.special_action == PetAction.LAND:
            self.squash = 0.55
        elif self.special_action == PetAction.GET_UP:
            self.squash += (1.0 - self.squash) * 0.03
        elif self.squash != 1.0:
            self.squash += (1.0 - self.squash) * 0.05
            if abs(self.squash - 1.0) < 0.01:
                self.squash = 1.0

        if self.special_action:
            self.special_timer -= dt
            if self.special_timer <= 0:
                if self.special_action == PetAction.LAND:
                    self.special_action = PetAction.GET_UP
                    self.special_timer = 1.5
                    state.current_action = PetAction.GET_UP
                elif self.special_action == PetAction.GET_UP:
                    self.special_action = None
                    self.squash = 1.0
                    state.current_action = PetAction.IDLE
                else:
                    self.special_action = None
                    state.current_action = PetAction.IDLE

        # 正在播放一次性动画时不自动切换动作
        _NO_AUTO = (PetAction.DRAG, PetAction.CLING, PetAction.LAND, PetAction.GET_UP,
                    PetAction.EAT, PetAction.PLAY, PetAction.CAT, PetAction.STUDY)
        if (not state.is_sleeping and not self.special_action
                and state.current_action not in _NO_AUTO):
            self._update_auto(dt, state)

        if self.action_timer > 0:
            self.action_timer -= dt
            if self.action_timer <= 0 and not state.is_sleeping:
                if state.current_action not in (
                    PetAction.DRAG, PetAction.CLING, PetAction.LAND, PetAction.GET_UP,
                    PetAction.EAT, PetAction.PLAY, PetAction.CAT, PetAction.STUDY):
                    state.current_action = PetAction.IDLE

    def _update_auto(self, dt, state):
        self.auto_action_timer -= dt
        if self.auto_action_timer <= 0:
            self.auto_action_timer = random.uniform(4, 12)
            self._choose_action(state)

    def _choose_action(self, state):
        if state.current_action in (PetAction.DRAG, PetAction.CLING):
            return
        mood = state.current_mood
        if mood == PetMood.HAPPY:
            pool = [(PetAction.WALK_LEFT, 25), (PetAction.WALK_RIGHT, 25),
                    (PetAction.DANCE, 15), (PetAction.IDLE, 20),
                    (PetAction.WAVE, 15)]
        elif mood == PetMood.SLEEPY:
            pool = [(PetAction.IDLE, 40), (PetAction.SLEEP, 40),
                    (PetAction.WALK_LEFT, 10), (PetAction.WALK_RIGHT, 10)]
        elif mood == PetMood.SAD:
            pool = [(PetAction.IDLE, 60), (PetAction.WALK_LEFT, 15),
                    (PetAction.WALK_RIGHT, 15), (PetAction.SLEEP, 10)]
        else:
            pool = [(PetAction.IDLE, 35), (PetAction.WALK_LEFT, 20),
                    (PetAction.WALK_RIGHT, 20), (PetAction.DANCE, 10),
                    (PetAction.WAVE, 15)]
        total = sum(w for _, w in pool)
        roll = random.uniform(0, total)
        c = 0
        chosen = PetAction.IDLE
        for a, w in pool:
            c += w
            if roll <= c:
                chosen = a
                break
        # 强制把任何左跑都改为向右跑（只使用右跑素材）
        if chosen == PetAction.WALK_LEFT:
            chosen = PetAction.WALK_RIGHT
        state.current_action = chosen
        if chosen in (PetAction.WALK_LEFT, PetAction.WALK_RIGHT):
            # 强制向右
            self.walk_direction = 1
            self.facing = 1
            self.action_timer = random.uniform(3, 8)
        elif chosen == PetAction.DANCE:
            self.action_timer = random.uniform(3, 6)
        elif chosen == PetAction.WAVE:
            self.action_timer = random.uniform(2, 4)
        elif chosen == PetAction.SLEEP:
            state.sleep()
        else:
            self.action_timer = random.uniform(2, 5)

    def get_breathe_offset(self):
        # 取消上下呼吸效果
        return 0.0

    def get_action_str(self, action):
        return {
            PetAction.IDLE: "idle", PetAction.WALK_LEFT: "walk",
            PetAction.WALK_RIGHT: "walk", PetAction.SLEEP: "sleep",
            PetAction.EAT: "eat", PetAction.PLAY: "play",
            PetAction.DRAG: "drag", PetAction.FALL: "fall",
            PetAction.DANCE: "dance", PetAction.WAVE: "wave",
            PetAction.CLING: "cling", PetAction.LAND: "land",
            PetAction.GET_UP: "getup",
            PetAction.CAT: "cat", PetAction.STUDY: "study",
        }.get(action, "idle")