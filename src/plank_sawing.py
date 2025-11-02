import time

import cv2
import numpy as np

from src.config import (
    PLANK_BOX_TOPLEFT_GIVEN, PLANK_BOX_BOTTOMRIGHT_GIVEN, SAW_ICON_POS_ABS,
    SAW_TARGET_RGB, SAW_COLOR_EPS, SAW_V_MIN, SAW_MIN_AREA,
    PLANK_NEXT_BOARD_DELAY, PLANK_EXPECTED_BOARDS, PLANK_MAX_ATTEMPTS,
    BOARD_CLAMP_MARGIN, TEMPLATE_MATCH_THRESHOLD, BOARD_TEMPLATES,
    SAW_SPAWN_COORDINATES, BOARD_WAYPOINTS
)
from src.vision import compute_patch_scan_region, confirm_completion_via_ui
from src.utils import sanitize_rect, human_drag_path, teleport_to, distance
# from src.bot_state import RUNNING, ABORT_DRAG  # Removed direct import to avoid stale references
from src import bot_state
from src.config import pyautogui

# ---------------------------------------------------------------------
# Geometry & Screen Grabs
# ---------------------------------------------------------------------

def plank_board_region():
    """Get the plank board region coordinates (x, y, w, h)."""
    tl, br = PLANK_BOX_TOPLEFT_GIVEN, PLANK_BOX_BOTTOMRIGHT_GIVEN
    x, y, w, h = sanitize_rect(tl, br)
    return x, y, w, h


def grab_board_bgr():
    """Grab a screenshot of the board region as BGR image."""
    x, y, w, h = plank_board_region()
    img = np.array(pyautogui.screenshot(region=(x, y, w, h)))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def detect_board_type():
    """Detect board type using template matching.
    Returns (board_type, confidence) or (None, 0) if no match found."""
    board_img = grab_board_bgr()
    best_match = None
    best_score = 0
    
    
    for board_type, template_path in BOARD_TEMPLATES.items():
        try:
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                print(f"[SAW] Warning: Could not load template {template_path}")
                continue
                
            # Resize template to match board region if needed
            board_h, board_w = board_img.shape[:2]
            template_h, template_w = template.shape[:2]
            
            if template_h != board_h or template_w != board_w:
                template = cv2.resize(template, (board_w, board_h))
            
            # Template matching
            result = cv2.matchTemplate(board_img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            
            if max_val > best_score:
                best_score = max_val
                best_match = board_type
                
        except Exception as e:
            print(f"[SAW] Error processing template {template_path}: {e}")
            continue
    
    if best_score >= TEMPLATE_MATCH_THRESHOLD:
        return best_match, best_score
    else:
        return None, 0

# ---------------------------------------------------------------------
# Saw Detection (primary color distance + optional template fallback)
# ---------------------------------------------------------------------

def detect_saw_in_window():
    """Detect the saw position in the mini-game window. Returns (x, y) or None."""
    wx, wy, ww, wh = compute_patch_scan_region()
    frame = np.array(pyautogui.screenshot(region=(wx, wy, ww, wh)))
    bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # Primary: LAB distance to target color with brightness gate
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    rgb_tile = np.zeros((1, 1, 3), dtype=np.uint8)
    rgb_tile[0, 0] = SAW_TARGET_RGB.astype(np.uint8)
    target_lab = cv2.cvtColor(rgb_tile, cv2.COLOR_RGB2LAB)[0, 0].astype(np.float32)

    diff = lab - target_lab
    dist = np.sqrt(diff[..., 0] ** 2 + diff[..., 1] ** 2 + diff[..., 2] ** 2)
    mask = (dist <= SAW_COLOR_EPS) & (hsv[..., 2] >= SAW_V_MIN)
    mask = (mask.astype(np.uint8) * 255)
    mask = cv2.medianBlur(mask, 3)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) >= SAW_MIN_AREA:
            M = cv2.moments(c)
            if M['m00'] != 0:
                cx, cy = int(M['m10'] / M['m00']), int(M['m01'] / M['m00'])
            else:
                x, y, w, h = cv2.boundingRect(c)
                cx, cy = x + w // 2, y + h // 2
            return wx + cx, wy + cy

    # Fallback: template match (if available)
    try:
        templ = cv2.imread('assets/saw_template.png', cv2.IMREAD_COLOR)
        if templ is not None:
            res = cv2.matchTemplate(bgr, templ, cv2.TM_CCOEFF_NORMED)
            _, maxv, _, maxloc = cv2.minMaxLoc(res)
            if maxv > 0.6:
                th, tw = templ.shape[:2]
                cx, cy = maxloc[0] + tw // 2, maxloc[1] + th // 2
                return wx + cx, wy + cy
    except Exception:
        pass

    return None

# ---------------------------------------------------------------------
# Groove Detection (Simplified: Black-hat + Otsu, no inversion) 
# ---------------------------------------------------------------------
def get_waypoints_for_board_type(board_type):
    """Get absolute waypoints for a detected board type."""
    if board_type not in BOARD_WAYPOINTS:
        print(f"[SAW] Unknown board type: {board_type}")
        return []
    
    relative_waypoints = BOARD_WAYPOINTS[board_type]
    bx, by, bw, bh = plank_board_region()
    
    # Convert relative waypoints to absolute screen coordinates
    absolute_waypoints = []
    for rel_x, rel_y in relative_waypoints:
        # Scale relative coordinates to actual board size
        abs_x = bx + int((rel_x / 600.0) * bw)  # 600 is template width
        abs_y = by + int((rel_y / 300.0) * bh)  # 300 is template height
        
        # Apply margin constraints (but not for diagonal cuts which need to extend beyond board)
        if board_type != 'diagonal':
            abs_x = max(bx + BOARD_CLAMP_MARGIN, min(abs_x, bx + bw - BOARD_CLAMP_MARGIN))
            abs_y = max(by + BOARD_CLAMP_MARGIN, min(abs_y, by + bh - BOARD_CLAMP_MARGIN))
        
        absolute_waypoints.append((abs_x, abs_y))
    
    return absolute_waypoints

# ---------------------------------------------------------------------
# Presence / Cycle Utilities
# ---------------------------------------------------------------------
def board_present():
    """Check if a board is present for cutting using template matching."""
    board_type, confidence = detect_board_type()
    
    if board_type and confidence >= TEMPLATE_MATCH_THRESHOLD:
        return True
    else:
        return False

# ---------------------------------------------------------------------
# Main solving pass (single cut)
# ---------------------------------------------------------------------
def solve_plank_sawing_once():
    """Attempt to solve one plank cutting operation using template matching.
    Returns (ok: bool, board_type: str|None)."""
    
    # Detect board type using template matching
    board_type, confidence = detect_board_type()
    
    if not board_type or confidence < TEMPLATE_MATCH_THRESHOLD:
        print('[SAW] No board detected or confidence too low')
        return False, None

    # Get predefined waypoints for this board type
    waypoints = get_waypoints_for_board_type(board_type)
    if not waypoints:
        print(f'[SAW] No waypoints available for board type: {board_type}')
        return False, board_type

    length = sum(
        distance(waypoints[i][0], waypoints[i][1], waypoints[i + 1][0], waypoints[i + 1][1])
        for i in range(len(waypoints) - 1)
    )
    print(
        f"[SAW] Board type: {board_type}, {len(waypoints)} waypoints, "
        f"total_path_len≈{int(length)}px, first={waypoints[0]}, last={waypoints[-1]}"
    )

    # Get the correct saw spawn position for this board type
    if board_type not in SAW_SPAWN_COORDINATES:
        print(f"[SAW] No saw spawn coordinates defined for board type: {board_type}")
        return False, board_type
    
    saw_spawn_pos = SAW_SPAWN_COORDINATES[board_type]
    print(f"[SAW] Using saw spawn position for {board_type}: {saw_spawn_pos}")

    if bot_state.ABORT_DRAG or not bot_state.RUNNING or bot_state.current_state != 'sawing':
        return False, board_type


    # Move to the correct saw spawn position and drag through waypoints
    print(f"[SAW] Moving to saw spawn at {saw_spawn_pos}")
    teleport_to(*saw_spawn_pos)
    
    # Execute the cutting path by dragging from saw spawn through all waypoints
    cutting_path = [saw_spawn_pos] + waypoints
    print(f"[SAW] Executing cutting path: {len(cutting_path)} points from saw to target")
    human_drag_path(cutting_path, clamp_box=False)  # Don't clamp since we start outside board region

    if bot_state.ABORT_DRAG:
        print('[SAW] Drag aborted.')
        return False, board_type

    print('[SAW] Drag completed, verifying...')
    return True, board_type

# ---------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------
def run_plank_sawing_until_perfect():
    """Main plank sawing loop using template matching. Returns True on success, False on exhaustion."""
    cuts_done = 0
    attempts = 0
    last_board_type = None
    
    while bot_state.RUNNING and bot_state.current_state == 'sawing' and attempts < PLANK_MAX_ATTEMPTS:
        # Check if any board is present - if not, we're done.
        if not board_present():
            print('[SAW] No more boards detected - minigame completed!')
            return True

        attempts += 1
        print(f"[SAW] Attempt {attempts}: starting template detection+cut...")

        ok, board_type = solve_plank_sawing_once()
        last_board_type = board_type if board_type is not None else last_board_type
        time.sleep(0.35)

        if ok:
            print(f"[SAW] Cut issued for {board_type}. Waiting up to {PLANK_NEXT_BOARD_DELAY}s for next board…")
            cuts_done += 1

            # Wait for old board to clear.
            time.sleep(PLANK_NEXT_BOARD_DELAY)
        else:
            print('[SAW] No cut issued this attempt. Retrying…')
            time.sleep(0.25)

    return cuts_done >= PLANK_EXPECTED_BOARDS
