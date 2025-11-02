import time
import random
from src.config import (
    DRAG_SPEED_PX_PER_SEC_RANGE, DRAG_MIN_DURATION, DRAG_MAX_DURATION,
    DRAG_TWEEN, PRE_PRESS_SETTLE_RANGE, POST_RELEASE_REACTION_RANGE,
    BOARD_CLAMP_MARGIN, PYAUTOGUI_AVAILABLE, pyautogui
)

def sleep_range(rng):
    """Sleep for a random duration within the given range."""
    a, b = rng
    if b > 0:
        time.sleep(random.uniform(a, b))

def distance(x1, y1, x2, y2):
    """Calculate Euclidean distance between two points."""
    dx, dy = x2 - x1, y2 - y1
    return (dx*dx + dy*dy) ** 0.5

def drag_duration_for_distance(d):
    """Calculate appropriate drag duration based on distance."""
    speed = max(random.uniform(*DRAG_SPEED_PX_PER_SEC_RANGE), 1.0)
    dur = d / speed
    if dur < DRAG_MIN_DURATION: 
        dur = DRAG_MIN_DURATION + random.uniform(0, 0.01)
    if dur > DRAG_MAX_DURATION: 
        dur = DRAG_MAX_DURATION - random.uniform(0, 0.01)
    return max(0.001, dur)

def teleport_to(x, y):
    """Instantly move mouse to position without animation."""
    require_display()
    pyautogui.moveTo(x, y, duration=0)

def move_segment_human(x1, y1, x2, y2, clamp_box=False, plank_board_region_func=None):
    """Move mouse from point A to B with human-like wobble."""
    require_display()
    # from src.bot_state import ABORT_DRAG, RUNNING  # Use module reference instead.
    from src import bot_state
    from src.config import STATE_SAWING
    
    seg_len = distance(x1, y1, x2, y2)
    steps = max(1, int(seg_len // 200))
    lastx, lasty = x1, y1
    
    for i in range(1, steps + 1):
        if bot_state.ABORT_DRAG or not bot_state.RUNNING or bot_state.current_state != STATE_SAWING:
            try: 
                pyautogui.mouseUp()
            except Exception: 
                pass
            return False
        
        t = i / steps
        wobble = (random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2))
        nx = x1 + (x2 - x1) * t + wobble[0]
        ny = y1 + (y2 - y1) * t + wobble[1]
        d = distance(lastx, lasty, nx, ny)
        dur = drag_duration_for_distance(d)
        
        if clamp_box and plank_board_region_func:
            bx, by, bw, bh = plank_board_region_func()
            maxx = bx + bw - 1 - BOARD_CLAMP_MARGIN
            maxy = by + bh - 1 - BOARD_CLAMP_MARGIN
            nx = min(max(nx, bx + BOARD_CLAMP_MARGIN), maxx)
            ny = min(max(ny, by + BOARD_CLAMP_MARGIN), maxy)
        
        pyautogui.moveTo(nx, ny, duration=dur, tween=DRAG_TWEEN)
        lastx, lasty = nx, ny
    
    return True

def human_drag_path(path_points, clamp_box=False, plank_board_region_func=None):
    """Execute a drag path with human-like movement."""
    from src import bot_state
    
    if not path_points: 
        return
    
    x0, y0 = path_points[0]
    teleport_to(x0, y0)
    sleep_range(PRE_PRESS_SETTLE_RANGE)
    pyautogui.mouseDown()
    last = (x0, y0)
    
    for (x, y) in path_points[1:]:
        if not move_segment_human(last[0], last[1], x, y, clamp_box, plank_board_region_func):
            return
        last = (x, y)
    
    pyautogui.mouseUp()
    sleep_range(POST_RELEASE_REACTION_RANGE)

def click_button(x, y):
    """Click a button at the specified position."""
    require_display()
    teleport_to(x, y)
    pyautogui.click()
    time.sleep(0.06)

def drag_between(x1, y1, x2, y2):
    """Drag from one point to another."""
    require_display()
    teleport_to(x1, y1)
    sleep_range(PRE_PRESS_SETTLE_RANGE)
    pyautogui.mouseDown()
    dur = drag_duration_for_distance(distance(x1, y1, x2, y2))
    pyautogui.moveTo(x2, y2, duration=dur, tween=DRAG_TWEEN)
    pyautogui.mouseUp()
    sleep_range(POST_RELEASE_REACTION_RANGE)

def sanitize_rect(tl, br):
    """Sanitize rectangle coordinates to ensure valid bounds."""
    (x1, y1), (x2, y2) = tl, br
    left, top = int(min(x1, x2)), int(min(y1, y2))
    right, bottom = int(max(x1, x2)), int(max(y1, y2))
    return left, top, right - left, bottom - top

def calculate_color_distance_lab(pixel_bgr, target_bgr):
    """Calculate color distance in LAB color space for better color matching."""
    import cv2
    import numpy as np
    
    # Convert pixel to LAB
    pixel_lab_tile = np.zeros((1, 1, 3), dtype=np.uint8)
    pixel_lab_tile[0, 0] = pixel_bgr
    pixel_lab = cv2.cvtColor(pixel_lab_tile, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
    
    # Convert target to LAB
    target_lab_tile = np.zeros((1, 1, 3), dtype=np.uint8)
    target_lab_tile[0, 0] = target_bgr
    target_lab = cv2.cvtColor(target_lab_tile, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
    
    # Calculate distance
    diff = pixel_lab - target_lab
    return float(np.sqrt(diff[0]**2 + diff[1]**2 + diff[2]**2))

def find_pixels_by_color(image, target_rgb, tolerance=15.0):
    """Find pixels in image that match target color within tolerance."""
    import cv2
    import numpy as np
    
    target_bgr = np.array([target_rgb[2], target_rgb[1], target_rgb[0]], dtype=np.uint8)
    matching_positions = []
    
    for y in range(image.shape[0]):
        for x in range(image.shape[1]):
            pixel_bgr = image[y, x]
            distance = calculate_color_distance_lab(pixel_bgr, target_bgr)
            
            if distance <= tolerance:
                matching_positions.append((x, y))
    
    return matching_positions

def log_module_action(module_name, action, details=""):
    """Standard logging format for module actions."""
    prefix = f"[{module_name.upper()}]"
    if details:
        print(f"{prefix} {action}: {details}")
    else:
        print(f"{prefix} {action}")

def group_nearby_positions(positions, max_distance=25):
    """Group nearby positions and return their centers."""
    if not positions:
        return []
    
    merged = []
    current_group = [positions[0]]
    
    for i in range(1, len(positions)):
        curr_x = positions[i][0]
        prev_x = current_group[-1][0]
        
        if curr_x - prev_x <= max_distance:
            current_group.append(positions[i])
        else:
            center_x = sum(pos[0] for pos in current_group) // len(current_group)
            center_y = current_group[0][1]  # Assume same Y for horizontal grouping
            merged.append((center_x, center_y))
            current_group = [positions[i]]
    
    # Don't forget the last group
    if current_group:
        center_x = sum(pos[0] for pos in current_group) // len(current_group)
        center_y = current_group[0][1]
        merged.append((center_x, center_y))
    
    return merged

def require_display():
    """Check if display functionality is available."""
    from src.config import PYAUTOGUI_AVAILABLE
    if not PYAUTOGUI_AVAILABLE:
        raise RuntimeError("Display functionality not available. This command requires a graphical environment.")