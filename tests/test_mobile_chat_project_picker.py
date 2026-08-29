from pathlib import Path


PICKER = Path('app/static/mobile-chat-project-picker.js').read_text(encoding='utf-8')
LOADER = Path('app/static/feature-loader.js').read_text(encoding='utf-8')


def test_mobile_chat_project_picker_is_loaded_only_with_voice_feature():
    assert "'mobile-chat-project-picker.js'" in LOADER
    voice_bundle = LOADER.split("voice: [", 1)[1].split("],", 1)[0]
    assert "mobile-chat-project-picker.js" in voice_bundle


def test_mobile_chat_uses_custom_picker_instead_of_android_native_select():
    assert 'mobile-chat-project-picker' in PICKER
    assert 'mobile-chat-project-trigger' in PICKER
    assert "aria-haspopup', 'listbox" in PICKER
    assert 'pointer-events: none !important' in PICKER
    assert '#voice-modal .voice-project-control > #voice-project' in PICKER
    assert "select.dispatchEvent(new Event('change', {bubbles: true}))" in PICKER


def test_picker_has_no_global_dom_observer_and_preserves_touch_accessibility():
    assert 'MutationObserver' not in PICKER
    assert 'min-height: 48px' in PICKER
    assert 'min-height: 46px' in PICKER
    assert "role', 'listbox" in PICKER
    assert "role', 'option" in PICKER
    assert 'aria-selected' in PICKER
    assert "event.key !== 'Escape'" in PICKER
