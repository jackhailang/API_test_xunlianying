# 保险出单接口自动化

本项目用 Excel 管理流程用例，用 YAML 管理试算、核保、承保三个接口的报文、变量提取和断言。  
Python 代码只负责发送请求、替换 `${变量名}`、按配置提取响应和执行断言，不写死保费、订单号等业务字段路径。

## 目录说明

```text
insurance_api_auto/
├── config/            环境地址、超时、日志、数据库配置
├── common/            YAML、Excel、替换、提取、断言、上下文
├── encapsulation/     HTTP、数据库、日志
├── testcase/          pytest 用例和夹具
├── testdata/          Excel 与接口 YAML
└── output/            日志、Allure 原始结果、HTML 报告
```

## 安装依赖

在项目根目录执行：

```powershell
cd d:\python\API_test\insurance_api_auto
pip install -r requirements.txt
```

建议使用 Python 3.8 及以上。生成 HTML 报告还需要单独安装 [Allure Commandline](https://github.com/allure-framework/allure2/releases)，并保证命令 `allure` 可用。`allure-pytest` 只负责产出原始结果。

## 生成 Excel 测试数据

```powershell
python testdata\create_excel.py
```

脚本会覆盖生成 `testdata/insurance_cases.xlsx`。默认包含：

| case_id | enabled | 说明 |
| --- | --- | --- |
| INS001 | Y | 执行试算、核保、承保 |
| INS002 | N | 只演示跳过，不发送请求 |

## 执行测试

在 `insurance_api_auto` 目录执行：

```powershell
pytest
```

只跑保险流程：

```powershell
pytest -m insurance
```

`enabled` 不是 `Y`、`YES`、`TRUE`、`1`、`是`、`启用` 的行会被跳过。  
每条启用的用例按 Excel 中的三个 YAML 顺序执行：试算 -> 核保 -> 承保。

日志在 `output/logs/insurance_api.log`。Allure 原始结果在 `output/results/`。

pytest 会话结束后会自动生成 HTML 报告。每次结果单独放在时间戳目录中，例如：

```text
output/reports/html/20261106_002630/index.html
```

历史报告不会被覆盖。全部历史入口是 `output/reports/html/history.html`。代码会同时查找当前进程 PATH、Windows 用户 Path 和系统 Path 中的 `java` 与 `allure`，因此不需要再手工执行 `allure generate`。

仍可按指定目录手动生成一份：

```powershell
allure generate output\results -o output\reports\html\手动目录
allure open output\reports\html\手动目录
```

报告中的每个接口是单独步骤，并附有请求报文、响应报文、提取结果和断言结果。断言失败时，pytest 用例状态为失败，Allure 步骤里能看到期望值和实际值。

## 切换环境

`config/config.yaml` 的 `environments` 中维护 `test`、`uat`、`prod`。YAML 里的地址以 `/` 开头时，会拼接对应环境的 `base_url`。以 `http://` 或 `https://` 开头的地址保持原样。

方式一，改配置：

```yaml
current_env: uat
```

方式二，环境变量优先于配置文件：

```powershell
$env:TEST_ENV="uat"
pytest
```

数据库不是主流程必需项。需要查库时使用 `DBClient.from_settings()`。密码不要写进业务代码，执行前设置：

```powershell
$env:DB_HOST="127.0.0.1"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="你的密码"
$env:DB_NAME="insurance"
```

## 新增测试用例和 YAML

1. 在 `testdata/Transaction/` 新增或复制一套 YAML。一个接口一个文件。
2. 在 `testdata/create_excel.py` 的 `CASE_ROWS` 增加一行，填三个 YAML 相对路径和 `enabled`。
3. 重新执行 `python testdata\create_excel.py`。也可以直接在 Excel 追加一行，表头保持不变。
4. YAML 必填 `name`、`method`、`url`。POST 报文放在 `json` 下。

路径相对 `testdata` 目录，例如 `Transaction/calculate.yaml`。

## 配置接口关联字段

框架不会猜测响应字段。关联关系只做两件事：

1. 当前接口的 `extract` 按点路径取出响应值，写入上下文。
2. 后续报文中的 `${变量名}` 用上下文替换。

试算把保费交给核保：

```yaml
extract:
  totalPremium: data.totalPremium
```

核保报文引用：

```yaml
totalPremium: "${totalPremium}"
```

核保把订单号交给承保：

```yaml
extract:
  orderId: data.orderId
```

承保报文引用：

```yaml
orderId: "${orderId}"
```

如果真实响应不是示例路径，只修改 YAML。例如保费实际在被保人险种节点：

```yaml
extract:
  totalPremium: data.insurants.0.coverages.0.actualPrem
```

订单号实际叫 `orderNo` 时：

```yaml
extract:
  orderId: data.orderNo
```

左侧 `orderId` 是上下文变量名，右侧才是响应路径。承保继续写 `${orderId}` 即可，不必改 Python。

路径不存在时，当前步骤失败，并提示修改该 YAML 的 `extract`。  
承保引用了还没提取的 `orderId` 时，异常为：

```text
上下文变量 orderId 不存在，请检查核保 YAML 的 extract 配置
```

数组下标用数字，例如 `data.items.0.id`。

整段值恰好是 `${变量名}` 时，保留响应里的原始类型；写在其他文字中时转成字符串，例如 `hebaojiaoyanma_${timestamp}`。

## 内置变量

每条用例开始时自动生成，不需要从响应提取：

| 变量 | 含义 |
| --- | --- |
| today | 当前日期，yyyy-MM-dd |
| now_time | 当前时间，HH:mm:ss |
| timestamp | 毫秒时间戳 |
| uuid | 随机 UUID |
| outChannelOrderId | 20 位数字流水号 |
| bkSerial | 18 位数字流水号 |
| orderNo | 18 位数字流水号 |

这些只是请求侧默认值。某个值如果必须来自接口响应，在前置 YAML 的 `extract` 里使用同名变量，提取结果会覆盖内置值。

## 断言

`assert` 支持：

- `status_code`：比较 HTTP 状态码。
- `equals`：比较 JSON 点路径，需提供 `path` 和 `expected`。
- `contains`：响应文本或某个路径的值包含期望内容。
- `not_empty`：路径对应的值不是空字符串、空数组或空对象。

示例 YAML 默认只断言 HTTP 200。业务码、保单号等断言已按注释放在 YAML 中，对照真实响应后去掉注释即可。

## 注意事项

- 示例报文里的姓名、证件号、手机号、邮箱和银行卡号来自接口文档样例。连接真实环境前改成测试数据。
- `data.totalPremium`、`data.orderId` 只是示例提取路径。第一次联调请先看 Allure 或日志中的响应报文，再改 YAML。
- 核保和承保没有自动重试，避免超时后重复出单。
- 未安装 Allure 命令行时，测试仍可执行，原始结果保留在 `output/results/`。
- 不要把数据库密码写入 `testcase` 或 YAML。密码通过环境变量 `DB_PASSWORD` 注入。
