import argparse
import logging
import os
import platform
import shutil
import subprocess
import tarfile
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)


class ChangeDirectory:
    def __init__(self, cwd):
        self._cwd = cwd

    def __enter__(self):
        self._old_cwd = os.getcwd()
        logging.debug(f"pushd {self._old_cwd} --> {self._cwd}")
        os.chdir(self._cwd)

    def __exit__(self, exctype, excvalue, trace):
        logging.debug(f"popd {self._old_cwd} <-- {self._cwd}")
        os.chdir(self._old_cwd)
        return False


def cd(cwd):
    return ChangeDirectory(cwd)


def cmd(args, **kwargs):
    logging.debug(f"+{args} {kwargs}")
    if "check" not in kwargs:
        kwargs["check"] = True
    if "resolve" in kwargs:
        resolve = kwargs["resolve"]
        del kwargs["resolve"]
    else:
        resolve = True
    if resolve:
        args = [shutil.which(args[0]), *args[1:]]
    return subprocess.run(args, **kwargs)


def cmdcap(args, **kwargs):
    kwargs["stdout"] = subprocess.PIPE
    kwargs["stderr"] = subprocess.PIPE
    kwargs["encoding"] = "utf-8"
    return cmd(args, **kwargs).stdout.strip()


def rm_rf(path: str):
    if not os.path.exists(path):
        return
    if os.path.isfile(path) or os.path.islink(path):
        os.remove(path)
    if os.path.isdir(path):
        shutil.rmtree(path)


def mkdir_p(path: str):
    os.makedirs(path, exist_ok=True)


def read_version_file(path: str) -> Dict[str, str]:
    versions = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            versions[key.strip()] = value.strip().strip('"')
    return versions


def enum_all_files(dir, dir2):
    for root, _, files in os.walk(dir):
        for file in files:
            yield os.path.relpath(os.path.join(root, file), dir2)


# ターゲット定義
TARGETS = [
    "macos_arm64",
    "ios_device_arm64",
    "ios_simulator_arm64",
    "android_arm64_v8a",
]

# ターゲット別パッチ定義
PATCHES: Dict[str, List[str]] = {
    "macos_arm64": [],
    "ios_device_arm64": [],
    "ios_simulator_arm64": [],
    "android_arm64_v8a": [],
}


def check_target(target: str) -> bool:
    """現在の OS でビルド可能なターゲットかどうかを確認する"""
    system = platform.system()
    if system == "Darwin":
        return target in ("macos_arm64", "ios_device_arm64", "ios_simulator_arm64", "android_arm64_v8a")
    elif system == "Linux":
        return target in ("android_arm64_v8a",)
    return False


def get_jolt_source(source_dir: str, version: str):
    """Jolt Physics ソースを clone して指定バージョンに checkout する"""
    jolt_dir = os.path.join(source_dir, "JoltPhysics")
    if not os.path.exists(jolt_dir):
        logging.info(f"Cloning JoltPhysics into {jolt_dir}...")
        cmd([
            "git", "clone", "--depth", "1",
            "--branch", f"v{version}",
            "https://github.com/jrouwe/JoltPhysics.git",
            jolt_dir,
        ])
    else:
        logging.info(f"JoltPhysics source already exists at {jolt_dir}")
        with cd(jolt_dir):
            cmd(["git", "fetch", "--tags", "--depth", "1", "origin",
                 f"refs/tags/v{version}:refs/tags/v{version}"],
                check=False)
            cmd(["git", "checkout", f"v{version}"])

    return jolt_dir


def apply_patch(patch: str, dir: str):
    with cd(dir):
        logging.info(f"Applying patch: {os.path.basename(patch)}")
        cmd(["git", "apply", patch])


def apply_patches(target: str, patch_dir: str, src_dir: str):
    patches = PATCHES.get(target, [])
    for patch in patches:
        patch_path = os.path.join(patch_dir, patch)
        apply_patch(patch_path, src_dir)
    if patches:
        logging.info(f"Applied {len(patches)} patch(es).")
    else:
        logging.info("No patches to apply.")


def reset_source(src_dir: str):
    """ソースをクリーンな状態に戻す"""
    with cd(src_dir):
        cmd(["git", "checkout", "--", "."])
        cmd(["git", "clean", "-df"])


# Jolt Physics のビルドで無効化する CMake オプション
# ライブラリのみビルドし、サンプルやテストは含めない
JOLT_COMMON_CMAKE_ARGS = [
    "-DTARGET_UNIT_TESTS=OFF",
    "-DTARGET_HELLO_WORLD=OFF",
    "-DTARGET_PERFORMANCE_TEST=OFF",
    "-DTARGET_SAMPLES=OFF",
    "-DTARGET_VIEWER=OFF",
    "-DENABLE_ALL_WARNINGS=OFF",
    "-DINTERPROCEDURAL_OPTIMIZATION=ON",
    "-DCPP_EXCEPTIONS_ENABLED=OFF",
    "-DCPP_RTTI_ENABLED=OFF",
    "-DGENERATE_DEBUG_SYMBOLS=OFF",
]


def build_jolt_macos(jolt_dir: str, build_dir: str):
    """macOS arm64 向け Jolt Physics をビルドする"""
    logging.info("=== Building Jolt Physics for macos_arm64 ===")

    cmake_src = os.path.join(jolt_dir, "Build")
    mkdir_p(build_dir)

    with cd(build_dir):
        cmd([
            "cmake", "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Distribution",
            "-DCMAKE_OSX_ARCHITECTURES=arm64",
            f"-DCMAKE_INSTALL_PREFIX={build_dir}/install",
            *JOLT_COMMON_CMAKE_ARGS,
            cmake_src,
        ])
        cmd(["ninja"])
        cmd(["ninja", "install"])


def build_jolt_ios_device(jolt_dir: str, build_dir: str):
    """iOS device arm64 向け Jolt Physics をビルドする"""
    logging.info("=== Building Jolt Physics for ios_device_arm64 ===")

    cmake_src = os.path.join(jolt_dir, "Build")
    mkdir_p(build_dir)

    with cd(build_dir):
        cmd([
            "cmake", "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Distribution",
            "-DCMAKE_SYSTEM_NAME=iOS",
            "-DCMAKE_OSX_SYSROOT=iphoneos",
            "-DCMAKE_OSX_ARCHITECTURES=arm64",
            "-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0",
            f"-DCMAKE_INSTALL_PREFIX={build_dir}/install",
            *JOLT_COMMON_CMAKE_ARGS,
            cmake_src,
        ])
        cmd(["ninja"])
        cmd(["ninja", "install"])


def build_jolt_ios_simulator(jolt_dir: str, build_dir: str):
    """iOS simulator arm64 向け Jolt Physics をビルドする"""
    logging.info("=== Building Jolt Physics for ios_simulator_arm64 ===")

    cmake_src = os.path.join(jolt_dir, "Build")
    mkdir_p(build_dir)

    with cd(build_dir):
        cmd([
            "cmake", "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Distribution",
            "-DCMAKE_SYSTEM_NAME=iOS",
            "-DCMAKE_OSX_SYSROOT=iphonesimulator",
            "-DCMAKE_OSX_ARCHITECTURES=arm64",
            "-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0",
            f"-DCMAKE_INSTALL_PREFIX={build_dir}/install",
            *JOLT_COMMON_CMAKE_ARGS,
            cmake_src,
        ])
        cmd(["ninja"])
        cmd(["ninja", "install"])


def build_jolt_android(jolt_dir: str, build_dir: str):
    """Android arm64-v8a 向け Jolt Physics をビルドする"""
    logging.info("=== Building Jolt Physics for android_arm64_v8a ===")

    android_home = os.environ.get("ANDROID_HOME")
    if not android_home:
        raise Exception("ANDROID_HOME is not set")

    # NDK パスを探す
    ndk_path = os.environ.get("ANDROID_NDK_HOME") or os.environ.get("ANDROID_NDK")
    if not ndk_path:
        ndk_dir = os.path.join(android_home, "ndk")
        if os.path.exists(ndk_dir):
            ndks = sorted(os.listdir(ndk_dir))
            if ndks:
                ndk_path = os.path.join(ndk_dir, ndks[-1])
    if not ndk_path or not os.path.exists(ndk_path):
        raise Exception("Android NDK not found. Set ANDROID_NDK_HOME or install NDK via SDK Manager.")

    toolchain_file = os.path.join(ndk_path, "build", "cmake", "android.toolchain.cmake")
    if not os.path.exists(toolchain_file):
        raise Exception(f"Android toolchain file not found: {toolchain_file}")

    cmake_src = os.path.join(jolt_dir, "Build")
    mkdir_p(build_dir)

    with cd(build_dir):
        cmd([
            "cmake", "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Distribution",
            f"-DCMAKE_TOOLCHAIN_FILE={toolchain_file}",
            "-DANDROID_USE_LEGACY_TOOLCHAIN_FILE=OFF",
            "-DANDROID_ABI=arm64-v8a",
            "-DANDROID_PLATFORM=android-21",
            "-DANDROID_STL=c++_static",
            f"-DCMAKE_INSTALL_PREFIX={build_dir}/install",
            *JOLT_COMMON_CMAKE_ARGS,
            cmake_src,
        ])
        cmd(["ninja"])
        cmd(["ninja", "install"])


# ターゲットごとのビルド関数
BUILD_FUNCS = {
    "macos_arm64": build_jolt_macos,
    "ios_device_arm64": build_jolt_ios_device,
    "ios_simulator_arm64": build_jolt_ios_simulator,
    "android_arm64_v8a": build_jolt_android,
}


def copy_headers(install_dir: str, package_dir: str):
    """ヘッダーファイルをパッケージディレクトリにコピーする"""
    src = os.path.join(install_dir, "include")
    dst = os.path.join(package_dir, "include")
    if os.path.exists(src):
        shutil.copytree(src, dst)


def copy_libraries(install_dir: str, package_dir: str):
    """ライブラリファイルをパッケージディレクトリにコピーする"""
    lib_dir = os.path.join(package_dir, "lib")
    mkdir_p(lib_dir)
    src_lib = os.path.join(install_dir, "lib")
    if os.path.exists(src_lib):
        for root, _, files in os.walk(src_lib):
            for f in files:
                if f.endswith(".a"):
                    shutil.copy2(os.path.join(root, f), lib_dir)


def copy_licenses(jolt_dir: str, package_dir: str, base_dir: str):
    """ライセンスファイルをパッケージディレクトリにコピーする"""
    license_src = os.path.join(jolt_dir, "LICENSE")
    if not os.path.exists(license_src):
        raise Exception(f"LICENSE not found: {license_src}")
    shutil.copy2(license_src, os.path.join(package_dir, "LICENSE"))

    notice_src = os.path.join(base_dir, "NOTICE")
    if not os.path.exists(notice_src):
        raise Exception(f"NOTICE not found: {notice_src}")
    shutil.copy2(notice_src, os.path.join(package_dir, "NOTICE"))


def generate_version_info(package_dir: str, version_file_path: str):
    """バージョン情報をパッケージに含める"""
    shutil.copyfile(version_file_path, os.path.join(package_dir, "VERSIONS"))


def verify_artifacts(target: str, package_dir: str):
    """成果物の検証を行う"""
    lib_dir = os.path.join(package_dir, "lib")

    if not os.path.exists(lib_dir):
        logging.warning("WARNING: lib directory not found")
        return

    # libJolt.a の存在確認
    jolt_lib = os.path.join(lib_dir, "libJolt.a")
    if not os.path.exists(jolt_lib):
        logging.warning("WARNING: libJolt.a not found")
        return

    logging.info(f"OK: libJolt.a found ({os.path.getsize(jolt_lib)} bytes)")

    if target in ("ios_device_arm64", "ios_simulator_arm64") and platform.system() == "Darwin":
        result = cmdcap(["otool", "-l", jolt_lib], check=False)
        # LTO (LLVM bitcode) の場合はプラットフォームタグが含まれないため
        # otool で検証できない。bitcode でない場合のみ検証する。
        if "is an LLVM bit-code file" in result:
            logging.info("OK: LTO bitcode objects detected, skipping platform tag verification")
        elif target == "ios_simulator_arm64":
            if "platform 7" in result:
                logging.info("OK: platform is iossim (7)")
            else:
                logging.warning("WARNING: expected platform iossim (7)")
        elif target == "ios_device_arm64":
            if "platform 2" in result:
                logging.info("OK: platform is ios (2)")
            else:
                logging.warning("WARNING: expected platform ios (2)")


def package_jolt(
    source_dir: str,
    build_dir: str,
    package_dir: str,
    target: str,
    base_dir: str,
):
    """ビルド成果物をパッケージングする"""
    jolt_dir = os.path.join(source_dir, "JoltPhysics")
    install_dir = os.path.join(build_dir, "install")

    jolt_package_dir = os.path.join(package_dir, "jolt")
    rm_rf(jolt_package_dir)
    mkdir_p(jolt_package_dir)

    # ライブラリをコピーする
    copy_libraries(install_dir, jolt_package_dir)

    # ヘッダーをコピーする
    copy_headers(install_dir, jolt_package_dir)

    # ライセンスをコピーする
    copy_licenses(jolt_dir, jolt_package_dir, base_dir)

    # バージョン情報をコピーする
    generate_version_info(jolt_package_dir, os.path.join(base_dir, "VERSION"))

    # 成果物を検証する
    verify_artifacts(target, jolt_package_dir)

    # tar.gz にパッケージングする
    version = read_version_file(os.path.join(base_dir, "VERSION"))
    jolt_version = version["JOLT_VERSION"]
    archive_name = f"jolt-v{jolt_version}-{target}.tar.gz"
    with cd(package_dir):
        with tarfile.open(archive_name, "w:gz") as tar:
            for file in enum_all_files("jolt", "."):
                tar.add(name=file, arcname=file)

    logging.info(f"Package created: {os.path.join(package_dir, archive_name)}")


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def main():
    parser = argparse.ArgumentParser(description="Jolt Physics マルチプラットフォームビルドツール")
    sp = parser.add_subparsers()

    # build サブコマンド
    bp = sp.add_parser("build", help="Jolt Physics をビルドする")
    bp.set_defaults(op="build")
    bp.add_argument("target", choices=TARGETS)
    bp.add_argument("--source-dir", help="ソースディレクトリ")
    bp.add_argument("--build-dir", help="ビルドディレクトリ")

    # package サブコマンド
    pp = sp.add_parser("package", help="ビルド成果物をパッケージングする")
    pp.set_defaults(op="package")
    pp.add_argument("target", choices=TARGETS)
    pp.add_argument("--source-dir", help="ソースディレクトリ")
    pp.add_argument("--build-dir", help="ビルドディレクトリ")
    pp.add_argument("--package-dir", help="パッケージ出力ディレクトリ")

    args = parser.parse_args()

    if not hasattr(args, "op"):
        parser.error("Required subcommand")

    if not check_target(args.target):
        raise Exception(f"Target {args.target} is not supported on {platform.system()}")

    version = read_version_file(os.path.join(BASE_DIR, "VERSION"))
    jolt_version = version["JOLT_VERSION"]

    source_dir = os.path.join(BASE_DIR, "_source", args.target)
    build_dir = os.path.join(BASE_DIR, "_build", args.target, "release")
    package_dir = os.path.join(BASE_DIR, "_package", args.target)
    patch_dir = os.path.join(BASE_DIR, "patches")

    if args.source_dir is not None:
        source_dir = os.path.abspath(args.source_dir)
    if args.build_dir is not None:
        build_dir = os.path.abspath(args.build_dir)

    if args.op == "build":
        mkdir_p(source_dir)
        mkdir_p(build_dir)

        with cd(BASE_DIR):
            # ソース取得
            jolt_dir = get_jolt_source(source_dir, jolt_version)

            # パッチ適用
            apply_patches(args.target, patch_dir, jolt_dir)

            # ビルド
            build_func = BUILD_FUNCS[args.target]
            build_func(jolt_dir, build_dir)

    if args.op == "package":
        if args.package_dir is not None:
            package_dir = os.path.abspath(args.package_dir)

        mkdir_p(package_dir)

        with cd(BASE_DIR):
            package_jolt(
                source_dir=source_dir,
                build_dir=build_dir,
                package_dir=package_dir,
                target=args.target,
                base_dir=BASE_DIR,
            )


if __name__ == "__main__":
    main()
