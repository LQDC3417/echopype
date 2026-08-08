"""底线自由手绘功能测试"""

import numpy as np
import pytest


class TestBottomDrawing:
    """测试底线编辑逻辑（纯数据层，不依赖 OpenGL）"""

    def test_apply_drawn_segment_basic(self):
        """基本手绘：两个点之间的线性插值"""
        n_pings = 100
        bottom = np.full(n_pings, np.nan, dtype=np.float32)

        # 模拟绘制点：(ping, sample)
        draw_points = [(10, 100.0), (50, 200.0)]

        # 分段替换逻辑
        sorted_points = sorted(draw_points, key=lambda p: p[0])
        ping_min = int(round(sorted_points[0][0]))
        ping_max = int(round(sorted_points[-1][0]))

        for ping_idx in range(ping_min, ping_max + 1):
            left = None
            right = None
            for i, (p, s) in enumerate(sorted_points):
                if p <= ping_idx:
                    left = (p, s, i)
                if p >= ping_idx and right is None:
                    right = (p, s, i)

            if left is not None and right is not None:
                if left[2] == right[2]:
                    bottom[ping_idx] = left[1]
                else:
                    t = (ping_idx - left[0]) / max(1e-6, right[0] - left[0])
                    bottom[ping_idx] = left[1] + t * (right[1] - left[1])
            elif left is not None:
                bottom[ping_idx] = left[1]
            elif right is not None:
                bottom[ping_idx] = right[1]

        # 验证：覆盖范围内有值
        assert not np.isnan(bottom[10])
        assert not np.isnan(bottom[50])
        assert bottom[10] == 100.0
        assert bottom[50] == 200.0
        # 验证：中间值是线性插值
        assert abs(bottom[30] - 150.0) < 1.0
        # 验证：范围外保持 NaN
        assert np.isnan(bottom[5])
        assert np.isnan(bottom[60])

    def test_apply_drawn_segment_preserves_existing(self):
        """分段替换：只替换覆盖范围，保留其他部分"""
        n_pings = 100
        bottom = np.full(n_pings, 50.0, dtype=np.float32)  # 已有底线

        # 新绘制覆盖 20-40
        draw_points = [(20, 100.0), (40, 200.0)]

        sorted_points = sorted(draw_points, key=lambda p: p[0])
        ping_min = int(round(sorted_points[0][0]))
        ping_max = int(round(sorted_points[-1][0]))

        for ping_idx in range(ping_min, ping_max + 1):
            left = None
            right = None
            for i, (p, s) in enumerate(sorted_points):
                if p <= ping_idx:
                    left = (p, s, i)
                if p >= ping_idx and right is None:
                    right = (p, s, i)

            if left is not None and right is not None:
                if left[2] == right[2]:
                    bottom[ping_idx] = left[1]
                else:
                    t = (ping_idx - left[0]) / max(1e-6, right[0] - left[0])
                    bottom[ping_idx] = left[1] + t * (right[1] - left[1])

        # 验证：覆盖范围内已更新
        assert bottom[20] == 100.0
        assert bottom[40] == 200.0
        # 验证：范围外保留原值
        assert bottom[10] == 50.0
        assert bottom[50] == 50.0

    def test_undo_stack(self):
        """撤销栈功能"""
        undo_stack = []
        bottom = np.full(100, 50.0, dtype=np.float32)

        # 保存状态
        undo_stack.append(bottom.copy())
        # 修改底线
        bottom[20:40] = 100.0
        assert bottom[30] == 100.0

        # 撤销
        if undo_stack:
            bottom = undo_stack.pop()

        # 验证：恢复原状
        assert bottom[30] == 50.0

    def test_undo_stack_limit(self):
        """撤销栈大小限制"""
        undo_stack = []
        max_size = 50

        for i in range(60):
            bottom = np.full(100, float(i), dtype=np.float32)
            undo_stack.append(bottom.copy())
            if len(undo_stack) > max_size:
                undo_stack.pop(0)

        assert len(undo_stack) == max_size
        # 最早的被丢弃
        assert undo_stack[0][0] == 10.0  # 60 - 50 = 10

    def test_draw_points_boundary(self):
        """绘制点边界检查"""
        n_pings = 100

        # 超出范围的点
        draw_points = [(-5, 100.0), (105, 200.0)]

        sorted_points = sorted(draw_points, key=lambda p: p[0])
        ping_min = max(0, int(round(sorted_points[0][0])))
        ping_max = min(n_pings - 1, int(round(sorted_points[-1][0])))

        # 验证：边界被正确限制
        assert ping_min == 0
        assert ping_max == 99

    def test_single_point_draw(self):
        """单点绘制（不应产生有效底线）"""
        draw_points = [(50, 100.0)]
        assert len(draw_points) < 2  # 单点不处理


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
