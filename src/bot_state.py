"""Global bot state management."""

from src.config import STATE_MENU

# Bot state variables
RUNNING = False
ABORT_DRAG = False
current_state = STATE_MENU
target_minigame = 'patching'