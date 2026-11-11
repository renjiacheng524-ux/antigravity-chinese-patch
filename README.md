# Antigravity 中文本地化补丁

给 [Google Antigravity](https://antigravity.google/) 桌面客户端加中文界面的开源工具。官方没有中文语言包，这里采用**注入式汉化**：把一段 DOM 运行时翻译引擎追加进 Electron 的 `preload` 脚本，再重新打包 `app.asar`。

- 不修改 Antigravity 的任何业务代码，只在外层 preload 末尾追加翻译引擎
- 版本无关：每次对**当前安装的** `app.asar` 现场解包 → 注入 → 重打包
- 自带备份，可一键还原
- 提供 `check` / `patch` / `--dry-run` 三种模式，方便接到「更新后自动重打」的启动脚本里

> 本仓库只包含汉化脚本与翻译词典，**不包含** Antigravity 本体、也不分发任何打包后的 `app.asar`。所有改动都在你自己的机器上本地完成。

## 效果

| 区域 | 译文 |
| --- | --- |
| 菜单栏 | 工作区 / 视图 / 窗口 |
| 侧边栏 | 新建对话 / 自动化 / 自定义配置 / 项目 / 设置 |
| 输入框 | 输入任何问题，输入 @ 提及，/ 触发操作 |
| 设置页 | 模型、智能体、Token 用量、WSL 环境等 |

## 原理

```
app.asar
  ├─ dist/preload.js                  ← 追加 engine.js
  ├─ dist/ideInstall/wizardPreload.js ← 追加 engine.js
  └─ 其他文件保持不变
          ↓ @electron/asar 重新打包
app.asar（汉化版）
```

Antigravity 的界面是远端页面渲染的，`preload` 运行在页面上下文里、能拿到 DOM，所以在 preload 末尾挂一个 `MutationObserver` 就能在元素出现时把英文文案替换掉。官方更新会整包替换安装目录，因此汉化必然被覆盖 —— 重新运行一次即可。

## 环境要求

- Windows 10 / 11（路径与进程处理按 Windows 写的）
- Python 3.8+
- Node.js **>= 22.12**（`@electron/asar` 的要求）

## 使用

```bash
git clone https://github.com/renjiacheng524-ux/antigravity-chinese-patch.git
cd antigravity-chinese-patch
npm install
```

**先彻底退出 Antigravity**（`app.asar` 被占用会写不进去），然后：

```bash
python hanhua.py            # 汉化；若目录下有 launch_antigravity.vbs 则顺带启动
python hanhua.py patch      # 只汉化，不启动（适合给启动器调用）
python hanhua.py check      # 只检查：已汉化 exit 0，未汉化 exit 2
python hanhua.py --dry-run  # 只试打包到 _new.asar，不动安装目录、不关进程
```

默认安装路径为 `%LOCALAPPDATA%\Programs\Antigravity\resources\app.asar`。装在别处的话，改 `hanhua.py` 顶部的 `ASAR` 常量。

执行成功后原版会备份在同目录：

```
app.asar.bak-20261111-205027
```

## 更新后自动重打（可选）

`check` 的退出码是给外部脚本用的契约：`0` = 已汉化，`2` = 需要重打。可以在启动器里这么做：

1. 启动前算一下 `app.asar` 的 `大小|修改时间`，和上次汉化后记下的值比对（不一致说明被更新覆盖了，这一步不启动 Python，零开销）
2. 不一致就跑 `python hanhua.py check`；返回 `2` 就再跑 `python hanhua.py patch`
3. 打完更新记录值，再正常拉起 `Antigravity.exe`

把启动器放在安装目录**之外**（例如 `%LOCALAPPDATA%\antigravity-launcher\`），更新就不会把它一起删掉。

## 翻译引擎（engine.js）

- **词典匹配**：`dictionary` 是 `"原文": "中文"` 的精确映射，覆盖菜单、按钮、设置项、提示语等界面固定文案
- **分词兜底**：`coreWords` 对未收录的短语做整词替换
- **动态模式**：对 `See 3 more`、`Install <名称>`、`Uninstall <名称>` 这类会变形的文案用正则处理
- **监听范围**：文本节点，以及 `placeholder` / `title` / `aria-label` / `value` 属性；穿透 Shadow DOM
- **保护**：代码块、文件内容、斜杠命令、输入框里用户输入的 `value` 一律跳过；已翻译节点打标记，避免重复处理
- **性能**：无英文字母的文本直接短路返回，字符串级缓存 O(1) 命中，变更用微任务批量处理

## 补充词条

在 `engine.js` 的 `dictionary` 里按同样格式加一行，然后重新运行 `python hanhua.py patch`。脚本会先剥离旧引擎再写入新引擎，因此可以直接覆盖升级。

```js
"Some new button": "某个新按钮",
```

注意 key 必须和界面上的英文**完全一致**（大小写、标点、结尾空格都算），动态文案适合加正则模式而不是词典。欢迎 PR。

## 已知限制

- 只翻译**本地 UI 文案**。服务端下发的动态内容（首页问候语、模型回复、任务标题）不在覆盖范围内
- 新版本会新增界面文案，需要补充词典
- 汉化会随官方更新失效，属预期行为；用上面的自愈启动器可自动恢复
- 只测过 Windows 版 Antigravity（当前验证版本 2.31.0）

## 还原原版

用备份覆盖回去，或在 Antigravity 卸载重装：

```powershell
Copy-Item "$env:LOCALAPPDATA\Programs\Antigravity\resources\app.asar.bak-<时间戳>" `
          "$env:LOCALAPPDATA\Programs\Antigravity\resources\app.asar" -Force
```

## 免责声明

本项目为非官方社区工具，与 Google 无关。Antigravity 及其名称、商标、代码版权归 Google 所有。本工具仅在你的本机修改已安装副本，仓库不包含、也不分发任何 Antigravity 代码或二进制。修改 `app.asar` 属于非官方行为，可能因版本更新、签名校验等原因失效；请自行评估风险，出问题用备份还原。

## License

[MIT](LICENSE)

---

## English

An unofficial Chinese (Simplified) localization patch for the Google Antigravity desktop client. Since Antigravity ships no language pack, this tool repacks `resources/app.asar`: it appends a DOM runtime translation engine (`engine.js`) to `dist/preload.js` and `dist/ideInstall/wizardPreload.js`, then repacks with the official `@electron/asar`. Windows only, requires Python 3.8+ and Node.js >= 22.12.

```bash
npm install
python hanhua.py patch   # quit Antigravity first
python hanhua.py check   # exit 0 = localized, 2 = needs patching
```

Only local UI strings are translated; server-provided content stays in English. No Antigravity code is redistributed. Not affiliated with Google.