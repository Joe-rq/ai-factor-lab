<h1 align="center">ai-factor-lab</h1>

<p align="center">
  一套让 AI 做因子研究<strong>可审计</strong>的操作系统——<br>
  账本、预注册、阳性对照，外加一个能完整跑通的合成平台。
</p>

<p align="center">
  <a href="https://github.com/Joe-rq/ai-factor-lab/actions/workflows/ci.yml"><img alt="ci" src="https://img.shields.io/github/actions/workflow/status/Joe-rq/ai-factor-lab/ci.yml?branch=main&amp;style=flat-square&amp;label=ci"></a>
  <a href="LICENSE"><img alt="license: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square"></a>
  <img alt="python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square">
  <img alt="runtime dependencies: 0" src="https://img.shields.io/badge/runtime%20deps-0-brightgreen?style=flat-square">
  <img alt="platform integration: none" src="https://img.shields.io/badge/platform%20integration-none-lightgrey?style=flat-square">
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#核心概念">核心概念</a> ·
  <a href="docs/">文档</a> ·
  <a href="docs/case-study.md">案例研究</a> ·
  <a href="README.md">English</a>
</p>

## 背景

本框架诞生于一次 WorldQuant BRAIN 的个人研究项目。生产环境的那一份会与平台
交互；**这个仓库不会**——这里的一切只跑在合成后端上。

**与 WorldQuant 无隶属关系。** 仓库不含任何平台数据、因子表达式、账户信息或
凭据，也不含任何平台对接与自动化。

## 这是什么

它不是因子生成器，是一套让研究记录**无法说谎**的机制。真正有意思的部分不是
「AI 能写出多少表达式」，而是每一条结论都能追溯到一条**在结论出现之前就已冻结**
的规则。

```
候选表达式 + 设置
       |
       v
  身份（SHA-256）
       |
       v
  账本：candidates -> plans -> attempts -> observations -> outcomes
       ^                    |
       |                    v
  预注册（冻结）        合成平台
       |                    |
       +------> 判读闸 <----+
                    |
                    v
                结局分类
```

五个概念，五个模块：

| 概念 | 模块 | 它回答什么 |
|---|---|---|
| 候选指纹 | `identity.py` | 这是不是我们已经跑过的同一条？ |
| 账本 | `ledger.py` | 发生了什么、顺序如何、依据哪条规则？ |
| 预注册 | `prereg.py` | 在看到结果之前，什么算成功？ |
| 判读闸 | `gates.py` | 通过、失败，还是**根本没测到**？ |
| 结局分类 | `classify.py` | 这属于哪一类结果？ |

`examples/synthetic/` 提供一个确定性的合成世界：30 个字段、一套极小的表达式
语言。它是一个**接缝**而不是玩具——demo 的收益由「建仓时点已知、收益下一期才
兑现」的方式计算，没有前视。

## 为什么需要它

语言模型会先给出一个看似合理的表达式，再给出一个看似合理的读数，最后给出一个
看似合理的解释——顺序就是如此。真正的失败模式不是代码写错，而是**研究记录里
「什么都没测到」与「测到了阴性结果」长得一模一样**。

三道具体防护：

1. **内容寻址的身份。** 同一条候选经不同路径进入，塌缩成同一行账；改一个字节
   就是另一条。
2. **终态不可变。** 数据库拒绝更新或删除结局。重跑是新的 attempt，不是改写历史。
3. **三态闸。** 每个闸只返回 `pass` / `fail` / `not_measured`。缺失的数据
   永远不会被静默读成失败。

## 核心概念

### 候选指纹

表达式先做空白归一化；设置补默认值并统一大写。候选 ID 是 `CAND-` 加上
「表达式 + 设置」规范 JSON 的 SHA-256。登记是幂等的。前缀只是展示选择，哈希才是
身份。

### 账本

五张表，单向流动。结局在 schema 层就不可变。观测 ID 由 attempt 与度量内容寻址。
SQLite 只当文件格式用，不依赖任何服务端。

### 预注册

预注册是一份**带类型的决策规则**：具名闸、封闭的结局词表，以及**每个闸都必须
显式登记的「未测到」槽位**。它在第一次仿真之前被哈希，plan 记录该摘要。以后
当然可以改主意，但不能假装规则一直是那一版。

### 阳性对照

一个永远不开火的闸，等于没有闸。demo 内置两条对照：

- `rank(f_29)`——负对照，合成世界里它与未来收益**没有线性联系**，必须不被认可；
- `rank(f_28)`——常数字段，方差为零，Sharpe 未定义，必须落成 `operational_error`。

负对照一旦被识别为 `recognized`，demo 以非零码退出。

### 三层验证

| 层 | 问题 | 谁判 | 本仓落在哪 |
|---|---|---|---|
| 规则层 | 代码与记录结构上是否成立？ | 机器 | `tests/`、`scripts/check-*.py` |
| 判据层 | 这条候选过没过冻结的规则？ | 机器 + 写下的判据 | `gates.py`、`classify.py`、`docs/preregistration.md` |
| 实效层 | 这项研究值不值得做？ | 人与世界 | 无法自动化 |

第三层是**验证红线**，任何仓库都替不了。

## 快速开始

需要 Python 3.11+ 与 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync
uv run python examples/synthetic/run_demo.py
```

一秒钟内跑完 100 条合成候选，输出形如：

```
expression                        sharpe fitness turnover  outcome
f_00                               4.006   3.767   0.485  recognized
-rank(f_00)                       -3.748  -3.369   0.390  effective_negative
rank(f_29)                         0.208   0.035   0.591  no_value
rank(f_28)                           n/a     n/a   0.000  operational_error
```

自己跑规则层：

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check-structure.py
uv run python scripts/check-hygiene.py
```

## 成果

**WorldQuant Challenge — Gold Level（2026）**。官方证书，姓名已遮盖。

*该奖项是平台层面的认可，不构成对本仓库的背书。*

证书图片位于 `docs/assets/worldquant-gold.png`，不含平台数据、账户信息或未遮盖的
个人信息。

![WorldQuant Challenge — Gold Level（2026），姓名已遮盖](docs/assets/worldquant-gold.png)

## 它是怎么造出来的

生产版本更大，而且私有——因为它包含账户数据和活的平台适配层。本仓库是**围绕同一
组不变式重写**的，不是导出。哪些是同一套逻辑、哪些换成了合成适配器、哪些被刻意
拿掉，见 [`docs/production-vs-repo.md`](docs/production-vs-repo.md)。

更完整的事故叙述——三起真实的判断失误与系统改动——见
[`docs/case-study.md`](docs/case-study.md)。

## 人与 AI 的分工

| 决策 | 谁 |
|---|---|
| 什么问题值得问 | 人 |
| 测哪些假设与字段 | 人 |
| 起草预注册规则 | AI 出规则，人审阅放行 |
| 把假设展开成候选表达式 | AI |
| 跑流水线、落账 | AI |
| 判断结果值不值得行动 | 人 |
| 看到结果之后改闸 | 人，并留下书面理由 |
| 对外发布结果 | 人 |

系统围绕这条分工设计：AI 可以大规模执行，但它既不能悄悄改写规则，也不能自己
把产出**晋升**为成果。

## 它不是什么

- 不是因子挖掘机器人，也不提供任何交易信号。
- 不含平台对接、自动化、凭据或会话。
- 不含真实行情、表达式、alpha ID 或账户信息。
- 不构成投资建议。
- 不承诺支持。issue 可能被直接关闭。

## 许可证与安全

Apache-2.0。见 [`LICENSE`](LICENSE) 与 [`SECURITY.md`](SECURITY.md)。
