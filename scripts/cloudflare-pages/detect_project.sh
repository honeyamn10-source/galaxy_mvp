#!/usr/bin/env bash
set -euo pipefail

# Emits project metadata for CI with automatic framework detection.
# Output format:
# project_type=...
# app_dir=...
# build_command=...
# output_dir=...
# install_command=...

ROOT="${1:-.}"
cd "$ROOT"

has_file() {
  [[ -f "$1" ]]
}

is_next() {
  has_file "next.config.js" || has_file "next.config.mjs" || has_file "next.config.ts"
}

is_vite() {
  has_file "vite.config.js" || has_file "vite.config.ts" || has_file "vite.config.mjs"
}

dep_exists() {
  local dep="$1"
  node -e 'const fs=require("fs");const f="package.json";if(!fs.existsSync(f)){process.exit(1)};const p=JSON.parse(fs.readFileSync(f,"utf8"));const all=Object.assign({},p.dependencies||{},p.devDependencies||{});process.exit(all[process.argv[1]]?0:1);' "$dep"
}

project_type=""
app_dir="."
build_command=""
output_dir=""
install_command=""

if has_file "package.json"; then
  install_command="npm ci"
fi

if is_next || (has_file "package.json" && dep_exists next); then
  project_type="next"
  build_command="npm run build"
  output_dir=".next"
elif is_vite || (has_file "package.json" && dep_exists vite); then
  project_type="vite"
  build_command="npm run build"
  output_dir="dist"
elif has_file "package.json" && dep_exists react-scripts; then
  project_type="react"
  build_command="npm run build"
  output_dir="build"
elif has_file "docs/landing/index.html"; then
  project_type="static"
  app_dir="docs/landing"
  build_command=""
  output_dir="/"
  install_command=""
elif has_file "index.html"; then
  project_type="static"
  app_dir="."
  build_command=""
  output_dir="/"
  install_command=""
else
  echo "Unsupported project layout for Cloudflare Pages deployment" >&2
  exit 1
fi

echo "project_type=${project_type}"
echo "app_dir=${app_dir}"
echo "build_command=${build_command}"
echo "output_dir=${output_dir}"
echo "install_command=${install_command}"
