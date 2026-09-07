"""
piece201 求人アカウント Instagram投稿画像 生成スクリプト（まとめ版）
PIL/Pillowを使用。Noto Serif CJK / Noto Sans CJK フォントが必要。

デザインルール（詳細はナレッジ移行書を参照）:
- 見出し: Noto Serif CJK, 本文: Noto Sans CJK
- 色分け: 雇用/業務委託=グレー系(95,100,112), フリーランス/面貸し=ロゴ赤系(178,60,38)
- テキストは中央寄せ、コンテンツ全体を画面内で上下中央配置
- 縦位置は「各行の高さを計算して積み上げる」方式で決定する(手動の決め打ち数値にしない)
- キャンバスサイズ: 1080x1350 (Instagram 4:5)
- 素材: ロゴ(logo watermark), 店内写真, ベージュレザーテクスチャ(表紙用)

使い方:
  SRC ディレクトリに素材画像を置き、OUT ディレクトリに出力される。
  各 post の背景生成 → 各 post のテキスト描画、の2段階で構成。
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random

# ==================== 共通設定 ====================
SRC = "./materials"   # 素材画像を置くディレクトリ（ロゴ・店内写真・ベージュ背景）
OUT = "./output"      # 生成物の出力先

FONT_SANS_REG  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_SANS_MED  = "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc"
FONT_SANS_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_SERIF_LIGHT = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Light.ttc"
FONT_SERIF_MED   = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Medium.ttc"
FONT_SERIF_SEMI  = "/usr/share/fonts/opentype/noto/NotoSerifCJK-SemiBold.ttc"

TW, TH = 1080, 1350  # Instagram 4:5

DARK = (40, 37, 33)     # 見出し・本文の基本色
GRAY = (135, 132, 126)  # 補足テキストの色
EMP  = (95, 100, 112)   # 雇用・業務委託カラー（グレー系）
MG   = (178, 60, 38)    # フリーランス・面貸しカラー（ロゴ赤系）


def F(path, size):
    """フォントオブジェクトを返す"""
    return ImageFont.truetype(path, size)


def draw_c(d, cx, y, text, font, fill):
    """中央寄せでテキストを1行描画する（anchor='ma' = 水平中央・垂直上端基準）"""
    d.text((cx, y), text, font=font, fill=fill, anchor="ma")


def lh(font, mult=1.3):
    """フォントサイズから1行分の高さを計算する（積み上げ配置の基準値）"""
    return int(font.size * mult)


def cover_crop(img, tw, th):
    """画像を指定アスペクト比(tw:th)でセンタークロップする"""
    iw, ih = img.size
    target_ratio = tw / th
    cur_ratio = iw / ih
    if cur_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        left = (iw - new_w) // 2
        img = img.crop((left, 0, left + new_w, ih))
    else:
        new_h = int(iw / target_ratio)
        top = (ih - new_h) // 2
        img = img.crop((0, top, iw, top + new_h))
    return img.resize((tw, th), Image.LANCZOS)


# ==================== 背景生成 ====================

def make_cover_bg(beige_path, out_path):
    """表紙用: ベージュレザーテクスチャを4:5にクロップ"""
    beige = Image.open(beige_path).convert("RGB")
    bg = cover_crop(beige, TW, TH)
    bg.save(out_path, quality=93)


def make_logo_bg(logo_path, base_shade, seed, out_path, watermark_opacity=20):
    """
    本文用: コンクリート調のシンプルなグレー背景に、ロゴを薄く透かして中央配置する。
    base_shade: ベースの明度 (220前後を推奨)
    seed: ノイズ乱数のシード（複数枚作る際に少しずつ質感を変えるため）
    """
    random.seed(seed)
    bg = Image.new("RGB", (TW, TH), (base_shade, base_shade - 2, base_shade - 6))
    draw = ImageDraw.Draw(bg)
    for _ in range(3000):
        x = random.randint(0, TW - 1)
        y = random.randint(0, TH - 1)
        shade = random.randint(-6, 6)
        b = base_shade + shade
        draw.point((x, y), fill=(b, b - 2, b - 5))
    bg = bg.filter(ImageFilter.GaussianBlur(1.2))

    bg = bg.convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")
    lw = int(TW * 0.5)
    lh_ = int(logo.size[1] * (lw / logo.size[0]))
    logo_r = logo.resize((lw, lh_), Image.LANCZOS).convert("RGBA")

    # ロゴの白背景を透過にしてから、指定の透明度で重ねる
    data = logo_r.getdata()
    new_data = []
    for r, g, b, a in data:
        if r > 235 and g > 235 and b > 235:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, watermark_opacity))
    logo_r.putdata(new_data)

    px = (TW - lw) // 2
    py = (TH - lh_) // 2
    bg.alpha_composite(logo_r, (px, py))
    bg.convert("RGB").save(out_path, quality=93)


def make_photo_bg(photo_path, out_path, darken_factor=0.5, crop_offset_ratio=0.5):
    """
    店内写真などの実写を暗めのフィルターをかけて背景にする。
    crop_offset_ratio: 0=左端クロップ, 0.5=中央クロップ, 1=右端クロップ
    """
    from PIL import ImageEnhance
    photo = Image.open(photo_path).convert("RGB")
    iw, ih = photo.size
    crop_w = int(ih * (TW / TH))
    max_offset = iw - crop_w
    left = int(max_offset * crop_offset_ratio)
    cropped = photo.crop((left, 0, left + crop_w, ih)).resize((TW, TH), Image.LANCZOS)
    darkened = ImageEnhance.Brightness(cropped).enhance(darken_factor)
    darkened.save(out_path, quality=93)


# ==================== テキスト描画: 汎用パーツ ====================

def draw_title_body_slide(bg_path, out_path, title, body_lines,
                           title_color=DARK, body_color=GRAY,
                           title_font=None, body_font=None):
    """
    「見出し + 本文複数行」の定番レイアウト。
    全体を画面の上下中央に配置し、行間は各フォントサイズから自動計算する。
    """
    img = Image.open(bg_path).convert("RGB")
    d = ImageDraw.Draw(img)
    cx = TW // 2

    f_title = title_font or F(FONT_SERIF_SEMI, 46)
    f_body = body_font or F(FONT_SANS_MED, 34)

    title_h = lh(f_title)
    body_h = lh(f_body, 1.45)

    total = title_h + 70 + body_h * len(body_lines)
    start_y = int((TH - total) / 2)

    y = start_y
    if title:
        draw_c(d, cx, y, title, f_title, title_color)
        y += title_h + 70
    for line in body_lines:
        draw_c(d, cx, y, line, f_body, body_color)
        y += body_h

    img.save(out_path, quality=93)


def draw_cover_slide(bg_path, out_path, lines, subtitle=None):
    """表紙スライド用: タイトル行(複数行可) + 小さいサブタイトル"""
    img = Image.open(bg_path).convert("RGB")
    d = ImageDraw.Draw(img)
    cx = TW // 2
    f_t = F(FONT_SERIF_MED, 58)
    t_h = lh(f_t, 1.35)

    total = t_h * len(lines)
    start_y = int((1230 - total) / 2) + 60
    y = start_y
    for line in lines:
        draw_c(d, cx, y, line, f_t, DARK)
        y += t_h

    if subtitle:
        draw_c(d, cx, TH - 95, subtitle, F(FONT_SANS_REG, 26), GRAY)

    img.save(out_path, quality=93)


def draw_comparison_row_slide(bg_path, out_path, title, rows, left_label, right_label):
    """
    「A vs B」比較表スライド。rows は
    [(label, left_val1, left_val2_or_None, right_val1, right_val2_or_None), ...]
    val2 がある場合は「小さい説明 + 大きい強調数字」の2段組で描画する。
    """
    img = Image.open(bg_path).convert("RGB")
    d = ImageDraw.Draw(img)
    cx = TW // 2

    ft = F(FONT_SERIF_SEMI, 56)
    f_head = F(FONT_SERIF_MED, 46)
    f_label = F(FONT_SANS_MED, 30)
    f_val1 = F(FONT_SANS_MED, 34)
    f_val_small = F(FONT_SANS_REG, 26)
    f_val_big = F(FONT_SANS_MED, 46)

    title_h = lh(ft)
    head_h = lh(f_head)
    row_h = 168
    total = title_h + 55 + head_h + 45 + row_h * len(rows)
    start_y = int((TH - total) / 2)

    y = start_y
    draw_c(d, cx, y, title, ft, DARK)
    y += title_h + 55

    label_cx, left_cx, right_cx = 175, 490, 850
    draw_c(d, left_cx, y, left_label, f_head, EMP)
    draw_c(d, right_cx, y, right_label, f_head, MG)
    y += head_h + 30
    d.line([(80, y), (TW - 80, y)], fill=(195, 192, 185), width=1)
    y += 45

    for label, a1, a2, b1, b2 in rows:
        row_center = y + row_h / 2 - 25
        draw_c(d, label_cx, row_center, label, f_label, GRAY)
        if a2:
            draw_c(d, left_cx, row_center - 10, a1, f_val_small, EMP)
            draw_c(d, left_cx, row_center + lh(f_val_small, 1.15), a2, f_val_big, EMP)
        else:
            draw_c(d, left_cx, row_center + 12, a1, f_val1, EMP)
        if b2:
            draw_c(d, right_cx, row_center - 10, b1, f_val_small, MG)
            draw_c(d, right_cx, row_center + lh(f_val_small, 1.15), b2, f_val_big, MG)
        else:
            draw_c(d, right_cx, row_center + 12, b1, f_val1, MG)
        y += row_h
        d.line([(80, y), (TW - 80, y)], fill=(210, 207, 200), width=1)

    img.save(out_path, quality=93)


def draw_closing_slide(bg_path, out_path, lead_lines, body_lines, dm_line, footer="piece201"):
    """締めスライド定型: リード文 + 本文 + DM誘導 + フッター"""
    img = Image.open(bg_path).convert("RGB")
    d = ImageDraw.Draw(img)
    cx = TW // 2

    f_lead = F(FONT_SERIF_MED, 40)
    f_body = F(FONT_SANS_MED, 34)
    f_foot = F(FONT_SANS_MED, 28)

    lead_h = lh(f_lead, 1.4)
    body_h = lh(f_body, 1.4)
    dm_h = lh(f_body, 1.3)

    total = lead_h * len(lead_lines) + 65 + body_h * len(body_lines) + 70 + dm_h
    start_y = int((TH - total) / 2) - 20
    y = start_y
    for line in lead_lines:
        draw_c(d, cx, y, line, f_lead, DARK)
        y += lead_h
    y += 65
    for line in body_lines:
        draw_c(d, cx, y, line, f_body, GRAY)
        y += body_h
    y += 70
    draw_c(d, cx, y, dm_line, f_body, MG)

    draw_c(d, cx, TH - 95, footer, f_foot, GRAY)
    img.save(out_path, quality=93)


# ==================== post7「フリーランスの保険と年金の話」の実例 ====================
# 8枚構成。他の post も同じ関数群の組み合わせで作成している。

def build_post7(materials_dir=SRC, out_dir=OUT):
    import os
    os.makedirs(out_dir, exist_ok=True)

    beige_path = f"{materials_dir}/beige_texture.png"   # piece201_-_1.png 相当
    logo_path = f"{materials_dir}/logo.jpeg"             # IMG_0304.jpeg 相当

    # 背景生成
    make_cover_bg(beige_path, f"{out_dir}/post7_bg_cover.jpg")
    for i in range(2, 9):
        make_logo_bg(logo_path, base_shade=224, seed=i + 100,
                     out_path=f"{out_dir}/post7_bg_slide{i}.jpg")

    # 1枚目: 表紙
    draw_cover_slide(
        f"{out_dir}/post7_bg_cover.jpg", f"{out_dir}/post7_final_slide1.jpg",
        ["フリーランスの", "保険と年金の話"],
        subtitle="piece201 / Nakameguro, Tokyo"
    )

    # 2枚目: 導入
    draw_title_body_slide(
        f"{out_dir}/post7_bg_slide2.jpg", f"{out_dir}/post7_final_slide2.jpg",
        title=None,
        body_lines=[
            "フリーランスになると、", "保険も年金も自分で選ぶ必要があります。", "",
            "会社員時代は当たり前だった制度、", "仕組みを知っておくと安心です。"
        ],
        body_color=DARK
    )

    # 3枚目: 選択肢1 美容師国保組合
    draw_title_body_slide(
        f"{out_dir}/post7_bg_slide3.jpg", f"{out_dir}/post7_final_slide3.jpg",
        title="①美容師国保組合",
        body_lines=[
            "美容師には、業界向けの", "国民健康保険組合という選択肢もあります。", "",
            "ただし加入には条件があり、", "事業所の所在地・自分の居住地、",
            "両方が対象エリア内である必要があります。", "",
            "組合は地域ごとに存在するため、", "今働いているサロンがどのエリアか",
            "確認しておくのがおすすめです。"
        ]
    )

    # 4枚目: 選択肢2 国民健康保険
    draw_title_body_slide(
        f"{out_dir}/post7_bg_slide4.jpg", f"{out_dir}/post7_final_slide4.jpg",
        title="②国民健康保険",
        body_lines=[
            "条件が合わない場合や、", "組合の資格を失った場合は、",
            "一般的な国民健康保険に加入します。", "",
            "保険料は前年の所得によって決まり、", "自治体の窓口で手続きをします。"
        ]
    )

    # 5枚目: 選択肢3 社会保険
    draw_title_body_slide(
        f"{out_dir}/post7_bg_slide5.jpg", f"{out_dir}/post7_final_slide5.jpg",
        title="③社会保険",
        body_lines=[
            "社会保険に加入する方法もあります。", "",
            "法人化して社会保険に加入する方法のほか、", "個人事業主のまま加入できる",
            "サービスを利用する方法もあります。"
        ]
    )

    # 6枚目: 国民年金の手続き
    draw_title_body_slide(
        f"{out_dir}/post7_bg_slide6.jpg", f"{out_dir}/post7_final_slide6.jpg",
        title=None,
        body_lines=[
            "会社員時代の厚生年金は、", "退職しても自動的には切り替わりません。", "",
            "退職日の翌日から14日以内に、", "自分で市区町村役場で",
            "国民年金への切り替え手続きが必要です。", "",
            "忘れると未納期間が発生し、", "将来の受給額に影響することもあります。"
        ],
        body_color=DARK
    )

    # 7枚目: 国民年金の金額・将来性
    draw_title_body_slide(
        f"{out_dir}/post7_bg_slide7.jpg", f"{out_dir}/post7_final_slide7.jpg",
        title=None,
        body_lines=[
            "国民年金は、厚生年金より", "支払う金額は少なくなりますが、",
            "その分もらえる年金額も少なくなるのが実情。", "",
            "少子高齢化が進む中、", "正直この先どうなるかは不透明。", "",
            "とはいえ、国民の義務。", "きちんと納める必要があります。"
        ],
        body_color=DARK
    )

    # 8枚目: 締め
    draw_closing_slide(
        f"{out_dir}/post7_bg_slide8.jpg", f"{out_dir}/post7_final_slide8.jpg",
        lead_lines=["保険も年金も、正直ひとりで", "調べるのは大変ですよね。"],
        body_lines=["piece201では、こうした手続き面も", "一緒に考えながらサポートしています。"],
        dm_line="わからないことは、DMで気軽に聞いてください"
    )


# ==================== post8「面貸し先の選び方」 ====================
# 8枚構成。post7 と同じ関数群の組み合わせで作成。

def build_post8(materials_dir=SRC, out_dir=OUT):
    import os
    os.makedirs(out_dir, exist_ok=True)

    beige_path = f"{materials_dir}/beige_texture.png"
    logo_path = f"{materials_dir}/logo.jpeg"

    # 背景生成
    make_cover_bg(beige_path, f"{out_dir}/post8_bg_cover.jpg")
    for i in range(2, 9):
        make_logo_bg(logo_path, base_shade=224, seed=i + 200,
                     out_path=f"{out_dir}/post8_bg_slide{i}.jpg")

    # 1枚目: 表紙
    draw_cover_slide(
        f"{out_dir}/post8_bg_cover.jpg", f"{out_dir}/post8_final_slide1.jpg",
        ["面貸し先の選び方", "5つのチェックポイント"],
        subtitle="piece201 / Nakameguro, Tokyo"
    )

    # 2枚目: 導入
    draw_title_body_slide(
        f"{out_dir}/post8_bg_slide2.jpg", f"{out_dir}/post8_final_slide2.jpg",
        title=None,
        body_lines=[
            "面貸しは、一度契約すると", "途中で変えるのは大変。", "",
            "契約前に見ておきたい、", "5つのチェックポイントをまとめました。"
        ],
        body_color=DARK
    )

    # 3枚目: ①契約内容の明確さ
    draw_title_body_slide(
        f"{out_dir}/post8_bg_slide3.jpg", f"{out_dir}/post8_final_slide3.jpg",
        title="①契約内容の明確さ",
        body_lines=[
            "歩合率だけでなく、", "材料費や水道光熱費の負担、",
            "契約書の有無まで確認を。", "",
            "口約束だけで始めるのは", "トラブルのもとです。"
        ]
    )

    # 4枚目: ②集客サポートの有無
    draw_title_body_slide(
        f"{out_dir}/post8_bg_slide4.jpg", f"{out_dir}/post8_final_slide4.jpg",
        title="②集客サポートの有無",
        body_lines=[
            "面貸しは自分の指名客のみ対応で、", "完全歩合60〜70%が相場。", "",
            "業務委託寄りになると、", "サロンが新規集客を担う代わりに",
            "歩合はやや下がります。", "",
            "自分の指名客だけで回せるか、", "も判断材料になります。"
        ]
    )

    # 5枚目: ③技術レベル・雰囲気
    draw_title_body_slide(
        f"{out_dir}/post8_bg_slide5.jpg", f"{out_dir}/post8_final_slide5.jpg",
        title="③技術レベル・雰囲気",
        body_lines=[
            "在籍しているスタイリストの", "レベル感や雰囲気も大事なポイント。", "",
            "横のコミュニケーションが", "取りやすい環境かどうかも",
            "確認しておきたいところです。"
        ]
    )

    # 6枚目: ④設備・立地
    draw_title_body_slide(
        f"{out_dir}/post8_bg_slide6.jpg", f"{out_dir}/post8_final_slide6.jpg",
        title="④設備・立地",
        body_lines=[
            "駅からの距離、席数、", "設備の充実度。", "",
            "日々の働きやすさに", "直結するポイントです。"
        ]
    )

    # 7枚目: ⑤税務・保険サポート
    draw_title_body_slide(
        f"{out_dir}/post8_bg_slide7.jpg", f"{out_dir}/post8_final_slide7.jpg",
        title="⑤税務・保険サポート",
        body_lines=[
            "確定申告や保険まわり、", "わからないときに相談できる",
            "体制があるかどうかも", "見ておくと安心です。"
        ]
    )

    # 8枚目: 締め
    draw_closing_slide(
        f"{out_dir}/post8_bg_slide8.jpg", f"{out_dir}/post8_final_slide8.jpg",
        lead_lines=["全部が完璧なサロンは", "なかなかありません。"],
        body_lines=["自分が何を優先するかを決めておくことが、", "後悔しない選び方のコツです。"],
        dm_line="気になる方はDMで"
    )


# ==================== post9「自由出勤の働き方、3つのリアル例」 ====================
# 7枚構成。post7/post8 と同じ関数群の組み合わせで作成。

def build_post9(materials_dir=SRC, out_dir=OUT):
    import os
    os.makedirs(out_dir, exist_ok=True)

    beige_path = f"{materials_dir}/beige_texture.png"
    logo_path = f"{materials_dir}/logo.jpeg"

    # 背景生成
    make_cover_bg(beige_path, f"{out_dir}/post9_bg_cover.jpg")
    for i in range(2, 8):
        make_logo_bg(logo_path, base_shade=224, seed=i + 300,
                     out_path=f"{out_dir}/post9_bg_slide{i}.jpg")

    # 1枚目: 表紙
    draw_cover_slide(
        f"{out_dir}/post9_bg_cover.jpg", f"{out_dir}/post9_final_slide1.jpg",
        ["自由出勤の働き方", "3つのリアル例"],
        subtitle="piece201 / Nakameguro, Tokyo"
    )

    # 2枚目: 導入
    draw_title_body_slide(
        f"{out_dir}/post9_bg_slide2.jpg", f"{out_dir}/post9_final_slide2.jpg",
        title=None,
        body_lines=[
            "自由出勤とは、", "出勤する曜日・時間を", "自分で決められる働き方。", "",
            "ライフスタイルに合わせて、", "働き方そのものを設計できます。"
        ],
        body_color=DARK
    )

    # 3枚目: ①子育てと両立型
    draw_title_body_slide(
        f"{out_dir}/post9_bg_slide3.jpg", f"{out_dir}/post9_final_slide3.jpg",
        title="①子育てと両立型",
        body_lines=[
            "月・水・金 9:00-13:00 出勤", "火・木・土日 お休み", "",
            "保育園に預けている時間だけ働き、", "それ以外は家族の時間にあてるスタイル。"
        ]
    )

    # 4枚目: ②掛け持ち・副業型
    draw_title_body_slide(
        f"{out_dir}/post9_bg_slide4.jpg", f"{out_dir}/post9_final_slide4.jpg",
        title="②掛け持ち・副業型",
        body_lines=[
            "月・火・木・金 出勤", "水 他サロンで勤務", "土日 お休み", "",
            "複数の収入源を組み合わせて、", "1つのサロンに依存しないスタイル。"
        ]
    )

    # 5枚目: ③がっつり稼ぐ集中型
    draw_title_body_slide(
        f"{out_dir}/post9_bg_slide5.jpg", f"{out_dir}/post9_final_slide5.jpg",
        title="③がっつり稼ぐ集中型",
        body_lines=[
            "月〜土 10:00-19:00 出勤", "日 お休み", "",
            "稼働日数を増やして、", "短期間で売上を伸ばしたい人向け。"
        ]
    )

    # 6枚目: まとめ
    draw_title_body_slide(
        f"{out_dir}/post9_bg_slide6.jpg", f"{out_dir}/post9_final_slide6.jpg",
        title=None,
        body_lines=[
            "どのパターンが正解、", "というものはありません。", "",
            "自分の生活・目標に合わせて", "働き方を設計できるのが、",
            "自由出勤の一番の魅力です。"
        ],
        body_color=DARK
    )

    # 7枚目: 締め
    draw_closing_slide(
        f"{out_dir}/post9_bg_slide7.jpg", f"{out_dir}/post9_final_slide7.jpg",
        lead_lines=["自分に合った働き方、", "一緒に考えてみませんか。"],
        body_lines=["出勤日数や時間帯の相談も", "気軽にしてください。"],
        dm_line="気になる方はDMで"
    )


if __name__ == "__main__":
    build_post7()
    print("post7 done")
    build_post8()
    print("post8 done")
    build_post9()
    print("post9 done")
