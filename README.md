# ca2s-adapter-fix

Capcom Arcade 2nd Stadium (Steam版) が、DXGI アダプタが4個以上ある PC で起動時に `0xc0000409` で落ちる問題を直す Mod です。Meta Virtual Monitor や Virtual Desktop などの仮想モニタがあると、アダプタが増えて発症します。

A mod that fixes the startup crash (`0xc0000409`) of Capcom Arcade 2nd Stadium (Steam) on PCs with four or more DXGI adapters, such as those with virtual monitors installed.

## 原因

ゲームは `IDXGIFactory::EnumAdapters` の結果を4要素の配列に格納しますが、ループの上限が1つずれていて、5個目をスタッククッキーの位置に書き込みます。アダプタが4個以上あるとクッキーが壊れ、関数の終わりで強制終了します。Basic Render Driver も1個に数えます。

exe は起動時に展開されるので、ファイルは書き換えられません。この Mod はゲームが `CreateDXGIFactory1` を呼んだ時点で、メモリ上の `cmp ebx, 4` を `cmp ebx, 3` に書き換えます。バグのある関数はループの直前にこの関数を呼ぶので、書き換えは必ず間に合います。書き換えるのは、イメージサイズと対象の5バイトが一致したときだけです。

## 対応バージョン

exe 1.0.0.4(Steam build 15647585)のみです。ゲームが更新されて対象のコードが変わると、何も書き換えずに動作し、元のクラッシュに戻ります。

## 導入 / Installation

1. 先に [MixedNuts Mod Loader](https://github.com/MixedNutsJP/ca2s-mod-loader) を導入します。`dxgi.dll` と `MixedNuts` フォルダを、ゲームのルート(`CapcomArcade2ndStadium.exe` と同じ場所)にコピーします
2. この Mod の `MixedNuts` フォルダを、ゲームのルートにそのままコピーします。ローダーの `MixedNuts` フォルダに統合されます

1. First install the [MixedNuts Mod Loader](https://github.com/MixedNutsJP/ca2s-mod-loader): copy its `dxgi.dll` and `MixedNuts` folder into the game's root directory (the folder containing `CapcomArcade2ndStadium.exe`).
2. Copy this mod's `MixedNuts` folder into the game's root directory. It merges into the loader's `MixedNuts` folder.

```
Capcom Arcade 2nd Stadium/
  CapcomArcade2ndStadium.exe
  dxgi.dll                                  <- MixedNuts Mod Loader
  MixedNuts/MixedNutsLoader.dll             <- MixedNuts Mod Loader
  MixedNuts/Mods/adapterfix/adapterfix.dll  <- この Mod / this mod
  MixedNuts/Mods/adapterfix/adapterfix.log  <- 起動時に生成 / generated at launch
```

単体の `dxgi.dll` だった旧版(1.0.0)を入れている場合は、ローダーの `dxgi.dll` で上書きし、ゲームのルートの `ca2s-adapter-fix.log` を削除してください。

If you have the old single-DLL version (1.0.0), overwrite its `dxgi.dll` with the loader's and delete `ca2s-adapter-fix.log` from the game's root.

## 確認 / Checking

起動後、`MixedNuts\loader.log` に `[OK] adapterfix: loaded` が、`MixedNuts\Mods\adapterfix\adapterfix.log` に次のいずれかが記録されます。

After launching, `MixedNuts\loader.log` shows `[OK] adapterfix: loaded`, and `MixedNuts\Mods\adapterfix\adapterfix.log` shows one of the following.

| ログの先頭 / Log line | 意味 / Meaning |
|---|---|
| `OK: patched` | 修正を適用した / The fix was applied |
| `WAIT:` | コードがまだ展開されていない、または対象のコードと一致しない。この後に `OK:` がなければ修正は未適用 / The code is not unpacked yet or does not match. Without a later `OK:`, the fix was not applied |
| `SKIP:` | 対応していないバージョンなので何もしていない / Unsupported game version; nothing was changed |
| `FAIL:` | 書き換えに失敗した / Patching failed |

## 削除 / Uninstall

`MixedNuts\Mods\adapterfix` フォルダを削除します。ローダーごと外す場合は、`dxgi.dll` と `MixedNuts` フォルダを削除します。ゲームのファイルは一切変更しません。

Delete the `MixedNuts\Mods\adapterfix` folder. To remove the loader as well, delete `dxgi.dll` and the `MixedNuts` folder. No game files are modified.

## ビルド / Build

Visual Studio 2022 の C++ ワークロードと CMake が必要です。ローダーの API は submodule の `mod-loader` から取り込みます。

Requires the Visual Studio 2022 C++ workload and CMake. The loader's API comes from the `mod-loader` submodule.

```
git clone --recursive https://github.com/MixedNutsJP/ca2s-adapter-fix.git
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
cmake --install build --config Release --prefix dist
```

`dist\` に、ゲームのルートへそのままコピーできる `MixedNuts` フォルダが出力されます。clone 済みの場合は `git submodule update --init` を実行してください。

`dist\` receives the `MixedNuts` folder to copy into the game's root. In an existing clone, run `git submodule update --init`.

## 構成

| パス | 内容 |
|---|---|
| `src/adapterfix.cpp` | `adapterfix.dll`。修正本体 |
| `mod-loader/` | [MixedNuts Mod Loader](https://github.com/MixedNutsJP/ca2s-mod-loader)(submodule) |
| `research/` | クラッシュダンプの解析スクリプト |

## 免責事項 / Disclaimer

**この Mod は無保証で提供されます。使用によって生じたいかなる損害についても、作者は一切の責任を負いません。** セーブデータの破損・消失、ゲームの動作不良、その他の不具合を含みます。自己責任でご使用ください。

**This mod is provided as-is, without any warranty. The author accepts no liability for any damage arising from its use,** including but not limited to corruption or loss of save data, game malfunction, or any other problem. Use it at your own risk.

この Mod は非公式のものです。株式会社カプコンとは関係ありません。

This is an unofficial mod and is not affiliated with or endorsed by Capcom Co., Ltd.

## 注意 / Notes

- ゲームのメモリを書き換えるため、ウイルス対策ソフトが誤検知することがあります。書き込むファイルは `MixedNuts\Mods\adapterfix\adapterfix.log` だけです。
  Because it modifies the game's memory, antivirus software may flag it. The only file it writes is `MixedNuts\Mods\adapterfix\adapterfix.log`.
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
