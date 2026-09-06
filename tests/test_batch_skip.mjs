// Task E lớp 2: decision matrix batch skip — logic thuần, stdlib node, không framework.
// Chạy: node tests/test_batch_skip.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const here = path.dirname(fileURLToPath(import.meta.url));
const ctx = {};
vm.createContext(ctx);
vm.runInContext(
    fs.readFileSync(path.join(here, '..', 'web', 'js', 'batch.js'), 'utf8'), ctx);
const t = ctx.batchOnFileError;
assert.equal(typeof t, 'function');

assert.equal(t(false, false), 'stop');  // skip TẮT + lỗi → dừng cả loạt
assert.equal(t(true, false), 'skip');   // skip BẬT + lỗi → bỏ qua, qua file sau
assert.equal(t(true, true), 'stop');    // đã hủy → dừng dù BẬT skip
assert.equal(t(false, true), 'stop');   // đã hủy, skip TẮT → dừng
assert.equal(t(undefined, false), 'stop');  // checkbox thiếu → an toàn: dừng

console.log('batch skip matrix: 5/5 OK');
