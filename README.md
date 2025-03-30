# ClickyClicker - Screen Auto-Clicker

## Overview

ClickyClicker is a simple automation tool that allows you to define specific rectangular areas on your screen and have the computer automatically click within those areas sequentially.

It features:
*   A transparent overlay for drawing click zones.
*   A control panel for managing the clicking process.
*   Support for multiple monitors.
*   Customizable click intervals for each defined area.

## How to Use

1.  **Run the Application:** Launch the `ClickyClicker` executable (or run the Python script).

2.  **Interface:**
    *   **Overlay:** A mostly transparent window will cover your selected monitor.
    *   **Control Panel:** A small window titled "ClickyClicker" will appear, usually in the top-left corner. This panel contains all the controls.

3.  **Select Monitor (if needed):**
    *   Use the "Monitor:" dropdown in the Control Panel to select which display the overlay should cover and where clicks should occur. Drawing and clicking are specific to the selected monitor.

4.  **Drawing Click Areas:**
    *   **Hold down the Shift key** on your keyboard. The overlay will become slightly more visible.
    *   While holding Shift, **Left-click and drag** on the overlay window to draw a rectangle. This defines a click area.
    *   **Release the mouse button** to finish drawing the area.
    *   **Release the Shift key**. The overlay will become nearly transparent again.
    *   Each area drawn will be marked with a number.
    *   *Note:* If you release the Shift key while dragging, the drawing will be cancelled.

5.  **Customize Intervals (Optional):**
    *   Click the "⚙ Customize Intervals" button in the Control Panel.
    *   A new window will appear allowing you to set a specific wait time (in milliseconds) *after* the click in each numbered area.
    *   Click "Save" to apply changes or "Cancel".

6.  **Start Clicking:**
    *   Click the "▶ Play" button in the Control Panel.
    *   The application will start clicking randomly within each defined area, in numerical order, respecting the interval set for each area.
    *   The overlay will become almost invisible during clicking.

7.  **Stop Clicking:**
    *   Click the "⏹ Stop" button in the Control Panel.
    *   The clicking sequence will stop.

8.  **Reset:**
    *   Click the "Reset" button to clear all drawn click areas from the current monitor.

9.  **Quit:**
    *   Press the `Esc` key while the overlay or control panel is focused.
    *   Alternatively, close the "ClickyClicker" Control Panel window.

## Notes

*   The application uses global keyboard hooks to detect the Shift key for drawing. Depending on how it's packaged or run, it might require administrator privileges to function correctly.
*   Click coordinates are captured relative to the screen, taking display scaling into account. 