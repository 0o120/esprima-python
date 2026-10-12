"""Nullable ESTree fields shared by serialization and legacy-fixture migration."""

NULLABLE_FIELDS = {
    'Literal': ('value',),
    'VariableDeclarator': ('init',),
    'FunctionDeclaration': ('id',),
    'FunctionExpression': ('id',),
    'ClassDeclaration': ('id', 'superClass'),
    'ClassExpression': ('id', 'superClass'),
    'PropertyDefinition': ('value',),
    'IfStatement': ('alternate',),
    'ForStatement': ('init', 'test', 'update'),
    'ReturnStatement': ('argument',),
    'YieldExpression': ('argument',),
    'BreakStatement': ('label',),
    'ContinueStatement': ('label',),
    'CatchClause': ('param',),
    'SwitchCase': ('test',),
    'TryStatement': ('handler', 'finalizer'),
    'ExportNamedDeclaration': ('declaration', 'source'),
    'ExportAllDeclaration': ('exported',),
    'ImportExpression': ('options',),
    'JSXElement': ('closingElement',),
    'JSXAttribute': ('value',),
}


def migrate_legacy_fixture(value):
    """Add documented canonical defaults to old ESTree snapshots.

    This is a schema migration, not an acceptance normalizer: semantic fields
    remain present and assertions still compare their exact values.
    """
    if isinstance(value, list):
        return [migrate_legacy_fixture(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: migrate_legacy_fixture(item) for key, item in value.items()}
    kind = result.get('type')
    if kind == 'Import':
        result['type'] = kind = 'ImportExpression'
    for field in NULLABLE_FIELDS.get(kind, ()):
        result.setdefault(field, None)
    if kind in ('MemberExpression', 'CallExpression'):
        result.setdefault('optional', False)
    if kind == 'ForOfStatement':
        result.setdefault('await', False)
    if kind in ('ImportDeclaration', 'ExportNamedDeclaration', 'ExportAllDeclaration'):
        result.setdefault('attributes', [])
    if kind == 'Literal' and 'regex' in result:
        result['value'] = None
    return result
