"""network — 路网模型加载（traffic_network.yaml → dataclass）

所属层：sim
依赖：yaml, pathlib
对接算法层：N/A（仿真数据源）

TrafficSim 的静态路网层：城市/辖区/干线/路口/信号方案/摄像头。
全部数据从 config/traffic_network.yaml 加载，代码不含路网事实。
"""
import hashlib
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

NETWORK_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "traffic_network.yaml"


@dataclass
class Phase:
    """信号相位。"""
    name: str
    green_s: int
    yellow_s: int
    min_green_s: int


@dataclass
class SignalPlan:
    """一套配时方案（peak/offpeak/night）。"""
    cycle_s: int
    phases: List[Phase]


@dataclass
class Approach:
    """进口道。"""
    direction: str
    lanes: int


@dataclass
class Intersection:
    """路口。"""
    id: str
    name: str
    district: str
    corridor: str
    road_class: str
    base_volume: int
    saturation_flow: int
    offset_s: int
    coordination_group: str
    approaches: List[Approach]
    plans: Dict[str, SignalPlan]

    @property
    def total_lanes(self) -> int:
        return sum(a.lanes for a in self.approaches)


@dataclass
class Corridor:
    """干线走廊。"""
    id: str
    name: str
    road_class: str
    length_km: float
    design_speed_kmh: int
    direction: str


@dataclass
class District:
    """辖区。"""
    id: str
    name: str


@dataclass
class CityNetwork:
    """上海市路网全景。"""
    city_name: str
    districts: List[District]
    corridors: List[Corridor]
    intersections: List[Intersection]
    camera_defaults: Dict[str, Any]
    incident_script: Dict[str, Any]

    def intersection(self, intersection_id: str) -> Optional[Intersection]:
        """按 ID 查找路口。"""
        for i in self.intersections:
            if i.id == intersection_id:
                return i
        return None

    def corridor(self, corridor_id: str) -> Optional[Corridor]:
        """按 ID 查找干线。"""
        for c in self.corridors:
            if c.id == corridor_id:
                return c
        return None

    def district(self, district_id: str) -> Optional[District]:
        """按 ID 查找辖区。"""
        for d in self.districts:
            if d.id == district_id:
                return d
        return None

    def intersections_of_corridor(self, corridor_id: str) -> List[Intersection]:
        """干线上的路口（按配置顺序）。"""
        return [i for i in self.intersections if i.corridor == corridor_id]

    def intersections_of_district(self, district_id: str) -> List[Intersection]:
        """辖区内的路口。"""
        return [i for i in self.intersections if i.district == district_id]

    def name_of(self, kind: str, entity_id: str) -> str:
        """实体 ID → 中文名（路口/干线/辖区）。"""
        if kind == "intersection":
            obj = self.intersection(entity_id)
        elif kind == "corridor":
            obj = self.corridor(entity_id)
        elif kind == "district":
            obj = self.district(entity_id)
        else:
            obj = None
        return obj.name if obj else entity_id


def _parse_plan(plan_dict: Dict[str, Any]) -> SignalPlan:
    """YAML 配置 → SignalPlan。"""
    return SignalPlan(
        cycle_s=int(plan_dict["cycle_s"]),
        phases=[
            Phase(
                name=p["name"],
                green_s=int(p["green_s"]),
                yellow_s=int(p.get("yellow_s", 3)),
                min_green_s=int(p.get("min_green_s", 15)),
            )
            for p in plan_dict["phases"]
        ],
    )


def load_network(config_path: Path = NETWORK_CONFIG_PATH) -> CityNetwork:
    """加载路网配置。

    Args:
        config_path: traffic_network.yaml 路径

    Returns:
        CityNetwork 实例

    Raises:
        FileNotFoundError: 配置文件缺失
        ValueError: 配置结构非法
    """
    with open(config_path, "r", encoding="utf-8") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)

    city = raw["city"]
    districts = [District(id=d["id"], name=d["name"]) for d in raw["districts"]]
    corridors = [
        Corridor(
            id=c["id"], name=c["name"], road_class=c["road_class"],
            length_km=float(c["length_km"]), design_speed_kmh=int(c["design_speed_kmh"]),
            direction=c["direction"],
        )
        for c in raw["corridors"]
    ]
    signal_defaults: Dict[str, Dict[str, SignalPlan]] = {
        road_class: {plan_name: _parse_plan(plan) for plan_name, plan in plans.items()}
        for road_class, plans in raw["signal_defaults"].items()
    }

    intersections: List[Intersection] = []
    for i in raw["intersections"]:
        road_class = i["road_class"]
        if road_class not in signal_defaults:
            raise ValueError(f"路口 {i['id']} 道路等级 {road_class} 无默认信号方案")
        intersections.append(
            Intersection(
                id=i["id"], name=i["name"], district=i["district"], corridor=i["corridor"],
                road_class=road_class, base_volume=int(i["base_volume"]),
                saturation_flow=int(i["saturation"]), offset_s=int(i.get("offset_s", 0)),
                coordination_group=i.get("coordination_group", ""),
                approaches=[Approach(direction=d, lanes=int(a["lanes"])) for d, a in i.get("approaches", {}).items()],
                plans=signal_defaults[road_class],
            )
        )

    return CityNetwork(
        city_name=city["name"],
        districts=districts,
        corridors=corridors,
        intersections=intersections,
        camera_defaults=raw.get("camera_defaults", {}),
        incident_script=raw.get("incident_script", {}),
    )


def seeded_rng(date: str, subject_id: str, kind: str) -> random.Random:
    """构建确定性随机源：同 (date, subject, kind) → 同序列。

    Args:
        date: 日期字符串 YYYY-MM-DD
        subject_id: 主体 ID（路口/干线/辖区）
        kind: 数据类别（如 status / incidents / history）

    Returns:
        random.Random 实例
    """
    digest = hashlib.sha256(f"{date}|{subject_id}|{kind}".encode("utf-8")).hexdigest()[:16]
    return random.Random(int(digest, 16))
