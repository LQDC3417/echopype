# EK80 淡水鱼类资源评估系统

基于 [echopype](https://github.com/OSOceanAcoustics/echopype) 的端到端 EK80 声学数据处理工具。

## 功能

- **声学处理**: raw → Sv 计算 → 噪声去除 → 底部检测
- **鱼群识别**: 基于 Sv 阈值的鱼群检测与聚类
- **密度估算**: NASC → 鱼类密度 (ind/ha) → 生物量估算
- **可视化**: echogram、鱼群分布图、密度剖面图

## 安装

```bash
pip install -e .
```

## 使用

```bash
# 运行完整流水线
fish-acoustics run configs/shanmei.yaml

# 只运行声学处理
fish-acoustics run configs/shanmei.yaml --step acoustic

# 查看处理状态
fish-acoustics status configs/shanmei.yaml
```

## 配置文件

参考 `configs/example.yaml`，为每个水库创建独立配置。

## 项目结构

```
src/
├── acoustic.py     # 声学处理
├── school.py       # 鱼群识别
├── density.py      # 密度估算
├── viz.py          # 可视化
├── cli.py          # CLI 入口
└── utils.py        # 通用工具
```
