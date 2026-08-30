from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / 'app/static/project-builder.css').read_text(encoding='utf-8')


def validate():
    assert 'V14 · reconhece largura, altura e zoom reduzido' in CSS
    assert '(max-height:900px)' in CSS
    assert '(max-resolution:.9dppx)' in CSS
    assert '#project-builder-form.project-builder' in CSS
    assert 'grid-template-columns:minmax(0,1fr) !important' in CSS
    assert 'grid-template-columns:repeat(3,minmax(0,1fr)) !important' in CSS
    assert '.project-builder-aside' in CSS
    assert 'position:static !important' in CSS
    assert '.project-builder-sticky-action' in CSS
    assert 'width:100% !important' in CSS


if __name__ == '__main__':
    validate()
    print('PROJECT BUILDER V14: OK')
    print('MONITOR BAIXO: OK')
    print('ZOOM REDUZIDO: OK')
    print('FULL WIDTH: OK')
    print('RESUMO ABAIXO: OK')
