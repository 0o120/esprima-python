"""Check wheel metadata, clean imports, CLI streams and packaged examples."""
import ast
import email
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']
    version_source = ast.parse((ROOT / 'esprima/_version.py').read_text(encoding='utf-8'))
    expected_version = next(ast.literal_eval(statement.value) for statement in version_source.body
                            if isinstance(statement, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == '__version__'
                                    for target in statement.targets))
    expected_tuple = tuple(int(part) for part in expected_version.split('.')[:3])
    readme = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert all(target.startswith(('https://', 'http://', '#'))
               for target in re.findall(r'\]\(([^)]+)\)', readme)), 'README links must work on PyPI'
    wheel = max((ROOT / 'dist').glob('*.whl'), key=lambda path: path.stat().st_mtime)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = email.message_from_bytes(archive.read(next(name for name in names if name.endswith('/METADATA'))))
        assert metadata['Name'] == 'esprima-fork'
        assert metadata['Version'] == expected_version
        assert metadata['Requires-Python'] == project['requires-python']
        assert metadata['License-Expression'] == project['license']
        assert metadata['Description-Content-Type'] == 'text/markdown'
        assert set(metadata.get_all('Classifier', [])) == set(project['classifiers'])
        assert set(metadata.get_all('Project-URL', [])) == {
            f'{name}, {url}' for name, url in project['urls'].items()}
        assert metadata.get_payload().strip() == readme.strip()
        assert not metadata.get_all('Requires-Dist') or all('extra ==' in value for value in metadata.get_all('Requires-Dist'))
        assert any(name.endswith('licenses/data/unicode/LICENSE.txt') for name in names)
        entrypoints = archive.read(next(name for name in names if name.endswith('/entry_points.txt'))).decode()
        assert 'esprima = esprima.__main__:main' in entrypoints
        assert not any(name.startswith(('test/', 'tests/', 'tools/', 'data/')) or '__pycache__' in name for name in names)
        with tempfile.TemporaryDirectory() as directory:
            archive.extractall(directory)
            code = ("import sys,json;sys.path.insert(0,sys.argv[1]);import esprima;"
                    f"assert esprima.version=={expected_version!r};assert esprima.__version__=={expected_tuple!r};"
                    "tree=esprima.parseModule('export const x=obj?.x??1n;', {'range':True});"
                    "assert tree.body[0].declaration.declarations[0].init.type=='LogicalExpression';"
                    "json.dumps(tree.toDict(),allow_nan=False);from esprima.__main__ import main;"
                    "raise SystemExit(main([]))")
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code, directory], cwd=directory,
                                    input='const x=1;', text=True, capture_output=True, check=True)
            assert json.loads(result.stdout)['type'] == 'Program'
            assert not result.stderr
    assert (ROOT / 'dist' / f"esprima_fork-{expected_version}.tar.gz").is_file()
    print('Source archive, wheel metadata, licenses, clean modern imports and CLI verified')


if __name__ == '__main__':
    main()
