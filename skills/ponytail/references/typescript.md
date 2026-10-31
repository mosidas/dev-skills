# TypeScript の型の書き方

`.ts`・`.tsx` のコードで型と関数のシグネチャを書くときの規則と例を定める。`design.md` 2.2(型で守る)を TypeScript の構文で適用する。implementer は `.ts`・`.tsx` を書くときと直すときに読む。reviewer は `.ts`・`.tsx` の差分を点検するときに読む。

## 1. 適用範囲

- `.ts`・`.tsx` のファイルを書く・直す・点検するときに適用する。
- 言語に依らない原則は `design.md` 2.2(型で守る)と 2.3(境界の内側の構造)が扱う。本書はその原則の TypeScript での書き方だけを扱う。
- ponytail のはしごを先に適用する。本書は作ると判断した型の形を確定する。型を作るかどうかの判断は変えない。
- 次は本書で扱わない。それぞれの所在の規則に従う。
  - 境界での検証の場所: ponytail 3.(規則)と secure 2.1(信頼境界と入力検証)
  - 構造化ログ: observe 2.1(構造化ログ)
  - テスト: ponytail 5.(単純にしないもの)のテストの判定
- リポジトリに型の慣習(判別子の名前・ブランドの形・スキーマのライブラリ)があればそれに合わせる。

## 2. 規則

判定の問いは `design.md` 2.2 と同じく「この誤りは実行時まで残るか」である。残るなら次の表の規則で型検査が拒否する形にする。表の行と 3. の小節は同じ順に並ぶ。

| 規則 | 要点 |
| :-- | :-- |
| 判別共用体 | 状態の種類は共通の判別子(`kind` のようなリテラルの項目)を持つ共用体で表す。ブール値とオプショナルの項目の組で表さない。判別子の名前はリポジトリで 1 つに揃える。 |
| ブランド型 | 意味の違うプリミティブには `string & { readonly __brand: "OrderId" }` の形のブランドを付ける。ブランドの付いた値は検証する型ガード(`input is OrderId`)からだけ作る。`as` では作らない。 |
| 不正な値を作れない構成 | 不正な値を書けない形で型を組み立てる。空でない配列は `[T, ...T[]]` で表す。偶数個の列は組の配列 `[T, T][]` で表す。実行時のガードとコメントで不変条件を守らない。 |
| 最も単純な全域の型 | どの値にも結果がある操作だけを使ううちは `T[]` のような緩い型を保つ。緩い型が `!`・`as`・「起こらないはず」の例外を強いる箇所でだけ型を強める。 |
| `any` より `unknown` | 外部のデータは `unknown` で受け取る。使う前に絞り込む。 |
| 型ガードより先にスキーマ | 外部のデータの型ガードを項目ごとに手で書く前にリポジトリのスキーマのライブラリを探す。型はスキーマから導出する。1 つのガードのために新しい依存を加えない。 |
| `as` を使わない | 型の主張に `as` を使わない。値の形は型ガードかスキーマで確かめる。`as const` はこの規則の対象外である。 |
| 絞り込みの優先順 | 判別子の分岐・`in` 演算子・`typeof` と `instanceof`・ユーザー定義の型ガードの順に試す。前の手段で絞れるときは後の手段を使わない。 |
| 型ガード | 型ガードは名前が主張する型を本体ですべて確かめる。名前は `isX` か `hasX` にする。 |
| 網羅性 | 判別子の `switch` の `default` で値を `never` 型の変数に代入する。種類を加えたときに扱っていない分岐を型検査が拒否する。 |
| `as` より `satisfies` | 値が型に合うかは `satisfies` で確かめる。`satisfies` はリテラルの型を広げない。 |
| 境界での解析 | データは境界をまたぐ所で名前のあるドメインの型に解析する。`Record<string, unknown>` のような緩い型は解析の関数の中で終わらせる。内側では型を信じて再検証しない。 |
| スキーマ由来の型 | 生成した型か既存の型があるときは `Pick`・`Omit`・`Parameters`・`ReturnType`・`Awaited`・`typeof` で導出する。同じ形のインターフェースを新しく書かない。 |
| オブジェクト引数 | 引数が 2 つ以上ある関数は名前の付いた項目を持つ 1 つのオブジェクトで引数を受け取る。毎フレームの描画・トークナイザー・パーサーのような密なループの関数は対象外とする。 |

## 3. 例

各小節のしない例とする例は同じ課題を扱う。コードの先頭の行のコメントでどちらの例かを示す。識別子は例のためのものである。

### 3.1. 判別共用体

```ts
// しない例
type FetchState = { loading: boolean; invoices?: Invoice[]; error?: string };
```

```ts
// する例
type FetchState =
  | { kind: "loading" }
  | { kind: "ready"; invoices: Invoice[] }
  | { kind: "error"; message: string };
```

しない例は `loading` が `true` で `error` にも値がある矛盾した状態を作れる。する例では種類ごとに存在する項目だけがあるので矛盾した状態を書けない。

### 3.2. ブランド型

```ts
// しない例
function cancelOrder(orderId: string): void {
  /* ... */
}

cancelOrder(user.id); // 利用者の ID を渡しても型検査を通る

type OrderId = string & { readonly __brand: "OrderId" };
const orderId = input as OrderId; // 確かめずにブランドを付けている
```

```ts
// する例
type OrderId = string & { readonly __brand: "OrderId" };

function isOrderId(input: string): input is OrderId {
  return /^ord_[0-9a-z]{12}$/.test(input);
}

function parseOrderId(input: string): OrderId {
  if (!isOrderId(input)) throw new Error(`注文 ID の形式でない: ${input}`);
  return input;
}

function cancelOrder(orderId: OrderId): void {
  /* orderId は検証済みとして扱う */
}
```

する例では `cancelOrder` に利用者の ID の文字列を渡すと型検査が拒否する。ブランドは `parseOrderId` が形式を確かめた後にだけ付く。だから内側の関数は値を再検証しない。

### 3.3. 不正な値を作れない構成

```ts
// しない例
function highestScore(scores: number[]): number {
  if (scores.length === 0) throw new Error("得点が無い");
  return Math.max(...scores);
}

type Headers = string[]; // 名前と値を交互に並べる。要素の数は偶数
```

```ts
// する例
type NonEmpty<T> = [T, ...T[]];

function highestScore(scores: NonEmpty<number>): number {
  return Math.max(...scores);
}

const isNonEmpty = <T,>(items: T[]): items is NonEmpty<T> => items.length > 0;

type Headers = [name: string, value: string][];
```

しない例は空の配列と奇数個の列を実行時の例外とコメントで防ぐ。`NonEmpty` と組の配列ではその値を型の上で書けない。`T[]` を受け取る所では `isNonEmpty` で 1 回だけ絞り込む。その後は空でないことが型に乗って渡る。

### 3.4. 最も単純な全域の型

```ts
// 緩い型のままでよい例
const total = (prices: number[]) => prices.reduce((sum, price) => sum + price, 0);
```

```ts
// しない例
function latestRelease(releases: Release[]): Release {
  return releases.at(0)!;
}
```

```ts
// する例
function latestRelease(releases: NonEmpty<Release>): Release {
  return releases[0];
}
```

`total` は空の配列にも 0 を返すので型を強めない。`latestRelease` のしない例は空の配列で `undefined` を返す誤りを `!` で型検査から隠す。入力を強めるか戻り値を `Release | undefined` に弱めると `!` が無くなる。

### 3.5. `any` より `unknown`

```ts
// しない例
function readPort(config: any): number {
  return config.port;
}
```

```ts
// する例
function readPort(config: unknown): number {
  if (typeof config === "object" && config !== null && "port" in config && typeof config.port === "number") {
    return config.port;
  }
  throw new Error("設定に数値の port が無い");
}
```

`any` は型検査を止める。`config.port` が文字列でも誤りは使う所まで残る。`JSON.parse` と `response.json()` は `any` を返すので受け取る変数に `unknown` を注釈する。項目が多いときは 3.6 のスキーマを使う。

### 3.6. 型ガードより先にスキーマ

```ts
// しない例
type Member = { id: string; role: "admin" | "member" };

function isMember(input: unknown): input is Member {
  return (
    typeof input === "object" && input !== null &&
    "id" in input && typeof input.id === "string" &&
    "role" in input && (input.role === "admin" || input.role === "member")
  );
}
```

```ts
// する例
import { z } from "zod";

const MemberSchema = z.object({
  id: z.string(),
  role: z.enum(["admin", "member"]),
});

type Member = z.infer<typeof MemberSchema>;

function parseMember(input: unknown): Member {
  return MemberSchema.parse(input);
}
```

しない例は型とガードの 2 か所に同じ形を書く。項目を加えるときに片方だけを直すと型とガードが食い違う。する例では形を持つのはスキーマだけである。失敗が想定した分岐なら `parse` でなく `safeParse` を使う。リポジトリが別のスキーマのライブラリを使うときはそのライブラリの型の導出を使う。

型が先にあるときはスキーマに型を注釈する。

```ts
type Member = { id: string; role: "admin" | "member" };

const MemberSchema: z.ZodType<Member> = z.object({
  id: z.string(),
  role: z.enum(["admin", "member"]),
});
```

スキーマから `role` を外すと型検査が代入を拒否する。スキーマが型より少ない項目しか確かめない誤りを型検査が見つける。

### 3.7. `as` を使わない

```ts
// しない例
const member = (await response.json()) as Member;
```

```ts
// する例
const body: unknown = await response.json();
const member = parseMember(body);
```

`as` は実行時に何も確かめない。応答の形が変わるとしない例の誤りは `member` を使う遠くの箇所で現れる。する例は応答を受け取った所で失敗する。`as const` は値の型を狭めるだけで偽の主張をしないので対象外である。

### 3.8. 絞り込みの優先順

3.8 から 3.10 は次の型を使う。

```ts
type Circle = { kind: "circle"; radius: number };
type Rect = { kind: "rect"; width: number; height: number };
type Shape = Circle | Rect;
```

```ts
// しない例
function area(shape: Shape): number {
  const circle = shape as Circle;
  if (circle.radius !== undefined) return Math.PI * circle.radius ** 2;
  const rect = shape as Rect;
  return rect.width * rect.height;
}
```

```ts
// する例
function area(shape: Shape): number {
  if (shape.kind === "circle") return Math.PI * shape.radius ** 2;
  return shape.width * shape.height;
}
```

判別子で分岐すると型検査が分岐ごとに型を狭める。しない例では種類を加えても `as` の分岐へ流れるだけで型検査は何も拒否しない。

### 3.9. 型ガード

```ts
// しない例
function isRect(input: unknown): input is Rect {
  return typeof input === "object" && input !== null && "width" in input;
}
```

```ts
// する例
function isRect(input: unknown): input is Rect {
  return (
    typeof input === "object" && input !== null &&
    "kind" in input && input.kind === "rect" &&
    "width" in input && typeof input.width === "number" &&
    "height" in input && typeof input.height === "number"
  );
}
```

`width` だけを確かめるガードは `height` の無い値も `Rect` と主張する。この誤りは `as` より見つけにくい。安全を名乗る `isRect` という名前の陰に隠れるためである。外部のデータなら 3.6 のスキーマを先に検討する。

### 3.10. 網羅性

```ts
// しない例
function label(shape: Shape): string {
  switch (shape.kind) {
    case "circle":
      return "円";
    default:
      return "四角形";
  }
}
```

```ts
// する例
function label(shape: Shape): string {
  switch (shape.kind) {
    case "circle":
      return "円";
    case "rect":
      return "四角形";
    default: {
      const exhaustive: never = shape;
      return exhaustive;
    }
  }
}

function draw(shape: Shape): void {
  switch (shape.kind) {
    case "circle":
      drawCircle(shape);
      break;
    case "rect":
      drawRect(shape);
      break;
    default: {
      const exhaustive: never = shape;
      void exhaustive;
    }
  }
}
```

`Shape` に三角形を加えるとする例の `default` で `shape` が `never` でなくなる。型検査は扱っていない種類を拒否する。しない例は三角形を「四角形」と表示しても型検査を通る。値を返す `switch` では `return` で変数を使う。値を返さない `switch` では `void` で変数を使う。

### 3.11. `as` より `satisfies`

```ts
type Config = { theme: "light" | "dark"; columns: number };
```

```ts
// しない例
const config = { theme: "dark" } as Config;
```

```ts
// する例
const config = { theme: "dark", columns: 3 } satisfies Config;
```

`as` は `columns` の欠けた値を通す。`satisfies` は欠けた項目を拒否する。`config.theme` の型は `"dark"` のまま残る。

### 3.12. 境界での解析

```ts
// しない例
async function loadInvoice(id: string): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/invoices/${id}`);
  return response.json();
}

function formatTotal(invoice: Record<string, unknown>): string {
  if (typeof invoice.total !== "number") throw new Error("total が数値でない");
  return `${invoice.total.toLocaleString()} 円`;
}
```

```ts
// する例
const InvoiceSchema = z.object({ id: z.string(), total: z.number() });
type Invoice = z.infer<typeof InvoiceSchema>;

async function loadInvoice(id: string): Promise<Invoice> {
  const response = await fetch(`/api/invoices/${id}`);
  const body: unknown = await response.json();
  return InvoiceSchema.parse(body);
}

function formatTotal(invoice: Invoice): string {
  return `${invoice.total.toLocaleString()} 円`;
}
```

緩い型を内側へ渡すと内側の関数がそれぞれ検証を繰り返す。境界の `loadInvoice` で 1 回だけ解析すれば内側の `formatTotal` は型を信じてよい。

### 3.13. スキーマ由来の型

```ts
// しない例
type InvoiceSummary = { id: string; total: number };

function renderSummary(summary: InvoiceSummary): string {
  /* ... */
}
```

```ts
// する例
import type { Invoice } from "./generated/api";

function renderSummary(summary: Pick<Invoice, "id" | "total">): string {
  /* ... */
}

type LoadedInvoice = Awaited<ReturnType<typeof loadInvoice>>;
```

手で書いた型は生成元の定義が変わっても追従しない。`Pick` で導出すれば生成元の項目の型が変わったときに型検査が使う側の不整合を拒否する。関数の戻り値の型も `ReturnType` と `Awaited` で導出できる。

### 3.14. オブジェクト引数

```ts
// しない例
function scheduleReminder(orderId: OrderId, delayMinutes: number, repeatCount: number): void {
  /* ... */
}

scheduleReminder(orderId, 3, 30); // 遅延と回数を取り違えても型検査を通る
```

```ts
// する例
function scheduleReminder(args: { orderId: OrderId; delayMinutes: number; repeatCount: number }): void {
  /* ... */
}

scheduleReminder({ orderId, delayMinutes: 30, repeatCount: 3 });
```

オブジェクトで受け取ると呼び出し側に項目の名前が出る。だから順の取り違えを読み手が見つけられる。密なループの関数ではオブジェクトの生成が呼び出しごとに生じるので対象外とする。

## 4. `as` を外すときの見分け

既存のコードの `as` を外すときは TypeScript が型を推論できない理由を先に特定する。理由ごとに直し方が違う。

| 理由 | 兆候 | 直し方 |
| :-- | :-- | :-- |
| 判別子が無い | 項目の有無で種類を見分けている | 判別子を加えて判別共用体にする(3.1) |
| 元の型が広すぎる | `Record<string, unknown>` か `object` から項目を取り出している | 境界で解析して型を狭める(3.12) |
| 境界に型が無い | `JSON.parse` の戻り値・`fetch` の応答・`postMessage` のデータに `as` を付けている | 形を持つスキーマで解析する。スキーマが無いときだけ加える(3.6) |
| 型で表せない | 確かめた事実(形式を確かめた ID・定数の表)を型が知らない | ブランド型(3.2)か `satisfies`(3.11)にする |

理由を特定しても外せないときは型の強制で型検査を通さない。計画の設計が問題に合っていない兆候として `agents/implementer.md` の進め方 3 に従う。
