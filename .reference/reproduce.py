"""Compare candidate bytes with independent ECMAScript on admitted values."""
import json
import subprocess

from policy import canonical_bytes

VECTORS = [
    {"\ue000": "e\u0301", "😀": "é", "a": True},
    [-0.0, 1.0, 333333333.33333329, 1e20, 1e21, 1e-6, 1e-7, 5e-324, 1.7976931348623157e308],
    {"2": "two", "10": "ten", "1": "one", "": "empty"},
    ["\x00\b\t\n\f\r\x1f", '"\\/', "é", "e\u0301", "\u2028\u2029"],
    {"z": [{"b": 1, "a": 2}, False, 1], "a": {}},
    [True, 1, "1", None, "9007199254740993"],
]

# An independent oracle for already admitted values only, not a production parser.
SCRIPT = '''
const fs = require('node:fs');
const encode = v => v === null || typeof v !== 'object' ? JSON.stringify(v)
  : Array.isArray(v) ? '[' + v.map(encode).join(',') + ']'
  : '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + encode(v[k])).join(',') + '}';
const values = JSON.parse(fs.readFileSync(0, 'utf8'));
console.log(JSON.stringify(values.map(v => Buffer.from(encode(v), 'utf8').toString('hex'))));
'''

if __name__ == '__main__':
    output = subprocess.check_output(['node', '-e', SCRIPT], input=json.dumps(VECTORS).encode())
    assert json.loads(output) == [canonical_bytes(value).hex() for value in VECTORS]
    print(f'{len(VECTORS)} independent ECMAScript byte comparisons passed')
