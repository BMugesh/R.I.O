"""R.I.O. Optional Windows System Tray Status Icon.

Provides a lightweight notification area presence with live status indicator
and quick actions (Open Web UI, View Status, Quit).
"""

import logging
import threading
from typing import Callable, Optional
import webbrowser

logger = logging.getLogger("rio.runtime.tray")


class SystemTrayManager:
    """Manages optional system tray icon and menu."""

    def __init__(
        self,
        on_quit: Optional[Callable[[], None]] = None,
        on_open_ui: Optional[Callable[[], None]] = None,
        get_status_fn: Optional[Callable[[], str]] = None,
    ):
        self.on_quit = on_quit
        self.on_open_ui = on_open_ui or (lambda: webbrowser.open("http://localhost:3000"))
        self.get_status_fn = get_status_fn or (lambda: "ONLINE")
        self._icon = None
        self._thread: Optional[threading.Thread] = None

    def _create_image(self):
        """Generate a clean cyan R.I.O. circle icon."""
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGBA", (64, 64), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            # Outer cyan glow ring
            draw.ellipse((4, 4, 60, 60), fill=(6, 182, 212, 255), outline=(14, 165, 233, 255), width=2)
            # Inner circle
            draw.ellipse((16, 16, 48, 48), fill=(15, 23, 42, 255))
            # Center core dot
            draw.ellipse((26, 26, 38, 38), fill=(56, 189, 248, 255))
            return img
        except Exception:
            return None

    def start(self) -> bool:
        """Start the system tray icon in a dedicated background thread."""
        try:
            import pystray
            image = self._create_image()
            if not image:
                return False

            def _quit_action(icon, item):
                icon.stop()
                if self.on_quit:
                    self.on_quit()

            def _open_action(icon, item):
                self.on_open_ui()

            status_label = f"R.I.O. ● {self.get_status_fn()}"
            menu = pystray.Menu(
                pystray.MenuItem(status_label, lambda icon, item: None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Open R.I.O. Web UI", _open_action, default=True),
                pystray.MenuItem("Quit Runtime", _quit_action),
            )

            self._icon = pystray.Icon("RIO", image, "R.I.O. Background Runtime", menu)
            self._thread = threading.Thread(target=self._icon.run, daemon=True)
            self._thread.start()
            logger.info("System tray icon started.")
            return True
        except ImportError:
            logger.debug("pystray not installed; skipping system tray icon.")
            return False
        except Exception as e:
            logger.debug(f"Could not start system tray icon: {e}")
            return False

    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
