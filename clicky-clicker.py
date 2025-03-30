"""
ScreenClicker - An Auto-Clicking Tool
This application allows users to define clickable areas on the screen and automate clicking within these areas.
The tool creates a transparent overlay window where users can draw rectangles to define click zones.
"""

# Required imports for GUI, automation, and utility functions
import tkinter as tk
from tkinter import ttk
import random
import time
import threading
import pyautogui
from screeninfo import get_monitors
import ctypes # Added for DPI awareness
from ctypes import wintypes
import keyboard # Added for global Shift key detection

# --- Windows API Constants for Click-Through ---
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
LWA_ALPHA = 0x00000002
# --- End Constants ---

# --- DPI Awareness (Windows specific) ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # Necessary for accurate coordinate mapping with scaling
except AttributeError:
    # Fallback for older Windows versions
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except AttributeError:
        print("Warning: Could not set DPI awareness. Coordinate mapping might be inaccurate on scaled displays.")

def get_scaling_factor():
    """Gets the system scaling factor (Windows only)."""
    try:
        # Get the DPI for the primary monitor (assumes system-wide scaling)
        # 96 DPI is the default standard (100% scaling)
        LOGPIXELSX = 88
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        dc = user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(dc, LOGPIXELSX)
        user32.ReleaseDC(0, dc)
        scaling_factor = dpi / 96.0
        print(f"Detected DPI: {dpi}, Scaling Factor: {scaling_factor}") # Debug info
        return scaling_factor
    except Exception as e:
        print(f"Warning: Could not detect scaling factor. Assuming 1.0. Error: {e}")
        return 1.0

# Get scaling factor at startup
SCALING_FACTOR = get_scaling_factor()
# --- End DPI Awareness ---

class ScreenClicker:
    """
    Main application class that handles the screen clicking functionality.
    Creates a transparent fullscreen overlay and a control panel for managing click areas.
    """
    
    def __init__(self, root):
        """Initialize the application with main window and control panel."""
        self.root = root
        self.root.title("ScreenClicker Overlay")
        self.root.attributes('-topmost', True)  # Keep window always on top
        self.root.attributes('-alpha', 0.1)  # Set window transparency - will adjust later
        self.root.withdraw() # Hide initially until monitor is selected

        # Fetch monitor info
        self.monitors = get_monitors()
        self.selected_monitor = next((m for m in self.monitors if m.is_primary), self.monitors[0]) # Default to primary or first

        # Set initial geometry based on selected monitor
        self.set_overlay_geometry(self.selected_monitor)
        self.root.deiconify() # Show window after setting geometry
        
        # --- Set Click-Through and Initial Alpha --- 
        # Must be called after deiconify and geometry is set
        self.root.update_idletasks()
        self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        self._set_clickthrough(True) # Start in click-through mode
        self._set_alpha(25) # ~10% alpha
        # --- End Click-Through Setup ---
        
        # Initialize state tracking variables
        self.click_areas = []  # List to store all defined click areas
        self.is_drawing = False  # Flag to track if user is currently drawing
        self.drawing_start_canvas_x = 0  # Starting X coordinate of drawing
        self.drawing_start_canvas_y = 0  # Starting Y coordinate of drawing
        self.is_playing = False  # Flag to track if clicking sequence is active
        self.click_thread = None  # Thread for click sequence
        self.shift_down = False # Flag for Shift key state
        self.listener_thread_stop = threading.Event() # Event to stop listener thread
        
        # Configure main window appearance (background color)
        self.root.configure(bg='gray') # Keep gray for slight visibility
        
        # Create transparent canvas for drawing click areas
        self.canvas = tk.Canvas(self.root, bg='gray', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Create separate control window with buttons and settings
        self.setup_control_window()
        
        # Setup UI elements in control window
        self.setup_ui() # Setup UI *after* getting monitors
        
        # Bind mouse and keyboard events
        self.setup_event_bindings()
        
        # Ensure control window stays on top after everything is initialized
        self.root.after(100, self.ensure_control_window_on_top)

        # --- Start Keyboard Listener --- 
        self.listener_thread = threading.Thread(target=self._listen_for_shift, daemon=True)
        self.listener_thread.start()
        # -----------------------------

    # --- Windows API Helper Functions ---
    def _set_clickthrough(self, enabled: bool):
        """Sets or removes the WS_EX_TRANSPARENT style."""
        try:
            style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            if enabled:
                style |= WS_EX_LAYERED | WS_EX_TRANSPARENT # Add both flags
            else:
                style &= ~WS_EX_TRANSPARENT # Remove only transparent, keep layered
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style)
        except Exception as e:
            print(f"Error setting clickthrough: {e}")

    def _set_alpha(self, alpha_value_0_255: int):
        """Sets window alpha using SetLayeredWindowAttributes."""
        try:
            # Ensure WS_EX_LAYERED is set before setting alpha
            style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            if not (style & WS_EX_LAYERED):
                 ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
            
            ctypes.windll.user32.SetLayeredWindowAttributes(self.hwnd, 0, alpha_value_0_255, LWA_ALPHA)
        except Exception as e:
            print(f"Error setting alpha: {e}")
    # --- End Windows API Helper Functions ---

    def set_overlay_geometry(self, monitor):
        """Sets the overlay window geometry to match the selected monitor."""
        self.root.geometry(f"{monitor.width}x{monitor.height}+{monitor.x}+{monitor.y}")
        # Re-apply styles if window handle exists (might be called before init finishes)
        if hasattr(self, 'hwnd') and self.hwnd:
             self.root.update_idletasks()
             # Re-fetch HWND just in case it changed?
             self.hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) 
             self._set_clickthrough(not self.is_drawing) # Re-apply based on drawing state
             current_alpha = 75 if self.is_drawing else 25 # Crude guess of current alpha
             # Ideally, store current alpha state if needed, using 25 as default reset
             self._set_alpha(current_alpha) 

    def ensure_control_window_on_top(self):
        """Ensure the control window stays on top after initialization."""
        self.control_window.attributes('-topmost', True)
        self.control_window.lift()
        self.control_window.focus_force()

    def setup_control_window(self):
        """Create and configure the control panel window."""
        self.control_window = tk.Toplevel(self.root)
        self.control_window.title("ClickyClicker")
        self.control_window.attributes('-topmost', True)
        self.control_window.geometry("+%d+%d" % (0, 0))  # Position at top-left
        self.control_window.resizable(False, False)
        
        # Create main frame for controls
        self.control_frame = ttk.Frame(self.control_window)
        self.control_frame.pack(fill=tk.X, side=tk.TOP)

    def setup_event_bindings(self):
        """Setup mouse and keyboard event handlers."""
        # Bind Shift+Click events for drawing click areas - NOW just regular clicks
        # Drawing logic will only proceed if self.shift_down is True
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        # Add binding for regular clicks to bring control window to front (this might still be needed?)
        # self.canvas.bind("<Button-1>", lambda e: self.control_window.lift()) # Covered by above now?
        
        # Bind escape key to quit and handle window closing
        self.root.bind("<Escape>", lambda e: self.quit())
        self.control_window.protocol("WM_DELETE_WINDOW", self.quit)

    def setup_ui(self):
        """
        Create and arrange all UI elements in the control panel.
        Includes instructions, interval settings, and control buttons.
        """
        # Add instruction label
        ttk.Label(self.control_frame, 
                 text="Hold Shift + Left Click to draw\nDrag and release to finish",
                 justify=tk.LEFT).pack(side=tk.LEFT, padx=5, pady=5)
        
        # --- Monitor Selection ---
        monitor_frame = ttk.Frame(self.control_frame)
        monitor_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(monitor_frame, text="Monitor:").pack(side=tk.LEFT)
        monitor_names = [f"Monitor {i+1}: {m.width}x{m.height}" + (" (Primary)" if m.is_primary else "") 
                         for i, m in enumerate(self.monitors)]
        self.monitor_var = tk.StringVar()
        monitor_combobox = ttk.Combobox(monitor_frame, textvariable=self.monitor_var, 
                                        values=monitor_names, state="readonly", width=25)
        # Set default selection in combobox
        default_monitor_index = self.monitors.index(self.selected_monitor)
        monitor_combobox.current(default_monitor_index) 
        monitor_combobox.bind("<<ComboboxSelected>>", self.on_monitor_select)
        monitor_combobox.pack(side=tk.LEFT)
        # --- End Monitor Selection ---

        # Create interval settings frame
        interval_frame = ttk.Frame(self.control_frame)
        interval_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_frame, text="Click interval (ms):").pack(side=tk.LEFT)
        self.interval_var = tk.IntVar(value=1000)
        ttk.Spinbox(interval_frame, from_=100, to=10000, increment=100, 
                   textvariable=self.interval_var, width=5).pack(side=tk.LEFT)
        
        # Add control buttons (Play, Stop, Reset)
        self.play_button = ttk.Button(self.control_frame, text="▶ Play", command=self.start_clicking)
        self.play_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(self.control_frame, text="⏹ Stop", command=self.stop_clicking, 
                                    state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(self.control_frame, text="Reset", command=self.reset).pack(side=tk.LEFT, padx=5)
        
        # Add Customize Intervals button
        self.customize_button = ttk.Button(self.control_frame, text="⚙ Customize Intervals", 
                                           command=self.open_interval_settings)
        self.customize_button.pack(side=tk.LEFT, padx=5)
        
        # Add status display
        self.status_var = tk.StringVar(value="Hold Shift + Left Click to draw.")
        ttk.Label(self.control_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=5, pady=5)

    def on_monitor_select(self, event=None):
        """Handles the selection of a different monitor."""
        selected_index = event.widget.current()
        self.selected_monitor = self.monitors[selected_index]
        print(f"Selected monitor: {self.selected_monitor}") # Debug info
        self.set_overlay_geometry(self.selected_monitor)
        self.reset() # Reset click areas when monitor changes
        self.status_var.set(f"Switched to Monitor {selected_index + 1}. Draw new areas.")
        self.control_window.lift() # Keep control window on top

    def on_mouse_down(self, event):
        """
        Handle the start of drawing a new click area.
        Triggered when user holds Shift and clicks left mouse button.
        """
        # Only proceed if Shift is held down (window is not click-through)
        if self.shift_down and not self.is_drawing and not self.is_playing:
            # --- Make window opaque to mouse for drawing --- (REMOVED - handled by Shift key listener)
            # self._set_clickthrough(False)
            # self._set_alpha(75) # ~30% alpha, slightly more visible
            # self.root.update_idletasks() # Ensure style changes apply before getting position
            # -----------------------------------------------
            
            # Capture absolute screen coordinates at start
            self.drawing_start_screen_x, self.drawing_start_screen_y = pyautogui.position()
            print(f"Mouse down - Screen Coords: ({self.drawing_start_screen_x}, {self.drawing_start_screen_y})") # Debug
            
            # Capture canvas coordinates for drawing the visual rectangle
            self.drawing_start_canvas_x = event.x 
            self.drawing_start_canvas_y = event.y
            print(f"Mouse down - Canvas Coords: ({self.drawing_start_canvas_x}, {self.drawing_start_canvas_y})") # Debug
            
            self.is_drawing = True
            # Create temporary rectangle using CANVAS coordinates
            # Make overlay slightly more visible during drawing
            # self.root.attributes('-alpha', 0.3) # Replaced by _set_alpha
            self.temp_rect = self.canvas.create_rectangle(
                self.drawing_start_canvas_x, self.drawing_start_canvas_y,
                self.drawing_start_canvas_x, self.drawing_start_canvas_y,
                outline="green", width=5,
                fill='lightgreen'
            )
            self.status_var.set("Drawing started...")

    def on_mouse_drag(self, event):
        """
        Update the size of the click area while user is dragging.
        Updates the temporary rectangle to show the current area being drawn.
        """
        if self.is_drawing and self.temp_rect:
            # Drag should update based on CANVAS coordinates for the visual rectangle
            # print(f"Dragging - Canvas Coords: ({event.x}, {event.y})") # Optional debug
            self.canvas.coords(self.temp_rect, 
                             self.drawing_start_canvas_x, self.drawing_start_canvas_y, 
                             event.x, event.y)
            self.status_var.set("Drawing in progress...")

    def on_mouse_up(self, event):
        """
        Finalize the drawing of a click area.
        Creates a permanent click area if the drawn rectangle is large enough.
        """
        # Only finish drawing if we were actually drawing
        # (Shift might have been released, cancelling the draw)
        if self.is_drawing and self.temp_rect:
            self.is_drawing = False # Set drawing flag false *before* potential style changes
            
            # --- Make window click-through again --- (REMOVED - handled by Shift key listener)
            # self._set_clickthrough(True) 
            # self._set_alpha(25) # ~10% alpha
            # self.root.update_idletasks() # Apply changes
            # ----------------------------------------
            
            # Capture absolute screen coordinates at end
            end_screen_x, end_screen_y = pyautogui.position()
            print(f"Mouse up - Screen Coords: ({end_screen_x}, {end_screen_y})") # Debug

            # Get CANVAS rectangle coordinates for drawing the visual rectangle
            canvas_x1 = min(self.drawing_start_canvas_x, event.x)
            canvas_y1 = min(self.drawing_start_canvas_y, event.y)
            canvas_x2 = max(self.drawing_start_canvas_x, event.x)
            canvas_y2 = max(self.drawing_start_canvas_y, event.y)
            print(f"Mouse up - Canvas Rect Coords: ({canvas_x1}, {canvas_y1}) to ({canvas_x2}, {canvas_y2})") # Debug

            # Check if the drawn area is large enough (using canvas coords for visual size check)
            if abs(canvas_x1 - canvas_x2) > 5 and abs(canvas_y1 - canvas_y2) > 5:
                # --- Use direct screen coordinates for clicking --- 
                screen_x1 = min(self.drawing_start_screen_x, end_screen_x)
                screen_y1 = min(self.drawing_start_screen_y, end_screen_y)
                screen_x2 = max(self.drawing_start_screen_x, end_screen_x)
                screen_y2 = max(self.drawing_start_screen_y, end_screen_y)
                print(f"Area #{len(self.click_areas) + 1}: Storing Screen Coords: ({screen_x1}, {screen_y1}) to ({screen_x2}, {screen_y2})") # Debug
                
                # --- OLD Conversion - Commented out ---
                # monitor_offset_x = self.selected_monitor.x
                # monitor_offset_y = self.selected_monitor.y
                # Apply scaling factor to canvas coordinates before adding offset
                # scaled_canvas_x1 = canvas_x1 * SCALING_FACTOR
                # scaled_canvas_y1 = canvas_y1 * SCALING_FACTOR
                # scaled_canvas_x2 = canvas_x2 * SCALING_FACTOR
                # scaled_canvas_y2 = canvas_y2 * SCALING_FACTOR
                # Ensure screen coordinates are integers
                # screen_x1 = int(scaled_canvas_x1 + monitor_offset_x)
                # screen_y1 = int(scaled_canvas_y1 + monitor_offset_y)
                # screen_x2 = int(scaled_canvas_x2 + monitor_offset_x)
                # screen_y2 = int(scaled_canvas_y2 + monitor_offset_y)
                # --- End OLD Conversion --- 
                
                # Create permanent rectangle on canvas (using UNscaled canvas coordinates)
                area_rect = self.canvas.create_rectangle(
                    canvas_x1, canvas_y1, canvas_x2, canvas_y2,
                    outline="green", width=5,
                    fill='lightgreen'
                )
                
                # Add numbered label to the click area (using canvas coordinates)
                area_num = len(self.click_areas) + 1
                center_x = (canvas_x1 + canvas_x2) / 2
                center_y = (canvas_y1 + canvas_y2) / 2
                area_label = self.canvas.create_text(
                    center_x, center_y, text=str(area_num),
                    font=("Arial", 12, "bold"), fill="white"
                )
                
                # Store the click area information (using direct screen coords)
                default_interval = self.interval_var.get()
                self.click_areas.append({
                    "rect": area_rect,
                    "label": area_label,
                    "screen_coords": (screen_x1, screen_y1, screen_x2, screen_y2), # Store direct absolute screen coords
                    "canvas_coords": (canvas_x1, canvas_y1, canvas_x2, canvas_y2), # Store canvas coords for highlighting
                    "number": area_num,
                    "interval": default_interval
                })
                
                self.status_var.set(f"Added click area #{area_num}")
            else:
                self.status_var.set("Area too small, try again.")
            
            # Clean up temporary drawing rectangle
            self.canvas.delete(self.temp_rect)
            self.temp_rect = None
            
            # Ensure control window stays on top
            self.control_window.lift()

    def start_clicking(self):
        """
        Start the automated clicking sequence.
        Creates a new thread to handle clicking without freezing the UI.
        """
        if not self.click_areas:
            self.status_var.set("Draw at least one click area first.")
            return
            
        if self.is_playing:
            return
            
        # Update UI state
        self.is_playing = True
        self.play_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("Clicking started...")
        
        # Alpha/Clickthrough is handled by Shift listener, ensure low alpha if not drawing
        if not self.shift_down:
             self._set_alpha(1) # Make nearly invisible during clicking
             self._set_clickthrough(True) # Ensure clickthrough during playback
        
        # Start clicking thread
        self.click_thread = threading.Thread(target=self.click_sequence, daemon=True)
        self.click_thread.start()
        self.control_window.lift()

    def click_sequence(self):
        """
        Execute the automated clicking sequence.
        Clicks in each defined area in order, with random positions within each area.
        Uses the specific interval defined for each area.
        """
        while self.is_playing:
            # Process each click area in numerical order
            for area in sorted(self.click_areas, key=lambda x: x["number"]):
                if not self.is_playing:
                    break
                    
                # Use absolute screen coordinates for clicking
                x1, y1, x2, y2 = area["screen_coords"]
                
                # Ensure coordinates are correctly ordered for random.randint
                min_x = min(x1, x2)
                max_x = max(x1, x2)
                min_y = min(y1, y2)
                max_y = max(y1, y2)
                
                # --- Debugging Start --- 
                print(f"Area #{area['number']} Click Gen: Using bounds x=({min_x}, {max_x}), y=({min_y}, {max_y})")
                # --- Debugging End ---
                
                # Ensure bounds are valid (min <= max) before generating random int
                if min_x > max_x or min_y > max_y:
                    print(f"Warning: Invalid bounds for Area #{area['number']}. Skipping click.")
                    continue # Skip this iteration if bounds are invalid
                    
                click_x = random.randint(min_x, max_x)
                click_y = random.randint(min_y, max_y)
                
                # Highlight current click area on the canvas (using canvas coords)
                self.root.after(0, lambda a=area: self.canvas.itemconfig(a["rect"], outline="red", fill='lightcoral'))
                
                # Perform click using absolute coordinates
                pyautogui.moveTo(click_x, click_y, duration=0.1)
                pyautogui.click()
                
                # Update status and wait for the area-specific interval
                area_interval_ms = area["interval"]
                self.update_status(f"Clicked area #{area['number']} at ({click_x}, {click_y}) - waiting {area_interval_ms}ms")
                time.sleep(area_interval_ms / 1000)
                
                # Restore area appearance on the canvas (using canvas coords)
                self.root.after(0, lambda a=area: self.canvas.itemconfig(a["rect"], outline="green", fill='lightgreen'))

    def update_status(self, message):
        """Update the status message in the UI thread-safely."""
        self.root.after(0, lambda: self.status_var.set(message))

    def stop_clicking(self):
        """Stop the automated clicking sequence and restore UI state."""
        self.is_playing = False
        self.play_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        # Restore alpha based on shift state
        if not self.shift_down:
             self._set_alpha(25) # Restore default alpha
             self._set_clickthrough(True) # Ensure clickthrough is on after stopping
        self.status_var.set("Clicking stopped.")
        self.control_window.lift()

    def reset(self):
        """Clear all click areas and reset the application state."""
        if self.is_playing:
            self.stop_clicking()
            
        self.canvas.delete("all")
        self.click_areas = []
        self.set_overlay_geometry(self.selected_monitor) # Re-apply geometry in case window was moved/resized somehow
        self.status_var.set(f"Reset complete on {self.monitor_var.get()}. Hold Shift + Left Click to draw.")
        self.control_window.lift()

    def open_interval_settings(self):
        """Open the window to customize intervals for each click area."""
        if not self.click_areas:
            self.status_var.set("No areas defined to customize intervals.")
            return
        
        settings_window = tk.Toplevel(self.control_window)
        settings_window.title("Customize Intervals")
        settings_window.attributes('-topmost', True)
        settings_window.resizable(False, False)
        settings_window.transient(self.control_window) # Keep it linked to control window
        settings_window.grab_set() # Make it modal

        # Store temporary interval variables for the UI
        temp_interval_vars = {}

        main_frame = ttk.Frame(settings_window, padding="10 10 10 10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(main_frame, text="Set post-click interval (ms) for each area:").pack(pady=(0, 10))

        # Create entry for each click area
        for area in sorted(self.click_areas, key=lambda x: x["number"]):
            area_frame = ttk.Frame(main_frame)
            area_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(area_frame, text=f"Area #{area['number']}:", width=10).pack(side=tk.LEFT)
            
            interval_var = tk.IntVar(value=area['interval'])
            temp_interval_vars[area['number']] = interval_var
            
            ttk.Spinbox(area_frame, from_=100, to=10000, increment=100, 
                       textvariable=interval_var, width=7).pack(side=tk.LEFT, padx=5)

        # --- Save and Cancel Buttons --- 
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        def save_intervals():
            for area_num, interval_var in temp_interval_vars.items():
                # Find the corresponding area in self.click_areas and update it
                for area in self.click_areas:
                    if area["number"] == area_num:
                        area["interval"] = interval_var.get()
                        break
            self.status_var.set("Intervals updated.")
            settings_window.destroy()
            self.control_window.lift()

        def cancel():
            settings_window.destroy()
            self.control_window.lift()
            self.status_var.set("Interval customization cancelled.")

        ttk.Button(button_frame, text="Save", command=save_intervals).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=5)
        
        # Handle closing window via 'X' button like cancel
        settings_window.protocol("WM_DELETE_WINDOW", cancel)

        # Center the settings window relative to the control window
        self.control_window.update_idletasks() # Ensure control window geometry is updated
        control_x = self.control_window.winfo_x()
        control_y = self.control_window.winfo_y()
        control_w = self.control_window.winfo_width()
        control_h = self.control_window.winfo_height()

        settings_window.update_idletasks() # Ensure settings window geometry is updated
        settings_w = settings_window.winfo_width()
        settings_h = settings_window.winfo_height()

        # Calculate position to center settings window next to control window (approx)
        pos_x = control_x + control_w + 10 # Position to the right
        pos_y = control_y 
        settings_window.geometry(f'{settings_w}x{settings_h}+{pos_x}+{pos_y}')

    def quit(self):
        """Clean up and close the application."""
        print("Quitting application...")
        # Stop keyboard listener
        if hasattr(self, 'listener_thread_stop'):
             self.listener_thread_stop.set() # Signal listener thread to stop
        # keyboard.unhook_all() # unhook_all is called within the listener thread now
        
        self.stop_clicking()
        self.root.quit()
        if hasattr(self, 'control_window') and self.control_window.winfo_exists():
             self.control_window.destroy()
        print("Application quit.")

    # --- Keyboard Listener Methods ---
    def _listen_for_shift(self):
        """Runs in a separate thread to listen for Shift key events."""
        try:
            # Hook both left and right shift keys
            keyboard.hook(self._on_shift_event, suppress=False)
            # Keep the thread alive until told to stop
            self.listener_thread_stop.wait()
            print("Keyboard listener thread stopping.")
        except Exception as e:
            print(f"Error in keyboard listener thread: {e}")
            # Attempt cleanup even if there was an error
            try:
                keyboard.unhook_all()
            except Exception:
                pass # Ignore errors during cleanup
        finally:
             # Ensure unhook_all is called on exit
            try:
                keyboard.unhook_all()
            except Exception:
                pass # Ignore errors during cleanup

    def _on_shift_event(self, event):
        """Handles Shift key press and release events."""
        is_shift = event.name == 'shift' or event.name == 'left shift' or event.name == 'right shift'
        if not is_shift:
             return # Ignore non-shift keys

        if event.event_type == keyboard.KEY_DOWN and not self.shift_down:
            # print("Shift DOWN") # Debug
            self.shift_down = True
            # Schedule UI updates on the main thread
            self.root.after(0, self._set_clickthrough, False)
            self.root.after(0, self._set_alpha, 75)

        elif event.event_type == keyboard.KEY_UP and self.shift_down:
            # print("Shift UP") # Debug
            self.shift_down = False
            # Schedule UI updates on the main thread
            self.root.after(0, self._set_clickthrough, True)
            self.root.after(0, self._set_alpha, 25)
            # If shift is released while drawing, cancel the draw
            if self.is_drawing:
                self.root.after(0, self._cancel_drawing)

    def _cancel_drawing(self):
        """Cancels an ongoing drawing operation."""
        if self.is_drawing:
            print("Cancelling drawing due to Shift release.") # Debug
            self.is_drawing = False
            if hasattr(self, 'temp_rect') and self.temp_rect:
                self.canvas.delete(self.temp_rect)
                self.temp_rect = None
            self.status_var.set("Drawing cancelled (Shift released).")
    # --- End Keyboard Listener Methods ---

# Application entry point
if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenClicker(root)
    root.mainloop()