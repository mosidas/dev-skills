# ネイティブアプリの規範

iOS・Android・デスクトップのネイティブアプリと、Flutter・React Native・Compose Multiplatform などのクロスプラットフォームで、Web と異なる規則をまとめる。共通の規範(コントラスト・色だけで示さない・状態の網羅・モーションの抑制)は `checklist.md` に従い、本ファイルはネイティブ固有の規則だけを扱う。本ファイルの規則はモバイルアプリを中心とする。デスクトップのネイティブアプリは、OS の規約(macOS は Apple HIG、Windows は Fluent Design)に従い、hover とキーボード操作は `checklist.md` の Web 固有の節を準用する。

## 1. OS の部品と規約を優先する

- 画面の部品は OS 標準のコントロール(ボタン・スイッチ・ピッカー・ナビゲーション部品)を自作より先に使う。Web の見た目やレイアウトをそのまま移植しない。
- 戻る操作(iOS の左端スワイプ、Android のシステム Back)を独自のジェスチャーやハンドラで乗っ取らない。

## 2. セーフエリアと window insets

- ノッチ・ホームインジケータ・ステータスバー・IME(ソフトウェアキーボード)が覆う領域を、セーフエリアまたは window insets で避ける。固定値のパディングで代用しない。
- キーボード表示時に入力欄が隠れないよう、フォーカス中のフィールドまでスクロールするか、レイアウトをキーボードの高さぶん縮める。

## 3. 文字の拡縮

- 文字サイズは iOS の Dynamic Type、Android の `sp` 単位で指定し、システムの文字サイズ設定に追従させる。固定 `pt`・`dp` を文字サイズに使わない。
- 利用者が最大の文字サイズを選択した状態でも、主要な文言が省略・重複せずに収まるレイアウトにする。

## 4. iOS と Android で異なる項目

| 項目 | iOS | Android |
| :-- | :-- | :-- |
| タップ領域 | 44×44pt 以上 | 48×48dp 以上、間隔 8dp |
| 文字サイズ | 既定 17pt、最小 11pt、Dynamic Type に追従 | `sp` 単位、システムの font_scale に追従 |
| 戻る操作 | 左端スワイプと標準の Back ボタン | システムの predictive back を乗っ取らない |
| 最上位ナビゲーション | タブバー(2〜5 項目) | ナビゲーションバー(compact、3〜5 項目)、レール(3〜7 項目)、expanded 以上でドロワー |
| シート | 下スワイプで閉じる。Cancel は先頭、Done は末尾 | `ModalBottomSheet` は外側タップで閉じる |
| 確認・通知 | アラートは最小限にし、意図的な行為の選択はアクションシートに任せる | `Dialog` は割り込みを必要とする場面だけに使い、軽い通知は Snackbar にする |

## 5. ナビゲーションとモーダル

- 最上位ナビゲーションは、画面幅とウィンドウサイズクラスに応じて上表の部品から選ぶ。タブとドロワーを同じ階層に混在させない。
- モーダルは、確認や選択で作業を中断させるときはシートかアラート/ダイアログを使い、進行を止めない軽い通知はトースト相当の部品(Android は Snackbar)を使う。

## 6. 権限とハプティクス

- 権限は起動時に一括で要求せず、その権限を使う操作の直前に要求する。
- ハプティクスは、システムが定義する意味(成功・警告・選択の変更など)を持つ短い事象に限って使う。装飾目的の連続した振動を使わない。

## 7. 色と外観

- 色はセマンティックな名前と色ロールで定義し、ライトとダークの両方の外観で個別に確認する。
- Dynamic Color(Android の Material You)を使う設計には、Dynamic Color が使えない端末・バージョン向けの静的な代替を用意する。

## 8. クロスプラットフォーム

- Flutter・React Native・Compose Multiplatform は、スクロール物理・画面遷移・戻る操作など OS の挙動には自動で追従する。
- ナビゲーション構成や部品の選択などの設計判断は自動追従の対象外であり、対象 OS ごとに 4. の表と本ファイルの規範に合わせて選ぶ。

## 9. 検証

- Simulator(iOS)と emulator(Android)で、ライトとダークの両方の外観、システムの最大文字サイズを通して確認する。

## 10. 出典

- [Apple Human Interface Guidelines: Layout](https://developer.apple.com/design/human-interface-guidelines/layout)、[Typography](https://developer.apple.com/design/human-interface-guidelines/typography)、[Accessibility](https://developer.apple.com/design/human-interface-guidelines/accessibility)、[VoiceOver](https://developer.apple.com/design/human-interface-guidelines/voiceover)、[Tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars)、[Toolbars](https://developer.apple.com/design/human-interface-guidelines/toolbars)、[Modality](https://developer.apple.com/design/human-interface-guidelines/modality)、[Sheets](https://developer.apple.com/design/human-interface-guidelines/sheets)、[Alerts](https://developer.apple.com/design/human-interface-guidelines/alerts)、[Privacy](https://developer.apple.com/design/human-interface-guidelines/privacy)、[Dark Mode](https://developer.apple.com/design/human-interface-guidelines/dark-mode)、[Playing haptics](https://developer.apple.com/design/human-interface-guidelines/playing-haptics)、[Virtual keyboards](https://developer.apple.com/design/human-interface-guidelines/virtual-keyboards)、[Offering help](https://developer.apple.com/design/human-interface-guidelines/offering-help)
- Material Design 3(developer.android.com での裏取り)。[Accessibility for apps](https://developer.android.com/guide/topics/ui/accessibility/apps)、[Use window size classes](https://developer.android.com/develop/ui/compose/layouts/adaptive/use-window-size-classes)、[Navigation bar](https://developer.android.com/develop/ui/compose/components/navigation-bar)、[Predictive back gesture](https://developer.android.com/guide/navigation/custom-back/predictive-back-gesture)、[Edge to edge](https://developer.android.com/develop/ui/views/layout/edge-to-edge)、[Tooltips](https://developer.android.com/develop/ui/compose/components/tooltip)、[Dynamic color](https://developer.android.com/develop/ui/views/theming/dynamic-colors)
- [Flutter: Platform adaptations](https://docs.flutter.dev/platform-integration/platform-adaptations)
- [React Native: Platform-specific code](https://reactnative.dev/docs/platform-specific-code)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)(Apache-2.0)、`skill/reference/ios.md`・`android.md`・`adapt.native.md`
