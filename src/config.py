import numpy as np

# Try to import pyautogui, but allow running without display
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
    # Configure pyautogui settings
    pyautogui.PAUSE = 0
    try:
        pyautogui.MINIMUM_DURATION = 0
        pyautogui.MINIMUM_SLEEP = 0
        pyautogui.DRAG_PAUSE = 0
        pyautogui.FAILSAFE = False
    except Exception:
        pass
except Exception:
    # Running without display - create mock for constants
    PYAUTOGUI_AVAILABLE = False
    class MockPyAutoGUI:
        @staticmethod
        def easeInOutQuad(t):
            return t
    pyautogui = MockPyAutoGUI()

# -------------------------- Global Tunables ----------------------------
BOARD_CLAMP_MARGIN = 2
SAW_DEBUG_MAX_INV = 0
SAW_DEBUG_LAST_DELTA = 0
BRIGHT_TOP_DELTA_MAX = 10
DEBUG_SAWING = True
SAVE_DEBUG_IMAGES = False  # Moved to debug command

# Movement and timing parameters
DRAG_SPEED_PX_PER_SEC_RANGE = (8000.0, 12000.0)
DRAG_MIN_DURATION = 0.05
DRAG_MAX_DURATION = 0.22
DRAG_TWEEN = pyautogui.easeInOutQuad

PRE_PRESS_SETTLE_RANGE = (0.004, 0.008)
POST_RELEASE_REACTION_RANGE = (0.025, 0.045)
BREATH_EVERY_N_MOVES = 18
BREATH_SLEEP_RANGE = (0.08, 0.14)

# -------------------------- Geometry ----------------------------------
# Let's assume a 1920x1080 screen, where the top-left pixel is (0, 0).
#
# The mini-games take place within a centered rectangular box:
#   • The center of the screen is at (960, 540).
#   • The mini-game box measures about 935×740 pixels.
#   • This means the top-left corner of the box is around (493, 170),
#     and the bottom-right corner around (1428, 910).
#
# Along the bottom (Y = 910) is a horizontal row of mini-game buttons:
#   • Hull Scrubbing: X = 630
#   • Board Cutting (Sawing): X = 795
#   • Hull Bracing: X = 955
#   • Hammering: X = 1120
#   • Hull Patching: X = 1285
#
# Each mini-game also has a “completion” indicator (a small green hex)
# near its button—typically offset by about 50 pixels horizontally.
# These are represented as small 30×30 regions defined near the
# button coordinates.
#
# All coordinates are absolute to a 1920×1080 display and serve as
# global references for detection, movement, and alignment across
# all mini-game modules.
BOX_OFFSET_X, BOX_OFFSET_Y = 493, 170

# Absolute button positions (Y fixed at 910)
BRACING_BUTTON_POS = (955, 910)
PATCHING_BUTTON_POS = (1285, 910)
SAWING_BUTTON_POS = (795, 910)
SCRUBBING_BUTTON_POS = (630, 910)
HAMMERING_BUTTON_POS = (1120, 910)

# Green check regions (x, y, w, h)
BRACING_GREEN_CHECK = (955 - 50 - 15, 910 - 15, 30, 30)
PATCHING_GREEN_CHECK = (1285 - 50 - 15, 910 - 15, 30, 30)
SAWING_GREEN_CHECK = (795 - 50 - 15, 910 - 15, 30, 30)
SCRUBBING_GREEN_CHECK = (630 - 50 - 15, 910 - 15, 30, 30)
HAMMERING_GREEN_CHECK = (1120 - 50 - 15, 910 - 15, 30, 30)

# 4x4 grid cell centers for hull bracing mini game
GRID_CENTERS = [[(850, 415), (920, 415), (995, 415), (1075, 415)],
                [(850, 490), (920, 490), (995, 490), (1075, 490)],
                [(850, 565), (920, 565), (995, 565), (1075, 565)],
                [(850, 640), (920, 640), (995, 640), (1075, 640)]]

# -------------------------- Plank Sawing constants ---------------------
PLANK_BOX_TOPLEFT_GIVEN = (645, 440)
PLANK_BOX_BOTTOMRIGHT_GIVEN = (1280, 715)
SAW_ICON_POS_ABS = (870, 165)

# Saw detection parameters
SAW_TARGET_RGB = np.array([162, 159, 162], dtype=np.float32)
SAW_COLOR_EPS = 22.0
SAW_V_MIN = 160
SAW_MIN_AREA = 30

# Plank groove detection parameters
PLANK_TARGET_RGB = np.array([54, 36, 27], dtype=np.float32)
PLANK_COLOR_EPS = 28.0
PLANK_V_MAX = 85
PLANK_MIN_GROOVE_AREA = 1200

# Plank cutting parameters
PLANK_DOWNSAMPLE = 2  # Reduced from 3 to preserve connectivity
PLANK_WAYPOINT_STEP = 6
PLANK_NEXT_BOARD_DELAY = 0.5
PLANK_EXPECTED_BOARDS = 4
PLANK_MAX_ATTEMPTS = 7

# Board template matching parameters
TEMPLATE_MATCH_THRESHOLD = 0.6
BOARD_TEMPLATES = {
    'L': 'assets/board-L.png',
    'diagonal': 'assets/board-diagonal.png',
    'horizontal': 'assets/board-horizontal.png',
    'vertical': 'assets/board-vertical.png',
    'zigzag': 'assets/board-zigzag.png'
}

# Saw spawn coordinates for each board type (absolute screen coordinates)
SAW_SPAWN_COORDINATES = {
    'diagonal': (950, 385),
    'horizontal': (510, 570),
    'L': (875, 385),
    'vertical': (875, 385),
    'zigzag': (690, 755)
}

# Predefined waypoints for each board type (relative to board region)
BOARD_WAYPOINTS = {
    'L': [(300, 0), (300, 152), (600, 152)],
    'diagonal': [(360, 0), (220, 350)],
    'horizontal': [(0, 150), (600, 150)],
    'vertical': [(285, 0), (285, 300)],
    'zigzag': [(155, 300), (258, 85), (332, 230), (455, 0)]
}

# ======================= HULL PATCHING constants ========================
PATCH_HSV_LOW = np.array([90, 40, 70])
PATCH_HSV_HIGH = np.array([120, 255, 255])
PATCH_MIN_AREA = 280
RECLICK_COOLDOWN_S = 0.75
MIN_CLICK_INTERVAL_S = 0.11

# -------------------------- Hull Scrubbing constants -------------------
SCRUB_BOARD_TOPLEFT = (575, 315)
SCRUB_BOARD_BOTTOMRIGHT = (1215, 760)
SCRUB_SCREENSHOT_INTERVAL = 0.5
SCRUB_DIFF_THRESHOLD = 30
SCRUB_MIN_DIRTY_AREA = 50
SCRUB_BRUSH_SIZE = 20
SCRUB_OVERLAP = 0.5

# -------------------------- Bot state constants -----------------------
STATE_MENU = 'menu'
STATE_PATCHING = 'patching'
STATE_BRACING = 'bracing'
STATE_SAWING = 'sawing'
STATE_SCRUBBING = 'scrubbing'
STATE_HAMMERING = 'hammering'
STATE_ALL_SEQUENCE = 'all_sequence'
STATE_COMPLETE = 'complete'