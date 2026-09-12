from gesture_control.gestures import analyze

from .hand_fixtures import make_hand


def _assert_only(active: dict, expected: set) -> None:
    for gesture_id, is_active in active.items():
        assert is_active == (gesture_id in expected), (
            f"{gesture_id}: expected {gesture_id in expected}, got {is_active} (active={active})"
        )


def test_neutral_pointing_hand_is_the_scroll_pose():
    # Index extended, everything else relaxed — the resting "move the
    # cursor / swipe to scroll" pose.
    landmarks = make_hand(index_ext=True, thumb="neutral")
    state = analyze(landmarks)
    _assert_only(state.active, {"point"})


def test_open_palm_is_also_the_scroll_pose():
    # Any hand shape that isn't one of the three named poses should still
    # register as "point" — a fully open hand included.
    landmarks = make_hand(index_ext=True, middle_ext=True, ring_ext=True, pinky_ext=True, thumb="neutral")
    state = analyze(landmarks)
    _assert_only(state.active, {"point"})


def test_fist():
    landmarks = make_hand(thumb="near_palm")
    state = analyze(landmarks)
    _assert_only(state.active, {"fist"})


def test_thumbs_up():
    landmarks = make_hand(thumb="up")
    state = analyze(landmarks)
    _assert_only(state.active, {"thumbs_up"})


def test_peace_sign():
    landmarks = make_hand(index_ext=True, middle_ext=True, thumb="neutral")
    state = analyze(landmarks)
    _assert_only(state.active, {"peace"})


def test_rock_sign():
    # Index + pinky extended, middle/ring curled — the dedicated
    # "previous reel" pose, distinct from point (index only) so it can
    # never fire the flick-scroll gesture alongside it.
    landmarks = make_hand(index_ext=True, pinky_ext=True, thumb="neutral")
    state = analyze(landmarks)
    _assert_only(state.active, {"rock"})


def test_fist_suppresses_thumbs_up():
    # A tucked thumb inside a fist can geometrically satisfy the thumbs-up
    # check too; fist must win so a closed hand never also fires a like.
    landmarks = make_hand(thumb="near_palm")
    state = analyze(landmarks)
    assert state.active["fist"] is True
    assert state.active["thumbs_up"] is False


def test_cursor_tracks_index_fingertip():
    landmarks = make_hand(index_ext=True, thumb="neutral")
    state = analyze(landmarks)
    assert state.cursor == (landmarks[8][0], landmarks[8][1])


def test_rejects_wrong_landmark_count():
    import pytest

    with pytest.raises(ValueError):
        analyze([(0.0, 0.0, 0.0)] * 20)
