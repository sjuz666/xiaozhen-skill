#!/bin/bash

# 小真 skill 安装脚本
# Xiaozhen skill installer

GLOBAL_DIR="$HOME/.claude/commands"
REF_DIR="$HOME/.claude/references"
BASE_URL="https://raw.githubusercontent.com/sjuz666/xiaozhen-skill/main"

echo "安装小真 skill... / Installing xiaozhen skill..."

# 创建目录 / Create directories
mkdir -p "$GLOBAL_DIR"
mkdir -p "$REF_DIR"

# 下载主文件 / Download main skill file
curl -fsSL "$BASE_URL/.claude/commands/小真.md" -o "$GLOBAL_DIR/小真.md"

if [ $? -ne 0 ]; then
  echo "✗ 主文件下载失败，请检查网络连接"
  echo "✗ Failed to download main skill file. Please check your connection."
  exit 1
fi

# 下载参考文档 / Download reference document
curl -fsSL "$BASE_URL/references/zhenxue-framework.md" -o "$REF_DIR/zhenxue-framework.md"

if [ $? -ne 0 ]; then
  echo "⚠ 参考文档下载失败，skill 仍可使用但部分功能受限"
  echo "⚠ Reference doc failed to download. Skill still works but some details may be limited."
else
  echo "✓ 参考文档已安装 / Reference doc installed"
fi

echo "✓ 安装成功！在 Claude Code 里输入 /小真 开始聊"
echo "✓ Done! Type /小真 in Claude Code to start"
