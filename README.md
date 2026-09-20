# GetMDList

把整个项目文件夹变成一份 MD 清单，直接丢给 AI。
Turn a project folder into a single MD file — paste it to any AI.

下载即用，无需安装 Python。全程本地运行，不上传任何数据。
Download-and-run. No Python required. Runs entirely offline — no data leaves your machine.

---

## 📥 下载 / Download

| 语言 / Language | 文件 / File |
|----------------|-------------|
| 中文 | `GetMDLis_c.exe` |
| English | `GetMDList_e.exe` |

双击运行即可。若被 Windows 拦截，见文末说明。
Double-click to run. If Windows blocks it, see the note at the bottom.

---

## 🚀 使用 / Usage

### 1. 选文件夹 / Choose a folder

把项目文件夹**拖进窗口**，或点「Open Folder / 选择文件夹」。
Drag your project folder **into the window**, or click "Open Folder".

> 💡 窗口缩成屏幕边缘的细条时，**把文件夹拖到细条附近，窗口会自动弹出来**。
> 不用先双击展开再拖。
>
> 💡 When the window is collapsed into a thin strip at the screen edge,
> **drag the folder near the strip and the window pops out automatically.**
> No need to double-click to expand first.

加载后，左边显示整个项目的目录树。
The full project tree appears on the left.

---

### 2. 标注（可选）/ Mark (optional)

点击树里的**文件或文件夹名**，在状态间循环切换：
Click a **file or folder name** in the tree to cycle through states:

| 状态 / State | 颜色 / Color | 谁会有 / Applies to | 含义 / Meaning |
|------|------|--------|------|
| 正常 / Normal | 默认 / default | 文件 + 文件夹 | 读取内容，出现在报告里 / Read, appears in the report |
| 标红 / Red | 🔴 | 文件 + 文件夹 | **不读取内容**，只在目录树里留名字 / Not read, name only in tree |
| 标黑 / Black | ⬛ | 文件 + 文件夹 | **完全隐身**，目录树和内容区都不出现 / Fully hidden |
| 混杂 / Mixed | 🟡 | 只有文件夹 / folders only | 内部状态不一致，程序自动算的 / Auto-computed: children have mixed states |

> 🟡 **混杂不影响读取**，只是提醒你"这个文件夹里动过手脚"。
> 比如 `src/` 里有 3 个文件，你只标红了 1 个，`src/` 就会变黄。
>
> 🟡 **Mixed does not affect reading** — it just tells you "something inside was marked".
> E.g. if `src/` has 3 files and you mark only 1 red, `src/` turns yellow.

**用途 / Use cases:**
- 不想让 AI 看的文件 → 标红 / Files you don't want the AI to see → Red
- `node_modules`、日志、测试数据 → 标黑，报告能小很多 / Black out `node_modules`, logs, test data — the report gets much smaller
- 右键文件夹 → 批量标注整个文件夹 / Right-click a folder → mark the whole folder at once

**不标注也行**，默认全部读取。
**Marking is optional** — everything is read by default.

---

### 3. 生成 MD / Generate MD

点「Generate MD / 生成 MD」。
Click "Generate MD".

程序把所有**正常状态**的文本文件内容，连同目录结构，汇总成一份 Markdown。
标红和标黑的内容不会进去。
All **normal-state** text files plus the folder structure are bundled into one Markdown.
Red and black items are excluded.

项目大时可能要等几秒，按钮短暂无响应是正常的。
For large projects this may take a few seconds — a brief freeze is normal.

---

### 4. 拿到文件 / Get the file

生成后**自动跳到 MD 页面**，底部有一个 **MD 图标**。
After generation you're **switched to the MD page** automatically. There's an **MD icon** at the bottom.

**按住它，拖到桌面 / 聊天窗口 / 资源管理器，松手即复制。**
**Press and drag it to your desktop / chat window / file manager, then release to copy.**

> ⚠️ 生成的 md 在系统临时目录里，**程序退出时自动删除**。
> 要用就**当场拖出去**。
>
> ⚠️ The generated md lives in the system temp folder and is **deleted when the app exits**.
> **Drag it out right away** if you need it.

---

### 5. 发给 AI / Paste to AI

把拖出来的 md 文件上传给 ChatGPT / Claude / 豆包 / 通义千问，
或复制内容粘进对话框，或让 agent 直接读这个文件。
Upload the md file to ChatGPT / Claude / Doubao / Qwen,
or copy its content into the chat box, or let your agent read the file directly.

AI 就能一次看到整个项目的结构和全部代码。
The AI sees the whole project structure and all code in one shot.

---

## 📜 预览翻页 / Preview paging

MD 预览 500 行一屏，项目大了要翻页：
The preview shows 500 lines per screen. For large projects:

- **滚轮到顶/底继续滚** → 自动翻上一页 / 下一页
  **Wheel past top/bottom** → auto flip to prev/next page
- **拖动滚动条到顶/底** → 同样翻页
  **Drag scrollbar to top/bottom** → same behavior
- 顶部显示当前行号范围
  Line range is shown at the top

---

## 📌 窗口操作 / Window

- 默认贴屏幕右侧，拖标题栏移动，靠近边缘自动吸附
  Docked right by default; drag the title bar to move; snaps to the nearest edge
- 没加载文件夹时缩成一条 6 像素边条，**双击展开**
  Collapses to a 6px strip when no folder is loaded — **double-click to expand**
- **拖动文件夹靠近边条时，窗口会自动弹出**，可直接拖入
  **Drag a folder near the strip and the window pops out** so you can drop it in
- 关闭窗口**不等于**退出，程序缩到托盘
  Closing the window **does not** quit — the app goes to the tray
- 托盘右键：「选择文件夹 / 隐藏窗口 / 退出」
  Tray right-click: "Open Folder / Hide Window / Quit"

---

## ⚠️ 被 Windows 拦截？/ Blocked by Windows?

未签名程序可能弹「未知发布者」警告，**不是病毒**。
Unsigned apps may trigger an "Unknown publisher" warning. **It's not a virus.**

- 右键 exe → 属性 → 勾选「解除锁定」→ 确定
  Right-click exe → Properties → check "Unblock" → OK
- 或点警告里的「更多信息」→「仍要运行」
  Or click "More info" → "Run anyway"

---

## 💻 系统要求 / Requirements

Windows 10 / 11（64 位），无需安装 Python。
Windows 10 / 11 (64-bit). No Python required.

---

## License

GNU General Public License v3.0 (GPL-3.0)

## Third-Party Components

This project uses the following third-party components:

| Component | License | Usage |
|-----------|---------|-------|
| PyQt5 | GPL v3 | GUI framework |

PyQt5 is copyright (c) Riverbank Computing Limited.
