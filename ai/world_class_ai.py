import random
import time
import threading
from constants import Constants
from typing import List, Tuple, Optional, Dict
from ai.ai_strategy import AIStrategy
from board import Board

# 定数の定義
AI_BLACK = 1
AI_WHITE = -1
AI_EMPTY = 0
DIRECTIONS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]

# コーナー位置
CORNERS = [(0, 0), (0, 7), (7, 0), (7, 7)]

# X-squares (危険地帯)
X_SQUARES = {(0, 0): [(1, 1)], (0, 7): [(1, 6)], (7, 0): [(6, 1)], (7, 7): [(6, 6)]}

# C-squares (注意が必要な場所)
C_SQUARES = {
    (0, 0): [(0, 1), (1, 0)],
    (0, 7): [(0, 6), (1, 7)],
    (7, 0): [(7, 1), (6, 0)],
    (7, 7): [(7, 6), (6, 7)],
}

# 位置の価値（静的評価）
POSITION_WEIGHTS = [
    [100, -20, 10, 5, 5, 10, -20, 100],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [10, -2, -1, -1, -1, -1, -2, 10],
    [5, -2, -1, -1, -1, -1, -2, 5],
    [5, -2, -1, -1, -1, -1, -2, 5],
    [10, -2, -1, -1, -1, -1, -2, 10],
    [-20, -50, -2, -2, -2, -2, -50, -20],
    [100, -20, 10, 5, 5, 10, -20, 100],
]


class WorldAI(AIStrategy):
    def __init__(self, game_logic, board_size=8):
        super().__init__(game_logic)
        self.board_size = board_size
        self.game_logic = game_logic
        self.max_time = 10
        self.start_time = 0
        self.time_limit_reached = False
        self.nodes_expanded = 0
        self.cutoffs = 0
        self.thinking = False
        self.difficulty = 3

        # トランスポジションテーブル (Hash -> {value, depth, flag, best_move})
        self.transposition_table = {}
        # キャッシュ
        self.valid_cache = {}
        # キラー手
        self.killer_moves = {}

    def _convert_to_ai_player(self, game_player):
        if game_player == Constants.BLACK:
            return AI_BLACK
        if game_player == Constants.WHITE:
            return AI_WHITE
        return None

    def _convert_to_game_player(self, ai_player):
        if ai_player == AI_BLACK:
            return Constants.BLACK
        if ai_player == AI_WHITE:
            return Constants.WHITE
        return None

    def _convert_board(self, game_board):
        ai_board = [
            [AI_EMPTY for _ in range(self.board_size)] for _ in range(self.board_size)
        ]
        if isinstance(game_board, Board):
            for i in range(self.board_size):
                for j in range(self.board_size):
                    cell = game_board.get_cell(i, j)
                    if cell == Constants.BLACK:
                        ai_board[i][j] = AI_BLACK
                    elif cell == Constants.WHITE:
                        ai_board[i][j] = AI_WHITE
            return ai_board
        # Fallback for list of lists
        if hasattr(game_board, "__getitem__"):
            try:
                for i in range(self.board_size):
                    for j in range(self.board_size):
                        cell = game_board[i][j]
                        if cell == Constants.BLACK:
                            ai_board[i][j] = AI_BLACK
                        elif cell == Constants.WHITE:
                            ai_board[i][j] = AI_WHITE
            except:
                pass
        return ai_board

    def start_thinking(self):
        self.thinking = True
        game_board = self.game_logic.state.board
        game_player = Constants.WHITE  # AI設定

        board = self._convert_board(game_board)
        player = self._convert_to_ai_player(game_player)

        time_limit = 1
        if self.difficulty == 2:
            time_limit = 3
        elif self.difficulty >= 3:
            time_limit = 5

        def think_and_move(board, player, time_limit):
            try:
                move = self.get_move(board, player, time_limit)
                if move is not None:
                    grid_x, grid_y = move
                    self.game_logic.place_stone(grid_x, grid_y)
                else:
                    self.game_logic.pass_turn()
            except Exception as e:
                print(f"AI Error: {e}")
                import traceback

                traceback.print_exc()
            finally:
                self.thinking = False

        thinking_thread = threading.Thread(
            target=think_and_move, args=(board, player, time_limit)
        )
        thinking_thread.daemon = True
        thinking_thread.start()

    def get_move(
        self, board: List[List[int]], player: int, time_limit: int = 10
    ) -> Tuple[int, int]:
        self.thinking = True
        self.max_time = time_limit
        self.start_time = time.time()
        self.time_limit_reached = False
        self.nodes_expanded = 0
        self.valid_cache = {}
        self.killer_moves = {}

        # メモリ管理（適当なサイズでクリア）
        if len(self.transposition_table) > 200000:
            self.transposition_table.clear()

        valid_moves = self.get_valid_moves(board, player)
        if not valid_moves:
            self.thinking = False
            return None

        if len(valid_moves) == 1:
            self.thinking = False
            return valid_moves[0]

        empty_count = sum(row.count(AI_EMPTY) for row in board)

        # --- エンドゲーム (完全読み) ---
        if empty_count <= 14:
            # 終盤専用のキャッシュを用意（スコアの性質が違うため）
            endgame_cache = {}
            move = self.endgame_solver(
                board, player, valid_moves, empty_count, endgame_cache
            )
            self.thinking = False
            return move

        # --- 通常探索 (反復深化) ---
        best_move = valid_moves[0]
        current_depth = 2
        max_depth = 20

        while current_depth <= max_depth:
            if self.is_time_up():
                break

            try:
                best_score = float("-inf")
                temp_best_move = None
                alpha = float("-inf")
                beta = float("inf")

                # 前回の深さで最善だった手を含む順序付け
                ordered_moves = self.order_moves(
                    board, valid_moves, player, current_depth
                )

                for move in ordered_moves:
                    new_board = self.make_move(board, move, player)
                    opponent = AI_WHITE if player == AI_BLACK else AI_BLACK

                    score = self.minimax(
                        new_board, current_depth - 1, alpha, beta, opponent, False
                    )

                    if self.is_time_up():
                        break

                    if score > best_score:
                        best_score = score
                        temp_best_move = move

                    alpha = max(alpha, best_score)

                if not self.is_time_up() and temp_best_move:
                    best_move = temp_best_move
                    # PVが見つかったら、それをテーブルに登録しておくと次のorder_movesで有利
                    board_hash = self.hash_board(board)
                    self.transposition_table[board_hash] = {
                        "value": best_score,
                        "depth": current_depth,
                        "flag": "exact",
                        "best_move": best_move,
                    }
                    current_depth += 1
                else:
                    break
            except Exception as e:
                print(f"Error in iterative deepening: {e}")
                break

        self.thinking = False
        return best_move

    def minimax(self, board, depth, alpha, beta, player, maximizing_player):
        self.nodes_expanded += 1
        if self.nodes_expanded & 1023 == 0:
            if self.is_time_up():
                self.time_limit_reached = True
                return 0

        board_hash = self.hash_board(board)

        # トランスポジションテーブル参照
        tt_move = None
        if board_hash in self.transposition_table:
            entry = self.transposition_table[board_hash]
            if entry["depth"] >= depth:
                if entry["flag"] == "exact":
                    return entry["value"]
                elif entry["flag"] == "lower":
                    alpha = max(alpha, entry["value"])
                elif entry["flag"] == "upper":
                    beta = min(beta, entry["value"])
                if alpha >= beta:
                    self.cutoffs += 1
                    return entry["value"]
            # 深さが足りなくても、最善手の情報はムーブオーダリングに使える
            tt_move = entry.get("best_move")

        if depth == 0 or self.is_game_over(board):
            current_turn_player = (
                player
                if maximizing_player
                else (AI_WHITE if player == AI_BLACK else AI_BLACK)
            )
            return self.evaluate_board(board, current_turn_player)

        valid_moves = self.get_valid_moves(board, player)

        if not valid_moves:
            opponent = AI_WHITE if player == AI_BLACK else AI_BLACK
            return self.minimax(
                board, depth, alpha, beta, opponent, not maximizing_player
            )

        # TT Moveを渡してオーダリング
        ordered_moves = self.order_moves(board, valid_moves, player, depth, tt_move)

        opponent = AI_WHITE if player == AI_BLACK else AI_BLACK
        best_move = None

        if maximizing_player:
            value = float("-inf")
            for move in ordered_moves:
                new_board = self.make_move(board, move, player)
                score = self.minimax(new_board, depth - 1, alpha, beta, opponent, False)

                if score > value:
                    value = score
                    best_move = move

                alpha = max(alpha, value)
                if alpha >= beta:
                    self.cutoffs += 1
                    self.killer_moves[depth] = move
                    break

            flag = "exact"
            if value <= alpha:
                flag = "upper"
            if value >= beta:
                flag = "lower"

        else:  # Minimizing player
            value = float("inf")
            for move in ordered_moves:
                new_board = self.make_move(board, move, player)
                score = self.minimax(new_board, depth - 1, alpha, beta, opponent, True)

                if score < value:
                    value = score
                    best_move = move

                beta = min(beta, value)
                if value <= alpha:
                    self.cutoffs += 1
                    self.killer_moves[depth] = move
                    break

            flag = "exact"
            if value <= alpha:
                flag = "upper"
            if value >= beta:
                flag = "lower"

        if not self.time_limit_reached:
            # ベストムーブも保存するのが重要
            self.transposition_table[board_hash] = {
                "value": value,
                "depth": depth,
                "flag": flag,
                "best_move": best_move,
            }

        return value

    def evaluate_board(self, board: List[List[int]], player: int) -> float:
        """戦略的評価関数"""
        if self.is_game_over(board):
            player_disks = sum(row.count(player) for row in board)
            opponent = AI_WHITE if player == AI_BLACK else AI_BLACK
            opponent_disks = sum(row.count(opponent) for row in board)
            if player_disks > opponent_disks:
                return 10000 + (player_disks - opponent_disks)
            elif opponent_disks > player_disks:
                return -10000 - (opponent_disks - player_disks)
            return 0

        opponent = AI_WHITE if player == AI_BLACK else AI_BLACK
        empty_count = sum(row.count(AI_EMPTY) for row in board)
        disk_count = 64 - empty_count

        # フェーズ別重み設定
        # 序盤はモビリティ(着手可能数)と開放度(Frontier)を最重要視
        if disk_count <= 20:
            w_pos = 5
            w_mob = 30  # 序盤重視
            w_front = 15  # 開放度重視
            w_stab = 1
            w_par = 0
        elif disk_count <= 50:
            w_pos = 10
            w_mob = 15
            w_front = 5
            w_stab = 15
            w_par = 2
        else:
            w_pos = 5
            w_mob = 5
            w_front = 1
            w_stab = 25
            w_par = 10

        score = 0

        # Position
        pos_score = 0
        for r in range(8):
            for c in range(8):
                if board[r][c] == player:
                    pos_score += POSITION_WEIGHTS[r][c]
                elif board[r][c] == opponent:
                    pos_score -= POSITION_WEIGHTS[r][c]
        score += pos_score * w_pos

        # Mobility
        p_moves = len(self.get_valid_moves(board, player))
        o_moves = len(self.get_valid_moves(board, opponent))
        if p_moves + o_moves > 0:
            score += 100 * (p_moves - o_moves) / (p_moves + o_moves + 1) * w_mob

        # Stability
        p_stab = self.calculate_stability_fast(board, player)
        o_stab = self.calculate_stability_fast(board, opponent)
        score += (p_stab - o_stab) * w_stab * 10

        # Frontier (相手より自分が少ない方が良い -> 相手-自分)
        if w_front > 0:
            p_front = self.count_frontier_discs(board, player)
            o_front = self.count_frontier_discs(board, opponent)
            score += (o_front - p_front) * w_front

        # Parity
        if empty_count % 2 == 0:
            score += w_par * 50
        else:
            score -= w_par * 50

        return score

    def calculate_stability_fast(self, board, player):
        stability = 0
        for cr, cc in CORNERS:
            if board[cr][cc] == player:
                stability += 10
                # 横方向
                dc = 1 if cc == 0 else -1
                curr_c = cc + dc
                while 0 <= curr_c < 8 and board[cr][curr_c] == player:
                    stability += 1
                    curr_c += dc
                # 縦方向
                dr = 1 if cr == 0 else -1
                curr_r = cr + dr
                while 0 <= curr_r < 8 and board[curr_r][cc] == player:
                    stability += 1
                    curr_r += dr
        return stability

    def count_frontier_discs(self, board, player):
        count = 0
        for r in range(8):
            for c in range(8):
                if board[r][c] == player:
                    for dr, dc in DIRECTIONS:
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < 8 and 0 <= nc < 8 and board[nr][nc] == AI_EMPTY:
                            count += 1
                            break
        return count

    def endgame_solver(self, board, player, valid_moves, empty_count, cache):
        best_move = None
        best_score = float("-inf")
        opponent = AI_WHITE if player == AI_BLACK else AI_BLACK

        for move in valid_moves:
            new_board = self.make_move(board, move, player)
            score = self.minimax_endgame(
                new_board,
                empty_count - 1,
                float("-inf"),
                float("inf"),
                opponent,
                False,
                cache,
            )
            if score > best_score:
                best_score = score
                best_move = move
        return best_move

    def minimax_endgame(
        self, board, depth, alpha, beta, player, maximizing_player, cache
    ):
        board_hash = self.hash_board(board)
        # EndGame専用キャッシュの使用
        # (手番プレイヤー情報もキーに含める必要がある)
        cache_key = (board_hash, player, maximizing_player)
        if cache_key in cache:
            return cache[cache_key]

        if self.is_game_over(board) or depth == 0:
            black = sum(row.count(AI_BLACK) for row in board)
            white = sum(row.count(AI_WHITE) for row in board)

            is_black_current = (player == AI_BLACK and maximizing_player) or (
                player == AI_WHITE and not maximizing_player
            )
            res = black - white if is_black_current else white - black
            return res

        valid_moves = self.get_valid_moves(board, player)
        if not valid_moves:
            opponent = AI_WHITE if player == AI_BLACK else AI_BLACK
            res = self.minimax_endgame(
                board, depth, alpha, beta, opponent, not maximizing_player, cache
            )
            cache[cache_key] = res
            return res

        opponent = AI_WHITE if player == AI_BLACK else AI_BLACK

        if maximizing_player:
            value = float("-inf")
            for move in valid_moves:
                new_board = self.make_move(board, move, player)
                score = self.minimax_endgame(
                    new_board, depth - 1, alpha, beta, opponent, False, cache
                )
                value = max(value, score)
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
        else:
            value = float("inf")
            for move in valid_moves:
                new_board = self.make_move(board, move, player)
                score = self.minimax_endgame(
                    new_board, depth - 1, alpha, beta, opponent, True, cache
                )
                value = min(value, score)
                beta = min(beta, value)
                if value <= alpha:
                    break

        cache[cache_key] = value
        return value

    def order_moves(self, board, moves, player, depth, tt_move=None):
        """ムーブオーダリング: PV Move(tt_move)を最優先する"""
        scored_moves = []
        opponent = AI_WHITE if player == AI_BLACK else AI_BLACK
        killer = self.killer_moves.get(depth)

        for move in moves:
            score = 0
            # 1. ハッシュムーブ（最善手候補）を絶対的優先
            if move == tt_move:
                score += 100000

            # 2. コーナー
            elif move in CORNERS:
                score += 50000

            # 3. キラー手
            elif move == killer:
                score += 10000

            # 4. 危険地帯ペナルティ
            else:
                # X-square
                is_x = False
                for corner, x_sqs in X_SQUARES.items():
                    if move in x_sqs and board[corner[0]][corner[1]] == AI_EMPTY:
                        score -= 5000
                        is_x = True
                        break
                if not is_x:
                    for corner, c_sqs in C_SQUARES.items():
                        if move in c_sqs and board[corner[0]][corner[1]] == AI_EMPTY:
                            score -= 2000
                            break

                # 位置重み
                r, c = move
                score += POSITION_WEIGHTS[r][c]

                # フリップ数（簡易計算） - 多いほうが枝刈りしやすい傾向（Mobilityとは逆説的だが探索では有効）
                # 厳密なシミュレーションをせず、方向探索のみ行う
                flip_count = 0
                for dr, dc in DIRECTIONS:
                    curr_r, curr_c = r + dr, c + dc
                    line_flips = 0
                    while (
                        0 <= curr_r < 8
                        and 0 <= curr_c < 8
                        and board[curr_r][curr_c] == opponent
                    ):
                        line_flips += 1
                        curr_r += dr
                        curr_c += dc
                    if (
                        line_flips > 0
                        and 0 <= curr_r < 8
                        and 0 <= curr_c < 8
                        and board[curr_r][curr_c] == player
                    ):
                        flip_count += line_flips
                score += flip_count

            scored_moves.append((score, move))

        scored_moves.sort(key=lambda x: x[0], reverse=True)
        return [m for s, m in scored_moves]

    def hash_board(self, board: List[List[int]]) -> int:
        """高速化: 文字列ではなくタプル化してハッシュを取る"""
        # Pythonのtuple hashはCレベルで実装されており高速
        return hash(tuple(tuple(row) for row in board))

    def is_time_up(self) -> bool:
        return time.time() - self.start_time > self.max_time

    def is_game_over(self, board: List[List[int]]) -> bool:
        return not self.get_valid_moves(board, AI_BLACK) and not self.get_valid_moves(
            board, AI_WHITE
        )

    def get_valid_moves(self, board, player):
        board_hash = self.hash_board(board)
        cache_key = (board_hash, player)

        if cache_key in self.valid_cache:
            return self.valid_cache[cache_key]

        if isinstance(board, Board):
            return self.game_logic.get_valid_moves(self._convert_to_game_player(player))

        valid_moves = []
        opponent = AI_WHITE if player == AI_BLACK else AI_BLACK

        # 高速化: 相手の石があるマスの周囲のみ探索候補にする最適化も可能だが
        # ここでは実装の複雑さを避けて全探索+高速チェック
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i][j] == AI_EMPTY:
                    if self._fast_is_valid(board, i, j, player, opponent):
                        valid_moves.append((i, j))

        self.valid_cache[cache_key] = valid_moves
        return valid_moves

    def _fast_is_valid(self, board, r, c, player, opponent):
        for dr, dc in DIRECTIONS:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8 and board[nr][nc] == opponent:
                nr += dr
                nc += dc
                while 0 <= nr < 8 and 0 <= nc < 8:
                    cell = board[nr][nc]
                    if cell == player:
                        return True
                    if cell == AI_EMPTY:
                        break
                    nr += dr
                    nc += dc
        return False

    def make_move(
        self, board: List[List[int]], move: Tuple[int, int], player: int
    ) -> List[List[int]]:
        if move is None:
            return [row[:] for row in board]
        new_board = [row[:] for row in board]
        r_start, c_start = move
        new_board[r_start][c_start] = player
        opponent = AI_WHITE if player == AI_BLACK else AI_BLACK

        for dr, dc in DIRECTIONS:
            r, c = r_start + dr, c_start + dc
            to_flip = []
            while (
                0 <= r < self.board_size
                and 0 <= c < self.board_size
                and new_board[r][c] == opponent
            ):
                to_flip.append((r, c))
                r += dr
                c += dc
            if (
                0 <= r < self.board_size
                and 0 <= c < self.board_size
                and new_board[r][c] == player
            ):
                for fr, fc in to_flip:
                    new_board[fr][fc] = player
        return new_board
