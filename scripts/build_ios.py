#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 iOS 未签名 IPA。

关键点：
1. 用 flutter build ios --release --no-codesign 构建 Runner.app
2. 手动按标准结构打包成 IPA：Payload/Runner.app
3. 输出到 dist/ios/<edition>-ios-unsigned.ipa
4. 同时输出 Runner.app 的 zip，方便自行签名
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_IOS = ROOT / "dist" / "ios"
BUILD_IOS = ROOT / "build" / "ios" / "iphoneos"
RUNNER_APP = BUILD_IOS / "Runner.app"


def run(cmd, cwd=None, check=True):
    print(f"+ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd or ROOT, check=check)


def parse_args():
    parser = argparse.ArgumentParser(description="Build iOS unsigned IPA")
    parser.add_argument(
        "--all-sources",
        action="store_true",
        help="使用全部站源（zhenguojian 版本）",
    )
    parser.add_argument(
        "--edition",
        default=None,
        help="可选，显式指定 edition，默认根据 --all-sources 推导",
    )
    return parser.parse_args()


def edition_name(args):
    if args.edition:
        return args.edition
    return "zhenguojian" if args.all_sources else "hongguojian"


def flutter_pub_get():
    # 先做一次宽松的 pub get，避免 pubspec.lock 与依赖不一致导致构建失败
    run(["flutter", "pub", "get"])


def flutter_build_ios(all_sources: bool):
    cmd = [
        "flutter",
        "build",
        "ios",
        "--release",
        "--no-codesign",
    ]
    if all_sources:
        cmd.append("--dart-define=ALL_SOURCES=true")
    cmd.append("--dart-define=DISABLE_REMOTE_IMAGES=true")
    run(cmd)


def make_ipa(edition: str):
    if not RUNNER_APP.exists():
        raise SystemExit(f"找不到 Runner.app：{RUNNER_APP}")

    DIST_IOS.mkdir(parents=True, exist_ok=True)

    payload_dir = DIST_IOS / "Payload"
    if payload_dir.exists():
        shutil.rmtree(payload_dir)
    payload_dir.mkdir(parents=True)

    # 标准 IPA 结构：Payload/Runner.app
    target_app = payload_dir / "Runner.app"
    shutil.copytree(RUNNER_APP, target_app, symlinks=True)

    ipa_path = DIST_IOS / f"{edition}-ios-unsigned.ipa"
    if ipa_path.exists():
        ipa_path.unlink()

    # 用 zip 打包 Payload 目录，注意 arcname 要用相对路径
    with zipfile.ZipFile(ipa_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(payload_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(DIST_IOS)
                zf.write(file_path, arcname)
            for d in dirs:
                dir_path = Path(root) / d
                arcname = dir_path.relative_to(DIST_IOS)
                # 确保空目录也被记录
                if not any(dir_path.iterdir()):
                    zf.writestr(str(arcname) + "/", "")

    print(f"已生成 IPA：{ipa_path}")

    # 额外输出 Runner.app 的 zip，方便自行签名
    app_zip = DIST_IOS / f"{edition}-ios-unsigned-app.zip"
    if app_zip.exists():
        app_zip.unlink()
    with zipfile.ZipFile(app_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BUILD_IOS):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(BUILD_IOS)
                zf.write(file_path, arcname)
    print(f"已生成 Runner.app 压缩包：{app_zip}")

    # 清理 Payload 临时目录
    shutil.rmtree(payload_dir, ignore_errors=True)


def main():
    args = parse_args()
    edition = edition_name(args)

    flutter_pub_get()
    flutter_build_ios(args.all_sources)
    make_ipa(edition)

    print("iOS 构建完成。")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败：{e}", file=sys.stderr)
        sys.exit(e.returncode)
