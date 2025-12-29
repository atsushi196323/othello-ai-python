import pygame
import sys
from constants import Constants
from game_logic import GameLogic
from renderer import Renderer

# 作成したAnalyzerをインポート
from game_analyzer import GameAnalyzer


class GameReviewer:
    """ゲーム終了後にオセロを振り返るためのクラス"""

    def __init__(self, screen, move_history):
        self.screen = screen
        self.full_history = move_history
        self.current_step = len(move_history)

        self.logic = GameLogic()
        self.renderer = Renderer(self.screen, self.logic, None)

        # ★追加: 分析機とアドバイス保持用の変数
        self.analyzer = GameAnalyzer()
        self.current_advice = None  # (x, y) または None
        self.is_analyzing = False  # 計算中フラグ（フリーズ防止のUI用）

        self.font = pygame.font.SysFont(None, 36)

        self.replay_to_step(self.current_step)

    def replay_to_step(self, step):
        """指定した手数まで盤面を再現する"""
        self.logic = GameLogic()
        self.renderer.game_logic = self.logic

        # ★追加: 盤面が変わったらアドバイスはクリアする
        self.current_advice = None
        self.is_analyzing = False

        for i in range(step):
            if i < len(self.full_history):
                move = self.full_history[i]
                self.logic.place_stone(move["x"], move["y"])
                self.logic.state.is_animating = False

    def handle_event(self, event):
        """キー操作などの処理"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                if self.current_step > 0:
                    self.current_step -= 1
                    self.replay_to_step(self.current_step)

            elif event.key == pygame.K_RIGHT:
                if self.current_step < len(self.full_history):
                    self.current_step += 1
                    # アドバイスを消すためにリセット推奨、または current_advice = None を明示
                    self.replay_to_step(self.current_step)

            elif event.key == pygame.K_ESCAPE:
                return False

            # ★追加: Hキーでヒント機能発動
            elif event.key == pygame.K_h:
                self.request_analysis()

        return True

    def request_analysis(self):
        """現在の盤面についてAIにアドバイスを求める"""
        # 既にアドバイスがある、またはゲーム終了、または相手のターンの場合は何もしない
        if self.current_advice is not None or self.logic.state.game_over:
            return

        # 簡易的な実装のため、ここで同期的に計算します
        # (計算中は画面が一瞬止まります)
        self.is_analyzing = True
        self.draw_ui()  # "Thinking..." を表示させるために一度描画更新
        pygame.display.flip()

        # AIに計算させる
        self.current_advice = self.analyzer.analyze(self.logic)
        self.is_analyzing = False

    def draw_ui(self):
        """振り返り用のUI描画"""
        # 背景
        ui_area = pygame.Rect(0, Constants.SIZE, Constants.SIZE, 50)
        pygame.draw.rect(self.screen, (50, 50, 50), ui_area)

        # 手数表示
        text_step = self.font.render(
            f"Step: {self.current_step} / {len(self.full_history)}",
            True,
            Constants.WHITE,
        )
        self.screen.blit(text_step, (20, Constants.SIZE + 10))

        # 操作説明
        help_str = "<- Prev | Next -> | H: Hint | Esc: Quit"
        text_help = self.font.render(help_str, True, Constants.WHITE)
        help_rect = text_help.get_rect(
            right=Constants.SIZE - 20, top=Constants.SIZE + 10
        )
        self.screen.blit(text_help, help_rect)

        # ★追加: アドバイスの描画
        if self.is_analyzing:
            # 計算中表示
            text_wait = self.font.render("Analyzing...", True, (255, 255, 0))
            self.screen.blit(text_wait, (Constants.SIZE // 2 - 60, Constants.SIZE + 10))

        elif self.current_advice:
            ax, ay = self.current_advice

            # 1. 金色の円を描画
            center_x = ax * Constants.GRID_SIZE + Constants.GRID_SIZE // 2
            center_y = ay * Constants.GRID_SIZE + Constants.GRID_SIZE // 2
            pygame.draw.circle(self.screen, (255, 215, 0), (center_x, center_y), 15, 4)

            # 2. 座標を画面下のUIエリアに表示
            advice_text = self.font.render(f"Advice: ({ax}, {ay})", True, (255, 215, 0))
            # 画面中央より少し右に表示
            self.screen.blit(
                advice_text, (Constants.SIZE // 2 + 50, Constants.SIZE + 10)
            )

    def run(self):
        # (変更なし)
        clock = pygame.time.Clock()
        running = True

        while running:
            clock.tick(30)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    pygame.quit()
                    sys.exit()
                if not self.handle_event(event):
                    running = False

            self.renderer.draw_board()
            self.draw_ui()  # アドバイス描画を含む
            pygame.display.flip()
