from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / 'app/static/users-layout-v25.css'
VIEWPORT = ROOT / 'app/static/viewport-adaptive-v15.js'


def main():
    css = CSS.read_text(encoding='utf-8')
    viewport = VIEWPORT.read_text(encoding='utf-8')

    required_css = [
        'DevPilot Users Layout V25',
        '#users-view .users-summary',
        'main:has(#users-view.active) #overview-view',
        'body:has(#users-view.active) #mission-control-panel',
        '@media (max-width: 900px)',
        '#users-view .users-table thead',
        '#users-view .users-table tr',
        '#users-view #new-user',
    ]
    for token in required_css:
        assert token in css, f'missing users V25 css contract: {token}'

    assert 'users-layout-v25.css' in viewport
    assert 'data-users-layout-v25' in viewport

    print('users layout V25 contract: OK')


if __name__ == '__main__':
    main()
