# 他の作者のソフトウェア（Third-party notices）

このリポジトリには、他の作者のソフトウェアを同梱していません。

## 初回セットアップで入る部品

`初回セットアップ.bat` は、`requirements.txt` にある次の部品を、インターネット（PyPI）から利用者のPCにダウンロードします。
これらはこのリポジトリには含まれていません。それぞれのライセンスに従います。

| 部品 | 使いみち | ライセンス |
|---|---|---|
| Flask（Werkzeug・Jinja2・itsdangerous・click・MarkupSafe を含む） | Webアプリの土台 | BSD-3-Clause |
| blinker（Flask が使う） | Webアプリの土台 | MIT |
| openpyxl（et-xmlfile を含む） | Excel 出力 | MIT |
| reportlab | 様式PDFへの記入 | BSD |
| Pillow（reportlab が使う） | 画像の処理 | MIT-CMU |
| charset-normalizer（reportlab が使う） | 文字コードの判定 | MIT |
| pypdf | PDFの結合・記入 | BSD-3-Clause |
| pypdfium2（PDFium を含む） | 記入位置の設定画面で様式PDFを画像にする | Apache-2.0 または BSD-3-Clause（同梱の PDFium とその部品は、それぞれのライセンス） |

（各部品のライセンスは、それぞれの配布元の表示が正となります。上の表は、確認した時点の表示を写したものです。）
