# Cloud–Edge–Device Simulator · 端边云协同仿真

[![CI](https://github.com/BoomShuai/cloud-edge-simulator/actions/workflows/ci.yml/badge.svg)](https://github.com/BoomShuai/cloud-edge-simulator/actions/workflows/ci.yml)

一个零运行依赖的教学型任务放置模拟器。比较只在终端、只在云端、最小时延和隐私约束策略，在同一组合成任务上观察时延、能耗、截止期命中率及放置分布。

```bash
python -m pip install -e .
python -m cloud_edge demo --output outputs/demo
python -m cloud_edge scenario --output private/scenario.json
python -m cloud_edge run --input private/scenario.json --output outputs/custom
```

Python3.9+，也可用`cloud-edge`命令。报告包含JSON逐任务决策、CSV汇总和Markdown对比表。输出目录必须是新目录，不覆盖已有报告。`--strategy`可选all/device_only/cloud_only/latency_greedy/privacy_aware；`--variant`生成可复现的合成工作负载变化。

| 策略 | 规则 |
| --- | --- |
| device_only | 所有任务留在终端 |
| cloud_only | 所有任务放到云端，作为基线 |
| latency_greedy | 按解析模型选择最小时延 |
| privacy_aware | 先按隐私等级限制候选；优先满足截止期，再比较时延+能耗分数 |

## 模型约定

输入/输出大小是十进制MB，带宽是Mbit/s，算力是TOPS，计算量是GOP。上传/下载时延分别为 `MB*8*1000/Mbps + link_latency_ms`；计算时延为 `GOP/TOPS` 毫秒，总时延再加固定的节点排队延迟。能耗只统计 `GOP * J/GOP`，不含传输或空闲能耗。

隐私等级4/5不允许上云，即使没有满足截止期的端/边节点也不会突破约束；候选集为空会报错。分数中的18为演示用能耗权重（ms/J），不是实测优化参数。每层最多一个候选节点，缺失往返链路、重复节点、无效带宽和非有限数值会被拒绝。

任务独立估计，固定排队时间，不模拟竞争、动态队列、DAG依赖或真实部署。P95取排序位置 `round((n-1)*0.95)` 的样本值。默认任务、设备能力和链路均是虚构参数；输出不等于实际硬件测量，也不证明某种策略在生产集群更优。

## 项目结构与检查

- `cloud_edge/core.py`：数据契约、估计模型、四种策略和指标。
- `cloud_edge/cli.py`：场景导入导出、报告生成。
- `tests/`：原有行为测试、单位换算、隐私约束、非法输入及CLI往返。

```bash
python -m unittest discover -s tests -v
python scripts/privacy_check.py --history
```

公开版保留原工作区的通用计算与策略接口，替换定向研究说明和具体设备名称，补充参数校验与独立CLI。历史CSV和资料另有私有归档；本仓库只提供源码与合成样例生成逻辑。

[MIT许可证](LICENSE) · [隐私边界](PRIVACY.md) · [贡献说明](CONTRIBUTING.md)
