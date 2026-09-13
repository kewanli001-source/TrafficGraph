"""sim — 交通仿真数据源（TrafficSim）

所属层：sim
依赖：src.sim.network, src.sim.engine
对接算法层：N/A（纯 Python 确定性仿真）

供 src/tools/traffic_backend.py 适配器调用：
  - get_sim()        : TrafficSim 单例
  - load_network()   : 路网模型加载
  - seeded_rng()     : 确定性随机源
"""
from src.sim.engine import TrafficSim, get_sim, plan_name_for_hour, demand_multiplier
from src.sim.network import CityNetwork, load_network, seeded_rng

__all__ = [
    "TrafficSim",
    "get_sim",
    "load_network",
    "seeded_rng",
    "CityNetwork",
    "plan_name_for_hour",
    "demand_multiplier",
]
