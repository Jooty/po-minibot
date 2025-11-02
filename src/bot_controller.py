import time
import sys
import os
import argparse

from src.config import (
    STATE_MENU, STATE_PATCHING, STATE_BRACING, STATE_SAWING, STATE_SCRUBBING, STATE_HAMMERING, STATE_ALL_SEQUENCE, STATE_COMPLETE,
    BRACING_BUTTON_POS, PATCHING_BUTTON_POS, SAWING_BUTTON_POS, SCRUBBING_BUTTON_POS, HAMMERING_BUTTON_POS, PYAUTOGUI_AVAILABLE,
    BOX_OFFSET_X, BOX_OFFSET_Y
)
from src.vision import confirm_completion_via_ui
from src.utils import click_button
from src.hull_patching import click_leaks_until_clear
from src.hull_bracing import solve_bracing_fixed_rows
from src.plank_sawing import run_plank_sawing_until_perfect
from src.hull_scrubbing import run_hull_scrubbing
from src.hull_hammering import run_hull_hammering
from src import bot_state

def on_press(key):
    """Handle keyboard input for bot control."""
    if not PYAUTOGUI_AVAILABLE:
        return
    
    try:
        if hasattr(key, 'char'):
            if key.char == '1':
                if bot_state.RUNNING and bot_state.target_minigame == 'scrubbing':
                    bot_state.RUNNING = False
                    print('Hull Scrubbing bot STOPPED')
                else:
                    bot_state.target_minigame = 'scrubbing'
                    bot_state.RUNNING = True
                    bot_state.current_state = STATE_MENU
                    print('Starting Hull Scrubbing bot - Press 1 or F11 to stop')
            
            elif key.char == '3':
                if bot_state.RUNNING and bot_state.target_minigame == 'bracing':
                    bot_state.RUNNING = False
                    print('Hull Bracing bot STOPPED')
                else:
                    bot_state.target_minigame = 'bracing'
                    bot_state.RUNNING = True
                    bot_state.current_state = STATE_MENU
                    print('Starting Hull Bracing bot - Press 3 or F11 to stop')
            
            elif key.char == '5':
                if bot_state.RUNNING and bot_state.target_minigame == 'patching':
                    bot_state.RUNNING = False
                    print('Hull Patching bot STOPPED')
                else:
                    bot_state.target_minigame = 'patching'
                    bot_state.RUNNING = True
                    bot_state.current_state = STATE_MENU
                    print('Starting Hull Patching bot - Press 5 or F11 to stop')
            
            elif key.char == '2':
                if bot_state.RUNNING and bot_state.target_minigame == 'sawing':
                    print('Plank Sawing bot STOPPED')
                    if PYAUTOGUI_AVAILABLE:
                        try: 
                            import pyautogui
                            pyautogui.mouseUp()
                        except Exception: 
                            pass
                    bot_state.ABORT_DRAG = True
                    bot_state.RUNNING = False
                    return
                else:
                    bot_state.target_minigame = 'sawing'
                    bot_state.RUNNING = True
                    bot_state.current_state = STATE_MENU
                    print('Starting Plank Sawing bot - Press 2 or F11 to stop')
            
            elif key.char == '4':
                if bot_state.RUNNING and bot_state.target_minigame == 'hammering':
                    bot_state.RUNNING = False
                    print('Hull Hammering bot STOPPED')
                else:
                    bot_state.target_minigame = 'hammering'
                    bot_state.RUNNING = True
                    bot_state.current_state = STATE_MENU
                    print('Starting Hull Hammering bot - Press 4 or F11 to stop')
        
        if hasattr(key, 'name'):
            if key.name == 'f11':
                bot_state.RUNNING = False
                bot_state.current_state = STATE_MENU
                print('Bot STOPPED')
            elif key.name == 'f1':
                if bot_state.RUNNING and bot_state.target_minigame == 'all_sequence':
                    bot_state.RUNNING = False
                    print('All Minigames Sequence STOPPED')
                else:
                    bot_state.target_minigame = 'all_sequence'
                    bot_state.RUNNING = True
                    bot_state.current_state = STATE_MENU
                    print('Starting All Minigames Sequence - Press F1 or F11 to stop')
    
    except AttributeError:
        pass

def handle_menu_state():
    if bot_state.target_minigame == 'patching':
        btn = PATCHING_BUTTON_POS
    elif bot_state.target_minigame == 'bracing':
        btn = BRACING_BUTTON_POS
    elif bot_state.target_minigame == 'scrubbing':
        btn = SCRUBBING_BUTTON_POS
    elif bot_state.target_minigame == 'hammering':
        btn = HAMMERING_BUTTON_POS
    elif bot_state.target_minigame == 'all_sequence':
        # For sequence mode, transition directly to sequence state
        bot_state.current_state = STATE_ALL_SEQUENCE
        return
    else:
        btn = SAWING_BUTTON_POS
    
    click_button(*btn)
    
    # Bug fix: the hammering minigame has a green crosshair that interferes
    # with our completion detection, since completion is detected by green pixels
    # around the mini game button.
    if bot_state.target_minigame == 'hammering':
        from src.utils import teleport_to
        # Move to neutral position (center of minigame box)
        neutral_x = BOX_OFFSET_X + 467  # Center of 935px wide box
        neutral_y = BOX_OFFSET_Y + 370  # Center of 740px tall box
        teleport_to(neutral_x, neutral_y)
    
    # Give time for minigame to load.
    time.sleep(2.0)
    
    new_state = (
        STATE_PATCHING if bot_state.target_minigame == 'patching' else
        STATE_BRACING if bot_state.target_minigame == 'bracing' else
        STATE_SCRUBBING if bot_state.target_minigame == 'scrubbing' else
        STATE_HAMMERING if bot_state.target_minigame == 'hammering' else
        STATE_SAWING
    )
    bot_state.current_state = new_state

def handle_patching_state():
    """Handle hull patching state."""
    if confirm_completion_via_ui('patching', confirm_frames=2, spacing=0.10):
        bot_state.current_state = STATE_COMPLETE
        return
    
    solved = click_leaks_until_clear()
    if solved:
        bot_state.current_state = STATE_COMPLETE

def handle_bracing_state():
    """Handle hull bracing state."""
    solved = solve_bracing_fixed_rows()
    if solved:
        bot_state.current_state = STATE_COMPLETE

def handle_sawing_state():
    """Handle plank sawing state."""
    # if confirm_completion_via_ui('sawing', confirm_frames=2, spacing=0.10):
    #     bot_state.current_state = STATE_COMPLETE
    #     return
    
    solved = run_plank_sawing_until_perfect()
    if solved:
        bot_state.current_state = STATE_COMPLETE

def handle_scrubbing_state():
    """Handle hull scrubbing state."""
    if confirm_completion_via_ui('scrubbing', confirm_frames=2, spacing=0.10):
        bot_state.current_state = STATE_COMPLETE
        return
    
    solved = run_hull_scrubbing()
    if solved:
        bot_state.current_state = STATE_COMPLETE

def handle_hammering_state():
    """Handle hull hammering state."""
    if confirm_completion_via_ui('hammering', confirm_frames=2, spacing=0.10):
        bot_state.current_state = STATE_COMPLETE
        return
    
    solved = run_hull_hammering()
    if solved:
        bot_state.current_state = STATE_COMPLETE

def handle_all_sequence_state():
    print("[SEQUENCE] Starting all minigames sequence automation")
    
    minigame_sequence = ['scrubbing', 'sawing', 'bracing', 'hammering', 'patching']
    
    while bot_state.RUNNING and bot_state.target_minigame == 'all_sequence':
        print("[SEQUENCE] ===== Starting new cycle of all minigames =====")
        
        for i, minigame in enumerate(minigame_sequence):
            if not bot_state.RUNNING or bot_state.target_minigame != 'all_sequence':
                print("[SEQUENCE] Sequence stopped by user")
                return
            
            print(f"[SEQUENCE] Running minigame {i+1}/{len(minigame_sequence)}: {minigame}")
            
            # Set the current minigame and start it.
            original_target = bot_state.target_minigame
            bot_state.target_minigame = minigame
            bot_state.current_state = STATE_MENU
            
            # Wait for minigame to complete.
            while (bot_state.RUNNING and 
                   bot_state.target_minigame == minigame and 
                   bot_state.current_state != STATE_COMPLETE):
                
                # Handle the current state.
                if bot_state.current_state == STATE_MENU:
                    handle_menu_state()
                elif bot_state.current_state == STATE_PATCHING:
                    handle_patching_state()
                elif bot_state.current_state == STATE_BRACING:
                    handle_bracing_state()
                elif bot_state.current_state == STATE_SAWING:
                    handle_sawing_state()
                elif bot_state.current_state == STATE_SCRUBBING:
                    handle_scrubbing_state()
                elif bot_state.current_state == STATE_HAMMERING:
                    handle_hammering_state()
                
                time.sleep(0.1) 
            
            # Restore sequence mode.
            bot_state.target_minigame = original_target
            
            if bot_state.current_state == STATE_COMPLETE:
                print(f"[SEQUENCE] {minigame} completed successfully!")
                
                # Wait 1 second between minigames (except after the last one).
                if i < len(minigame_sequence) - 1:
                    print("[SEQUENCE] Waiting 1 second before next minigame...")
                    time.sleep(1.0)
            else:
                print(f"[SEQUENCE] {minigame} did not complete successfully")
                break
        
        # Check if we completed all minigames successfully.
        if bot_state.RUNNING and bot_state.target_minigame == 'all_sequence':
            print("[SEQUENCE] All minigames completed! Waiting 10 seconds before repeating...")
            
            # Wait 10 seconds before repeating the entire sequence.
            for countdown in range(10, 0, -1):
                if not bot_state.RUNNING or bot_state.target_minigame != 'all_sequence':
                    print("[SEQUENCE] Sequence stopped during countdown")
                    return
                print(f"[SEQUENCE] Repeating in {countdown} seconds...")
                time.sleep(1.0)
        else:
            break
    
    print("[SEQUENCE] All minigames sequence ended")

def handle_complete_state():
    """Handle completion state."""
    bot_state.RUNNING = False


def main():
    if not PYAUTOGUI_AVAILABLE:
        print("Error: Display functionality not available.")
        print("This bot requires a graphical environment to run.")
        print("For annotation only, use: minibot image.png")
        return
    
    print('Multi-Minigame Bot')
    print('Press 1 for Hull Scrubbing')
    print('Press 2 for Plank Sawing')
    print('Press 3 for Hull Bracing')
    print('Press 4 for Hull Hammering')
    print('Press 5 for Hull Patching')
    print('Press F1 for All Minigames Sequence (auto-loop)')
    print('Press F11 to stop')
    
    try:
        from pynput import keyboard
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
    except Exception as e:
        print(f"Could not start keyboard listener: {e}")
        return
    
    while True:
        if bot_state.RUNNING:
            if bot_state.current_state == STATE_MENU:
                handle_menu_state()
            elif bot_state.current_state == STATE_PATCHING:
                handle_patching_state()
            elif bot_state.current_state == STATE_BRACING:
                handle_bracing_state()
            elif bot_state.current_state == STATE_SAWING:
                handle_sawing_state()
            elif bot_state.current_state == STATE_SCRUBBING:
                handle_scrubbing_state()
            elif bot_state.current_state == STATE_HAMMERING:
                handle_hammering_state()
            elif bot_state.current_state == STATE_ALL_SEQUENCE:
                handle_all_sequence_state()
            elif bot_state.current_state == STATE_COMPLETE:
                handle_complete_state()
            time.sleep(0.006)
        else:
            time.sleep(0.01)

def create_parser():
    """Create the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog='minibot',
        description='Po-minibot: Automation bot for Po mini-games',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  minibot                               # Run interactive bot (requires display)
  minibot debug annotate image.png      # Annotate image with coordinates
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Debug command group
    debug_parser = subparsers.add_parser('debug', help='Debug and analysis tools')
    debug_subparsers = debug_parser.add_subparsers(dest='debug_command', help='Debug commands')
    
    # Annotate subcommand
    annotate_parser = debug_subparsers.add_parser(
        'annotate', 
        help='Annotate image with bot coordinate overlays'
    )
    annotate_parser.add_argument(
        'image_path',
        help='Path to image file (PNG/JPG) to annotate'
    )
    
    
    
    
    
    return parser

def run_bot():
    """Entry point for running the bot."""
    parser = create_parser()
    
    # If no arguments, run interactive mode
    if len(sys.argv) == 1:
        if not PYAUTOGUI_AVAILABLE:
            parser.print_help()
            print("\nError: Display functionality not available.")
            print("This bot requires a graphical environment for interactive mode.")
            print("To annotate an image, use: minibot debug annotate path/to/image.png")
            sys.exit(1)
        args = argparse.Namespace(command=None)
    else:
        args = parser.parse_args()
    
    # Handle debug commands
    if args.command == 'debug':
        if args.debug_command == 'annotate':
            image_path = args.image_path
            if not os.path.exists(image_path):
                print(f"Error: Image file not found: {image_path}")
                sys.exit(1)
            
            # Check if it's an image file
            valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif')
            if not image_path.lower().endswith(valid_extensions):
                print(f"Error: Unsupported file type. Supported: {', '.join(valid_extensions)}")
                sys.exit(1)
            
            print(f"Annotating image: {image_path}")
            from src.annotation import annotate_image
            annotate_image(image_path)
            return
            
        
        
        
        else:
            parser.parse_args(['debug', '--help'])
    
    # Interactive mode (default when no command specified)
    if args.command is None:
        bot_state.RUNNING = False
        bot_state.current_state = STATE_MENU
        bot_state.target_minigame = 'sawing'
        main()