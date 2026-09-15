# piece201 求人アカウント自動投稿パイプライン｜作り方・使い方ガイド

このドキュメントは、他の人にこの仕組みを説明・引き継ぐためのガイドです。
「何を」「なぜ」「どうやって」作ったかを、手順込みでまとめています。
チャットの経緯・確定事項の細部（キャプション全文・ロードマップ・失敗談など）は
`docs/handover.md` にすべて記録されているので、詳細が必要な場合はそちらを参照してください。

---

## 1. これは何か

Instagram求人アカウント「フリーランス美容師の働き方&求人」(`@freelance_biyoshi_kyujin`)
向けに、以下を自動化した仕組みです。

- カルーセル投稿用の画像（1080×1350、6〜8枚組）をPythonで自動生成
- 生成した画像をGoogle Driveにアップロードして公開URL化
- そのURLとキャプションを使い、Metricool経由でInstagramに予約投稿

目的は、美容室piece201（東京・中目黒）のフリーランス（面貸し）スタイリスト採用。
将来的には複数サロンを扱う求人メディアに育てる構想もある（詳細は`handover.md`の1章）。

---

## 2. 全体の仕組み（パイプライン概要）

```
①ネタ決め・壁打ち（人間の確認必須）
        │
②画像生成（Python / Pillow）
   scripts/generate_all_slides.py の build_postN() 関数
        │
③Google Driveへアップロード（公開URL化）
   scripts/drive_upload.py
        │
④Metricoolで予約投稿を作成
   Metricool MCPツール（createScheduledPost）
        │
⑤Driveの一時ファイルを削除（容量節約）
   scripts/drive_upload.py delete
        │
⑥ドキュメント更新・git commit/push
   docs/handover.md に記録し、リポジトリに保存
```

**重要**：③でDriveを経由しているのは、Metricoolの`media`パラメータが
「公開URL」を要求するのに対し、画像生成した直後の状態ではローカルファイルしか
無いため。Drive上で「リンクを知っている全員が閲覧可」に設定し、そのURLを
Metricoolに渡すと、Metricool側が自動でダウンロードして`static.metricool.com`の
URLに変換・保存してくれる。取り込みが確認できたらDrive上の元ファイルは消してよい
（Metricool側にはもう保存されているため）。

---

## 3. なぜこの構成になったか（経緯の要約）

- 当初はClaude.ai（チャット単体）で画像生成しようとしたが、そのサンドボックス環境は
  ネットワークが無効化されており、画像を外部の公開URLにできなかった
- そこでClaude Code環境（ローカル実行・ネットワーク利用可）に移行し、
  Python（Pillow）で画像生成 → Google Drive → Metricoolという自動化パイプラインを
  ゼロから構築した
- Google Driveのアップロードは、当初サービスアカウント方式を検討したが、
  個人の無料Gmailアカウントにはサービスアカウント用のストレージクォータが無く失敗。
  そのため、アカウント本人（増田氏）の権限を借りるOAuth 2.0方式に切り替えた
- Metricoolへの投稿作成は、Claude Code環境に接続済みのMetricool MCPツールを
  直接呼び出す方式にしたため、Metricool APIキーの発行・管理が不要だった

---

## 4. 必要なもの（環境・アカウント）

| 項目 | 内容 |
|---|---|
| Metricoolアカウント | 無料プランで可。Instagramビジネス/クリエイターアカウントと連携済みであること |
| InstagramとFacebookページの連携 | Meta仕様上必須（下記6章参照） |
| Googleアカウント（Drive） | 画像アップロード用。個人の無料Gmailアカウントで可 |
| Google Cloud OAuthクライアント | Drive APIを使うためのOAuthクライアントID・シークレット |
| Claude Code環境 | Metricool MCPサーバーが接続されている必要あり |
| フォント | Noto Serif CJK / Noto Sans CJK（`/usr/share/fonts/opentype/noto/`に配置） |

---

## 5. ファイル構成

```
biyoshi_kyujin/
├── docs/
│   ├── handover.md          # 経緯・確定事項・全キャプション・ロードマップ（詳細版）
│   └── guide.md             # このファイル（手順ガイド）
├── scripts/
│   ├── generate_all_slides.py   # 画像生成スクリプト本体（build_postN()を追加していく）
│   ├── drive_upload.py          # Driveアップロード/削除
│   ├── oauth_step1_get_auth_url.py  # OAuth認証URL発行（初回・再認証時）
│   └── oauth_step2_exchange_code.py # OAuth認証コード→トークン交換
├── assets/
│   ├── materials/           # 素材（ロゴ・ベージュ背景・店内写真）
│   └── posts/postN/         # 投稿ごとの最終画像(post N_final_slideM.jpg)とcaption.txt
├── config/
│   └── drive_config.json    # プロジェクトID・Drive保存先フォルダID・Metricool Brand ID
└── secrets/                 # 機密情報（.gitignore対象、コミットしない）
    ├── oauth_client_secret.json   # Google Cloud OAuthクライアント情報
    └── drive_oauth_token.json     # 発行済みリフレッシュトークン
```

`assets/posts/postN/`には最終画像(`postN_final_slideM.jpg`)と`caption.txt`のみを
コミットする。生成過程の背景画像(`postN_bg_*.jpg`)は中間ファイルなのでコミットしない
（生成のたびに作られては削除される想定）。

---

## 6. 初回セットアップ手順

### 6-1. Metricool × Instagram連携
InstagramをMetricool経由で自動投稿するには、Meta仕様上
「Instagramがビジネス/クリエイターアカウントであること」と
「Facebookページとリンクされていること」の両方が必須。

1. Facebookアプリで新規にFacebookページを作成（アカウント名義で）
2. **PCブラウザで**Facebookにログインし、対象のFacebookページに切り替え
3. ページの「設定」→「コネクテッドエクスペリエンス」→「リンク済みのプロフィール」→
   「アカウントを追加」→「Instagramアカウントを追加」から連携
4. Metricool側で「Connect via Facebook」を選択し連携

**教訓**：モバイルアプリ経由の連携は「profile is not a Business/Creator」等の
エラーが出やすく不安定。PCブラウザから行うと成功しやすい。

### 6-2. Google Drive OAuthのセットアップ
1. Google Cloud Consoleでプロジェクトを作成し、Drive APIを有効化
2. OAuthクライアントID（デスクトップアプリ種別）を作成し、
   `secrets/oauth_client_secret.json`として保存
3. アップロード先のGoogle Driveフォルダを作成し、フォルダIDを
   `config/drive_config.json`の`upload_folder_id`に設定
4. 以下の認証フローを実行（初回のみ、また後述のトークン失効時にも再実行）：

```bash
# ①認証URLを発行
python3 scripts/oauth_step1_get_auth_url.py
# → 表示されたURLをブラウザで開き、Googleアカウントでログイン・許可する

# ②許可後、http://localhost/?state=...&code=...&scope=... という
#   「このサイトにアクセスできません」エラー画面に遷移する（正常な動作）。
#   ブラウザのアドレスバーに表示されているURL全文をコピーする。

# ③そのURLをトークンに交換する（http URLなのでINSECURE_TRANSPORTフラグが必要）
OAUTHLIB_INSECURE_TRANSPORT=1 python3 scripts/oauth_step2_exchange_code.py "<②でコピーしたURL全文>"
# → secrets/drive_oauth_token.json にリフレッシュトークンが保存される
```

### 6-3. Metricool MCPの接続
Claude Code環境側でMetricool MCPサーバーを接続し、`.claude/settings.json`に
以下を設定して読み取り系ツール呼び出しの許可プロンプトを省略する：

```json
{
  "permissions": {
    "allow": ["mcp__Metricool_Social_Media_Management__*"]
  }
}
```

※ 実際に投稿を作成・公開する書き込み系アクション（`createScheduledPost`）は、
外部への不可逆な公開操作のため、プラットフォーム側の安全確認プロンプトが
別途入る。これはリポジトリ設定では消せない仕様。

---

## 7. 新しい投稿を1本作る手順（日常運用）

### ステップ1：ネタ決め・壁打ち（画像生成の前に必ず行う）
1. 次のネタを`docs/handover.md`の「予定（優先順）」ロードマップから選ぶ、
   または新規に提案する
2. スライド構成案（各枚の見出し・要旨）とキャプション全文を先に提示する
3. 具体的な数字（税制・控除額・材料費率など）を含む場合は、必ずWeb検索で
   裏取りしてから提示する（記憶やアシスタントの推測だけで数字を出さない）
4. 発注者（増田氏）の確認・OKを待つ。修正指示があれば反映して再提示する
5. **OKが出るまで画像生成に着手しない**（最重要ルール）

### ステップ2：画像生成
`scripts/generate_all_slides.py`に`build_postN()`という関数を追加する。
既存の`build_post7()`〜`build_post16()`をコピーして書き換えるのが早い。

使う共通パーツ：
- `draw_cover_slide()`：表紙（タイトル+サブタイトル）
- `draw_title_body_slide()`：見出し+本文（①②③...の各項目に使う定番レイアウト）
- `draw_comparison_row_slide()`：「A vs B」の比較表スライド
- `draw_closing_slide()`：まとめ+締め（DM誘導）を1枚に統合したスライド
- `fit_font()`：長い文字列が画面端からはみ出さないよう自動でフォントサイズを縮小する安全弁（新しいテキストを入れるときは特に意識しなくてよい、自動で効く）

生成コマンド例：
```bash
python3 -c "
import scripts.generate_all_slides as g
g.build_post17(materials_dir='./assets/materials', out_dir='./assets/posts/post17')
print('post17 done')
"
```

生成後、必ず数枚〜全枚を目視確認する（Readツールで画像を開いて確認）。
特に長いタイトル・比較表・締めスライドは文字がはみ出していないか要チェック。

### ステップ3：キャプション保存
`assets/posts/postN/caption.txt`にキャプション全文を保存する。

### ステップ4：投稿頻度・タイミングの決定
- 1日1本ペースを守る（複数本まとめてネタができても小出しにする）
- Metricoolの`getScheduledPosts`で既存の予約状況を確認し、次に空いている日を選ぶ
- `getBestTimeToPostByNetwork`でその曜日のベストタイム（エンゲージメント予測値が
  最大の時間帯）を取得し、その時刻に設定する（曜日固定ではない）
- **予約時刻は必ず「今から20分以上先」に設定する**。Driveアップロード等の準備に
  数分かかるため、余裕が短いと`createScheduledPost`実行時に指定時刻が過去になり
  「Publication date cannot be in the past」エラーで失敗し、やり直しで許可プロンプトが
  2回連続で出てしまう

### ステップ5：Google Driveへアップロード
```bash
OAUTHLIB_INSECURE_TRANSPORT=1 python3 scripts/drive_upload.py \
  assets/posts/post17/post17_final_slide1.jpg \
  assets/posts/post17/post17_final_slide2.jpg \
  ... \
  assets/posts/post17/post17_final_slideN.jpg
```
出力される`{ファイルID}\t{URL}`の一覧を控えておく（あとで削除する際にファイルIDを使う）。

### ステップ6：Metricoolで予約投稿を作成
Metricool MCPツール`createScheduledPost`を呼び出す。主なパラメータ：
- `blogId`：`6852890`（Metricool Brand ID、`config/drive_config.json`にも記載）
- `date` / `publicationDate`：ステップ4で決めた日時（Asia/Tokyo）
- `info.text`：キャプション全文
- `info.media`：ステップ5で得たDriveの公開URL配列（順番＝スライド順）
- `info.providers`：`[{"network": "instagram"}]`
- `info.instagramData`：`{"type": "POST", "showReelOnFeed": true}`
- `info.autoPublish`：`true`（指定時刻に自動公開）

**ここでは絶対に「投稿して」等の明確な指示がない限り予約・公開操作を
行わないこと**（壁打ち→OK→画像化→OKまでは進めてよいが、投稿の実行は別途承認が必要）。

### ステップ7：Metricool取り込みの確認とDrive削除
`createScheduledPost`のレスポンスの`media`が`https://static.metricool.com/...`の
URLに変換されていれば、Metricool側への取り込みは完了。その後Drive上の元ファイルを
削除して容量を節約する：
```bash
OAUTHLIB_INSECURE_TRANSPORT=1 python3 scripts/drive_upload.py delete <ファイルID1> <ファイルID2> ...
```

### ステップ8：記録・git管理
1. `docs/handover.md`を更新する：
   - 「投稿済みキャプション全文」セクションに新しいキャプションを追記
   - 「各投稿の画像構成」セクションにスライド構成の要約を追記
   - 「予定（優先順）」ロードマップの該当項目を「投稿予約済み」に更新し、次の項目を明示
   - 「Metricool自動投稿システムの状況と課題」セクションに、投稿ID・予約日時などの
     実績を1行で追記
2. 生成過程の中間ファイル（`postN_bg_*.jpg`）を削除する
3. `git add` → `git commit` → `git push` でリポジトリに保存する

---

## 8. デザイン・運用ルール（要点）

- 見出し：Noto Serif CJK／本文：Noto Sans CJK。テキストは中央寄せ・上下中央配置
- 色分け：雇用・業務委託＝グレー系、フリーランス・面貸し＝ロゴ赤系
- 「まとめ」と「締め（DM誘導）」は1枚に統合する
- 絵文字は画像内に描画すると文字化けするため使わない（キャプション本文でのみ使用）
- キャプションのハッシュタグは5個まで
- 本文はサロン中立の情報発信に徹し、piece201への言及は最後のスライド・キャプションの
  締めのみに留める（自社アピールを本文中で挟まない）
- 具体的な数字（税制・控除額など）は必ずWeb検索で裏取りしてから使う
- 業界用語の違いに注意：面貸し（完全歩合60〜70%・新規客なし・自由出勤）／
  業務委託（歩合40〜50%・時間拘束あり・サロンが新規集客）／
  雇用（固定給+歩合10〜20%・拘束最大）。piece201は面貸し（指名売上歩合70%）

詳細な数値・確定事項は`docs/handover.md`の6章を参照。

---

## 9. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `Publication date cannot be in the past` | 予約時刻までの余裕が短すぎた | 20分以上先の時刻に設定し直す |
| `invalid_grant: Token has been expired or revoked` | Google DriveのOAuthリフレッシュトークンが失効 | 本ガイド6-2章の認証フローを再実行し、`secrets/drive_oauth_token.json`を更新する |
| Metricool予約のたびに許可プロンプトが2回出る | 上記の日付エラーで1回失敗→リトライしたため、実際に2回ツールを呼んでいる | 20分以上先の時刻を最初から指定すれば1回で済む |
| 画像の文字が画面端からはみ出す | フォントサイズが大きすぎる／`fit_font()`を通していないテキスト描画を追加した | 新しいテキスト描画は既存の`draw_*_slide()`関数を再利用する（`fit_font()`が自動で効く） |
| 画像内の絵文字が「✕」になる | Noto CJKフォントに絵文字グリフが無い | 画像内では絵文字を使わない。キャプション本文でのみ使う |
| Instagram連携で「profile is not a Business/Creator」エラー | モバイルアプリ経由の連携が不安定 | PCブラウザから連携操作をやり直す |

---

## 10. さらに詳しく知りたいとき

- **経緯・背景・確定事項の全て**（プロジェクトの目的、増田氏の経歴、piece201の詳細、
  アカウント設計の紆余曲折、投稿済み全キャプション、今後のネタロードマップ、
  過去の失敗談と教訓）→ `docs/handover.md`
- **画像生成のコード詳細**→ `scripts/generate_all_slides.py`のコメント・関数定義
