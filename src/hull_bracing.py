import cv2
import numpy as np
from collections import deque
from src.config import (
    GRID_CENTERS, BREATH_EVERY_N_MOVES, BREATH_SLEEP_RANGE, STATE_BRACING
)
from src.vision import is_green_check_visible, confirm_completion_via_ui
from src.utils import drag_between, sleep_range
from src import bot_state

def detect_grid_blocks():
    """Detect the current state of the 4x4 grid."""
    grid = [['empty'] * 4 for _ in range(4)]
    
    for r in range(4):
        for c in range(4):
            x, y = GRID_CENTERS[r][c]
            from src.config import pyautogui
            b, g, red = np.mean(
                cv2.cvtColor(
                    np.array(pyautogui.screenshot(region=(x-5, y-5, 10, 10))), 
                    cv2.COLOR_RGB2BGR
                ),
                axis=(0, 1)
            )
            
            if red > 150 and g > 100 and b > 40:
                grid[r][c] = 'blank'
            elif red > 35 and red > b + 20:
                grid[r][c] = 'red'
            elif b > 35 and b > red + 5:
                grid[r][c] = 'blue'
            elif red < 15 and g < 15 and b < 15:
                grid[r][c] = 'empty'
            else:
                grid[r][c] = 'blank'
    
    return grid

def grid_to_state(grid):
    """Convert grid to immutable state tuple."""
    return tuple(tuple(row) for row in grid)

def state_to_grid(state):
    """Convert state tuple back to mutable grid."""
    return [list(row) for row in state]

def locked_cells_for_fixed_rows(state):
    """Get cells that are locked due to completed rows."""
    locked = set()
    if all(state[0][c] == 'red' for c in range(4)):
        for c in range(4): 
            locked.add((0, c))
    if all(state[3][c] == 'blue' for c in range(4)):
        for c in range(4): 
            locked.add((3, c))
    return locked

def is_correctly_placed(cell_r, cell_c, cell_type):
    """Check if a cell is in the correct target position."""
    return (cell_type == 'red' and cell_r == 0) or (cell_type == 'blue' and cell_r == 3)

def placed_count_fixed_rows(state):
    """Count correctly placed pieces in target rows."""
    return (sum(1 for c in range(4) if state[0][c] == 'red') + 
            sum(1 for c in range(4) if state[3][c] == 'blue'))

def goal_achieved_fixed_rows(state):
    """Check if the goal state is achieved."""
    return (all(state[0][c] == 'red' for c in range(4)) and 
            all(state[3][c] == 'blue' for c in range(4)))

def get_possible_moves_typed(state, locked):
    """Get all possible moves from current state."""
    g = state_to_grid(state)
    empties = [(r, c) for r in range(4) for c in range(4) if g[r][c] == 'empty']

    def move_priority(fr, fc, t):
        if (fr, fc) in locked:
            return None
        if t in ('red', 'blue'):
            if is_correctly_placed(fr, fc, t):
                return 2
            return 0
        return 1

    moves = []
    for (er, ec) in empties:
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nr, nc = er+dr, ec+dc
            if 0 <= nr < 4 and 0 <= nc < 4:
                t = g[nr][nc]
                if t in ('red', 'blue', 'blank'):
                    pr = move_priority(nr, nc, t)
                    if pr is None:
                        continue
                    ng = [row[:] for row in g]
                    ng[er][ec] = t
                    ng[nr][nc] = 'empty'
                    moves.append((grid_to_state(ng), ((nr, nc), (er, ec)), t, pr))

    def vertical_bias(entry):
        ns, mv, t, pr = entry
        (fr, fc), (tr, tc) = mv
        if t == 'red':
            return abs(fr - 0) - abs(tr - 0)
        if t == 'blue':
            return abs(fr - 3) - abs(tr - 3)
        return 0

    moves.sort(key=lambda e: (e[3], -vertical_bias(e)))
    return moves

def immediate_inverse(m1, m2):
    """Check if two moves are immediate inverses of each other."""
    return m1 and m2 and (m1[0] == m2[1] and m1[1] == m2[0])

def plan_path_increasing_fixed(state, max_depth=12):
    """Plan a path that increases the score."""
    start_score = placed_count_fixed_rows(state)
    locked = locked_cells_for_fixed_rows(state)

    Node = lambda s, last_mv, path: (s, last_mv, path)
    q = deque([Node(state, None, [])])
    seen = {state: start_score}

    while q:
        s, last_mv, path = q.popleft()
        score = placed_count_fixed_rows(s)
        
        if score > start_score:
            return path
        
        if len(path) >= max_depth:
            continue
        
        for ns, mv, t, pr in get_possible_moves_typed(s, locked):
            if immediate_inverse(last_mv, mv):
                continue
            
            nscore = placed_count_fixed_rows(ns)
            if nscore < score:
                continue
            
            prev = seen.get(ns, -1)
            if prev >= nscore:
                continue
            
            seen[ns] = nscore
            q.append((ns, mv, path + [mv]))
    
    return []

def execute_moves_live(grid, moves, move_counter_dict):
    """Execute a series of moves on the live grid."""
    for (fr, fc), (tr, tc) in moves:
        if not bot_state.RUNNING:
            return False
        
        x1, y1 = GRID_CENTERS[fr][fc]
        x2, y2 = GRID_CENTERS[tr][tc]
        drag_between(x1, y1, x2, y2)
        
        grid[tr][tc] = grid[fr][fc]
        grid[fr][fc] = 'empty'
        move_counter_dict['count'] += 1
        
        if move_counter_dict['count'] % BREATH_EVERY_N_MOVES == 0:
            sleep_range(BREATH_SLEEP_RANGE)
    
    return True

def solve_bracing_fixed_rows():
    """Main bracing solver loop."""
    grid = detect_grid_blocks()
    local = state_to_grid(grid_to_state(grid))
    move_counter = {'count': 0}
    
    while bot_state.RUNNING and bot_state.current_state == STATE_BRACING:
        if is_green_check_visible('bracing'):
            if confirm_completion_via_ui('bracing', confirm_frames=2, spacing=0.10):
                return True
            else:
                grid = detect_grid_blocks()
                local = state_to_grid(grid_to_state(grid))
        
        s = grid_to_state(local)
        if goal_achieved_fixed_rows(s):
            if confirm_completion_via_ui('bracing', confirm_frames=2, spacing=0.10):
                return True
            else:
                grid = detect_grid_blocks()
                local = state_to_grid(grid_to_state(grid))
                continue
        
        path = plan_path_increasing_fixed(s, max_depth=12)
        if not path:
            grid = detect_grid_blocks()
            local = state_to_grid(grid_to_state(grid))
            continue
        
        if not execute_moves_live(local, path, move_counter):
            return False
    
    return False