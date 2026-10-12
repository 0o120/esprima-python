"""Release-candidate integration across parser, semantic walker and generator.

Optional dependencies are installed together by the coordinated release check.
Reference parser dependencies are development-only and never execute fixtures.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

import esprima

try:
    import acornwalk
    import escodegen
    import esutils
except ImportError:
    if os.environ.get("TOOLCHAIN_EXPECT_INSTALLED"):
        raise
    acornwalk = escodegen = esutils = None

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path(os.environ.get("TOOLCHAIN_REFERENCE_NODE_MODULES", str(ROOT / "tools/reference/node_modules")))

CASES = [
    ("script", "const {x=7, [key]: y, ...rest}=value; const [head,,...tail]=list;", False),
    ("script", "async function* collect(xs){for await(const x of xs){yield await x;}}", False),
    ("script", "const n=1_000_000; const big=9007199254740993123456789n; n??=7; n&&=8; n||=9;", False),
    ("script", "const overflow=1e400; const negative=-1e400; const zero=-0;", False),
    ("script", "const text='\U0001f600\uff0c\U000e0001'; const lone='\\uD800';", False),
    ("script", "const result=(obj?.a)?.[key]?.(7) ?? ((fallback&&ready)||other);", False),
    ("script", "class C extends Parent { #x=7; static #y; [key]=7; static {this.x=7;} get #p(){return this.#x;} set #p(v){this.#x=v;} constructor(){super();} has(o){return #x in o;} async *values(xs){for await(const v of xs){yield await v;}} }", False),
    ("script", "try{run();}catch{recover();} const valid=/[a-z]+/d; const set=/[a&&a]/v;", False),
    ("script", "function f(){'use\\x20strict'; with(obj){return /* comment */ value;}}", False),
    ("script", "let obj={__proto__, ['__proto__']:7, __proto__:null}; ({__proto__:a,__proto__:b}=obj);", False),
    ("module", 'import data from "m" with {type:"json"}; export {data as "a b"}; export * as "n s" from "n" with {type:"json"};', False),
    ("module", 'const data=await import(path,{with:{type:"json"}}); export default data;', False),
    ("module", 'import {"a-b" as data} from "m"; export {data}; const meta=import.meta;', False),
    ("script", 'const view=<><UI.Box name="a" {...props}>{value}<Inner /></UI.Box></>;', True),
]


def parse(source, mode="script", jsx=False, **options):
    options.update(range=True, loc=True, jsx=jsx)
    return (esprima.parseModule if mode == "module" else esprima.parseScript)(source, options)


def normalized(value):
    if isinstance(value, list):
        return [normalized(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in {"start", "end", "loc", "range", "raw", "tokens", "comments", "hashbang", "number"} or key.startswith("_"):
                continue
            if key == "value" and "number" in value:
                result[key] = {"ecmascriptNumber": value["number"]}
            elif key == "value" and "regex" in value:
                result[key] = None
            elif key == "directive":
                result[key] = "use strict" if item == "use strict" else "<non-strict-directive>"
            else:
                result[key] = normalized(item)
        return result
    return value


def reference(jobs):
    program = r"""
const fs=require('fs'),path=require('path');
const modules=process.argv[1],acorn=require(path.join(modules,'acorn'));
const JSX=acorn.Parser.extend(require(path.join(modules,'acorn-jsx'))());
const jobs=JSON.parse(fs.readFileSync(0,'utf8'));
const output=jobs.map(j=> (j.jsx?JSX:acorn.Parser).parse(j.source,{
  ecmaVersion:2026,sourceType:j.mode,ranges:true,locations:true
}));
process.stdout.write(JSON.stringify(output, function(key,value){
  if (key==='value'&&this.regex) return null;
  if (typeof value==='number'&&!Number.isFinite(value))
    return {ecmascriptNumber: Number.isNaN(value)?'NaN':(value>0?'Infinity':'-Infinity')};
  return typeof value==='bigint'?null:value;
}));
"""
    process = subprocess.run(["node", "-e", program, str(REFERENCE)], input=json.dumps(jobs),
        capture_output=True, text=True, encoding="utf-8", check=True)
    return [normalized(tree) for tree in json.loads(process.stdout)]


@unittest.skipUnless(acornwalk is not None and escodegen is not None and esutils is not None,
    "coordinated parser/walker/generator/utility installations required")
class ToolchainIntegrationTests(unittest.TestCase):
    def test_candidate_versions_and_optional_installed_origins(self):
        expected = ((esprima, (5, 0, 0)), (acornwalk, "2.0.0"), (escodegen, "2.0.0"), (esutils, "2.0.0"))
        for module, version in expected:
            self.assertEqual(module.__version__, version)
            if os.environ.get("TOOLCHAIN_EXPECT_INSTALLED"):
                self.assertIn("site-packages", str(Path(module.__file__).resolve()), module.__name__)
        self.assertEqual(esutils.code.UNICODE_VERSION, "17.0.0")

    def test_native_mapping_walk_search_generation_and_reparse(self):
        jobs = []
        for mode, source, jsx in CASES:
            with self.subTest(source=source):
                tree = parse(source, mode, jsx)
                mapping = tree.toDict()
                before = copy.deepcopy(mapping)
                native_nodes, mapping_nodes = [], []
                acornwalk.full(tree, lambda node, state, category: native_nodes.append((node, category)))
                acornwalk.full(mapping, lambda node, state, category: mapping_nodes.append((node, category)))
                self.assertEqual([(acornwalk.getField(node, "type"), kind) for node, kind in native_nodes],
                    [(node["type"], kind) for node, kind in mapping_nodes])
                for (native, _), (serialized, _) in zip(native_nodes, mapping_nodes, strict=True):
                    if serialized["type"] in {"FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"}:
                        self.assertEqual(acornwalk.getField(native, "async"), serialized.get("async", False))
                    if serialized["type"] == "ForOfStatement":
                        self.assertEqual(acornwalk.getField(native, "await"), serialized.get("await", False))
                for node, kind in native_nodes:
                    start, end = acornwalk.nodeRange(node)
                    found = acornwalk.findNodeAt(tree, start, end, kind)
                    self.assertIs(found.node, node)
                for compact in (False, True):
                    options = {"format": {"compact": compact}}
                    native_code = escodegen.generate(tree, options)
                    self.assertEqual(native_code, escodegen.generate(mapping, options))
                    self.assertEqual(tree.toDict(), before)
                    self.assertEqual(mapping, before)
                    self.assertEqual(normalized(parse(native_code, mode, jsx).toDict()), normalized(before))
                    jobs.append({"source": native_code, "mode": mode, "jsx": jsx})
        if shutil.which("node") and (REFERENCE / "acorn").exists():
            expected = reference([{"source": source, "mode": mode, "jsx": jsx} for mode, source, jsx in CASES])
            actual = reference(jobs)
            self.assertEqual(actual, [tree for tree in expected for _ in range(2)])

    def test_transform_original_native_and_mapping_nodes(self):
        source = "const original=7; function f(){return original+7;}"
        outputs = []
        for tree in (parse(source), parse(source).toDict()):
            matched = []
            def transform(node, state, category):
                kind = acornwalk.getField(node, "type")
                field, value = ("name", "updated") if kind == "Identifier" and acornwalk.getField(node, "name") == "original" else (
                    ("value", 8) if kind == "Literal" and acornwalk.getField(node, "value") == 7 else (None, None))
                if field is not None:
                    matched.append(node)
                    if isinstance(node, dict):
                        node[field] = value
                        node.pop("raw", None)
                    else:
                        setattr(node, field, value)
                        if kind == "Literal":
                            node.raw = None
            acornwalk.full(tree, transform)
            self.assertEqual(len(matched), 4)
            outputs.append(escodegen.generate(tree))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(normalized(parse(outputs[0]).toDict()), normalized(parse(source.replace("original", "updated").replace("7", "8")).toDict()))

    def test_utf16_positions_delegate_callbacks_and_escaping(self):
        source = "/*\U0001f600*/ const \U00010400='\U0001f600\uff0c';\r\n\U00010400;"
        delegated = []
        tree = esprima.parseScript(source, {"range": True, "loc": True, "tokens": True, "comment": True},
            delegate=lambda node, meta: delegated.append((node, meta.start.offset, meta.end.offset)))
        binding = tree.body[0].declarations[0].id
        self.assertEqual(binding.range, [13, 15])
        self.assertIs(acornwalk.findNodeAt(tree, 13, 15, "VariablePattern").node, binding)
        self.assertTrue(any(node is binding and start == 13 and end == 15 for node, start, end in delegated))
        self.assertEqual(tree.comments[0].range, [0, 6])
        for mapping in (tree, tree.toDict()):
            code = escodegen.generate(mapping, {"format": {"escapeless": True}})
            self.assertEqual(normalized(parse(code).toDict()), normalized(tree.toDict()))

    def test_attached_comments_with_utf16_source_and_blank_lines(self):
        source = "/*\U0001f600*/\n\nfunction f(){return /* inline */ value;}\n\nconst target=7;"
        tree = parse(source, comment=True, attachComment=True)
        options = {"comment": True, "sourceCode": source, "format": {"preserveBlankLines": True}}
        outputs = []
        for representation in (tree, tree.toDict()):
            before = normalized(copy.deepcopy(esprima.toDict(representation)))
            generated = escodegen.generate(representation, options)
            self.assertIn("\U0001f600", generated)
            self.assertEqual(normalized(parse(generated).toDict()), normalized(parse(source).toDict()))
            self.assertEqual(normalized(esprima.toDict(representation)), before)
            outputs.append(generated)
        self.assertEqual(outputs[0], outputs[1])

    def test_explicit_jsx_spread_children(self):
        source = "const view=<><A />{...children}{/* empty */}</>;"
        tree = parse(source, jsx=True)
        seen = []
        acornwalk.full(tree, lambda node, state, kind: seen.append(acornwalk.getField(node, "type")))
        self.assertIn("JSXSpreadChild", seen)
        for representation in (tree, tree.toDict()):
            for compact in (False, True):
                generated = escodegen.generate(representation, {"format": {"compact": compact}})
                self.assertEqual(normalized(parse(generated, jsx=True).toDict()), normalized(tree.toDict()))
        # Pinned acorn-jsx deliberately has no spread-child grammar. The explicit
        # extension above is round-tripped locally and is not represented as a
        # successful independent Acorn conformance check.

    @unittest.skipUnless(shutil.which("node") and (REFERENCE / "source-map").exists(),
        "pinned independent source-map consumer required")
    def test_native_mapping_source_maps_with_independent_consumer(self):
        source = 'const text="\U0001f600"; const target=other;'
        tree = parse(source)
        expected = tree.body[1].declarations[0].id.loc.start
        consumer = r"""
const fs=require('fs'),path=require('path');
const {SourceMapConsumer}=require(path.join(process.argv[1],'source-map'));
const data=JSON.parse(fs.readFileSync(0,'utf8'));
SourceMapConsumer.with(data.map,null,consumer=>{
  process.stdout.write(JSON.stringify(consumer.originalPositionFor(data.position)));
});
"""
        for representation in (tree, tree.toDict()):
            for compact in (False, True):
                result = escodegen.generate(representation, {"sourceMap": "input.js", "sourceMapWithCode": True,
                    "sourceContent": source, "file": "out.js", "format": {"compact": compact, "escapeless": True}})
                prefix = result.code[:result.code.index("target")]
                position = {"line": prefix.count("\n") + 1,
                    "column": len(prefix.rsplit("\n", 1)[-1].encode("utf-16-le")) // 2}
                payload = {"map": result.map.toJSON(), "position": position}
                process = subprocess.run(["node", "-e", consumer, str(REFERENCE)], input=json.dumps(payload),
                    capture_output=True, text=True, encoding="utf-8", check=True)
                original = json.loads(process.stdout)
                self.assertEqual((original["line"], original["column"], original["name"]),
                    (expected.line, expected.column, "target"))
                self.assertEqual(payload["map"]["sourcesContent"], [source])


if __name__ == "__main__":
    unittest.main()
