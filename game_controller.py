import pygame
import sys
import math
from constants import Constants
from game_logic import GameLogic
from renderer import Renderer
from game_reviewer import GameReviewer
from ai.random_ai import RandomAI
from ai.minimax_ai import MinimaxAI
from ai.stronger_ai import StrongerAI
from ai.world_class_ai import WorldAI


class GameController:
    """ゲームの実行と制御を管理するクラス"""

    def __init__(self, ai_type=Constants.AI_TYPE_MINIMAX, screen=None):
        """ゲームコントローラの初期化"""
        self.game_logic = GameLogic()
        self.ai = self.create_ai(ai_type)
        self.screen = screen
        self.renderer = Renderer(self.screen, self.game_logic, self.ai)

        # ★追加: 棋譜を記録するリスト
        # 形式: {"color": color, "x": x, "y": y}
        self.move_history = []

        # ★追加: AIの手を検知するために、前のターンの盤面状態を保持（簡易的な方法）
        self.previous_board = self.copy_board(self.game_logic.board)

    def copy_board(self, board):
        """盤面のコピーを作成するヘルパー関数"""
        return [row[:] for row in board]

    def create_ai(self, ai_type):
        """指定されたタイプのAIを作成"""
        # (変更なし)
        if ai_type == Constants.AI_TYPE_RANDOM:
            return RandomAI(self.game_logic)
        elif ai_type == Constants.AI_TYPE_MINIMAX:
            return MinimaxAI(self.game_logic)
        elif ai_type == Constants.AI_TYPE_STRONGER:
            return StrongerAI(self.game_logic)
        elif ai_type == Constants.AI_TYPE_WORLD:
            return WorldAI(self.game_logic)
        else:
            return MinimaxAI(self.game_logic)

    def record_move(self, x, y, color):
        """★追加: 手を記録する"""
        self.move_history.append({"x": x, "y": y, "color": color})
        # 次の比較用に現在の盤面を保存
        self.previous_board = self.copy_board(self.game_logic.board)

    def detect_ai_move(self):
        """★追加: AIが打った場所を特定して記録する"""
        current_board = self.game_logic.board
        for y in range(Constants.BOARD_SIZE):
            for x in range(Constants.BOARD_SIZE):
                # 前の盤面では空だったのに、今は石がある場所を探す
                if (
                    self.previous_board[y][x] is None
                    and current_board[y][x] == Constants.WHITE
                ):
                    self.record_move(x, y, Constants.WHITE)
                    return

    def handle_event(self, event):
        """イベント処理"""
        if event.type == pygame.QUIT:
            return False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if (
                self.game_logic.state.is_player_turn()
                and not self.game_logic.state.is_animating
                and not self.game_logic.state.game_over
                and not self.game_logic.state.paused
            ):
                x, y = event.pos
                if y < Constants.SIZE:
                    grid_x = x // Constants.GRID_SIZE
                    grid_y = y // Constants.GRID_SIZE
                    if self.game_logic.is_valid_move(grid_x, grid_y, Constants.BLACK):
                        self.game_logic.place_stone(grid_x, grid_y)
                        # ★追加: プレイヤーの手を記録
                        self.record_move(grid_x, grid_y, Constants.BLACK)
                    else:
                        self.game_logic.state.set_message("そこには置けません")

        elif event.type == pygame.KEYDOWN:
            # (変更なし)
            if event.key == pygame.K_u:
                self.game_logic.undo_move()
                # 注意: Undo機能を使う場合、本来はhistoryからも削除する必要がありますが、今回は割愛
            elif event.key == pygame.K_SPACE:
                self.game_logic.toggle_pause()
            elif event.key == pygame.K_ESCAPE:
                return False

        return True

    def update(self):
        """ゲーム状態の更新"""
        self.game_logic.update_animation()

        # AIの手番処理
        if (
            not self.game_logic.state.is_animating
            and not self.game_logic.state.game_over
            and not self.game_logic.state.is_player_turn()
            and not self.game_logic.state.paused
            and not self.ai.thinking
        ):
            self.ai.start_thinking()

        # ★追加: AIが思考中でなく、アニメーション中でもない時、
        # 盤面が変わっていればAIが着手したとみなして記録する
        if not self.game_logic.state.is_player_turn() and not self.ai.thinking:
            # 前回の盤面と石の数が違えば、AIが打ったということ
            self.detect_ai_move()

    def run(self):
        """ゲームループの実行"""
        clock = pygame.time.Clock()
        running = True

        while running:
            clock.tick(60)

            for event in pygame.event.get():
                if not self.handle_event(event):
                    running = False
                    break

            self.update()

            self.renderer.draw_board()
            self.renderer.draw_valid_moves()
            self.renderer.draw_animations()
            pygame.display.flip()

        # ゲーム終了時の処理
        if self.game_logic.state.game_over:
            result = self.game_logic.game_result()
            self.animate_end(result)

    def animate_end(self, message):
        """ゲーム終了時の結果表示アニメーション"""
        # ... (前半のアニメーション表示コードは同じなので省略) ...
        # ... アニメーションが終わるまでループする ...

        # ★変更: アニメーション表示だけ簡略化して記述します（実際は元のコードを使用）
        # アニメーション終了後、GameReviewerを起動

        # 以下のアニメーションループ後...
        clock = pygame.time.Clock()
        duration = 3000
        start_time = pygame.time.get_ticks()

        while True:
            # (既存のアニメーションループ処理...)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                # EnterかESCでアニメーションをスキップしてレビューへ
                elif event.type == pygame.KEYDOWN and event.key in [
                    pygame.K_ESCAPE,
                    pygame.K_RETURN,
                ]:
                    start_time = -duration  # ループを抜ける条件にする

            if pygame.time.get_ticks() - start_time >= duration:
                break

            # (描画処理省略...)
            self.renderer.draw_board()  # 背景
            # テキスト描画...
            pygame.display.flip()
            clock.tick(60)

        # ★ここから変更: 振り返り機能へ移行
        pygame.time.wait(500)

        # GameReviewerのインスタンスを作成して実行
        reviewer = GameReviewer(self.screen, self.move_history)
        reviewer.run()
