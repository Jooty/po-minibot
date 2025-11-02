import time
import cv2
import numpy as np
from src.config import (
    BOX_OFFSET_X, BOX_OFFSET_Y, PYAUTOGUI_AVAILABLE, pyautogui
)
from src.utils import teleport_to
from src.vision import confirm_completion_via_ui
from src import bot_state

def capture_minigame_board():
    """Capture screenshot of the minigame board area."""
    from src.utils import require_display
    require_display()
    
    # Use the standard minigame box coordinates.
    x, y = BOX_OFFSET_X, BOX_OFFSET_Y
    w, h = 935, 740 
    
    screenshot = pyautogui.screenshot(region=(x, y, w, h))
    return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

def detect_nailheads_at_y480():
    """
    Detect nailheads along a horizontal line at absolute Y=480.
    Scans only within the minigame box looking for nail RGB values ~(110,110,110).
    Returns list of (x, y) coordinates where nailheads are found.
    """
    from src.utils import require_display
    require_display()
    
    # Scan line at absolute Y=480 only within the minigame box.
    scan_y = 480
    scan_x_start = BOX_OFFSET_X  # Left edge of minigame box.
    scan_x_end = BOX_OFFSET_X + 935  # Right edge of minigame box (935px width).
    
    # Take a screenshot of the scan line (1 pixel high, full width).
    screenshot = pyautogui.screenshot(region=(scan_x_start, scan_y, scan_x_end - scan_x_start, 1))
    scan_line = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    
    # Target RGB for nailheads: approximately (110, 110, 110).
    target_rgb = np.array([110, 110, 110], dtype=np.float32)
    color_tolerance = 15.0
    
    nailhead_positions = []
    
    # Find pixels that match the nailhead color using common utility.
    from src.utils import find_pixels_by_color
    
    matching_pixels = find_pixels_by_color(scan_line, [110, 110, 110], color_tolerance)
    
    for rel_x, _ in matching_pixels:
        abs_x = scan_x_start + rel_x
        nailhead_positions.append((abs_x, scan_y))
    
    # Group nearby pixels into nailhead centers.
    if not nailhead_positions:
        return []
    
    # Group nearby nailhead positions using common utility.
    from src.utils import group_nearby_positions
    merged_nailheads = group_nearby_positions(nailhead_positions, max_distance=25)
    
    from src.utils import log_module_action
    log_module_action("HAMMERING", f"Found {len(merged_nailheads)} nailheads at Y={scan_y}")
    for i, (x, y) in enumerate(merged_nailheads):
        log_module_action("HAMMERING", f"Nailhead {i+1}: ({x}, {y})")
    
    return merged_nailheads

def detect_nailheads_from_image(image_path):
    """
    Detect nailheads from a static image file.
    Scans at Y=480 within the minigame box looking for nail RGB values ~(110,110,110).
    Returns list of (x, y) coordinates where nailheads are found.
    """
    import cv2
    import numpy as np
    
    # Load the image
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"[HAMMERING] Error: Could not load image {image_path}")
        return []
    
    print(f"[HAMMERING] Loaded image: {image_path} ({img.shape[1]}x{img.shape[0]})")
    
    # Extract the scan line at Y=480 within minigame box
    scan_y = 480
    scan_x_start = BOX_OFFSET_X  # Left edge of minigame box
    scan_x_end = BOX_OFFSET_X + 935  # Right edge of minigame box
    
    # Check if scan line is within image bounds
    if scan_y >= img.shape[0]:
        print(f"[HAMMERING] Error: Scan line Y={scan_y} is outside image bounds (height={img.shape[0]})")
        return []
    
    # Extract the scan line (1 pixel high)
    scan_line = img[scan_y:scan_y+1, scan_x_start:scan_x_end]
    
    # Target RGB for nailheads: approximately (110, 110, 110)
    target_rgb = np.array([110, 110, 110], dtype=np.float32)
    color_tolerance = 15.0  # More strict tolerance to reduce false positives
    
    nailhead_positions = []
    
    # Find pixels that match the nailhead color using common utility
    from src.utils import find_pixels_by_color
    
    matching_pixels = find_pixels_by_color(scan_line, [110, 110, 110], color_tolerance)
    
    for rel_x, _ in matching_pixels:
        abs_x = scan_x_start + rel_x
        nailhead_positions.append((abs_x, scan_y))
    
    # Group nearby pixels into nailhead centers
    if not nailhead_positions:
        return []
    
    # Group nearby nailhead positions using common utility
    from src.utils import group_nearby_positions
    merged_nailheads = group_nearby_positions(nailhead_positions, max_distance=25)
    
    from src.utils import log_module_action
    log_module_action("HAMMERING", f"Found {len(merged_nailheads)} nailheads at Y={scan_y}")
    for i, (x, y) in enumerate(merged_nailheads):
        log_module_action("HAMMERING", f"Nailhead {i+1}: ({x}, {y})")
    
    return merged_nailheads

def add_debug_annotations(nailhead_positions):
    """Add debug annotations for each detected nailhead position."""
    print(f"[HAMMERING] Adding debug annotations for {len(nailhead_positions)} nailheads")
    
    # For each nailhead, print a debug annotation line.
    for i, (x, y) in enumerate(nailhead_positions):
        print(f"[DEBUG] Nailhead {i+1} at coordinates: ({x}, {y})")

def track_current_nail_positions(original_nailhead_positions):
    """
    Track current nail positions by searching downward from original positions.
    Returns list of (x, current_y, is_flush) for each nail.
    """
    from src.utils import require_display
    require_display()
    
    current_nail_states = []
    flush_threshold_y = 560  # Nails below this Y-level are considered flush
    
    for original_x, original_y in original_nailhead_positions:
        print(f"[HAMMERING] Tracking nail from original position ({original_x}, {original_y})")
        
        # Search downward from original position to find current nail head.
        search_range = 100  # Search up to 100 pixels down.
        current_nail_y = None
        
        # Take a vertical screenshot strip to search for the nail.
        strip_width = 15  # Width of search area around nail center.
        strip_x = original_x - strip_width // 2
        strip_y = original_y
        strip_height = search_range
        
        try:
            screenshot = pyautogui.screenshot(region=(strip_x, strip_y, strip_width, strip_height))
            search_img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # Target nail color: approximately (110, 110, 110) in BGR.
            target_bgr = np.array([110, 110, 110], dtype=np.float32)
            color_tolerance = 15.0
            
            # Search each row in the strip for nail color.
            for search_y in range(search_img.shape[0]):
                row_pixels = search_img[search_y, :]
                
                # Check each pixel in this row.
                for search_x in range(row_pixels.shape[0]):
                    pixel_bgr = row_pixels[search_x].astype(np.float32)
                    
                    # Calculate color distance.
                    diff = pixel_bgr - target_bgr
                    distance = np.sqrt(diff[0]**2 + diff[1]**2 + diff[2]**2)
                    
                    if distance <= color_tolerance:
                        # Found nail color - this is likely the current nail head position.
                        current_nail_y = original_y + search_y
                        break
                
                if current_nail_y is not None:
                    break
            
            if current_nail_y is None:
                # Nail not found in search area - might be fully sunk or moved too far.
                print(f"[HAMMERING] Nail at X={original_x} not found in search area - assuming fully sunk")
                current_nail_states.append((original_x, flush_threshold_y + 10, True))  # Mark as flush
            else:
                # Determine if nail is flush.
                is_flush = current_nail_y >= flush_threshold_y
                current_nail_states.append((original_x, current_nail_y, is_flush))
                
                status = "FLUSH" if is_flush else "needs hammering"
                print(f"[HAMMERING] Nail at X={original_x} found at Y={current_nail_y} - {status}")
                
        except Exception as e:
            print(f"[HAMMERING] Error tracking nail at X={original_x}: {e}")
            # Assume nail needs hammering if we can't track it.
            current_nail_states.append((original_x, original_y, False))
    
    return current_nail_states

def check_nail_completion(nailhead_positions):
    """
    Check which nails are properly sunk at Y=565.
    Returns list of (x, y) positions for nail heads that still need hammering.
    """
    from src.utils import require_display
    require_display()
    
    incomplete_nails = []
    
    for nail_x, _ in nailhead_positions:
        # Check a wider area to avoid nail shaft (which is exactly 10px wide).
        # Use 15px width to be safe and avoid shaft detection.
        check_width = 15  # Wider than nail shaft to avoid false positives.
        check_height = 30  # From Y=535 to Y=565 to detect raised nail tops.
        check_x = nail_x - check_width // 2
        check_y = 535  # Start checking above the sunk level
        
        screenshot = pyautogui.screenshot(region=(check_x, check_y, check_width, check_height))
        check_img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        
        # Find the actual nail head position by scanning for nail color.
        nail_head_found = False
        best_nail_x = nail_x  # Default to original position.
        max_nail_pixels = 0
        
        # Scan the area to find where the nail head actually is.
        for scan_x in range(check_width):
            nail_pixels_in_column = 0
            
            for scan_y in range(check_height):
                pixel_bgr = check_img[scan_y, scan_x]
                
                from src.utils import calculate_color_distance_lab
                
                distance = calculate_color_distance_lab(pixel_bgr, np.array([110, 110, 110]))
                
                if distance <= 15.0:
                    nail_pixels_in_column += 1
            
            # Track the column with the most nail pixels (likely the nail head).
            if nail_pixels_in_column > max_nail_pixels:
                max_nail_pixels = nail_pixels_in_column
                best_nail_x = check_x + scan_x  # Convert back to absolute coordinates.
                nail_head_found = True
        
        # If we found significant nail pixels above the sunk level, nail needs more hammering.
        if max_nail_pixels > 10:  # Threshold for unsunk nail detection.
            # Return the actual detected nail head position, not original position.
            incomplete_nails.append((best_nail_x, 480))  # Use detected head position.
            print(f"[HAMMERING] Nail head detected at X={best_nail_x} (was X={nail_x}), not fully sunk ({max_nail_pixels} raised pixels)")
        else:
            print(f"[HAMMERING] Nail at X={nail_x} is properly sunk")
    
    return incomplete_nails

def check_for_hammer_sprite():
    """Check for the bright yellow-white hammer sprite 20 pixels to the right of cursor."""
    from src.utils import require_display
    require_display()
    
    # Get current cursor position.
    cursor_x, cursor_y = pyautogui.position()
    
    # Check 20 pixels to the right of cursor.
    check_x = cursor_x + 20
    check_y = cursor_y
    
    # Take a 1x1 pixel screenshot at the check position.
    try:
        screenshot = pyautogui.screenshot(region=(check_x, check_y, 1, 1))
        pixel_rgb = np.array(screenshot)[0, 0]  # Get RGB values.
        
        # Target RGB for the hammer sprite: (254, 245, 170).
        target_rgb = np.array([254, 245, 170])
        
        # Calculate RGB distance.
        distance = np.sqrt(np.sum((pixel_rgb - target_rgb) ** 2))
        
        # Use a tolerance of 30 for color matching.
        color_tolerance = 30.0
        
        if distance <= color_tolerance:
            return True, pixel_rgb
        else:
            return False, pixel_rgb
            
    except Exception as e:
        print(f"[HAMMERING] Error checking hammer sprite: {e}")
        return False, None

def wait_for_hammer_sprite(max_frames=300):
    """Wait for the hammer sprite to appear, checking once per frame."""
    frame_count = 0
    
    while frame_count < max_frames:
        sprite_found, pixel_rgb = check_for_hammer_sprite()
        
        if sprite_found:
            print(f"[HAMMERING] Hammer sprite detected! RGB: {pixel_rgb}")
            return True
        
        # Wait approximately one frame (assuming 60fps).
        time.sleep(1.0 / 60.0)
        frame_count += 1
    
    print(f"[HAMMERING] Hammer sprite not detected after {max_frames} frames")
    return False

def run_hull_hammering():
    """Enhanced hull hammering automation with visual sprite detection."""
    from src.config import STATE_HAMMERING
    
    print("[HAMMERING] Starting visual-based hull hammering automation")
    
    try:
        # Check for immediate completion first.
        if confirm_completion_via_ui('hammering', confirm_frames=2, spacing=0.10):
            print("[HAMMERING] MINIGAME ALREADY COMPLETE! Green completion check detected.")
            return True
        
        # Detect nailheads at Y=480.
        nailhead_positions = detect_nailheads_at_y480()
        
        if not nailhead_positions:
            print("[HAMMERING] No nailheads detected")
            return False
        
        print(f"[HAMMERING] Detected {len(nailhead_positions)} nailheads")
        add_debug_annotations(nailhead_positions)
        
        # Track which nails still need hammering.
        remaining_nails = nailhead_positions.copy()
        max_attempts = 20  # Prevent infinite loops
        attempt = 0
        
        while remaining_nails and attempt < max_attempts:
            if not bot_state.RUNNING or bot_state.current_state != STATE_HAMMERING:
                print("[HAMMERING] Bot stopped during execution")
                return False
            
            # Check for completion via green check mark first.
            if confirm_completion_via_ui('hammering', confirm_frames=2, spacing=0.10):
                print("[HAMMERING] MINIGAME COMPLETE! Green completion check detected.")
                return True
            
            attempt += 1
            print(f"[HAMMERING] === Hammering attempt {attempt} ===")
            
            # Track current positions of all nails.
            current_nail_states = track_current_nail_positions(nailhead_positions)
            
            # Filter out nails that are already flush (below Y=560).
            nails_needing_hammer = []
            for nail_x, current_y, is_flush in current_nail_states:
                if not is_flush:
                    nails_needing_hammer.append((nail_x, current_y))
            
            if not nails_needing_hammer:
                print("[HAMMERING] All nails are flush! Checking for completion...")
                # Double-check completion one more time via green check.
                if confirm_completion_via_ui('hammering', confirm_frames=2, spacing=0.10):
                    print("[HAMMERING] MINIGAME COMPLETE! Green completion check confirmed.")
                    return True
                else:
                    print("[HAMMERING] No green check detected yet, continuing hammering...")
                    # Continue to next iteration
            
            print(f"[HAMMERING] {len(nails_needing_hammer)} nails still need hammering")
            
            # Hammer the nails that still need work.
            for i, (nail_x, nail_y) in enumerate(nails_needing_hammer):
                if not bot_state.RUNNING or bot_state.current_state != STATE_HAMMERING:
                    break
                
                print(f"[HAMMERING] Moving to nail {i+1}/{len(nails_needing_hammer)} at current position ({nail_x}, {nail_y})")
                
                # Teleport to the current nail position (not the original position).
                teleport_to(nail_x, nail_y)
                
                # Wait for the hammer sprite to appear and then click.
                print(f"[HAMMERING] Waiting for hammer sprite at nail ({nail_x}, {nail_y})...")
                if wait_for_hammer_sprite():
                    print(f"[HAMMERING] Striking nail at ({nail_x}, {nail_y})!")
                    pyautogui.click()
                else:
                    print(f"[HAMMERING] Warning: No hammer sprite detected for nail at ({nail_x}, {nail_y})")
                
                # Small delay between nails.
                time.sleep(0.1)
            
            # Wait a moment for nails to settle before next tracking.
            print("[HAMMERING] Waiting for nails to settle...")
            time.sleep(0.5)
            
            # Update remaining nails for next iteration (will be recalculated via tracking).
            remaining_nails = nails_needing_hammer
        
        if attempt >= max_attempts:
            print("[HAMMERING] Maximum attempts reached, some nails may not be fully sunk")
            return True  # Return success anyway to avoid infinite loops.
        
        print("[HAMMERING] All nails hammered successfully!")
        return True
        
    except Exception as e:
        print(f"[HAMMERING] Error during hammering: {e}")
        import traceback
        traceback.print_exc()
        return False