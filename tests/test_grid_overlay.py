"""测试网格叠加是否正确设置"""
import sys
sys.path.insert(0, '.')
from src.core.utils import load_config
from src.core.acoustic import open_single_file, process_single_file
from src.core.grid import create_grid, compute_grid_density
from src.viz.opengl_renderer import EchogramRenderer
from pathlib import Path
import numpy as np

config = load_config('configs/example.yaml')
ed = open_single_file(Path('raw_data/20250706SCSK-D20250706-T024009.raw'), config)
ds = process_single_file(ed, config)
sv = ds['Sv'].values
if sv.ndim == 3:
    sv = sv[0]

renderer = EchogramRenderer()
renderer.set_data(sv)

cells = create_grid(ds, surface_depth_m=2.0, vertical_interval_m=2.0, horizontal_interval=100)
grid_df = compute_grid_density(ds, cells, config)

renderer.set_grid_data(grid_df, ds, color_by='mean_sv')
print('grid_cells:', len(renderer._grid_cells) if renderer._grid_cells else 0)
if renderer._grid_cells:
    c = renderer._grid_cells[0]
    print('First cell:', {k: c[k] for k in ['ping_start','ping_end','sample_start','sample_end']})
print('OK')
