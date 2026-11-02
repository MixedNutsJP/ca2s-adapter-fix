# ca2s-adapter-fix

Capcom Arcade 2nd Stadium (Steam版) が、DXGI アダプタが4個以上ある PC で起動時に `0xc0000409` で落ちる問題を直すプロキシ `dxgi.dll` です。Meta Virtual Monitor や Virtual Desktop などの仮想モニタがあると、アダプタが増えて発症します。

A proxy `dxgi.dll` that fixes the startup crash (`0xc0000409`) of Capcom Arcade 2nd Stadium (Steam) on PCs with four or more DXGI adapters, such as those with virtual monitors installed.

## 原因

ゲームは `IDXGIFactory::EnumAdapters` の結果を4要素の配列に格納しますが、ループの上限が1つずれていて、5個目をスタッククッキーの位置に書き込みます。アダプタが4個以上あるとクッキーが壊れ、関数の終わりで強制終了します。Basic Render Driver も1個に数えます。

exe は起動時に展開されるので、ファイルは書き換えられません。この DLL はゲームが `CreateDXGIFactory1` を呼んだ時点で、メモリ上の `cmp ebx, 4` を `cmp ebx, 3` に書き換えます。バグのある関数はループの直前にこの関数を呼ぶので、書き換えは必ず間に合います。書き換えるのは exe 名、イメージサイズ、対象の5バイトがすべて一致したときだけです。

## 対応バージョン

exe 1.0.0.4(Steam build 15647585)のみです。ゲームが更新されて対象のコードが変わると、何も書き換えずに動作し、元のクラッシュに戻ります。

## ビルド

Visual Studio 2022 の C++ ワークロードと CMake が必要です。

```
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

## インストール

`build\Release\dxgi.dll` をゲームフォルダ(`CapcomArcade2ndStadium.exe` と同じ場所)にコピーします。

## 確認

起動すると、ゲームフォルダに `ca2s-adapter-fix.log` ができます。

| ログの先頭 | 意味 |
|---|---|
| `OK: patched` | 修正を適用した |
| `WAIT:` | コードがまだ展開されていない、または対象のコードと一致しない。この後に `OK:` がなければ修正は未適用 |
| `SKIP:` | 対応していないバージョンなので何もしていない |
| `FAIL:` | 書き換え、または本物の dxgi.dll の読み込みに失敗した |

## アンインストール

ゲームフォルダの `dxgi.dll` と `ca2s-adapter-fix.log` を削除します。

## 構成

| パス | 内容 |
|---|---|
| `src/dxgi_proxy.cpp` | 修正の適用、本物の dxgi.dll への転送先の解決、ログ |
| `src/stubs.asm` | 全エクスポートの転送用スタブ |
| `src/dxgi.def` | エクスポート定義。序数は System32 版と同じ |
| `research/` | クラッシュダンプの解析スクリプト |

## 免責事項 / Disclaimer

**この Mod は無保証で提供されます。使用によって生じたいかなる損害についても、作者は一切の責任を負いません。** セーブデータの破損・消失、ゲームの動作不良、その他の不具合を含みます。自己責任でご使用ください。

**This mod is provided as-is, without any warranty. The author accepts no liability for any damage arising from its use,** including but not limited to corruption or loss of save data, game malfunction, or any other problem. Use it at your own risk.

この Mod は非公式のものです。株式会社カプコンとは関係ありません。

This is an unofficial mod and is not affiliated with or endorsed by Capcom Co., Ltd.

## 注意 / Notes

- ゲームのメモリを書き換えるため、ウイルス対策ソフトが誤検知することがあります。書き込むファイルはゲームフォルダの `ca2s-adapter-fix.log` だけです。
  Because it modifies the game's memory, antivirus software may flag it. The only file it writes is `ca2s-adapter-fix.log` in the game folder.
- オンラインランキングや実績への影響は確認していません。
  The effect on online rankings and achievements has not been tested.

## クレジット / Credits

**Created by MixedNuts**

## ライセンス / License

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。
See [LICENSE](LICENSE) for details.

再配布・改変は自由ですが、**著作権表示とライセンス文を必ず残してください。**
MIT ライセンスの条件です。

You are free to redistribute and modify this, but **the copyright notice and the
license text must be retained** — that is a condition of the MIT License.
