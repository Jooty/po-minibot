"""Hull patching mini-game automation."""

import time
import cv2
import numpy as np
from src.config import (
    PATCH_HSV_LOW, PATCH_HSV_HIGH, PATCH_MIN_AREA, 
    RECLICK_COOLDOWN_S, MIN_CLICK_INTERVAL_S, STATE_PATCHING
)
from src.vision import compute_patch_scan_region, grab_patch_region, confirm_completion_via_ui
from src.utils import teleport_to, distance
from src import bot_state

_recent_clicks = []

def _now():
    """Get current timestamp."""
    return time.time()

def _prune_recent():
    """Remove old clicks from recent clicks list."""
    t = _now()
    global _recent_clicks
    _recent_clicks = [(x, y, ts) for (x, y, ts) in _recent_clicks 
                      if t - ts < RECLICK_COOLDOWN_S]

def _too_recent(x, y, tol=32):
    """Check if a position was clicked too recently."""
    for cx, cy, ts in _recent_clicks:
        if abs(cx - x) <= tol and abs(cy - y) <= tol:
            return True
    return False

def _record_click(x, y):
    """Record a click at the given position."""
    _recent_clicks.append((x, y, _now()))

def detect_leak_centers():
    """Detect centers of leaks that need patching."""
    px, py, pw, ph = compute_patch_scan_region()
    frame = grab_patch_region()
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, PATCH_HSV_LOW, PATCH_HSV_HIGH)
    mask = cv2.medianBlur(mask, 5)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tops = []
    
    for c in contours:
        a = cv2.contourArea(c)
        if a < PATCH_MIN_AREA:
            continue
        
        pts = c.reshape(-1, 2)
        if pts.size == 0:
            continue
        
        min_y = int(np.min(pts[:, 1]))
        xs_at_top = pts[pts[:, 1] == min_y][:, 0]
        if xs_at_top.size == 0:
            xs_at_top = pts[np.abs(pts[:, 1] - min_y) <= 1][:, 0]
        
        cx = int(np.median(xs_at_top))
        cy = int(min_y)
        sx, sy = px + cx, py + cy
        
        # Check bounds.
        if sx <= px or sy <= py or sx >= px + pw - 1 or sy >= py + ph - 1:
            continue
        
        tops.append((sx, sy))
    
    return tops

def order_clicks_nearest(centers, start_pos=None):
    """Order click targets by nearest-neighbor to minimize travel."""
    if not centers:
        return []
    
    if start_pos is None:
        try:
            from src.config import pyautogui
            mx, my = pyautogui.position()
        except Exception:
            mx, my = centers[0]
        start_pos = (mx, my)
    
    ordered = []
    remaining = centers[:]
    cur = start_pos
    
    while remaining:
        remaining.sort(key=lambda p: distance(cur[0], cur[1], p[0], p[1]))
        nxt = remaining.pop(0)
        ordered.append(nxt)
        cur = nxt
    
    return ordered

def click_leaks_until_clear():
    """Main patching loop - click leaks until completion."""
    last_click_time = 0.0
    
    while bot_state.RUNNING and bot_state.current_state == STATE_PATCHING:
        if confirm_completion_via_ui('patching', confirm_frames=2, spacing=0.10):
            return True
        
        _prune_recent()
        centers = detect_leak_centers()
        
        if not centers:
            time.sleep(0.02)
            continue
        
        for (cx, cy) in order_clicks_nearest(centers):
            if _too_recent(cx, cy):
                continue
            
            now = _now()
            wait_needed = MIN_CLICK_INTERVAL_S - (now - last_click_time)
            if wait_needed > 0:
                time.sleep(wait_needed)
            
            teleport_to(cx, cy)
            from src.config import pyautogui
            pyautogui.mouseDown()
            pyautogui.mouseUp()
            _record_click(cx, cy)
            last_click_time = _now()
            time.sleep(0.02)
        
        time.sleep(0.01)
    
    return False