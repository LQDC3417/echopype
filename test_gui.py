#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试GUI重构"""

import sys
import os

# 设置工作目录
os.chdir('D:/Administrator/Desktop/echopype')
sys.path.insert(0, 'D:/Administrator/Desktop/echopype')

try:
    from src.gui.property_panel import ProcessingTab, PropertyPanel
    print('✓ 导入成功')
except Exception as e:
    print(f'✗ 导入失败: {e}')
    sys.exit(1)

try:
    tab = ProcessingTab()
    print(f'✓ ProcessingTab 创建成功')
    print(f'  预设数量: {tab.combo_preset.count()}')
except Exception as e:
    print(f'✗ ProcessingTab 创建失败: {e}')
    sys.exit(1)

try:
    config = tab.get_all_config()
    print(f'✓ get_all_config 成功')
    print(f'  配置结构: {list(config.keys())}')
    print(f'  底部检测配置: {config["processing"]["bottom_detection"]}')
except Exception as e:
    print(f'✗ get_all_config 失败: {e}')
    sys.exit(1)

try:
    assert hasattr(tab, 'apply_all_clicked')
    print(f'✓ apply_all_clicked 信号存在')
except Exception as e:
    print(f'✗ 信号检查失败: {e}')
    sys.exit(1)

print('\n✓ GUI重构验证通过')
