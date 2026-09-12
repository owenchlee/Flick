from gesture_control.actions import (
    ACTIONS,
    CUSTOM_HOTKEY,
    LIKE,
    NONE,
    OPEN_COMMENTS,
    SCROLL,
    SCROLL_PREV,
    SPEED_2X,
    ActionExecutor,
    actions_by_category,
)


def make_fake_backend():
    calls = []
    backend = {
        "click": lambda: calls.append(("click",)),
        "mouse_down": lambda: calls.append(("mouse_down",)),
        "mouse_up": lambda: calls.append(("mouse_up",)),
        "scroll": lambda amount: calls.append(("scroll", amount)),
        "hotkey": lambda combo: calls.append(("hotkey", combo)),
    }
    return backend, calls


def test_every_action_id_is_unique_and_matches_its_key():
    for action_id, spec in ACTIONS.items():
        assert action_id == spec.id


def test_actions_by_category_covers_every_registered_action():
    grouped = actions_by_category()
    total = sum(len(specs) for specs in grouped.values())
    assert total == len(ACTIONS)


def test_none_action_does_nothing():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)
    assert executor.fire(NONE) is None
    assert calls == []


def test_like_fires_backend_click():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)
    status = executor.fire(LIKE)
    assert calls == [("click",)]
    assert status == "LIKED"


def test_open_comments_fires_backend_click():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)
    status = executor.fire(OPEN_COMMENTS)
    assert calls == [("click",)]
    assert status == "COMMENTS"


def test_custom_hotkey_requires_a_hotkey_string():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)
    assert executor.fire(CUSTOM_HOTKEY, custom_hotkey="") is None
    assert calls == []

    status = executor.fire(CUSTOM_HOTKEY, custom_hotkey="ctrl+shift+s")
    assert calls == [("hotkey", "ctrl+shift+s")]
    assert status == "CTRL+SHIFT+S"


def test_speed_2x_hold_is_idempotent_while_held():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)

    assert executor.begin_hold(SPEED_2X) == "2X SPEED"
    assert executor.begin_hold(SPEED_2X) is None  # already held, no duplicate mouse_down
    assert calls == [("mouse_down",)]

    assert executor.end_hold(SPEED_2X) == "NORMAL SPEED"
    assert executor.end_hold(SPEED_2X) is None  # already released
    assert calls == [("mouse_down",), ("mouse_up",)]


def test_release_all_holds_ends_an_active_speed_2x():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)
    executor.begin_hold(SPEED_2X)
    executor.release_all_holds()
    assert calls == [("mouse_down",), ("mouse_up",)]


def test_scroll_forwards_amount_to_backend():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)
    executor.scroll(SCROLL, 42)
    executor.scroll(SCROLL, 0)  # zero delta shouldn't call the backend
    assert calls == [("scroll", 42)]


def test_scroll_prev_fires_backend_scroll_with_given_amount():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)
    status = executor.fire(SCROLL_PREV, scroll_amount=2500)
    assert calls == [("scroll", 2500)]
    assert status == "PREV REEL"


def test_scroll_prev_requires_a_nonzero_amount():
    backend, calls = make_fake_backend()
    executor = ActionExecutor(backend)
    assert executor.fire(SCROLL_PREV, scroll_amount=0) is None
    assert calls == []
