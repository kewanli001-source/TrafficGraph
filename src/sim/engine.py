"""engine — 交通仿真引擎（确定性时变模型）

所属层：sim
依赖：src.sim.network
对接算法层：N/A（纯 Python 仿真，不依赖外部框架）

模型要点：
  - 时变需求：按道路等级的早晚高峰高斯曲线 + 周末平坦化
  - 确定性：所有随机量由 sha256(date|subject|kind) 种子驱动，同日同主体同数
  - 服务水平：Webster 近似延误 → HCM LOS A-F
  - 事件影响：按严重度对进口道通行能力施加折减（critical 0.45 / major 0.65 /
    construction 0.75 / minor 0.85）
  - 信号建议：Webster 最优周期 C0=(1.5L+5)/(1-Y) 校验 + 绿波 offset 重整
  - 时钟：默认真实时间；TRAFFIC_SIM_CLOCK 环境变量可固定演示时钟
"""
import logging
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.sim.network import CityNetwork, Intersection, load_network, seeded_rng

logger = logging.getLogger(__name__)

# ── 道路等级模型参数 ──────────────────────────────────
FREEFLOW_KMH = {"主干道": 50, "快速路": 80, "次干道": 40}

# 高斯高峰（小时, σ, 峰高）按道路等级
_PEAKS = {
    "主干道": [(8.2, 0.9, 1.00), (18.1, 1.1, 0.95)],
    "快速路": [(8.0, 0.8, 1.05), (17.5, 1.0, 1.00)],
    "次干道": [(8.5, 1.0, 0.90), (18.3, 1.2, 0.85)],
}
_BASE = {"主干道": 0.30, "快速路": 0.36, "次干道": 0.28}

# 进口道流量份额：干线方向两侧合计 0.72，相交道路两侧合计 0.28
_MAJOR_SHARE, _MINOR_SHARE = 0.36, 0.14

# HCM 服务水平阈值（平均控制延误，秒/车）
_LOS_THRESHOLDS = [(10.0, "A"), (20.0, "B"), (35.0, "C"), (55.0, "D"), (80.0, "E")]

# 事件参数
_SEVERITY_PARAM = {
    "critical":     {"factor": 0.45, "dur_min": (75, 120), "lane": "占用两条车道", "label": "重大"},
    "major":        {"factor": 0.65, "dur_min": (40, 70),  "lane": "占用一条车道", "label": "较大"},
    "minor":        {"factor": 0.85, "dur_min": (15, 35),  "lane": "占用路肩",     "label": "一般"},
    "construction": {"factor": 0.75, "dur_min": (480, 600), "lane": "围挡半幅路面", "label": "施工"},
}


def _los_of(delay_s: float) -> str:
    """平均控制延误 → LOS 等级。"""
    for threshold, letter in _LOS_THRESHOLDS:
        if delay_s <= threshold:
            return letter
    return "F"


def _is_weekend(date: datetime) -> bool:
    return date.weekday() >= 5


def demand_multiplier(road_class: str, date: datetime, hour: float) -> float:
    """道路等级 × 日期 × 时刻 → 需求乘数（相对早高峰基线 1.0）。

    周末高峰削峰约 45%，平峰基线略升。
    """
    peaks = _PEAKS.get(road_class, _PEAKS["主干道"])
    base = _BASE.get(road_class, 0.30)
    weekend = _is_weekend(date)
    factor = base
    for center, sigma, height in peaks:
        h = height * (0.55 if weekend else 1.0)
        factor += h * math.exp(-((hour - center) ** 2) / (2 * sigma ** 2))
    if weekend:
        factor += 0.05
    # 夜间低谷
    if hour < 5.5 or hour > 22.5:
        factor *= 0.35
    return factor


def plan_name_for_hour(hour: int) -> str:
    """小时 → 配时方案名（peak / offpeak / night）。"""
    if 7 <= hour < 9 or 17 <= hour < 19:
        return "peak"
    if 23 <= hour or hour < 5:
        return "night"
    return "offpeak"


def peak_level_for_hour(hour: int) -> str:
    """小时 → 峰值等级描述。"""
    if 7 <= hour < 9:
        return "早高峰"
    if 17 <= hour < 19:
        return "晚高峰"
    if 23 <= hour or hour < 6:
        return "夜间低谷"
    return "平峰"


class TrafficSim:
    """上海市交通仿真引擎。

    所有公开方法返回原始 dict（由 src/tools/traffic_backend.py 转换为
    Pydantic 模型），内部计算只依赖 (date, subject_id) 种子，保证确定性。
    """

    def __init__(self, network: Optional[CityNetwork] = None):
        """初始化仿真引擎。

        Args:
            network: 路网模型；缺省时从 config/traffic_network.yaml 加载
        """
        self.net = network or load_network()

    # ── 时钟 ──────────────────────────────────────

    def now(self) -> datetime:
        """当前仿真时钟：优先 TRAFFIC_SIM_CLOCK 固定时钟，否则真实时间。"""
        fixed = os.getenv("TRAFFIC_SIM_CLOCK")
        if fixed:
            try:
                return datetime.fromisoformat(fixed)
            except ValueError:
                logger.warning(f"TRAFFIC_SIM_CLOCK 非法 ISO 格式: {fixed}，忽略")
        return datetime.now()

    def set_clock(self, value: Optional[datetime]) -> None:
        """固定/恢复仿真时钟（测试用）。None 恢复真实时间。"""
        if value is None:
            os.environ.pop("TRAFFIC_SIM_CLOCK", None)
        else:
            os.environ["TRAFFIC_SIM_CLOCK"] = value.isoformat()

    # ── 内核计算 ──────────────────────────────────

    def _directions_of(self, inter: Intersection) -> tuple:
        """路口的干线方向与相交方向（进口道方向名）。"""
        corridor = self.net.corridor(inter.corridor)
        if corridor and "南北" in corridor.direction:
            return ("北", "南"), ("东", "西")
        return ("东", "西"), ("北", "南")

    def _capacity_factor(self, inter: Intersection, date: datetime, at: datetime) -> float:
        """事件导致的通行能力折减（取当前活跃事件中最严重者）。"""
        worst = 1.0
        for inc in self._incidents_for_date(date):
            if inc["intersection_id"] != inter.id:
                continue
            start = datetime.fromisoformat(inc["start_time"])
            clear = datetime.fromisoformat(inc["expected_clear"])
            if start <= at < clear:
                worst = min(worst, _SEVERITY_PARAM[inc["severity"]]["factor"])
        return worst

    def _approach_states(
        self,
        inter: Intersection,
        at: datetime,
        date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """计算路口各进口道实时状态（需求/饱和度/排队/延误/二次排队）。

        Args:
            inter: 路口
            at: 仿真时刻
            date: 归属日期（默认 at 的日期），种子以此为准

        Returns:
            每个进口道的状态字典列表
        """
        date = date or at
        date_str = date.strftime("%Y-%m-%d")
        hour = at.hour + at.minute / 60.0
        plan_name = plan_name_for_hour(at.hour)
        plan = inter.plans[plan_name]
        cycle = plan.cycle_s
        major_dirs, minor_dirs = self._directions_of(inter)
        cap_factor = self._capacity_factor(inter, date, at)
        rng = seeded_rng(date_str, inter.id, "status")

        approach_by_dir = {a.direction: a for a in inter.approaches}
        states: List[Dict[str, Any]] = []
        for direction, share in [(major_dirs[0], _MAJOR_SHARE), (major_dirs[1], _MAJOR_SHARE),
                                 (minor_dirs[0], _MINOR_SHARE), (minor_dirs[1], _MINOR_SHARE)]:
            approach = approach_by_dir.get(direction)
            lanes = approach.lanes if approach else 3
            sat_flow = inter.saturation_flow
            # 主相位绿灯：东西向取"东西直行"，南北向取"南北直行"
            phase_keyword = "东西" if direction in ("东", "西") else "南北"
            main_phase = next(
                (p for p in plan.phases if phase_keyword in p.name and "直行" in p.name),
                plan.phases[0],
            )
            green_ratio = max(0.05, main_phase.green_s / cycle)
            demand = inter.base_volume * share * demand_multiplier(inter.road_class, date, hour)
            demand *= rng.uniform(0.92, 1.08)
            capacity = sat_flow * green_ratio * cap_factor * lanes / 3.0
            vc = demand / capacity if capacity > 0 else 9.99
            vc = min(vc, 2.5)

            # Webster 一致延误 + 过饱和附加项（简化）
            lam = green_ratio
            x_eff = min(vc, 0.97)
            d1 = 0.9 * cycle * (1 - lam) ** 2 / (2 * (1 - lam * x_eff))
            d2 = 60.0 * max(0.0, vc - 1.0)
            delay = d1 + d2

            # 排队长度：过饱和溢出近似（6 m/车，按车道均摊）
            queue_m = max(0.0, (vc - 0.85)) * 180.0 * lanes / 3.0 * rng.uniform(0.85, 1.15)
            if vc < 0.85:
                queue_m = rng.uniform(15, 60) * lanes / 3.0
            cycle_failures = int(vc > 1.05) or (1 if vc > 0.95 and rng.random() < 0.3 else 0)

            states.append({
                "approach": f"{direction}进口",
                "lanes": lanes,
                "flow_veh_h": round(demand),
                "capacity_veh_h": round(capacity),
                "saturation": round(vc, 2),
                "queue_m": round(queue_m),
                "avg_delay_s": round(delay, 1),
                "cycle_failures": cycle_failures,
            })
        return states

    def _intersection_metrics(
        self, inter: Intersection, at: datetime, date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """路口汇总指标（饱和度/延误/LOS/均速）。"""
        states = self._approach_states(inter, at, date)
        vcs = [s["saturation"] for s in states]
        delays = [s["avg_delay_s"] for s in states]
        vc = sum(vcs) / len(vcs)
        delay = sum(delays) / len(delays)
        freeflow = FREEFLOW_KMH.get(inter.road_class, 50)
        speed = max(5.0, freeflow * (1 - 0.55 * min(1.0, vc)))
        return {
            "vc": round(vc, 2),
            "delay_s": round(delay, 1),
            "los": _los_of(delay),
            "speed_kmh": round(speed, 1),
            "max_vc": round(max(vcs), 2),
            "max_queue_m": max(s["queue_m"] for s in states),
            "states": states,
        }

    # ── 事件 ──────────────────────────────────────

    def _incidents_for_date(self, date: datetime) -> List[Dict[str, Any]]:
        """生成某日的事件清单（确定性：date 种子）。"""
        date_str = date.strftime("%Y-%m-%d")
        script = self.net.incident_script
        if not script:
            return []
        baseline = script.get("baseline", {})
        types = script.get("types", ["交通事故"])
        rng = seeded_rng(date_str, script.get("daily_seed", "city"), "incidents")

        incidents: List[Dict[str, Any]] = []
        seq = 0
        for severity, base_count in baseline.items():
            count = max(0, round(base_count * rng.uniform(0.8, 1.2)))
            for _ in range(count):
                seq += 1
                inter = self.net.intersections[rng.randrange(len(self.net.intersections))]
                itype = types[rng.randrange(len(types))]
                if severity == "construction":
                    start_hour = 8
                    dur = rng.randint(*_SEVERITY_PARAM[severity]["dur_min"])
                else:
                    # 80% 落在高峰窗口，贴近真实接警分布
                    if rng.random() < 0.8:
                        start_hour = rng.choice([rng.uniform(7, 9), rng.uniform(17, 19)])
                    else:
                        start_hour = rng.uniform(6, 22)
                    dur = rng.randint(*_SEVERITY_PARAM[severity]["dur_min"])
                start = date.replace(hour=0, minute=0, second=0) + timedelta(hours=start_hour)
                clear = start + timedelta(minutes=dur)
                param = _SEVERITY_PARAM[severity]
                incidents.append({
                    "incident_id": f"INC-{date_str.replace('-', '')}-{seq:02d}",
                    "type": itype,
                    "severity": severity,
                    "severity_label": param["label"],
                    "location": inter.name,
                    "intersection_id": inter.id,
                    "lane_block": param["lane"],
                    "start_time": start.isoformat(),
                    "expected_clear": clear.isoformat(),
                    "status": "处置中",
                    "impact_level": "高" if severity in ("critical", "construction") else ("中" if severity == "major" else "低"),
                })
        incidents.sort(key=lambda i: i["start_time"])
        return incidents

    def active_incidents(self, at: Optional[datetime] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        """当前活跃事件（窗口 [start, clear) 内）。"""
        at = at or self.now()
        result = []
        # 查看今日与昨日（跨零点事件）
        for day_offset in (0, 1):
            day = at - timedelta(days=day_offset)
            for inc in self._incidents_for_date(day):
                start = datetime.fromisoformat(inc["start_time"])
                clear = datetime.fromisoformat(inc["expected_clear"])
                if start <= at < clear:
                    result.append(inc)
        if severity:
            result = [i for i in result if i["severity"] == severity]
        return result

    # ── 公开查询（供 traffic_backend 调用） ─────────

    def city_overview(self, date: Optional[str] = None) -> Dict[str, Any]:
        """全市态势总览。"""
        at = datetime.fromisoformat(date) if date else self.now()
        metrics = {}
        for inter in self.net.intersections:
            m = self._intersection_metrics(inter, at)
            m["name"] = inter.name
            metrics[inter.id] = m
        weighted_vc = sum(m["vc"] * w for m, w in
                          ((metrics[i.id], i.base_volume) for i in self.net.intersections))
        weighted_vc /= sum(i.base_volume for i in self.net.intersections)
        index = max(0.0, min(10.0, 1.2 + weighted_vc * 6.0))
        yesterday = at - timedelta(days=1)
        y_metrics = {i.id: self._intersection_metrics(i, at.replace(
            year=yesterday.year, month=yesterday.month, day=yesterday.day)) for i in self.net.intersections}
        y_index = max(0.0, min(10.0, 1.2 + sum(
            m["vc"] * i.base_volume for m, i in zip(y_metrics.values(), self.net.intersections)
        ) / sum(i.base_volume for i in self.net.intersections) * 6.0))
        top5 = sorted(self.net.intersections, key=lambda i: metrics[i.id]["max_vc"], reverse=True)[:5]
        avg_speed = sum(m["speed_kmh"] for m in metrics.values()) / len(metrics)
        return {
            "city": self.net.city_name,
            "congestion_index": round(index, 1),
            "trend_vs_yesterday": round(index - y_index, 1),
            "peak_level": peak_level_for_hour(at.hour),
            "avg_speed_kmh": round(avg_speed, 1),
            "top5_congested_intersections": [
                {"id": i.id, "name": i.name, "saturation": metrics[i.id]["max_vc"],
                 "queue_m": metrics[i.id]["max_queue_m"]}
                for i in top5
            ],
            "active_incident_count": len(self.active_incidents(at)),
            "timestamp": at.isoformat(),
        }

    def intersection_status(self, intersection_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """单路口实时状态。"""
        inter = self.net.intersection(intersection_id)
        if inter is None:
            return {"error": f"路口不存在: {intersection_id}，可用路口如 JK-SJ01"}
        at = datetime.fromisoformat(date) if date else self.now()
        m = self._intersection_metrics(inter, at)
        plan_name = plan_name_for_hour(at.hour)
        plan = inter.plans[plan_name]
        active = [i for i in self.active_incidents(at) if i["intersection_id"] == inter.id]
        return {
            "id": inter.id,
            "name": inter.name,
            "corridor": self.net.name_of("corridor", inter.corridor),
            "district": self.net.name_of("district", inter.district),
            "los": m["los"],
            "saturation": m["vc"],
            "avg_delay_s": m["delay_s"],
            "queue": [{"approach": s["approach"], "queue_m": s["queue_m"],
                       "saturation": s["saturation"], "cycle_failures": s["cycle_failures"]}
                      for s in m["states"]],
            "current_phase": plan.phases[at.minute % max(1, len(plan.phases))].name,
            "cycle_len_s": plan.cycle_s,
            "active_plan": plan_name,
            "incident_effect": active[0]["lane_block"] + f"（{active[0]['type']}）" if active else None,
            "timestamp": at.isoformat(),
        }

    def corridor_congestion(self, corridor_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """干线走廊拥堵与绿波状态。"""
        corridor = self.net.corridor(corridor_id)
        if corridor is None:
            return {"error": f"干线不存在: {corridor_id}，可用干线如 COR-SJ"}
        at = datetime.fromisoformat(date) if date else self.now()
        date_str = at.strftime("%Y-%m-%d")
        inters = self.net.intersections_of_corridor(corridor_id)
        per_inter = []
        for inter in inters:
            m = self._intersection_metrics(inter, at)
            rng = seeded_rng(date_str, inter.id, "offset")
            dev = rng.uniform(0, 12)
            per_inter.append({"id": inter.id, "name": inter.name, "saturation": m["vc"],
                              "speed_kmh": m["speed_kmh"], "offset_s": inter.offset_s,
                              "offset_deviation_s": round(dev, 1)})
        mean_vc = sum(p["saturation"] for p in per_inter) / len(per_inter)
        mean_dev = sum(p["offset_deviation_s"] for p in per_inter) / len(per_inter)
        avg_speed = sum(p["speed_kmh"] for p in per_inter) / len(per_inter)
        bandwidth = max(0, int(inter.plans["peak"].cycle_s * 0.45 - mean_dev * 2.2)) if inters else 0
        return {
            "id": corridor.id,
            "name": corridor.name,
            "road_class": corridor.road_class,
            "avg_speed_kmh": round(avg_speed, 1),
            "saturation": round(mean_vc, 2),
            "greenwave_status": "已实现" if mean_dev <= 8 and mean_vc < 0.9 else "断裂",
            "greenwave_bandwidth_s": bandwidth,
            "mean_offset_deviation_s": round(mean_dev, 1),
            "intersections": per_inter,
            "timestamp": at.isoformat(),
        }

    def district_congestion(self, district_id: str, date: Optional[str] = None) -> Dict[str, Any]:
        """辖区拥堵指数。"""
        district = self.net.district(district_id)
        if district is None:
            return {"error": f"辖区不存在: {district_id}，可用辖区如 DIST-CBD"}
        at = datetime.fromisoformat(date) if date else self.now()
        inters = self.net.intersections_of_district(district_id)
        metrics = {i.id: self._intersection_metrics(i, at) for i in inters}
        mean_vc = sum(m["vc"] for m in metrics.values()) / len(metrics) if metrics else 0
        index = round(max(0.0, min(10.0, 1.2 + mean_vc * 6.0)), 1)
        # 与昨日对比（同日同辖区种子）
        yday = at - timedelta(days=1)
        y_metrics = {i.id: self._intersection_metrics(i, at.replace(
            year=yday.year, month=yday.month, day=yday.day)) for i in inters}
        y_vc = sum(m["vc"] for m in y_metrics.values()) / len(y_metrics) if y_metrics else 0
        y_index = round(max(0.0, min(10.0, 1.2 + y_vc * 6.0)), 1)
        # 全市排名
        all_ranks = []
        for d in self.net.districts:
            d_inters = self.net.intersections_of_district(d.id)
            if not d_inters:
                continue
            d_vc = sum(self._intersection_metrics(i, at)["vc"] for i in d_inters) / len(d_inters)
            all_ranks.append((d.id, d_vc))
        all_ranks.sort(key=lambda t: t[1], reverse=True)
        rank = [d for d, _ in all_ranks].index(district_id) + 1
        worst = max(inters, key=lambda i: metrics[i.id]["max_vc"]) if inters else None
        return {
            "id": district.id,
            "name": district.name,
            "congestion_index": index,
            "trend_vs_yesterday": round(index - y_index, 1),
            "rank_in_city": rank,
            "worst_intersection": {"id": worst.id, "name": worst.name,
                                   "saturation": metrics[worst.id]["max_vc"]} if worst else None,
            "intersection_count": len(inters),
            "timestamp": at.isoformat(),
        }

    def signal_timing(self, intersection_id: str, plan_type: Optional[str] = None) -> Dict[str, Any]:
        """路口配时方案。"""
        inter = self.net.intersection(intersection_id)
        if inter is None:
            return {"error": f"路口不存在: {intersection_id}，可用路口如 JK-SJ01"}
        at = self.now()
        plan_name = plan_type or plan_name_for_hour(at.hour)
        if plan_name not in inter.plans:
            return {"error": f"方案不存在: {plan_name}，可用方案 peak/offpeak/night"}
        plan = inter.plans[plan_name]
        rng = seeded_rng(at.strftime("%Y-%m-%d"), inter.id, "timing")
        last_adjusted = at - timedelta(days=rng.randint(1, 14), hours=rng.randint(0, 23))
        return {
            "intersection_id": inter.id,
            "intersection_name": inter.name,
            "current_plan": plan_name,
            "cycle_s": plan.cycle_s,
            "phases": [
                {"name": p.name, "green_s": p.green_s, "yellow_s": p.yellow_s,
                 "min_green_s": p.min_green_s}
                for p in plan.phases if p.green_s > 0
            ],
            "offset_s": inter.offset_s,
            "coordination_group": inter.coordination_group,
            "last_adjusted": last_adjusted.isoformat(),
        }

    def flow_history(
        self,
        intersection_id: Optional[str] = None,
        corridor_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """路口/干线逐时流量历史（24h × N 天）。"""
        if not intersection_id and not corridor_id:
            return {"error": "必须提供 intersection_id 或 corridor_id"}
        if corridor_id:
            corridor = self.net.corridor(corridor_id)
            if corridor is None:
                return {"error": f"干线不存在: {corridor_id}"}
            inters = self.net.intersections_of_corridor(corridor_id)
            subject_name = corridor.name
        else:
            inter = self.net.intersection(intersection_id)
            if inter is None:
                return {"error": f"路口不存在: {intersection_id}"}
            inters = [inter]
            subject_name = inter.name
        at = self.now()
        start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else at - timedelta(days=6)
        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else at
        base_volume = sum(i.base_volume for i in inters)
        road_class = inters[0].road_class
        rng = seeded_rng(f"{start.date()}|{end.date()}", inters[0].id, "flow_history")
        items = []
        day = start
        while day <= end:
            for hour in range(24):
                m = demand_multiplier(road_class, day, hour)
                flow = base_volume * m * rng.uniform(0.93, 1.07)
                vc = m * base_volume / (sum(i.saturation_flow for i in inters) * 0.42)
                freeflow = FREEFLOW_KMH.get(road_class, 50)
                speed = max(5.0, freeflow * (1 - 0.55 * min(1.0, vc)))
                items.append({
                    "datetime": f"{day.strftime('%Y-%m-%d')} {hour:02d}:00",
                    "flow_veh_h": round(flow),
                    "avg_speed_kmh": round(speed, 1),
                    "saturation": round(min(vc, 2.0), 2),
                })
            day += timedelta(days=1)
        return {"subject": subject_name, "road_class": road_class, "items": items}

    def camera_list(
        self, intersection_id: Optional[str] = None, corridor_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """摄像头清单（每路口 2 路）。"""
        defaults = self.net.camera_defaults
        per_int = int(defaults.get("per_intersection", 2))
        url_pattern = defaults.get("stream_url_pattern", "rtsp://sim/{camera_id}")
        presets = defaults.get("ptz_presets", ["全景"])
        if intersection_id:
            inter = self.net.intersection(intersection_id)
            if inter is None:
                return [{"error": f"路口不存在: {intersection_id}"}]
            inters = [inter]
        elif corridor_id:
            inters = self.net.intersections_of_corridor(corridor_id)
            if not inters:
                return [{"error": f"干线不存在: {corridor_id}"}]
        else:
            inters = self.net.intersections
        cameras = []
        for inter in inters:
            for n in range(1, per_int + 1):
                camera_id = f"CAM-{inter.id.split('-', 1)[1]}-{n}"
                cameras.append({
                    "camera_id": camera_id,
                    "name": f"{inter.name}{'·全景' if n == 1 else '·进口道'}",
                    "intersection_id": inter.id,
                    "stream_url": url_pattern.format(camera_id=camera_id),
                    "status": "在线",
                    "ptz_preset": presets[(n - 1) % len(presets)],
                })
        return cameras

    def incident_history(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """事件历史（含处置时长与派单号）。"""
        at = self.now()
        start = datetime.strptime(start_date, "%Y-%m-%d") if start_date else at - timedelta(days=6)
        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else at
        items = []
        day = start
        while day <= end:
            for inc in self._incidents_for_date(day):
                clear = datetime.fromisoformat(inc["expected_clear"])
                start_t = datetime.fromisoformat(inc["start_time"])
                inc2 = dict(inc)
                inc2["clearance_minutes"] = int((clear - start_t).total_seconds() / 60)
                inc2["dispatch_id"] = inc["incident_id"].replace("INC-", "DSP-")
                if clear <= at:
                    inc2["status"] = "已处置"
                items.append(inc2)
            day += timedelta(days=1)
        return items

    def dispatch_records(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """派单/调度记录（由事件历史推导）。"""
        incidents = self.incident_history(start_date, end_date)
        if incident_id:
            incidents = [i for i in incidents if i["incident_id"] == incident_id]
        records = []
        for inc in incidents:
            rng = seeded_rng(inc["incident_id"], inc["type"], "dispatch")
            resource_map = {
                "追尾事故": ["警力", "拖车"], "刮擦事故": ["警力"],
                "车辆抛锚": ["拖车"], "货物洒落": ["养护", "警力"],
                "道路施工": ["养护", "信号"], "临时管制": ["警力", "信号"],
            }
            resources = resource_map.get(inc["type"], ["警力"])
            dispatched_at = datetime.fromisoformat(inc["start_time"]) - timedelta(minutes=rng.randint(1, 4))
            arrived = rng.randint(3, 12) if inc["severity"] == "critical" else rng.randint(5, 18)
            records.append({
                "dispatch_id": inc["dispatch_id"],
                "incident_id": inc["incident_id"],
                "resource_type": "、".join(resources),
                "units": rng.randint(2, 6),
                "dispatched_at": dispatched_at.isoformat(),
                "arrived_minutes": arrived,
                "resolved_at": inc["expected_clear"],
                "result": "已恢复通行" if inc.get("status") == "已处置" else "处置中",
            })
        return records

    def event_alarm_history(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """接处警记录（由事件历史推导）。"""
        incidents = self.incident_history(start_date, end_date)
        items = []
        for inc in incidents:
            rng = seeded_rng(inc["incident_id"], "alarm", "source")
            source = rng.choice(["110接警", "122指令", "市民热线", "视频识别"])
            alarm_time = datetime.fromisoformat(inc["start_time"]) - timedelta(minutes=rng.randint(2, 8))
            items.append({
                "alarm_id": inc["incident_id"].replace("INC-", "ALM-"),
                "source": source,
                "type": inc["type"],
                "location": inc["location"],
                "intersection_id": inc["intersection_id"],
                "alarm_time": alarm_time.isoformat(),
                "handle_time_minutes": rng.randint(3, 10) + inc.get("clearance_minutes", 30) // 4,
                "level": inc["severity_label"],
            })
        return items

    def signal_optimization_suggestion(
        self,
        intersection_id: Optional[str] = None,
        corridor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """信号优化建议（Webster 周期校验 + 绿波 offset 重整）。

        Returns:
            建议字典（target / problem / suggestions / based_on / safety_notes）
        """
        at = self.now()
        if intersection_id:
            return self._suggest_for_intersection(intersection_id, at)
        if corridor_id:
            return self._suggest_for_corridor(corridor_id, at)
        return {"error": "必须提供 intersection_id 或 corridor_id"}

    def _suggest_for_intersection(self, intersection_id: str, at: datetime) -> Dict[str, Any]:
        """单路口：Webster 最优周期 + 绿信比重分配建议。"""
        inter = self.net.intersection(intersection_id)
        if inter is None:
            return {"error": f"路口不存在: {intersection_id}"}
        m = self._intersection_metrics(inter, at)
        plan_name = plan_name_for_hour(at.hour)
        plan = inter.plans[plan_name]
        major_dirs, minor_dirs = self._directions_of(inter)
        states = {s["approach"][0]: s for s in m["states"]}

        # Y = 关键流向 v/c 之和（东西取大者 + 南北取大者）
        y_major = max(states[d]["saturation"] for d in major_dirs) if major_dirs else 0
        y_minor = max(states[d]["saturation"] for d in minor_dirs) if minor_dirs else 0
        y = y_major + y_minor
        # 总损失时间 = 黄灯之和
        lost = sum(p.yellow_s for p in plan.phases if p.green_s > 0)
        c0 = (1.5 * lost + 5) / max(0.05, 1 - min(y, 0.98)) if y < 0.98 else 240

        suggestions = []
        problem = []
        critical_vc = m["max_vc"]
        if critical_vc >= 0.92:
            problem.append(f"关键进口道饱和度 {critical_vc}，过饱和高峰排队溢出")
            if c0 > plan.cycle_s:
                proposed = min(int(c0) + 10, 180)
                gain = round(min(28.0, (c0 / plan.cycle_s - 1) * 60 + 8), 0)
                suggestions.append({
                    "type": "cycle",
                    "current": f"{plan.cycle_s}s",
                    "proposed": f"{proposed}s",
                    "expected_gain": f"高峰平均延误预计下降约 {int(gain)}%",
                    "constraint_check": f"周期 {proposed}s ≤ 180s 上限，最小绿灯 15s 可满足",
                })
            # 绿信比：向关键相位倾斜
            phase_keyword = "东西" if states[major_dirs[0]]["saturation"] >= states[minor_dirs[0]]["saturation"] else "南北"
            suggestions.append({
                "type": "split",
                "current": f"{phase_keyword}直行绿信比 "
                           f"{next(p for p in plan.phases if phase_keyword in p.name and '直行' in p.name).green_s / plan.cycle_s:.2f}",
                "proposed": f"{phase_keyword}直行绿灯 +8s（对向左转 -6s、相交直行 -2s）",
                "expected_gain": "关键排队长度预计缩短 15%-20%",
                "constraint_check": "被调相位剩余绿灯 ≥ 最小绿灯 15s，行人过街时间满足 GB 14886",
            })
        else:
            problem.append(f"饱和度 {critical_vc} 处于合理区间，配时无过饱和风险")
            if plan.cycle_s > c0 + 20:
                proposed = max(70, int(c0))
                suggestions.append({
                    "type": "cycle",
                    "current": f"{plan.cycle_s}s",
                    "proposed": f"{proposed}s",
                    "expected_gain": "周期偏大，缩短后平峰延误预计下降 10%-15%",
                    "constraint_check": f"周期 {proposed}s ≥ 最小周期 70s",
                })

        return {
            "target": f"{inter.name}（{intersection_id}）",
            "target_type": "intersection",
            "problem": "；".join(problem) if problem else "无明显问题",
            "suggestions": suggestions,
            "based_on": f"Webster 最优周期 C0=(1.5L+5)/(1-Y)：L={lost}s，Y={round(y, 2)}，C0={int(c0)}s；"
                        f"结合当前方案周期 {plan.cycle_s}s 与检测器实时饱和度",
            "safety_notes": "配时调整须避开高峰切换（整点前后 5 分钟）；"
                            "任何相位绿灯不得低于 GB 14886 行人过街最小绿灯要求（主干道 15s）",
        }

    def _suggest_for_corridor(self, corridor_id: str, at: datetime) -> Dict[str, Any]:
        """干线：绿波带宽校验与 offset 重整建议。"""
        corridor = self.net.corridor(corridor_id)
        if corridor is None:
            return {"error": f"干线不存在: {corridor_id}"}
        cong = self.corridor_congestion(corridor_id)
        if "error" in cong:
            return cong
        suggestions = []
        problem = []
        mean_dev = cong["mean_offset_deviation_s"]
        if mean_dev > 8:
            problem.append(f"平均相位差偏差 {mean_dev}s，绿波协调断裂，带宽仅 {cong['greenwave_bandwidth_s']}s")
            retune = [
                {"id": p["id"], "current_offset_s": p["offset_s"],
                 "proposed_offset_s": p["offset_s"] - round(p["offset_deviation_s"]) if p["offset_deviation_s"] > 6 else p["offset_s"]}
                for p in cong["intersections"] if p["offset_deviation_s"] > 6
            ]
            suggestions.append({
                "type": "offset",
                "current": f"{len(retune)} 个路口相位差偏差超 6s",
                "proposed": f"按理想推进速度重整 {len(retune)} 个路口 offset："
                            + "；".join(f"{r['id']} {r['current_offset_s']}s→{r['proposed_offset_s']}s" for r in retune[:5]),
                "expected_gain": f"绿波带宽预计由 {cong['greenwave_bandwidth_s']}s 恢复至 "
                                 f"{int(cong['greenwave_bandwidth_s'] * 1.6 + 8)}s",
                "constraint_check": "offset 调整不改变单点周期与最小绿灯，协调组切换需全线同步",
            })
        if cong["saturation"] >= 0.92:
            problem.append(f"干线平均饱和度 {cong['saturation']}，接近饱和")
            suggestions.append({
                "type": "split",
                "current": "干线方向直行绿信比按既有方案",
                "proposed": "高峰时段干线方向直行绿灯统一 +5s（相交方向 -5s）",
                "expected_gain": "干线方向平均行程车速预计提升 8%-12%",
                "constraint_check": "相交道路剩余绿灯 ≥ 最小绿灯 15s",
            })
        if not problem:
            problem.append("绿波协调状态良好，无明显优化空间")
        return {
            "target": f"{corridor.name}（{corridor_id}）",
            "target_type": "corridor",
            "problem": "；".join(problem),
            "suggestions": suggestions,
            "based_on": f"干线 {len(cong['intersections'])} 个路口实测 offset 偏差与饱和度分布；"
                        f"绿波带宽 = 周期 − 相位差累计偏差（推进速度 {corridor.design_speed_kmh} km/h）",
            "safety_notes": "干线协调切换须在低峰时段统一下发，避免单点独立切换造成绿波断裂",
        }


_engine: Optional[TrafficSim] = None


def get_sim() -> TrafficSim:
    """获取 TrafficSim 单例。"""
    global _engine
    if _engine is None:
        _engine = TrafficSim()
    return _engine
