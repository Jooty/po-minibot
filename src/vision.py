import time
import cv2
import numpy as np
from src.config import (
    BRACING_GREEN_CHECK, PATCHING_GREEN_CHECK, SAWING_GREEN_CHECK, SCRUBBING_GREEN_CHECK, HAMMERING_GREEN_CHECK,
    BOX_OFFSET_X, BOX_OFFSET_Y, GRID_CENTERS, BRACING_BUTTON_POS,
    PATCHING_BUTTON_POS, SAWING_BUTTON_POS, SCRUBBING_BUTTON_POS, HAMMERING_BUTTON_POS, PYAUTOGUI_AVAILABLE, pyautogui
)

PATCH_SCAN_REGION = None

def is_green_check_visible(check_type):
    """Check if a green completion check is visible for the given mini-game."""
    from src.utils import require_display
    require_display()
    region_map = {
        'bracing': BRACING_GREEN_CHECK,
        'patching': PATCHING_GREEN_CHECK,
        'sawing': SAWING_GREEN_CHECK,
        'scrubbing': SCRUBBING_GREEN_CHECK,
        'hammering': HAMMERING_GREEN_CHECK
    }
    
    region = region_map.get(check_type)
    if not region:
        return False
    
    frame = cv2.cvtColor(
        np.array(pyautogui.screenshot(region=region)), 
        cv2.COLOR_RGB2BGR
    )
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([40, 100, 100]), np.array([80, 255, 255]))
    return cv2.countNonZero(mask) > 50

def confirm_completion_via_ui(which, confirm_frames=2, spacing=0.08):
    """Confirm completion by checking green check multiple times."""
    for _ in range(confirm_frames):
        if not is_green_check_visible(which):
            return False
        time.sleep(spacing)
    return True

def compute_patch_scan_region():
    """Compute the scanning region for the patch mini-game window."""
    global PATCH_SCAN_REGION
    if PATCH_SCAN_REGION is not None:
        return PATCH_SCAN_REGION
    
    points = []
    for row in GRID_CENTERS:
        for (x, y) in row:
            points.append((x, y))
    
    points += [
        BRACING_BUTTON_POS,
        PATCHING_BUTTON_POS,
        SAWING_BUTTON_POS,
        SCRUBBING_BUTTON_POS,
        (BRACING_GREEN_CHECK[0] + BRACING_GREEN_CHECK[2], 
         BRACING_GREEN_CHECK[1] + BRACING_GREEN_CHECK[3]),
        (PATCHING_GREEN_CHECK[0] + PATCHING_GREEN_CHECK[2], 
         PATCHING_GREEN_CHECK[1] + PATCHING_GREEN_CHECK[3]),
        (SAWING_GREEN_CHECK[0] + SAWING_GREEN_CHECK[2], 
         SAWING_GREEN_CHECK[1] + SAWING_GREEN_CHECK[3]),
        (SCRUBBING_GREEN_CHECK[0] + SCRUBBING_GREEN_CHECK[2], 
         SCRUBBING_GREEN_CHECK[1] + SCRUBBING_GREEN_CHECK[3]),
    ]
    
    left, top = BOX_OFFSET_X, BOX_OFFSET_Y
    right = max(p[0] for p in points) + 20
    bottom = max(p[1] for p in points) + 20
    
    # Trim bottom 50 pixels to avoid clicking on minigame buttons
    bottom = bottom - 50
    
    PATCH_SCAN_REGION = (left, top, right - left, bottom - top)
    return PATCH_SCAN_REGION

def grab_patch_region():
    """Grab a screenshot of the patch region."""
    from src.utils import require_display
    require_display()
    x, y, w, h = compute_patch_scan_region()
    img = np.array(pyautogui.screenshot(region=(x, y, w, h)))
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)