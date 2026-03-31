import math
from colorsys import hsv_to_rgb
from dataclasses import dataclass
from numbers import Real
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st


ObjectEvent = list[Any]
ObjectRecord = dict[str, Any]


def validate_objects_data(data: list[ObjectRecord]) -> list[ObjectRecord]:
    validated: list[ObjectRecord] = []
    for item in data:
        if not isinstance(item, dict):
            raise TypeError("Each object must be a dict with keys 'name' and 'events'.")

        name = item.get("name")
        events = item.get("events")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Object 'name' must be a non-empty string.")
        if not isinstance(events, list):
            raise TypeError("Object 'events' must be a list.")

        validated_events: list[ObjectEvent] = []
        for event in events:
            if not isinstance(event, (list, tuple)) or len(event) != 3:
                raise ValueError("Each event must be [anno: str, beg: float, end: float].")
            anno, beg, end = event
            if not isinstance(anno, str):
                raise TypeError("Event anno must be a string.")
            if not isinstance(beg, Real) or not isinstance(end, Real):
                raise TypeError("Event beg/end must be float-like numbers.")
            validated_events.append([anno, float(beg), float(end)])

        validated.append({"name": name, "events": validated_events})
    return validated


def flatten_objects_data(data: list[ObjectRecord]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for obj in data:
        for anno, beg, end in obj["events"]:
            rows.append({"对象": obj["name"], "事件": anno, "开始": float(beg), "结束": float(end)})
    return pd.DataFrame(rows, columns=["对象", "事件", "开始", "结束"])


def build_objects_summary(events_df: pd.DataFrame) -> pd.DataFrame:
    if events_df.empty:
        return pd.DataFrame(columns=["对象", "事件数", "最早开始", "最晚结束"])
    return (
        events_df.groupby("对象", sort=False)
        .agg(事件数=("事件", "count"), 最早开始=("开始", "min"), 最晚结束=("结束", "max"))
        .reset_index()
        .sort_values("对象")
        .reset_index(drop=True)
    )


def build_color_map(names: list[str]) -> dict[str, str]:
    color_map: dict[str, str] = {}
    total = max(len(names), 1)
    for idx, name in enumerate(names):
        hue = idx / total
        red, green, blue = hsv_to_rgb(hue, 0.55, 0.86)
        color_map[name] = "#{:02x}{:02x}{:02x}".format(
            int(red * 255), int(green * 255), int(blue * 255)
        )
    return color_map


def assign_event_lanes(plot_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if plot_df.empty:
        return plot_df.copy(), []

    rows: list[dict[str, Any]] = []
    category_order: list[str] = []
    for object_name, group in plot_df.groupby("对象", sort=False):
        lane_ends: list[float] = []
        lane_labels: list[str] = []
        sorted_group = group.sort_values(["开始", "结束", "事件"], kind="stable")
        for _, event in sorted_group.iterrows():
            lane_idx = None
            for idx, lane_end in enumerate(lane_ends):
                if float(event["开始"]) >= lane_end:
                    lane_idx = idx
                    lane_ends[idx] = float(event["结束"])
                    break
            if lane_idx is None:
                lane_idx = len(lane_ends)
                lane_ends.append(float(event["结束"]))
                lane_labels.append(object_name if lane_idx == 0 else object_name + ("\u200b" * lane_idx))

            rows.append(
                {
                    "对象": object_name,
                    "事件": event["事件"],
                    "开始": float(event["开始"]),
                    "结束": float(event["结束"]),
                    "持续": float(event["结束"]) - float(event["开始"]),
                    "泳道": lane_labels[lane_idx],
                }
            )
        category_order.extend(reversed(lane_labels))
    return pd.DataFrame(rows), category_order


@dataclass
class TimelineViewer:
    data: list[ObjectRecord]
    title: str = "对象事件甘特图"
    session_prefix: str = "timeline_viewer"
    initial_visible_count: int = 12
    max_plot_rows: int = 5000

    def __post_init__(self) -> None:
        self.data = validate_objects_data(self.data)
        self.events_df = flatten_objects_data(self.data)
        self.summary_df = build_objects_summary(self.events_df)
        self.all_names = self.summary_df["对象"].astype(str).tolist()

    def _key(self, suffix: str) -> str:
        return f"{self.session_prefix}_{suffix}"

    def _get_state_list(self, suffix: str) -> list[str]:
        key = self._key(suffix)
        current = st.session_state.get(key, [])
        return [name for name in current if name in self.all_names]

    def _set_state_list(self, suffix: str, values: list[str]) -> None:
        st.session_state[self._key(suffix)] = values

    def _ensure_state(self) -> None:
        defaults = {
            "selected_objects": [],
            "visible_selected_objects": [],
            "visible_objects": self.all_names[: min(self.initial_visible_count, len(self.all_names))],
        }
        for suffix, default in defaults.items():
            if self._key(suffix) not in st.session_state:
                self._set_state_list(suffix, default)
            else:
                self._set_state_list(suffix, self._get_state_list(suffix))

    def _sync_selected_from_page(self, page_df: pd.DataFrame, selection_suffix: str) -> None:
        selected = set(self._get_state_list(selection_suffix))
        page_names = set(page_df["对象"].astype(str).tolist())
        page_selected = set(page_df.loc[page_df["选择"], "对象"].astype(str).tolist())
        self._set_state_list(selection_suffix, sorted((selected - page_names) | page_selected))

    def _render_object_table(
        self,
        filtered_summary: pd.DataFrame,
        panel_key: str,
        selection_suffix: str,
    ) -> tuple[set[str], set[str]]:
        if filtered_summary.empty:
            st.info("没有匹配的对象。")
            return set(), set()

        c1, c2, c3 = st.columns([1, 1, 2])
        page_size = c1.selectbox(
            "每页条数", [25, 50, 100, 200], index=1, key=self._key(f"{panel_key}_page_size")
        )
        total_pages = max(1, math.ceil(len(filtered_summary) / page_size))
        current_page = min(int(st.session_state.get(self._key(f"{panel_key}_page"), 1)), total_pages)
        page = int(
            c2.number_input(
                "页码",
                min_value=1,
                max_value=total_pages,
                value=current_page,
                step=1,
                key=self._key(f"{panel_key}_page"),
            )
        )

        start = (page - 1) * page_size
        page_df = filtered_summary.iloc[start : start + page_size].copy()
        current_selected = set(self._get_state_list(selection_suffix))
        page_names = set(page_df["对象"].astype(str).tolist())
        page_all_selected = bool(page_names) and page_names.issubset(current_selected)

        c3.caption(f"当前筛选结果 {len(filtered_summary)} 项，已勾选 {len(current_selected)} 项。")
        toggle_label = "取消当前页全选" if page_all_selected else "全选当前页"
        if c3.button(toggle_label, key=self._key(f"{panel_key}_toggle_page_selection"), width="stretch"):
            if page_all_selected:
                current_selected -= page_names
            else:
                current_selected |= page_names
            self._set_state_list(selection_suffix, sorted(current_selected))
            st.rerun()

        page_df.insert(0, "选择", page_df["对象"].isin(current_selected))
        edited_df = st.data_editor(
            page_df,
            hide_index=True,
            width="stretch",
            disabled=["对象", "事件数", "最早开始", "最晚结束"],
            column_config={
                "选择": st.column_config.CheckboxColumn("选择"),
                "对象": st.column_config.TextColumn("对象"),
                "事件数": st.column_config.NumberColumn("事件数"),
                "最早开始": st.column_config.NumberColumn("最早开始", format="%.2f"),
                "最晚结束": st.column_config.NumberColumn("最晚结束", format="%.2f"),
            },
            key=self._key(f"{panel_key}_selector_table"),
        )
        self._sync_selected_from_page(edited_df, selection_suffix)
        return page_names, set(self._get_state_list(selection_suffix))

    def _update_visible_objects(self, new_visible: set[str]) -> None:
        self._set_state_list("visible_objects", [name for name in self.all_names if name in new_visible])

    def _render_time_window(self, plot_df: pd.DataFrame) -> tuple[float, float]:
        min_time = float(plot_df["开始"].min())
        max_time = float(plot_df["结束"].max())
        if min_time == max_time:
            st.caption(f"事件时间窗口固定为 {min_time:.2f}")
            return min_time, max_time

        step = max((max_time - min_time) / 500.0, 0.01)
        return st.slider(
            "事件时间窗口",
            min_value=min_time,
            max_value=max_time,
            value=(min_time, max_time),
            step=step,
            key=self._key("time_window"),
        )

    def _build_plot_df_for_visible_objects(self) -> tuple[pd.DataFrame, float | None, float | None]:
        visible = self._get_state_list("visible_objects")
        plot_df = self.events_df[self.events_df["对象"].isin(visible)].copy()
        plot_df = plot_df[plot_df["结束"] >= plot_df["开始"]].copy()
        if plot_df.empty:
            return plot_df, None, None

        window_start, window_end = self._render_time_window(plot_df)
        plot_df = plot_df[(plot_df["结束"] >= window_start) & (plot_df["开始"] <= window_end)].copy()
        return plot_df, window_start, window_end

    def _render_selector_panel(
        self,
        title: str,
        summary_df: pd.DataFrame,
        panel_key: str,
        selection_suffix: str,
        search_suffix: str,
        caption_prefix: str,
    ) -> tuple[set[str], set[str], set[str]]:
        st.subheader(title)
        search_name = st.text_input(
            "搜索对象名",
            value="",
            key=self._key(search_suffix),
            placeholder="按对象 name 搜索",
        )
        filtered_summary = summary_df.copy()
        if search_name.strip():
            filtered_summary = filtered_summary[
                filtered_summary["对象"].str.contains(search_name.strip(), case=False, na=False)
            ].reset_index(drop=True)

        _, selected_names = self._render_object_table(filtered_summary, panel_key, selection_suffix)
        filtered_names = set(filtered_summary["对象"].astype(str).tolist())
        st.caption(f"{caption_prefix} {len(filtered_names)} 项，当前勾选 {len(selected_names)} 项。")
        return filtered_names, selected_names, set(self._get_state_list("visible_objects"))

    def _render_controls(self) -> None:
        _, selected_names, visible_names = self._render_selector_panel(
            title="对象筛选与显示集合",
            summary_df=self.summary_df,
            panel_key="all_objects",
            selection_suffix="selected_objects",
            search_suffix="search_name",
            caption_prefix="当前显示集合",
        )
        b1, b2, b3 = st.columns(3)
        if b1.button("添加所选", key=self._key("add_selected"), width="stretch"):
            self._update_visible_objects(visible_names | selected_names)
            st.rerun()
        if b2.button("删除所选", key=self._key("remove_selected"), width="stretch"):
            self._update_visible_objects(visible_names - selected_names)
            st.rerun()
        if b3.button("删除全部", key=self._key("remove_all"), width="stretch"):
            self._set_state_list("visible_objects", [])
            st.rerun()

    def _render_chart(self, plot_df: pd.DataFrame, window_start: float, window_end: float) -> None:
        st.subheader("甘特图")
        if plot_df.empty:
            st.info("显示集合为空，或当前时间窗口内没有可显示事件。")
            return

        if len(plot_df) > self.max_plot_rows:
            plot_df = plot_df.sort_values(["对象", "开始", "结束", "事件"]).head(self.max_plot_rows)
            st.warning(f"事件过多，仅渲染前 {self.max_plot_rows} 条。")

        lane_df, category_order = assign_event_lanes(plot_df)
        color_map = build_color_map(sorted(lane_df["对象"].unique().tolist()))
        fig = px.bar(
            lane_df,
            x="持续",
            y="泳道",
            base="开始",
            color="对象",
            orientation="h",
            text="事件",
            hover_name="事件",
            hover_data={
                "事件": False,
                "开始": ":.2f",
                "结束": ":.2f",
                "持续": ":.2f",
                "对象": True,
                "泳道": False,
            },
            color_discrete_map=color_map,
        )
        fig.update_traces(textposition="inside", insidetextanchor="middle", cliponaxis=False)
        fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=category_order)
        fig.update_layout(
            height=max(420, min(1800, 36 * max(len(category_order), 12))),
            xaxis_title="时间轴（浮点数）",
            yaxis_title=None,
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=False,
            bargap=0.25,
            xaxis=dict(range=[window_start, window_end]),
        )
        st.plotly_chart(fig, width="stretch")
        st.caption(
            f"已显示对象 {lane_df['对象'].nunique()} 个，事件 {len(lane_df)} 条，泳道 {len(category_order)} 条。"
        )

    def _render_visible_objects_panel(self, plot_df: pd.DataFrame) -> None:
        visible_summary = build_objects_summary(plot_df)
        _, selected_names, visible_names = self._render_selector_panel(
            title="当前甘特图对象",
            summary_df=visible_summary,
            panel_key="visible_objects",
            selection_suffix="visible_selected_objects",
            search_suffix="visible_search_name",
            caption_prefix="当前图上对象",
        )

        b1, b2, b3 = st.columns(3)
        if b1.button("仅保留所选", key=self._key("keep_visible_selected"), width="stretch"):
            self._update_visible_objects(visible_names & selected_names)
            st.rerun()
        if b2.button("删除所选", key=self._key("remove_visible_selected"), width="stretch"):
            self._update_visible_objects(visible_names - selected_names)
            st.rerun()
        if b3.button("删除全部", key=self._key("remove_visible_all"), width="stretch"):
            self._set_state_list("visible_objects", [])
            st.rerun()

    def render(self) -> None:
        self._ensure_state()
        st.set_page_config(layout="wide", page_title=self.title)
        st.title(self.title)
        st.markdown("数据格式：`[{name: str, events: [[anno: str, beg: float, end: float], ...]}]`")
        self._render_controls()
        plot_df, window_start, window_end = self._build_plot_df_for_visible_objects()
        if plot_df.empty or window_start is None or window_end is None:
            st.subheader("甘特图")
            st.info("显示集合为空，或当前时间窗口内没有可显示事件。")
            st.subheader("当前甘特图对象")
            st.info("当前甘特图中没有对象可供进一步筛选。")
            return
        self._render_chart(plot_df, window_start, window_end)
        self._render_visible_objects_panel(plot_df)
