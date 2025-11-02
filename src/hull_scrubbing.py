import time
import os
import cv2
import numpy as np
from src.config import (
    SCRUB_BOARD_TOPLEFT, SCRUB_BOARD_BOTTOMRIGHT, SCRUB_SCREENSHOT_INTERVAL,
    SCRUB_DIFF_THRESHOLD, SCRUB_MIN_DIRTY_AREA, SCRUB_BRUSH_SIZE, SCRUB_OVERLAP,
    PYAUTOGUI_AVAILABLE, pyautogui
)
from src.utils import human_drag_path, sleep_range, teleport_to
from src.vision import confirm_completion_via_ui
from src import bot_state

def _ensure_no_pyautogui_delays():
    """Ensure PyAutoGUI has absolutely no delays for maximum speed."""
    if PYAUTOGUI_AVAILABLE:
        pyautogui.PAUSE = 0
        pyautogui.MINIMUM_DURATION = 0
        pyautogui.MINIMUM_SLEEP = 0
        if hasattr(pyautogui, 'DRAG_PAUSE'):
            pyautogui.DRAG_PAUSE = 0

def load_reference_images():
    """Load clean and dirty reference images."""
    assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
    clean_path = os.path.join(assets_dir, 'scrub-board-clean.png')
    dirty_path = os.path.join(assets_dir, 'scrub-board-dirty.png')
    
    if not os.path.exists(clean_path):
        raise FileNotFoundError(f"Clean reference image not found: {clean_path}")
    if not os.path.exists(dirty_path):
        raise FileNotFoundError(f"Dirty reference image not found: {dirty_path}")
    
    clean_img = cv2.imread(clean_path, cv2.IMREAD_COLOR)
    dirty_img = cv2.imread(dirty_path, cv2.IMREAD_COLOR)
    
    if clean_img is None or dirty_img is None:
        raise ValueError("Failed to load reference images")
    
    return clean_img, dirty_img

def capture_scrub_board():
    """Capture screenshot of the scrubbing board area."""
    from src.utils import require_display
    require_display()
    
    x1, y1 = SCRUB_BOARD_TOPLEFT
    x2, y2 = SCRUB_BOARD_BOTTOMRIGHT
    w, h = x2 - x1, y2 - y1
    
    screenshot = pyautogui.screenshot(region=(x1, y1, w, h))
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

def find_dirty_areas(current_img, clean_img):
    """Find dirty areas by comparing current image to clean reference."""
    # Resize images to match if needed.
    h1, w1 = current_img.shape[:2]
    h2, w2 = clean_img.shape[:2]
    
    if (h1, w1) != (h2, w2):
        clean_img = cv2.resize(clean_img, (w1, h1))
    
    # Calculate absolute difference.
    diff = cv2.absdiff(current_img, clean_img)
    
    # Convert to grayscale and threshold.
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray_diff, SCRUB_DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)
    
    # Remove noise with morphological operations.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
    
    # Find contours of dirty areas.
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter contours by area.
    dirty_regions = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= SCRUB_MIN_DIRTY_AREA:
            x, y, w, h = cv2.boundingRect(contour)
            dirty_regions.append((x, y, w, h))
    
    return dirty_regions, cleaned

def merge_nearby_segments(segments, merge_distance=30):
    """Merge nearby dirty segments to reduce redundant scrubbing."""
    if not segments:
        return []
    
    # Sort segments by left position.
    sorted_segments = sorted(segments, key=lambda s: s['left'])
    merged = []
    current = sorted_segments[0]
    
    for next_segment in sorted_segments[1:]:
        # Check if segments are close enough to merge.
        gap = next_segment['left'] - current['right']
        if gap <= merge_distance:
            # Merge segments.
            current['right'] = max(current['right'], next_segment['right'])
            current['width'] = current['right'] - current['left']
        else:
            # Save current segment and start new one.
            merged.append(current)
            current = next_segment
    
    # Don't forget the last segment.
    merged.append(current)
    return merged

def analyze_dirty_rows(dirty_regions, board_shape):
    """Analyze which of the 10 horizontal rows contain dirt and create scrub segments for each dirty area."""
    board_h, board_w = board_shape[:2]
    num_rows = 10
    row_height = board_h // num_rows
    
    # Initialize row dirt tracking with segments.
    dirty_rows = []
    
    for row_idx in range(num_rows):
        # Skip top row (0) and bottom row (9) - only scrub middle rows 1-8.
        if row_idx == 0 or row_idx == (num_rows - 1):
            continue
            
        row_top = row_idx * row_height
        row_bottom = row_top + row_height
        row_dirty_segments = []
        
        # Find all dirty regions that intersect with this row.
        for x, y, w, h in dirty_regions:
            region_top = y
            region_bottom = y + h
            region_left = x
            region_right = x + w
            
            # Check for vertical overlap between region and row.
            if not (region_bottom <= row_top or region_top >= row_bottom):
                # Add horizontal segment for this dirty region.
                # Add some margin around the dirty area for better coverage.
                margin = 20
                segment_left = max(0, region_left - margin)
                segment_right = min(board_w, region_right + margin)
                
                row_dirty_segments.append({
                    'left': segment_left,
                    'right': segment_right,
                    'width': segment_right - segment_left
                })
        
        if row_dirty_segments:
            # Merge overlapping segments.
            merged_segments = merge_nearby_segments(row_dirty_segments)
            
            dirty_rows.append({
                'row_idx': row_idx,
                'top': row_top,
                'bottom': row_bottom,
                'center_y': row_top + row_height // 2,
                'height': row_height,
                'width': board_w,
                'dirty_segments': merged_segments
            })
    
    return dirty_rows

def perform_row_scrub(row):
    """Perform rapid side-to-side scrubbing across an entire horizontal row."""
    from src.utils import require_display
    require_display()
    _ensure_no_pyautogui_delays()
    from src.config import STATE_SCRUBBING
    
    x1, y1 = SCRUB_BOARD_TOPLEFT
    left_x = x1 + 10  # Small margin from edge.
    right_x = x1 + row['width'] - 10  # Small margin from edge.
    scrub_y = y1 + row['center_y']
    
    
    # Move to starting position (left side of row).
    teleport_to(left_x, scrub_y)
    
    # Perform rapid side-to-side scrubbing across the entire row.
    scrub_passes = 12
    
    for pass_num in range(scrub_passes):
        if not bot_state.RUNNING or bot_state.current_state != STATE_SCRUBBING:
            break
        
        # Add slight vertical variation to cover the row height.
        y_offset = (pass_num % 3 - 1) * (row['height'] // 6)  # Slight up/down variation.
        current_y = scrub_y + y_offset
            
        # Horizontal scrubbing motion across full row width
        if pass_num % 2 == 0:
            # Left to right across entire row.
            pyautogui.moveTo(right_x, current_y, duration=0.001)
        else:
            # Right to left across entire row.
            pyautogui.moveTo(left_x, current_y, duration=0.001)
    
    # Final quick passes at different heights within the row.
    for height_offset in [-row['height']//4, 0, row['height']//4]:
        if not bot_state.RUNNING or bot_state.current_state != STATE_SCRUBBING:
            break
        y_pos = scrub_y + height_offset
        pyautogui.moveTo(right_x, y_pos, duration=0.001)
        pyautogui.moveTo(left_x, y_pos, duration=0.001)

def perform_continuous_scrub_row(row, power_tracker, row_idx):
    """Perform continuous bidirectional scrub only on dirty segments within the row."""
    from src.utils import require_display
    require_display()
    _ensure_no_pyautogui_delays() 
    from src.config import STATE_SCRUBBING
    
    # Convert row coordinates to screen coordinates.
    x1, y1 = SCRUB_BOARD_TOPLEFT
    scrub_y = y1 + row['center_y']
    
    # Scrub each dirty segment in this row.
    for seg_idx, segment in enumerate(row['dirty_segments']):
        segment_left = x1 + segment['left']
        segment_right = x1 + segment['right']
        
        # Start at left side of dirty segment.
        teleport_to(segment_left, scrub_y)
        
        # Check if this segment should use power based on fair distribution.
        use_power = power_tracker.should_use_power_for_segment(row_idx, seg_idx)
        if use_power:
            power_tracker.start_power_use(row_idx, seg_idx)
            pyautogui.mouseDown()
        
        # Scrub left to right across the dirty segment.
        pyautogui.moveTo(segment_right, scrub_y, duration=0.001)
        
        # Immediately scrub right to left across the dirty segment.
        pyautogui.moveTo(segment_left, scrub_y, duration=0.001)
        
        if use_power:
            pyautogui.mouseUp()
            power_tracker.end_power_use()
            # Wait for power to recharge - keep the 0.6s recharge time.
            time.sleep(0.6)  # Slightly longer than recharge to ensure power is ready.
        else:
            # Minimal pause between segments when not using power for speed.
            time.sleep(0.05)

class PowerTracker:
    """Track power availability and distribute usage evenly across segments."""
    def __init__(self):
        self.last_power_end = 0
        self.power_duration = 0.5  # Power lasts 0.5 seconds.
        self.recharge_duration = 1.0  # Takes 1 second to recharge.
        self.segment_power_schedule = []  # Queue of segments that should get power.
        self.segments_used_power = set()  # Track which segments have used power this cycle.
        
    def schedule_power_for_segments(self, all_segments):
        """Create a randomized schedule for power usage across all segments."""
        import random
        
        # Create a list of all segment identifiers.
        segment_ids = []
        for row_idx, row in enumerate(all_segments):
            for seg_idx, segment in enumerate(row.get('dirty_segments', [])):
                segment_ids.append((row_idx, seg_idx))
        
        # Shuffle the segments to randomize power distribution.
        random.shuffle(segment_ids)
        
        # Reset tracking.
        self.segment_power_schedule = segment_ids
        self.segments_used_power = set()
        
        print(f"[SCRUBBING] Scheduled power for {len(segment_ids)} segments in random order")
    
    def should_use_power_for_segment(self, row_idx, seg_idx):
        """Check if this specific segment should use power now."""
        segment_id = (row_idx, seg_idx)
        
        # Check if power is available.
        if not self.can_use_power():
            return False
        
        # Use power much more aggressively - aim for ~80% usage rate.
        # Only skip if this segment has used power recently in this cycle.
        if segment_id in self.segments_used_power:
            # Give it another chance if we haven't distributed much power yet.
            total_segments = len(self.segment_power_schedule) + len(self.segments_used_power)
            used_ratio = len(self.segments_used_power) / max(1, total_segments)
            
            # Allow re-use if we're still early in the cycle.
            import random
            if used_ratio < 0.5:  # Less than half the segments have been powered.
                return random.random() < 0.3  # 30% chance to re-use power.
            return False
        
        # Check if this segment is next in the schedule - high priority.
        if self.segment_power_schedule and self.segment_power_schedule[0] == segment_id:
            return True
        
        # Use power very frequently - 85% chance for any segment that hasn't used it.
        import random
        return random.random() < 0.85
        
    def can_use_power(self):
        """Check if power is available (non-blocking)."""
        current_time = time.time()
        time_since_last_power = current_time - self.last_power_end
        return time_since_last_power >= self.recharge_duration
    
    def start_power_use(self, row_idx, seg_idx):
        """Mark the start of power usage for a specific segment."""
        segment_id = (row_idx, seg_idx)
        
        # Remove from schedule if it was scheduled.
        if self.segment_power_schedule and self.segment_power_schedule[0] == segment_id:
            self.segment_power_schedule.pop(0)
        
        # Mark as used.
        self.segments_used_power.add(segment_id)
        self.power_start_time = time.time()
        
        print(f"[SCRUBBING] Using power on segment {segment_id}")
        
    def end_power_use(self):
        """Mark the end of power usage and start recharge timer."""
        self.last_power_end = time.time()

def scrub_dirty_areas(dirty_regions, board_shape):
    """Execute continuous row-based scrubbing with intermittent power."""
    if not dirty_regions:
        return True
    
    from src.config import STATE_SCRUBBING
    
    # Analyze which rows contain dirt.
    dirty_rows = analyze_dirty_rows(dirty_regions, board_shape)
    
    if not dirty_rows:
        return True
    
    # Initialize power tracker.
    power_tracker = PowerTracker()
    
    # Schedule power usage across all segments for fair distribution.
    power_tracker.schedule_power_for_segments(dirty_rows)
    
    # Scrub ONLY the dirty rows continuously.
    for i, row in enumerate(dirty_rows):
        if not bot_state.RUNNING or bot_state.current_state != STATE_SCRUBBING:
            break

        # Perform continuous scrub with fair power distribution.
        perform_continuous_scrub_row(row, power_tracker, i)
    
    return True

def is_board_clean(current_img, clean_img, max_dirty_pixels=500):
    """Check if the board is sufficiently clean by comparing to clean reference."""
    dirty_regions, thresh = find_dirty_areas(current_img, clean_img)
    
    # Count total dirty pixels.
    total_dirty_pixels = cv2.countNonZero(thresh)
    
    # Board is clean if very few dirty pixels remain.
    is_clean = total_dirty_pixels <= max_dirty_pixels
    
    return is_clean

def check_completion_against_clean_board():
    """Check if current board matches the clean reference image for completion."""
    try:
        # Take screenshot of current board.
        current_board = capture_scrub_board()
        
        # Load clean reference.
        clean_img, _ = load_reference_images()
        
        # Compare current board to clean reference.
        is_clean = is_board_clean(current_board, clean_img)
        
        return is_clean
        
    except Exception as e:
        print(f"[SCRUBBING] Error checking completion: {e}")
        return False

def run_hull_scrubbing():
    """Main hull scrubbing automation loop."""
    from src.config import STATE_SCRUBBING
    
    print("[SCRUBBING] Starting hull scrubbing automation")
    
    try:
        clean_img, dirty_img = load_reference_images()
        print("[SCRUBBING] Reference images loaded successfully")
        
        attempts = 0
        max_attempts = 50 
        
        while bot_state.RUNNING and bot_state.current_state == STATE_SCRUBBING and attempts < max_attempts:
            attempts += 1
            
            # Check for completion via green check mark.
            if confirm_completion_via_ui('scrubbing', confirm_frames=2, spacing=0.10):
                print("[SCRUBBING] MINIGAME COMPLETE! Green completion check detected.")
                return True
            
            # Capture current board state.
            current_board = capture_scrub_board()
            
            # Find dirty areas that still need scrubbing.
            dirty_regions, _ = find_dirty_areas(current_board, clean_img)
            
            if not dirty_regions:
                print("[SCRUBBING] No dirty regions detected, checking final completion...")
                # Double-check completion one more time via green check.
                if confirm_completion_via_ui('scrubbing', confirm_frames=2, spacing=0.10):
                    print("[SCRUBBING] MINIGAME COMPLETE! Green completion check confirmed.")
                    return True
                else:
                    print("[SCRUBBING] No green check detected yet, continuing scrubbing...")
                    # Continue scrubbing even if no regions detected - might need more cleaning.
                    continue
            
            
            # Scrub the dirty areas.
            scrub_dirty_areas(dirty_regions, current_board.shape)
            
            # Wait before next screenshot - reduced for faster response.
            time.sleep(0.3)  # Faster than default SCRUB_SCREENSHOT_INTERVAL (0.5)
        
        if attempts >= max_attempts:
            print("[SCRUBBING] Maximum attempts reached, stopping")
            return False
        
        return True
        
    except Exception as e:
        print(f"[SCRUBBING] Error during scrubbing: {e}")
        return False