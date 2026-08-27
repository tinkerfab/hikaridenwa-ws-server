# hikaridenwa-ws-server

光電話ルータ(HGW)の多機能電話ポートに内線として登録し、着信(INVITE)の発信者番号を解析した上でWebSocketにブロードキャストするだけの、最小構成のSIPクライアント/WSサーバ。

## これは何か

- **サーバはSIPクライアント + WebSocketブロードキャストだけに徹する**。着信履歴の保存・表示ロジックは一切持たない
- **着信履歴等の状態はWSクライアント側の責務にする**。ブラウザ・Windowsネイティブアプリなど、複数のクライアント実装を将来的に用意できるようにする
- **複数のWSクライアントに同時にブロードキャストできる**こと(1台のスマホと1台のPCで同時に同じ着信通知を受け取る、等)

サーバはWebSocketメッセージを送りっぱなしにするだけで、それをどう表示・保存・通知するかは各クライアントの自由。サーバ再起動時に「履歴が消える/消えない」を気にする必要自体がなくなる(そもそもサーバは履歴を持たない)。

## アーキテクチャ

```
hikaridenwa-ws-server/
  Dockerfile
  docker-compose.yml
  requirements.txt / requirements-dev.txt
  pytest.ini
  secrets/
    app.env.example
    app.env                     # (gitignore対象) 運用者が作成
  app/
    main.py                     # FastAPI composition root。/healthz・/ws のみ
    config.py                   # 外部envファイル読込・設定検証
    logging_setup.py            # app.log用のRotatingFileHandlerセットアップ(履歴ログはなし)
    healthcheck.py              # Docker HEALTHCHECKから呼ばれる
    pipeline.py                 # SIP層のイベント → ヘッダ解析 → WS配信、の配線
    sip/                        # pjsua2アダプタ層
      bridge.py / pj_account.py / pj_call.py / call_lifecycle.py
      raw_headers.py / caller_id.py
    ws/ws_hub.py                # 履歴なし。接続中の全クライアントへブロードキャストするだけ
    static/                     # Webブラウザ用リファレンスクライアント(状態はすべてクライアント側)
      index.html / app.js / styles.css
  tests/
```

### 処理の流れ(着信1件あたり)

1. HGWがINVITEを送信 → pjsua2が`180 Ringing`を返送、`RING_TIMEOUT_S`のタイムアウトタイマーを開始
2. `extract_headers` → `parse_caller_id` でヘッダから発信者番号を解析
3. `{"type": "call:ringing", "call": {...}}` を接続中の全WSクライアントへブロードキャスト
4. HGWからCANCEL/BYEが届く、または`RING_TIMEOUT_S`経過で仮想内線が480を返す → `{"type": "call:ended", "call": {...}}` をブロードキャスト

サーバ側はこれらのイベントをどこにも保存しない。ブロードキャストした時点でサーバの役目は終わり。

### 受動的な内線としての動作

このアプリは着信を検知するだけの受動的な観測者。`180 Ringing`は返すが`200 OK`は一切返さない。実際の通話は同じ内線構成の中の他の電話機・内線が処理する。

## WebSocketメッセージ仕様

`/ws`に接続すると、以降に発生した着信イベントを受信できる。**接続時点の履歴は送られない**(そもそもサーバが保持していない)— 履歴が必要なクライアントは、自分が受信したイベントを自前で蓄積すること。

全メッセージ共通のエンベロープ:

```json
{"type": "call:ringing" | "call:ended", "call": { ... }}
```

### `call:ringing`

着信検知直後に送られる。

```json
{
  "type": "call:ringing",
  "call": {
    "id": "8b2e6e2a-2e1a-4f7a-9b7e-1e6a3b2c9f10",
    "call_id": "0",
    "received_at": 1787633293.31,
    "number": "08022777337",
    "display_name": "08022777337",
    "anonymous": false,
    "source": "from",
    "status": "ringing"
  }
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | string (uuid) | **この通話を突き合わせるための安定したキー。クライアントはこれをキーにレコードを管理すること** |
| `call_id` | string | pjsua2内部の通話インデックス(小さい整数の文字列)。**通話終了後に他の通話へ再利用されるため、突き合わせキーとしては使えない** — `id`を使うこと |
| `received_at` | number (unix epoch秒) | INVITE受信時刻 |
| `number` | string \| null | 発信者番号。非通知や取得不可の場合は`null` |
| `display_name` | string \| null | 発信者の表示名(あれば) |
| `anonymous` | bool | 非通知かどうか |
| `source` | `"pai"` \| `"rpid"` \| `"from"` \| `"none"` | 番号をどのSIPヘッダから取得したか |
| `status` | `"ringing"` | 常にこの値(`call:ended`が来るまで通話は継続中) |

なぜ`call_id`とは別に`id`があるか: `call_id`はpjsua2が内部的に使う小さい整数(SIPの通話数が増えるだけ枯渇しては困るので、通話終了後は次の通話へ再利用される)。サーバはこの再利用を検知できるよう、着信ごとに`uuid4`の`id`を発行し、`call:ringing`→`call:ended`の2イベントで同じ`id`を使い回す(その通話が終わった時点でサーバ内の対応表からは削除される)。クライアントは必ず`id`をキーにレコードを管理すること。`call_id`だけをキーにすると、古い(終了済みの)通話のレコードを新しい通話の情報で上書きしてしまう恐れがある。

### `call:ended`

```json
{
  "type": "call:ended",
  "call": {
    "id": "8b2e6e2a-2e1a-4f7a-9b7e-1e6a3b2c9f10",
    "call_id": "0",
    "ended_at": 1787633323.94,
    "end_reason": "disconnected" | "timeout"
  }
}
```

`end_reason`は`"disconnected"`(HGWからCANCEL/BYEを受信=他の内線が応答/発信者が切断)、または`"timeout"`(`RING_TIMEOUT_S`経過による自動終了)のいずれか。`call:ringing`の全フィールドは含まれないため、クライアント側で`id`をキーに自分が保持しているレコードのステータスを更新すること。`id`が`null`の場合(サーバがこの`call_id`に対応する進行中の通話を追跡できていなかった、例えばサーバ再起動を跨いだ等)は、クライアント側でも安全に突き合わせる方法がないため無視してよい。

### クライアント実装上の注意

- サーバは複数クライアントへ同一メッセージをそのままブロードキャストする。1台のクライアントが再接続してもサーバ側の状態は変わらない
- 接続断からの再接続時、サーバ側は何もリプレイしない。再接続の間に発生した着信はクライアント側で「見逃した」ことになる(現時点の既知の制限。将来的に必要ならサーバ側に短期リングバッファを足す運用も検討可能だが、現状は意図的にステートレスにしている)
- サーバ→クライアントの一方向通信のみを想定。クライアント→サーバのメッセージは現状処理しない(`/ws`は接続を維持するためだけに`receive_text()`を呼んでいる)
- 突き合わせキーは必ず`id`を使うこと(`call_id`は再利用されるため不可。上記参照)

## Webブラウザ用リファレンスクライアント

`app/static/`に、`/ws`へ接続してリアルタイム着信表示ができる素のHTML/CSS/JSクライアントを同梱している。サーバ起動後、`http://<ホスト>:<HTTP_PORT>/`で開ける。

- サーバは`app/static/`配下の静的ファイルを返すだけで、状態も履歴も一切持たない。表示・履歴管理ロジックはすべて`app/static/app.js`側で完結している(サーバの「SIP+WSブロードキャストのみ」という責務は変わっていない)
- 着信履歴は`localStorage`にこのブラウザ限定で保存される(直近50件、リングバッファ)。別の端末・別のブラウザとは同期されない — これは意図した設計で、複数クライアントがそれぞれ自分の履歴を持てることを確認するためのリファレンス実装でもある
- `call:ringing`は`id`をキーに同一カードを追加・更新し、`call:ended`でステータスを「終了」に切り替える
- WebSocket切断時は3秒ごとに自動再接続。ライト/ダークモードはOS設定に自動追従、モバイル幅にも対応

Windowsネイティブアプリ等の別クライアントを実装する場合も、上記「WebSocketメッセージ仕様」の契約(特に`id`の扱い)に従えば、このリファレンスクライアントと同じ情報を再現できる。

## 動作要件

- **Linux上のDocker**(`network_mode: host`の都合上、Docker Desktop for Mac/Windowsでは動作しない)
- 光電話ルータ(HGW)の管理画面で内線(拡張内線)を追加できること

## セットアップ

```bash
cp secrets/app.env.example secrets/app.env
# secrets/app.env を編集し、HGWのIPアドレス・内線番号・認証情報を設定

mkdir -p data
sudo chown 1000:1000 data   # コンテナは非rootユーザー(uid:gid 1000:1000)で動作するため

docker compose up --build -d
docker compose logs | grep "registration state"   # 200 OKが出ていればSIP登録成功
curl http://localhost:8080/healthz
```

`http://<ホスト>:<HTTP_PORT>/`を開くと同梱のブラウザ用リファレンスクライアントが表示される(詳細は後述「Webブラウザ用リファレンスクライアント」参照)。他のWSクライアントを実装する場合は`ws://<ホスト>:<HTTP_PORT>/ws`へ接続する。

## 設定リファレンス

### 必須

| 変数名 | 説明 |
|---|---|
| `HGW_HOST` | HGWのLAN側IPアドレス |
| `SIP_EXTENSION` | HGW管理画面で作成した内線番号 |
| `SIP_AUTH_USER` | SIP認証ユーザー名 |
| `SIP_PASSWORD` | SIP認証パスワード |

### 任意(デフォルト値あり)

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `HGW_PORT` | `5060` | HGWのSIPポート |
| `SIP_REGISTER_EXPIRES` | `600` | REGISTERの有効期限(秒) |
| `LOCAL_BIND_IP` | `0.0.0.0` | SIPソケットをbindするローカルアドレス |
| `RING_TIMEOUT_S` | `30` | 他の内線が応答しないまま経過したら480で終了させるまでの秒数 |
| `HTTP_PORT` | `8080` | `/healthz`・`/ws`のリッスンポート |
| `DATA_DIR` | `./data` | `app.log`・`sip.log`の書き出し先。Docker実行時は`ENV DATA_DIR=/app/data`が優先 |

## テスト方針

pjsua2のネイティブ層(`WhoisAccount`/`WhoisCall`)を除き、全モジュールがpytestでテストされている。実際の判断ロジックをpjsua2非依存の純粋Pythonクラスに寄せる方針を取っている。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

pjsua2に依存するのは`app/sip/bridge.py`・`app/sip/pj_account.py`・`app/sip/pj_call.py`のみで、これらを直接importしなければ通常の開発・テストにpjsua2のビルドは不要(`app/main.py`は起動時=lifespan内で遅延importしている)。

## 既知の制限事項

- WSクライアント再接続時にサーバ側からのリプレイは一切ない(意図的な設計。上記「クライアント実装上の注意」参照)
- 同梱のブラウザ用クライアントはリファレンス実装。着信履歴はブラウザの`localStorage`限定で、同期・バックアップの仕組みはない
- Windowsネイティブクライアントは本リポジトリのスコープ外(別リポジトリ/別成果物として検討中)
- `network_mode: host`のため、Docker Desktop for Mac/Windowsでは動作しない

## ライセンス

GPL-2.0-or-later。詳細は[LICENSE](LICENSE)を参照。

```
hikaridenwa-ws-server
Copyright (C) 2026  Tadashi Sawaguchi

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
```

このプロジェクトは実行時に[PJSIP (pjproject)](https://github.com/pjsip/pjproject)の`pjsua2`バインディングを同一プロセス内で利用している。pjprojectはGPL v2以降とのデュアルライセンス(GPLに従えない場合は`licensing@pjsip.org`宛に商用ライセンスの相談が可能)であり、本リポジトリのライセンスもこれに揃えている。詳細は[PJSIPのライセンスページ](https://docs.pjsip.org/en/latest/overview/license.html)を参照。
