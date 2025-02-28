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

class ScreenClicker:
    """
    Main application class that handles the screen clicking functionality.
    Creates a transparent fullscreen overlay and a control panel for managing click areas.
    """
    
    def __init__(self, root):
        """Initialize the application with main window and control panel."""
        self.root = root
        self.root.title("ScreenClicker")
        self.root.attributes('-topmost', True)  # Keep window always on top
        self.root.attributes('-fullscreen', True)  # Make window fullscreen
        self.root.attributes('-alpha', 0.1)  # Set window transparency
        
        # Initialize state tracking variables
        self.click_areas = []  # List to store all defined click areas
        self.is_drawing = False  # Flag to track if user is currently drawing
        self.drawing_start_x = 0  # Starting X coordinate of drawing
        self.drawing_start_y = 0  # Starting Y coordinate of drawing
        self.is_playing = False  # Flag to track if clicking sequence is active
        self.click_thread = None  # Thread for click sequence
        
        # Configure main window appearance
        self.root.configure(bg='gray')
        
        # Create transparent canvas for drawing click areas
        self.canvas = tk.Canvas(self.root, bg='gray', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Create separate control window with buttons and settings
        self.setup_control_window()
        
        # Setup UI elements in control window
        self.setup_ui()
        
        # Bind mouse and keyboard events
        self.setup_event_bindings()
        
        # Ensure control window stays on top after everything is initialized
        self.root.after(100, self.ensure_control_window_on_top)

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
        # Bind Shift+Click events for drawing click areas
        self.canvas.bind("<Shift-Button-1>", self.on_mouse_down)
        self.canvas.bind("<Shift-B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.on_mouse_up)
        
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
        
        # Add status display
        self.status_var = tk.StringVar(value="Hold Shift + Left Click to draw.")
        ttk.Label(self.control_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=5, pady=5)

    def on_mouse_down(self, event):
        """
        Handle the start of drawing a new click area.
        Triggered when user holds Shift and clicks left mouse button.
        """
        if not self.is_drawing and not self.is_playing:
            print(f"Mouse down at ({event.x}, {event.y})")  # Debug info
            self.is_drawing = True
            self.drawing_start_x = event.x
            self.drawing_start_y = event.y
            # Create temporary rectangle to show drawing progress
            self.temp_rect = self.canvas.create_rectangle(
                self.drawing_start_x, self.drawing_start_y,
                self.drawing_start_x, self.drawing_start_y,
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
            print(f"Dragging to ({event.x}, {event.y})")  # Debug info
            self.canvas.coords(self.temp_rect, 
                             self.drawing_start_x, self.drawing_start_y, 
                             event.x, event.y)
            self.status_var.set("Drawing in progress...")

    def on_mouse_up(self, event):
        """
        Finalize the drawing of a click area.
        Creates a permanent click area if the drawn rectangle is large enough.
        """
        if self.is_drawing and self.temp_rect:
            print(f"Mouse up at ({event.x}, {event.y})")  # Debug info
            self.is_drawing = False
            
            # Check if the drawn area is large enough
            if abs(self.drawing_start_x - event.x) > 5 and abs(self.drawing_start_y - event.y) > 5:
                # Store coordinates
                screen_x1 = self.drawing_start_x
                screen_y1 = self.drawing_start_y
                screen_x2 = event.x
                screen_y2 = event.y
                
                # Create permanent rectangle
                area_rect = self.canvas.create_rectangle(
                    self.drawing_start_x, self.drawing_start_y, event.x, event.y,
                    outline="green", width=5,
                    fill='lightgreen'
                )
                
                # Add numbered label to the click area
                area_num = len(self.click_areas) + 1
                center_x = (self.drawing_start_x + event.x) / 2
                center_y = (self.drawing_start_y + event.y) / 2
                area_label = self.canvas.create_text(
                    center_x, center_y, text=str(area_num),
                    font=("Arial", 12, "bold"), fill="white"
                )
                
                # Store the click area information
                self.click_areas.append({
                    "rect": area_rect,
                    "label": area_label,
                    "screen_coords": (screen_x1, screen_y1, screen_x2, screen_y2),
                    "number": area_num
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
        
        # Minimize main window and make it more transparent
        self.root.iconify()
        self.root.attributes('-alpha', 0.05)
        
        # Start clicking thread
        self.click_thread = threading.Thread(target=self.click_sequence, daemon=True)
        self.click_thread.start()
        self.control_window.lift()

    def click_sequence(self):
        """
        Execute the automated clicking sequence.
        Clicks in each defined area in order, with random positions within each area.
        """
        interval_ms = self.interval_var.get()
        
        while self.is_playing:
            # Process each click area in numerical order
            for area in sorted(self.click_areas, key=lambda x: x["number"]):
                if not self.is_playing:
                    break
                    
                # Calculate random click position within the area
                x1, y1, x2, y2 = area["screen_coords"]
                click_x = random.randint(int(x1), int(x2))
                click_y = random.randint(int(y1), int(y2))
                
                # Highlight current click area
                self.canvas.itemconfig(area["rect"], outline="red", fill='lightcoral')
                
                # Perform click
                pyautogui.moveTo(click_x, click_y, duration=0.1)
                pyautogui.click()
                
                # Update status and wait for next interval
                self.update_status(f"Clicked area #{area['number']} at ({click_x}, {click_y})")
                time.sleep(interval_ms / 1000)
                
                # Restore area appearance
                self.canvas.itemconfig(area["rect"], outline="green", fill='lightgreen')

    def update_status(self, message):
        """Update the status message in the UI thread-safely."""
        self.root.after(0, lambda: self.status_var.set(message))

    def stop_clicking(self):
        """Stop the automated clicking sequence and restore UI state."""
        self.is_playing = False
        self.play_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.root.deiconify()
        self.root.attributes('-alpha', 0.1)
        self.status_var.set("Clicking stopped.")
        self.control_window.lift()

    def reset(self):
        """Clear all click areas and reset the application state."""
        if self.is_playing:
            self.stop_clicking()
            
        self.canvas.delete("all")
        self.click_areas = []
        self.root.attributes('-alpha', 0.1)
        self.status_var.set("Hold Shift + Left Click to draw.")
        self.control_window.lift()

    def quit(self):
        """Clean up and close the application."""
        self.stop_clicking()
        self.root.quit()
        self.control_window.destroy()

# Application entry point
if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenClicker(root)
    root.mainloop()