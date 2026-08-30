from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JS = (ROOT / 'app/static/super-admin-system-map.js').read_text(encoding='utf-8')
CSS = (ROOT / 'app/static/super-admin-mobile-v12.css').read_text(encoding='utf-8')


def validate():
    assert 'super-admin-mobile-v12.css' in JS
    assert 'data-super-admin-mobile-v12' in JS

    assert '#super-admin-system-view .system-map-metrics' in CSS
    assert 'grid-template-columns: repeat(2, minmax(0, 1fr))' in CSS
    assert 'grid-auto-flow: column' in CSS
    assert '.system-map-inspector' in CSS
    assert 'order: -1' in CSS
    assert 'max-height: 310px' in CSS
    assert '--dp-super-admin-nav-space' in CSS
    assert 'body.mobile-route .voice-dock' in CSS


if __name__ == '__main__':
    validate()
    print('SUPER ADMIN MOBILE V12: OK')
    print('MÉTRICAS 2 COLUNAS: OK')
    print('FLUXO HORIZONTAL: OK')
    print('INSPECTOR PRIMEIRO: OK')
    print('SAFE AREA: OK')
