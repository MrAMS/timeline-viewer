# Timeline Viewer

一个基于 Streamlit 的对象事件甘特图查看器。

输入数据格式：

```python
[
    {
        "name": "对象A",
        "events": [
            ["需求分析", 0.0, 4.5],
            ["开发", 4.5, 10.0],
            ["测试", 8.0, 12.0],
        ],
    },
    {
        "name": "对象B",
        "events": [
            ["设计", 1.5, 5.5],
            ["联调", 6.0, 9.0],
        ],
    },
]
```

其中：

- `name` 必须是非空字符串。
- `events` 必须是列表。
- 每个事件必须是 `[anno: str, beg: float, end: float]`。
- `beg` 和 `end` 需要是数值类型，不会自动把字符串时间戳转换成浮点数。

## 功能

- 按对象名搜索对象。
- 用表格勾选对象，分页浏览大量对象。
- 支持当前页全选/取消全选。
- 通过 `添加所选`、`删除所选`、`删除全部` 管理显示集合。
- 甘特图支持双端时间窗口拖条。
- 同一对象的重叠事件会自动拆到多行，不重叠事件会复用同一行。
- 每个事件条内部显示事件名。
- 甘特图下方会显示“当前甘特图对象”表，可对当前图上对象继续筛选和删除。

## 文件结构

- `timeline_viewer.py`: 纯粹的 `TimelineViewer` 实现，以及数据校验、汇总、分泳道等核心逻辑。
- `main.py`: 运行入口、用于演示的大样本数据生成器、以及单元测试。

## 运行

直接运行 `main.py` 时，会使用大样本测试数据启动查看器：

```bash
streamlit run main.py
```

## 作为组件使用

你也可以在别的脚本里直接导入 `TimelineViewer`：

```python
from timeline_viewer import TimelineViewer

data = [
    {"name": "对象A", "events": [["事件1", 0.0, 3.0], ["事件2", 2.5, 5.0]]},
    {"name": "对象B", "events": [["事件3", 1.0, 4.0]]},
]

TimelineViewer(data=data, title="我的时间线").render()
```

## 测试

单元测试已经合并到 `main.py`，可以直接运行：

```bash
python -m unittest main -v
```

当前测试覆盖：

- 大样本数据生成结果的基本结构。
- 汇总表统计是否正确。
- 重叠事件是否被正确分配到多泳道。
- `TimelineViewer` 是否接受合法外部数据。
- 非数值时间是否会被明确拒绝。

## 设计说明

这个项目现在刻意分成两层：

- `timeline_viewer.py` 只负责 viewer 本身，不放测试数据生成逻辑。
- `main.py` 负责 demo 和测试，这样 viewer 主体更干净，外部接入时只需要关心一个类。
