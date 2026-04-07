# jolt-build

[Jolt Physics](https://github.com/jrouwe/JoltPhysics) をソースからマルチプラットフォーム向けにビルドし、GitHub Releases で配布するプロジェクト。

## 対応プラットフォーム

| ターゲット | アーキテクチャ | ランナー |
|:---|:---|:---|
| macOS | arm64 | `macos-latest` |
| iOS device | arm64 | `macos-latest` |
| iOS simulator | arm64 | `macos-latest` |
| Android | arm64-v8a | `ubuntu-latest` |

## ダウンロード

プリビルトバイナリは [Releases](../../releases) ページから取得できる。

各リリースに含まれる成果物:

```
jolt-v{version}-macos_arm64.tar.gz
jolt-v{version}-ios_device_arm64.tar.gz
jolt-v{version}-ios_simulator_arm64.tar.gz
jolt-v{version}-android_arm64_v8a.tar.gz
```

各アーカイブの構成:

```
jolt/
├── lib/          # 静的ライブラリ (.a)
├── include/      # ヘッダーファイル
├── LICENSE
├── NOTICE
└── VERSIONS
```

## ローカルビルド

必要なもの:
- Python 3
- CMake, Ninja
- Xcode (macOS/iOS ターゲット)
- Android NDK (Android ターゲット、`ANDROID_HOME` の設定が必要)

```bash
# ビルド
python3 run.py build <target>

# パッケージング
python3 run.py package <target>
```

ターゲット: `macos_arm64`, `ios_device_arm64`, `ios_simulator_arm64`, `android_arm64_v8a`

## CI/CD

GitHub Actions でビルドを自動化している。バージョンタグ (`v*`) を push すると自動で Release が作成される。

`workflow_dispatch` で個別プラットフォームの手動ビルドも可能。

## バージョニング

Jolt Physics のアップストリームバージョンに追従する。`VERSION` ファイルで管理:

- `JOLT_VERSION` - Jolt Physics のバージョン
- `JOLT_COMMIT` - checkout する git タグ
- `JOLT_BUILD_VERSION` - リビルド用サフィックス付きバージョン (例: `5.5.0.0`)

## ライセンス

Apache License 2.0

このプロジェクトが利用しているソフトウェアのライセンスの詳細は [NOTICE](NOTICE) を参照。
