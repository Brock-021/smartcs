#!/bin/bash
# SmartCS 自动化测试脚本
# 每次代码优化后运行：bash run_tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================"
echo " SmartCS 自动化测试套件"
echo " 版本: 2.0"
echo " 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================"

# 清理旧数据库（保证测试环境干净）
rm -f "$SCRIPT_DIR/data/smartcs.db"

# ==========================================
# Step 1: 启动测试服务器
# ==========================================
echo ""
echo ">>> 启动测试服务器..."
python3 app.py &
SERVER_PID=$!
sleep 2

# 验证服务器就绪
if ! curl -s http://localhost:5000/ > /dev/null 2>&1; then
    echo "❌ 服务器启动失败"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi
echo "   服务器已就绪 (PID: $SERVER_PID)"

FAIL_COUNT=0

# ==========================================
# Step 2: 运行测试
# ==========================================
run_test_suite() {
    local name="$1"
    local cmd="$2"
    echo ""
    echo "──────────────────────────────"
    echo "  [$name]"
    echo "──────────────────────────────"
    if eval "$cmd"; then
        echo "  ✅ [$name] 通过"
    else
        echo "  ❌ [$name] 失败"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# 2a. 原有 HTTP 集成测试
run_test_suite "基础集成测试" "python3 test_smartcs.py"
run_test_suite "全功能集成测试" "python3 test_smartcs_full.py"
run_test_suite "角色权限测试" "python3 test_roles.py"

# 2b. 停止服务器（新单元测试使用 Flask test client，不需要服务器）
kill $SERVER_PID 2>/dev/null || true
sleep 1

# 2c. 单元测试（Flask test client, 独立运行，自动使用临时数据库）
run_test_suite "单元测试 (Flask test client)" "python3 -m unittest test_unit -v"

# ==========================================
# Step 3: 汇总
# ==========================================
echo ""
echo "================================"
if [ $FAIL_COUNT -eq 0 ]; then
    echo " ✅ 全部测试套件通过"
    echo "================================"
    exit 0
else
    echo " ❌ 存在 $FAIL_COUNT 个测试套件失败，请检查"
    echo "================================"
    exit 1
fi
