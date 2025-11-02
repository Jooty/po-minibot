import os
import cv2

# Annotate an image with various reference points and regions for debugging purposes.
# Expects a 1920x1080 image as input.

def annotate_image(image_path):
    from src.config import (
        BOX_OFFSET_X, BOX_OFFSET_Y, BRACING_GREEN_CHECK, PATCHING_GREEN_CHECK,
        SAWING_GREEN_CHECK, SCRUBBING_GREEN_CHECK, PLANK_BOX_TOPLEFT_GIVEN, PLANK_BOX_BOTTOMRIGHT_GIVEN,
        SAW_ICON_POS_ABS, GRID_CENTERS, SAW_SPAWN_COORDINATES, BRACING_BUTTON_POS,
        PATCHING_BUTTON_POS, SAWING_BUTTON_POS, SCRUBBING_BUTTON_POS
    )
    from src.utils import sanitize_rect

    def _draw_text(img, x, y, text):
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.5
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
        pad = 3
        box_w, box_h = tw + 2*pad, th + 2*pad
        top_left = (int(x - box_w//2), int(y - 10 - box_h))
        bottom_right = (top_left[0] + box_w, top_left[1] + box_h)
        cv2.rectangle(img, top_left, bottom_right, (0, 0, 0), -1)
        cv2.rectangle(img, top_left, bottom_right, (255, 255, 255), 1)
        org = (top_left[0] + pad, bottom_right[1] - pad - baseline)
        cv2.putText(img, text, org, font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    def _draw_point(img, pt, label):
        x, y = int(pt[0]), int(pt[1])
        cv2.circle(img, (x, y), 5, (0, 255, 255), -1)
        cv2.circle(img, (x, y), 5, (0, 0, 0), 1)
        _draw_text(img, x, y, label)

    def _draw_rect(img, xywh, label):
        x, y, w, h = map(int, xywh)
        cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 255), 2)
        _draw_text(img, x + w // 2, y, label)

    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"[annotate] Failed to read image: {image_path}")
        return

    # Mini-game box
    BOX_W, BOX_H = 935, 740
    box_x, box_y = int(BOX_OFFSET_X), int(BOX_OFFSET_Y)
    _draw_rect(img, (box_x, box_y, BOX_W, BOX_H), "MINIGAME_BOX (935x740)")

    # Buttons
    _draw_point(img, BRACING_BUTTON_POS, "BRACING_BUTTON_POS")
    _draw_point(img, PATCHING_BUTTON_POS, "PATCHING_BUTTON_POS")
    _draw_point(img, SAWING_BUTTON_POS, "SAWING_BUTTON_POS")
    _draw_point(img, SCRUBBING_BUTTON_POS, "SCRUBBING_BUTTON_POS")

    # Green check regions
    _draw_rect(img, BRACING_GREEN_CHECK, "BRACING_GREEN_CHECK")
    _draw_rect(img, PATCHING_GREEN_CHECK, "PATCHING_GREEN_CHECK")
    _draw_rect(img, SAWING_GREEN_CHECK, "SAWING_GREEN_CHECK")
    _draw_rect(img, SCRUBBING_GREEN_CHECK, "SCRUBBING_GREEN_CHECK")

    # Plank sawing box
    px, py, pw, ph = sanitize_rect(PLANK_BOX_TOPLEFT_GIVEN, PLANK_BOX_BOTTOMRIGHT_GIVEN)
    _draw_rect(img, (px, py, pw, ph), "PLANK_BOX")

    # Saw icon fallback
    _draw_point(img, SAW_ICON_POS_ABS, "SAW_ICON_POS_ABS")

    # Saw spawn coordinates for each board type
    for board_type, saw_pos in SAW_SPAWN_COORDINATES.items():
        _draw_point(img, saw_pos, f"SAW_{board_type.upper()}")

    # Grid centers
    for r, row in enumerate(GRID_CENTERS):
        for c, pt in enumerate(row):
            _draw_point(img, pt, f"GRID_CENTERS[{r}][{c}]")

    # Screen center reference
    _draw_point(img, (960, 540), "SCREEN_CENTER (960,540)")

    # Nailhead detection line at Y=480 
    minigame_left = box_x
    minigame_right = box_x + BOX_W
    cv2.line(img, (minigame_left, 480), (minigame_right, 480), (0, 255, 0), 2) 
    _draw_text(img, (minigame_left + minigame_right) // 2, 480, "NAILHEAD_SCAN_LINE (Y=480)")

    # Save annotated image
    base, ext = os.path.splitext(image_path)
    out_path = f"{base}_annotated.png"
    cv2.imwrite(out_path, img)
    print(f"[annotate] Wrote {out_path}")