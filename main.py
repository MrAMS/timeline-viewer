import random
import unittest

from timeline_viewer import TimelineViewer, assign_event_lanes, build_objects_summary, flatten_objects_data


def generate_demo_data(object_count: int = 240) -> list[dict[str, object]]:
    rng = random.Random(20260331)
    action_pool = [
        "需求",
        "方案",
        "设计",
        "开发",
        "联调",
        "测试",
        "修复",
        "验收",
        "上线",
        "复盘",
    ]
    data: list[dict[str, object]] = []
    for idx in range(object_count):
        name = f"对象_{idx + 1:04d}"
        event_count = rng.randint(4, 9)
        base = rng.uniform(0.0, 120.0)
        cursor = base
        events: list[list[object]] = []
        for event_idx in range(event_count):
            overlap = rng.random() < 0.38
            start = cursor - rng.uniform(0.0, 4.5) if overlap else cursor + rng.uniform(0.3, 2.4)
            duration = rng.uniform(1.2, 8.5)
            end = start + duration
            anno = f"{action_pool[event_idx % len(action_pool)]}-{event_idx + 1}"
            events.append([anno, round(start, 2), round(end, 2)])
            cursor = max(cursor, start) + rng.uniform(1.0, 3.6)
        data.append({"name": name, "events": events})
    return data


class TimelineViewerTests(unittest.TestCase):
    def test_generate_demo_data_shape(self) -> None:
        data = generate_demo_data(180)
        self.assertEqual(len(data), 180)
        self.assertTrue(all("name" in item and "events" in item for item in data))
        self.assertTrue(all(len(item["events"]) >= 4 for item in data))

    def test_summary_matches_generated_objects(self) -> None:
        data = generate_demo_data(40)
        events_df = flatten_objects_data(data)
        summary_df = build_objects_summary(events_df)
        self.assertEqual(len(summary_df), 40)
        self.assertTrue((summary_df["事件数"] >= 4).all())
        self.assertTrue((summary_df["最晚结束"] >= summary_df["最早开始"]).all())

    def test_assign_event_lanes_splits_overlaps(self) -> None:
        data = [
            {"name": "对象A", "events": [["事件1", 0.0, 4.0], ["事件2", 1.0, 3.0], ["事件3", 4.0, 6.0]]},
            {"name": "对象B", "events": [["事件4", 2.0, 5.0]]},
        ]
        lane_df, category_order = assign_event_lanes(flatten_objects_data(data))
        lanes_for_a = lane_df[lane_df["对象"] == "对象A"]["泳道"].nunique()
        lanes_for_b = lane_df[lane_df["对象"] == "对象B"]["泳道"].nunique()

        self.assertEqual(lanes_for_a, 2)
        self.assertEqual(lanes_for_b, 1)
        self.assertGreaterEqual(len(category_order), 3)

    def test_viewer_accepts_external_data(self) -> None:
        viewer = TimelineViewer(
            data=[
                {"name": "对象X", "events": [["事件A", 1.5, 3.5], ["事件B", 4.0, 5.25]]},
                {"name": "对象Y", "events": [["事件C", 0.0, 1.0]]},
            ]
        )
        self.assertEqual(viewer.all_names, ["对象X", "对象Y"])
        self.assertEqual(len(viewer.events_df), 3)
        self.assertEqual(viewer.events_df.iloc[0]["对象"], "对象X")

    def test_viewer_rejects_non_numeric_event_time(self) -> None:
        with self.assertRaises(TypeError):
            TimelineViewer(data=[{"name": "对象X", "events": [["事件A", "1.5", 3.5]]}])


if __name__ == "__main__":
    TimelineViewer(data=generate_demo_data()).render()
