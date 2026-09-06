// --- Quyết định skip/bỏ qua file lỗi trong batch tuần tự (hàm thuần, test bằng node) ---
// Dùng chung cho cả 2 điểm quyết định trong wsBulkTranslate (lỗi pre-SSE + lỗi SSE).
// Trả 'skip' (ghi failed, qua file sau) hoặc 'stop' (dừng cả loạt).
function batchOnFileError(skipErr, cancelled) {
    return (skipErr && !cancelled) ? 'skip' : 'stop';
}
