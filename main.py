"""Entry point: runs the live gesture-tracking camera window.

Run `python configure.py` first (or anytime) to change what each gesture
does — main.py picks up config.json on launch, and picks up live edits if
you press "C" while it's running.
"""

from gesture_control.app import GestureControlApp


def main() -> None:
    GestureControlApp().run()


if __name__ == "__main__":
    main()
