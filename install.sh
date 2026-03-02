#!/bin/bash

# 小真 skill 安装脚本
# Xiaozhen skill installer

GLOBAL_DIR="$HOME/.claude/commands"
FILE_URL="https://raw.githubusercontent.com/sjuz666/xiaozhen-skill/main/.claude/commands/小真.md"
FILE_NAME="小真.md"

echo "安装小真 skill... / Installing xiaozhen skill..."

mkdir -p "$GLOBAL_DIR"
curl -fsSL "$FILE_URL" -o "$GLOBAL_DIR/$FILE_NAME"

if [ $? -eq 0 ]; then
  echo "✓ 安装成功！在 Claude Code 里输入 /小真 开始聊"
  echo "✓ Done! Type /小真 in Claude Code to start"
else
  echo "✗ 安装失败，请检查网络连接"
  echo "✗ Installation failed. Please check your connection."
  exit 1
fi
