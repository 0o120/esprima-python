// Pinned development parser oracle. Source programs are parsed, never executed.
const fs = require('node:fs');
const acorn = require('./node_modules/acorn');
const jsx = require('./node_modules/acorn-jsx');
const JSXParser = acorn.Parser.extend(jsx());

function normalize(value) {
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === 'object') {
    const result = {};
    for (const [key, item] of Object.entries(value)) {
      if (['start', 'end', 'range', 'loc', 'raw'].includes(key)) continue;
      if (key === 'value' && value.regex) {
        result.value = null;
      } else if (key === 'directive') {
        result.directive = item === 'use strict' ? 'use strict' : '<non-strict-directive>';
      } else {
        result[key] = normalize(item);
      }
    }
    return result;
  }
  return typeof value === 'bigint' ? null : value;
}

const jobs = JSON.parse(fs.readFileSync(0, 'utf8'));
if (!Array.isArray(jobs)) throw new TypeError('Input must be an array of parse jobs');
const result = jobs.map(job => {
  if (typeof job.source !== 'string') throw new TypeError('Each job requires source text');
  const Parser = job.jsx ? JSXParser : acorn.Parser;
  const ast = Parser.parse(job.source, {ecmaVersion: 2026,
    sourceType: job.module ? 'module' : 'script', locations: true, ranges: true});
  return job.normalized ? normalize(ast) : ast;
});
process.stdout.write(JSON.stringify(result, (_, value) => typeof value === 'bigint' ? null : value));
