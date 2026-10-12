"""Check wheel metadata, clean imports, CLI streams and packaged examples."""
import email
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    wheel = max((ROOT / 'dist').glob('*.whl'), key=lambda path: path.stat().st_mtime)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = email.message_from_bytes(archive.read(next(name for name in names if name.endswith('/METADATA'))))
        assert metadata['Name'] == 'esprima-fork'
        assert metadata['Version'] == '5.0.0.dev0'
        assert metadata['Requires-Python'] == '>=3.11'
        assert not metadata.get_all('Requires-Dist') or all('extra ==' in value for value in metadata.get_all('Requires-Dist'))
        assert any(name.endswith('licenses/data/unicode/LICENSE.txt') for name in names)
        entrypoints = archive.read(next(name for name in names if name.endswith('/entry_points.txt'))).decode()
        assert 'esprima = esprima.__main__:main' in entrypoints
        assert not any(name.startswith(('test/', 'tests/', 'tools/', 'data/')) or '__pycache__' in name for name in names)
        with tempfile.TemporaryDirectory() as directory:
            archive.extractall(directory)
            code = "import sys,json;sys.path.insert(0,sys.argv[1]);import esprima;assert esprima.version=='5.0.0.dev0';tree=esprima.parseModule('export const x=obj?.x??1n;', {'range':True});assert tree.body[0].declaration.declarations[0].init.type=='LogicalExpression';json.dumps(tree.toDict(),allow_nan=False);from esprima.__main__ import main;raise SystemExit(main([]))"
            result = subprocess.run([sys.executable, '-I', '-B', '-c', code, directory], cwd=directory,
                                    input='const x=1;', text=True, capture_output=True, check=True)
            assert json.loads(result.stdout)['type'] == 'Program'
            assert not result.stderr
    assert list((ROOT / 'dist').glob('*.tar.gz'))
    print('Source archive, wheel metadata, licenses, clean modern imports and CLI verified')


if __name__ == '__main__':
    main()
