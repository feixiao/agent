#!/usr/bin/env bash
# ==============================================================================
# OpenMotion 本地源码自动化部署与服务管理脚本
# Supported OS: macOS (Apple Silicon / Intel), Linux
# ==============================================================================
set -euo pipefail

# ANSI 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_step()    { echo -e "\n${BOLD}${CYAN}==>${NC} ${BOLD}$*${NC}"; }

# 默认配置参数
TARGET_DIR="${OPENMOTION_DIR:-/Users/fx/wk/github/openmotion}"
BRANCH="${OPENMOTION_BRANCH:-main}"
PORT="${PORT:-4173}"
DATA_DIR="${MOTION_DATA_DIR:-$HOME/.openmotion/data}"
REPO_URL="https://github.com/nexu-io/openmotion.git"

CHECK_ONLY=false
NO_BUILD=false
AUTO_START=false
CLEAN_INSTALL=false

usage() {
  cat << EOF
用法: $(basename "$0") [选项]

OpenMotion 本地源码部署与环境准备脚本。

选项:
  -t, --target <DIR>     源码安装目标路径 (默认: $TARGET_DIR)
  -b, --branch <BRANCH>  Git 分支或 Tag (默认: $BRANCH)
  -p, --port <PORT>      Studio 运行端口 (默认: $PORT)
  -d, --data-dir <DIR>   项目持久化存储目录 (默认: $DATA_DIR)
  -c, --check-only       仅运行前置环境检查，不执行下载与构建
      --no-build         仅克隆与安装依赖，跳过 Studio 构建
      --clean            如果目标目录已存在，先清空重新安装
  -s, --start            部署完成后立即启动 Studio 预览服务
  -h, --help             显示此帮助信息

环境变量支持:
  OPENMOTION_DIR         默认安装路径
  OPENMOTION_BRANCH      Git 分支
  PORT                   服务监听端口
  MOTION_DATA_DIR        用户数据目录
  MOTION_BROWSER_PATH    自定义 Chromium / Chrome 路径
  HYPERFRAMES_FFMPEG_PATH 自定义 FFmpeg 路径
  HYPERFRAMES_FFPROBE_PATH 自定义 FFprobe 路径

示例:
  $(basename "$0") --check-only
  $(basename "$0") -t /Users/fx/wk/github/openmotion --start
EOF
  exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--target) TARGET_DIR="$2"; shift 2 ;;
    -b|--branch) BRANCH="$2"; shift 2 ;;
    -p|--port) PORT="$2"; shift 2 ;;
    -d|--data-dir) DATA_DIR="$2"; shift 2 ;;
    -c|--check-only) CHECK_ONLY=true; shift ;;
    --no-build) NO_BUILD=true; shift ;;
    --clean) CLEAN_INSTALL=true; shift ;;
    -s|--start) AUTO_START=true; shift ;;
    -h|--help) usage ;;
    *) log_error "未知选项: $1"; usage ;;
  esac
done

# ------------------------------------------------------------------------------
# 步骤 1: 系统前置依赖检测与自动路径探测
# ------------------------------------------------------------------------------
log_step "步骤 1: 系统前置依赖检测"

DETECTED_CHROME=""
DETECTED_FFMPEG=""
DETECTED_FFPROBE=""
PREFLIGHT_PASS=true

# 1.1 OS 检查
OS_NAME="$(uname -s)"
OS_ARCH="$(uname -m)"
log_info "检测到操作系统: $OS_NAME ($OS_ARCH)"

# 1.2 Git 检查
if command -v git >/dev/null 2>&1; then
  log_success "Git 已安装: $(git --version)"
else
  log_error "未检测到 Git，请先安装 Git。"
  PREFLIGHT_PASS=false
fi

# 1.3 Node.js 检查 (需 >= 22.18.0)
if command -v node >/dev/null 2>&1; then
  NODE_VER="$(node -v)"
  if node -e 'const [major,minor]=process.versions.node.split(".").map(Number);if(major<22||(major===22&&minor<18)){process.exit(1)}' 2>/dev/null; then
    log_success "Node.js 版本满足要求: $NODE_VER (>= 22.18.0)"
  else
    log_error "Node.js 版本不符合要求: $NODE_VER (必须 >= 22.18.0)"
    PREFLIGHT_PASS=false
  fi
else
  log_error "未检测到 Node.js，请先安装 Node.js 22.18+。"
  PREFLIGHT_PASS=false
fi

# 1.4 npm 检查
if command -v npm >/dev/null 2>&1; then
  log_success "npm 已安装: v$(npm -v)"
else
  log_error "未检测到 npm。"
  PREFLIGHT_PASS=false
fi

# 1.5 FFmpeg 与 FFprobe 检测
if [[ -n "${HYPERFRAMES_FFMPEG_PATH:-}" && -x "$HYPERFRAMES_FFMPEG_PATH" ]]; then
  DETECTED_FFMPEG="$HYPERFRAMES_FFMPEG_PATH"
elif [[ -x "/opt/homebrew/bin/ffmpeg" ]]; then
  DETECTED_FFMPEG="/opt/homebrew/bin/ffmpeg"
elif [[ -x "/usr/local/bin/ffmpeg" ]]; then
  DETECTED_FFMPEG="/usr/local/bin/ffmpeg"
elif command -v ffmpeg >/dev/null 2>&1; then
  DETECTED_FFMPEG="$(command -v ffmpeg)"
fi

if [[ -n "${HYPERFRAMES_FFPROBE_PATH:-}" && -x "$HYPERFRAMES_FFPROBE_PATH" ]]; then
  DETECTED_FFPROBE="$HYPERFRAMES_FFPROBE_PATH"
elif [[ -x "/opt/homebrew/bin/ffprobe" ]]; then
  DETECTED_FFPROBE="/opt/homebrew/bin/ffprobe"
elif [[ -x "/usr/local/bin/ffprobe" ]]; then
  DETECTED_FFPROBE="/usr/local/bin/ffprobe"
elif command -v ffprobe >/dev/null 2>&1; then
  DETECTED_FFPROBE="$(command -v ffprobe)"
fi

if [[ -n "$DETECTED_FFMPEG" && -n "$DETECTED_FFPROBE" ]]; then
  log_success "FFmpeg 发现: $DETECTED_FFMPEG"
  log_success "FFprobe 发现: $DETECTED_FFPROBE"
else
  log_error "未完整检测到 FFmpeg 与 FFprobe。请运行 'brew install ffmpeg' (macOS) 或使用系统包管理安装。"
  PREFLIGHT_PASS=false
fi

# 1.6 Google Chrome / Chromium 检测
if [[ -n "${MOTION_BROWSER_PATH:-}" && -x "$MOTION_BROWSER_PATH" ]]; then
  DETECTED_CHROME="$MOTION_BROWSER_PATH"
elif [[ "$OS_NAME" == "Darwin" ]]; then
  CANDIDATE_CHROME_PATHS=(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
  )
  for cpath in "${CANDIDATE_CHROME_PATHS[@]}"; do
    if [[ -x "$cpath" ]]; then
      DETECTED_CHROME="$cpath"
      break
    fi
  done
else
  for cname in google-chrome chromium chromium-browser; do
    if command -v "$cname" >/dev/null 2>&1; then
      DETECTED_CHROME="$(command -v "$cname")"
      break
    fi
  done
fi

if [[ -n "$DETECTED_CHROME" ]]; then
  log_success "Chromium/Chrome 发现: $DETECTED_CHROME"
else
  log_warn "未自动发现 Chrome/Chromium 浏览器。无头渲染可能需要手动配置 MOTION_BROWSER_PATH。"
fi

# 1.7 端口占用检查
if lsof -i :"$PORT" >/dev/null 2>&1; then
  log_warn "端口 $PORT 目前已被占用，启动 Studio 前需释放该端口或更改 PORT。"
else
  log_success "端口 $PORT 空闲可用"
fi

if [ "$PREFLIGHT_PASS" = false ]; then
  log_error "前置依赖检查未通过，请根据上述提示修复后重试。"
  exit 1
fi

if [ "$CHECK_ONLY" = true ]; then
  log_success "前置检查完成，所有关键环境均满足要求。"
  exit 0
fi

# ------------------------------------------------------------------------------
# 步骤 2: 代码仓库克隆与更新
# ------------------------------------------------------------------------------
log_step "步骤 2: 源码仓库部署至 $TARGET_DIR"

if [ -d "$TARGET_DIR" ]; then
  if [ "$CLEAN_INSTALL" = true ]; then
    log_warn "已指定 --clean，正在清理现有目录: $TARGET_DIR"
    rm -rf "$TARGET_DIR"
  elif [ -d "$TARGET_DIR/.git" ]; then
    log_info "检测到已存在 Git 仓库，正在拉取最新代码 ($BRANCH)..."
    git -C "$TARGET_DIR" fetch origin "$BRANCH"
    git -C "$TARGET_DIR" checkout "$BRANCH"
    git -C "$TARGET_DIR" pull --ff-only origin "$BRANCH" || log_warn "本地可能存在更改，已保留本地版本。"
  else
    log_warn "目标目录已存在但不是 Git 仓库: $TARGET_DIR"
  fi
fi

if [ ! -d "$TARGET_DIR" ]; then
  mkdir -p "$(dirname "$TARGET_DIR")"
  log_info "正在克隆 OpenMotion ($BRANCH) [跳过 LFS 大媒体以提速]..."
  git -c filter.lfs.process= -c filter.lfs.smudge= -c filter.lfs.required=false \
    clone --depth 1 --single-branch --branch "$BRANCH" "$REPO_URL" "$TARGET_DIR"
  log_success "源码克隆成功: $TARGET_DIR"
fi

cd "$TARGET_DIR"

# ------------------------------------------------------------------------------
# 步骤 3: 锁定依赖安装 (npm ci)
# ------------------------------------------------------------------------------
log_step "步骤 3: 安装项目依赖 (npm ci)"
log_info "正在安装严格锁定的依赖包 (含 Hyperframes 0.9.7, GSAP 3.15.0)..."
npm ci --include=dev
log_success "项目依赖安装完成"

# ------------------------------------------------------------------------------
# 步骤 4: 编译 Studio 编辑器前端
# ------------------------------------------------------------------------------
if [ "$NO_BUILD" = false ]; then
  log_step "步骤 4: 编译 Studio 编辑器前端 (npm run build:studio)"
  npm run build:studio
  if [ -f "$TARGET_DIR/studio/build/index.html" ]; then
    log_success "Studio 前端编译成功！(产物: studio/build/index.html)"
  else
    log_error "编译完成但未找到 studio/build/index.html"
    exit 1
  fi
else
  log_info "跳过前端编译步骤 (--no-build)"
fi

# ------------------------------------------------------------------------------
# 步骤 5: 配置持久化工作区与环境变量
# ------------------------------------------------------------------------------
log_step "步骤 5: 配置环境变量与数据工作区"

mkdir -p "$DATA_DIR"
log_info "数据持久化工作区已就绪: $DATA_DIR"

ENV_FILE="$TARGET_DIR/.env"
cat << EOF > "$ENV_FILE"
# 自动生成的 OpenMotion 本地运行时环境变量
MOTION_BROWSER_PATH="${DETECTED_CHROME}"
HYPERFRAMES_FFMPEG_PATH="${DETECTED_FFMPEG}"
HYPERFRAMES_FFPROBE_PATH="${DETECTED_FFPROBE}"
MOTION_DATA_DIR="${DATA_DIR}"
PORT=${PORT}
EOF
log_success "环境变量文件已写入: $ENV_FILE"

# ------------------------------------------------------------------------------
# 步骤 6: 生成服务管理辅助脚本
# ------------------------------------------------------------------------------
log_step "步骤 6: 生成启动与运维管理脚本"

# 6.1 start_studio.sh
cat << 'EOF' > "$TARGET_DIR/start_studio.sh"
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

mkdir -p "$DIR/.artifacts/logs"
LOG_FILE="$DIR/.artifacts/logs/studio.log"

if [ -f "$DIR/.env" ]; then
  set -a; source "$DIR/.env"; set +a
fi

DATA_DIR="${MOTION_DATA_DIR:-$HOME/.openmotion/data}"
PREVIEW_JSON="$DATA_DIR/preview.json"

if [ -f "$PREVIEW_JSON" ]; then
  PREV_PID=$(node -e 'try{console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).pid||"")}catch(e){}' "$PREVIEW_JSON" 2>/dev/null || echo "")
  if [ -n "$PREV_PID" ] && ps -p "$PREV_PID" >/dev/null 2>&1; then
    PREV_PORT=$(node -e 'try{console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).port||"")}catch(e){}' "$PREVIEW_JSON" 2>/dev/null || echo "")
    echo "[OpenMotion] 服务已在运行中 (PID: $PREV_PID, 端口: $PREV_PORT)"
    echo "[OpenMotion] 访问地址: http://localhost:$PREV_PORT/"
    exit 0
  fi
fi

echo "[OpenMotion] 正在启动 Studio 预览服务..."
OUTPUT=$(node --env-file=.env --experimental-strip-types preview.ts 2>&1)
echo "$OUTPUT" > "$LOG_FILE"

STUDIO_URL=$(echo "$OUTPUT" | node -e '
let input = "";
process.stdin.on("data", c => input += c);
process.stdin.on("end", () => {
  try {
    const data = JSON.parse(input);
    console.log(data.studioUrl || data.previewUrl || "");
  } catch(e) {}
});
' 2>/dev/null || echo "")

if [ -n "$STUDIO_URL" ]; then
  echo "[OpenMotion] Studio 启动成功！"
  echo "[OpenMotion] 访问地址: $STUDIO_URL"
  echo "[OpenMotion] 日志记录: $LOG_FILE"
else
  echo "[OpenMotion] 启动输出:"
  echo "$OUTPUT"
fi
EOF
chmod +x "$TARGET_DIR/start_studio.sh"

# 6.2 stop_studio.sh
cat << 'EOF' > "$TARGET_DIR/stop_studio.sh"
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f "$DIR/.env" ]; then
  set -a; source "$DIR/.env"; set +a
fi

DATA_DIR="${MOTION_DATA_DIR:-$HOME/.openmotion/data}"
PREVIEW_JSON="$DATA_DIR/preview.json"

if [ -f "$PREVIEW_JSON" ]; then
  CURRENT_PID=$(node -e 'try{console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).pid||"")}catch(e){}' "$PREVIEW_JSON" 2>/dev/null || echo "")
  CURRENT_PORT=$(node -e 'try{console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).port||"")}catch(e){}' "$PREVIEW_JSON" 2>/dev/null || echo "")
  if [ -n "$CURRENT_PID" ] && ps -p "$CURRENT_PID" >/dev/null 2>&1; then
    echo "[OpenMotion] 正在停止服务 (PID: $CURRENT_PID)..."
    kill "$CURRENT_PID" 2>/dev/null || true
    sleep 1
    if ps -p "$CURRENT_PID" >/dev/null 2>&1; then
      kill -9 "$CURRENT_PID" 2>/dev/null || true
    fi
  fi
  if [ -n "$CURRENT_PORT" ] && lsof -i :"$CURRENT_PORT" >/dev/null 2>&1; then
    kill -9 $(lsof -t -i :"$CURRENT_PORT") 2>/dev/null || true
  fi
  rm -f "$PREVIEW_JSON"
fi

if [ -n "${PORT:-}" ] && lsof -i :"$PORT" >/dev/null 2>&1; then
  echo "[OpenMotion] 正在停止端口 $PORT 占用进程..."
  kill -9 $(lsof -t -i :"$PORT") 2>/dev/null || true
fi
echo "[OpenMotion] 服务已停止。"
EOF
chmod +x "$TARGET_DIR/stop_studio.sh"

# 6.3 status_studio.sh
cat << 'EOF' > "$TARGET_DIR/status_studio.sh"
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f "$DIR/.env" ]; then
  set -a; source "$DIR/.env"; set +a
fi

DATA_DIR="${MOTION_DATA_DIR:-$HOME/.openmotion/data}"
PREVIEW_JSON="$DATA_DIR/preview.json"

echo "=== OpenMotion 服务状态 ==="

RUNNING=false
CURRENT_PID=""
CURRENT_PORT=""

if [ -f "$PREVIEW_JSON" ]; then
  CURRENT_PID=$(node -e 'try{console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).pid||"")}catch(e){}' "$PREVIEW_JSON" 2>/dev/null || echo "")
  CURRENT_PORT=$(node -e 'try{console.log(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).port||"")}catch(e){}' "$PREVIEW_JSON" 2>/dev/null || echo "")
  if [ -n "$CURRENT_PID" ] && ps -p "$CURRENT_PID" >/dev/null 2>&1; then
    RUNNING=true
  fi
fi

if [ "$RUNNING" = false ] && [ -n "${PORT:-}" ]; then
  if lsof -i :"$PORT" >/dev/null 2>&1; then
    CURRENT_PID=$(lsof -t -i :"$PORT" | head -n 1)
    CURRENT_PORT="$PORT"
    RUNNING=true
  fi
fi

if [ "$RUNNING" = true ]; then
  echo "状态:       [运行中] 🟢"
  echo "进程 PID:   $CURRENT_PID"
  echo "服务端口:   $CURRENT_PORT"
  echo "Studio URL: http://localhost:$CURRENT_PORT/#project/project"
  if command -v curl >/dev/null 2>&1; then
    HEALTH=$(curl -s "http://127.0.0.1:$CURRENT_PORT/api/health" 2>/dev/null || echo "")
    if [ -n "$HEALTH" ]; then
      echo "健康检查:   通过 (服务名称: $(node -e 'try{console.log(JSON.parse(process.argv[1]).service)}catch(e){}' "$HEALTH" 2>/dev/null || echo "ok"))"
    fi
  fi
else
  echo "状态:       [已停止] ⚪"
fi
EOF
chmod +x "$TARGET_DIR/status_studio.sh"

# 6.4 通用标准 MCP 配置文件 (支持 omp / Cursor / Windsurf / Claude Code / Cline 等)
cat << EOF > "$TARGET_DIR/mcp_server_config.json"
{
  "mcpServers": {
    "openmotion": {
      "command": "node",
      "args": [
        "--experimental-strip-types",
        "$TARGET_DIR/mcp.ts"
      ],
      "env": {
        "MOTION_DATA_DIR": "$DATA_DIR",
        "MOTION_BROWSER_PATH": "$DETECTED_CHROME",
        "HYPERFRAMES_FFMPEG_PATH": "$DETECTED_FFMPEG",
        "HYPERFRAMES_FFPROBE_PATH": "$DETECTED_FFPROBE"
      }
    }
  }
}
EOF
cp "$TARGET_DIR/mcp_server_config.json" "$TARGET_DIR/claude_mcp_config.json"

log_success "辅助管理脚本与 MCP 模板已生成于: $TARGET_DIR"

# ------------------------------------------------------------------------------
# 步骤 7: 自动启动 (若指定 -s/--start)
# ------------------------------------------------------------------------------
if [ "$AUTO_START" = true ]; then
  log_step "步骤 7: 启动 Studio 预览服务"
  bash "$TARGET_DIR/start_studio.sh"
  sleep 2
  bash "$TARGET_DIR/status_studio.sh"
fi

# ------------------------------------------------------------------------------
# 部署完成报告
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}================================================================${NC}"
echo -e "${BOLD}${GREEN}        🎉 OpenMotion 本地源码部署与环境初始化成功！            ${NC}"
echo -e "${BOLD}${GREEN}================================================================${NC}"
echo -e "安装路径:     ${BOLD}$TARGET_DIR${NC}"
echo -e "数据工作区:   ${BOLD}$DATA_DIR${NC}"
echo -e "Studio 端口:  ${BOLD}$PORT${NC}"
echo ""
echo -e "常用服务管理指令:"
echo -e "  启动 Studio:  ${CYAN}$TARGET_DIR/start_studio.sh${NC} (或在目录中运行 ${CYAN}npm start${NC})"
echo -e "  查看状态:     ${CYAN}$TARGET_DIR/status_studio.sh${NC}"
echo -e "  停止服务:     ${CYAN}$TARGET_DIR/stop_studio.sh${NC}"
echo -e "  Studio 访问:  ${BOLD}http://localhost:$PORT${NC}"
echo ""
echo -e "Agent MCP 接入指南 (Model Context Protocol):"
echo -e "  已生成通用标准 MCP 配置文件: ${CYAN}$TARGET_DIR/mcp_server_config.json${NC}"
echo -e "  - 支持客户端: ${BOLD}omp${NC}、${BOLD}Cursor${NC}、${BOLD}Windsurf${NC}、${BOLD}Claude Code${NC}、${BOLD}Cline${NC}、${BOLD}Codex${NC} 等"
echo -e "  - Codex 可直接执行: ${CYAN}cd $TARGET_DIR && bash scripts/install-motion.command${NC}"
echo -e "${BOLD}${GREEN}================================================================${NC}"
