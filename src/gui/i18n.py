"""国际化(i18n)模块 — 支持中/英文界面切换

使用方式:
    from src.gui.i18n import T, set_language, get_language

    # 获取当前语言的文本
    title = T("app_title")

    # 切换语言
    set_language("en")  # 切换到英文
    set_language("zh")  # 切换到中文（默认）
"""

# 当前语言 (zh / en)
_current_language = "zh"

# ═══════════════════════════════════════════════════════════════
# 文本字典
# ═══════════════════════════════════════════════════════════════

_TEXTS = {
    # ── 应用级 ──
    "app_title": {
        "zh": "Echogram — 鱼类声学资源评估系统",
        "en": "Echogram — Fish Acoustic Resource Assessment System",
    },
    "app_version": {
        "zh": "2.0",
        "en": "2.0",
    },
    "about_title": {
        "zh": "关于 Echogram",
        "en": "About Echogram",
    },
    "about_html": {
        "zh": (
            "<h3>Echogram</h3>"
            "<p>鱼类声学资源评估系统 v2.0</p>"
            "<p>基于 echopype + PySide6 + OpenGL</p>"
            "<p>参照 Echoview 界面设计</p>"
            "<hr>"
            "<p><b>功能:</b></p>"
            "<ul>"
            "<li>EK80 多频段 raw 数据批量导入</li>"
            "<li>Sv 校准 + 噪声去除 + 底部检测</li>"
            "<li>鱼群自动识别 (Echoview 算法)</li>"
            "<li>密度/生物量估算</li>"
            "<li>高性能 OpenGL echogram 渲染</li>"
            "</ul>"
        ),
        "en": (
            "<h3>Echogram</h3>"
            "<p>Fish Acoustic Resource Assessment System v2.0</p>"
            "<p>Built on echopype + PySide6 + OpenGL</p>"
            "<p>UI inspired by Echoview</p>"
            "<hr>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>EK80 multi-frequency raw data batch import</li>"
            "<li>Sv calibration + noise removal + bottom detection</li>"
            "<li>Automatic school detection (Echoview algorithm)</li>"
            "<li>Density / biomass estimation</li>"
            "<li>High-performance OpenGL echogram rendering</li>"
            "</ul>"
        ),
    },

    # ── 菜单栏 ──
    "menu_file": {"zh": "文件(&F)", "en": "&File"},
    "menu_edit": {"zh": "编辑(&E)", "en": "&Edit"},
    "menu_view": {"zh": "显示(&V)", "en": "&View"},
    "menu_process": {"zh": "处理(&P)", "en": "&Process"},
    "menu_analysis": {"zh": "分析(&A)", "en": "&Analysis"},
    "menu_help": {"zh": "帮助(&H)", "en": "&Help"},

    # 文件菜单
    "import_raw_files": {"zh": "导入 Raw 文件...", "en": "Import Raw Files..."},
    "open_config": {"zh": "打开配置文件...", "en": "Open Config..."},
    "save_config": {"zh": "保存配置...", "en": "Save Config..."},
    "menu_export": {"zh": "导出结果...", "en": "Export Results..."},
    "quit": {"zh": "退出", "en": "Quit"},

    # 编辑菜单
    "undo": {"zh": "撤销", "en": "Undo"},
    "redo": {"zh": "重做", "en": "Redo"},
    "clear_noise": {"zh": "清除噪声区域", "en": "Clear Noise Regions"},
    "clear_schools": {"zh": "清除鱼群显示", "en": "Clear School Display"},

    # 显示菜单
    "reset_view": {"zh": "重置视图", "en": "Reset View"},
    "fit_view": {"zh": "适应窗口", "en": "Fit to Window"},
    "show_noise_overlay": {"zh": "显示噪声叠加", "en": "Show Noise Overlay"},
    "show_school_overlay": {"zh": "显示鱼群叠加", "en": "Show School Overlay"},
    "show_bottom_line": {"zh": "显示底线", "en": "Show Bottom Line"},

    # 处理菜单
    "run_all": {"zh": "全部运行", "en": "Run All"},
    "batch_process": {"zh": "批量处理文件...", "en": "Batch Process Files..."},
    "compute_sv": {"zh": "计算 Sv", "en": "Compute Sv"},
    "noise_removal": {"zh": "噪声去除", "en": "Noise Removal"},
    "detect_bottom": {"zh": "检测底部", "en": "Detect Bottom"},
    "detect_schools": {"zh": "检测鱼群", "en": "Detect Schools"},
    "compute_density": {"zh": "计算密度", "en": "Compute Density"},

    # 分析菜单
    "export_density_report": {"zh": "导出密度报告", "en": "Export Density Report"},
    "menu_export_schools": {"zh": "导出鱼群清单", "en": "Export School List"},

    # 帮助菜单
    "about": {"zh": "关于", "en": "About"},

    # ── 工具栏 ──
    "toolbar_import": {"zh": "导入", "en": "Import"},
    "toolbar_open_config": {"zh": "打开配置", "en": "Open Config"},
    "toolbar_save_config": {"zh": "保存配置", "en": "Save Config"},
    "toolbar_run_all": {"zh": "全部运行", "en": "Run All"},
    "toolbar_undo": {"zh": "撤销", "en": "Undo"},
    "toolbar_redo": {"zh": "重做", "en": "Redo"},
    "toolbar_export": {"zh": "导出", "en": "Export"},

    # Echogram 工具栏
    "toolbar_mode": {"zh": "模式", "en": "Mode"},
    "mode_navigate": {"zh": "导航", "en": "Navigate"},
    "mode_select_noise": {"zh": "选择噪声", "en": "Select Noise"},
    "mode_draw_bottom": {"zh": "绘制底线", "en": "Draw Bottom"},
    "mode_inspect": {"zh": "检查", "en": "Inspect"},
    "toolbar_reset": {"zh": "重置", "en": "Reset"},
    "toolbar_fit": {"zh": "适应", "en": "Fit"},
    "toolbar_prev": {"zh": "< 上一个", "en": "< Prev"},
    "toolbar_next": {"zh": "下一个 >", "en": "Next >"},
    "toolbar_color": {"zh": "颜色", "en": "Color"},
    "toolbar_sv": {"zh": "Sv", "en": "Sv"},
    "toolbar_sv_min": {"zh": "最小", "en": "Min"},
    "toolbar_sv_max": {"zh": "最大", "en": "Max"},

    # ── 状态栏 ──
    "status_ready": {"zh": "就绪 — 导入 Raw 文件开始", "en": "Ready — Import Raw files to start"},
    "status_depth": {"zh": "深度: -- m", "en": "Depth: -- m"},
    "status_depth_fmt": {"zh": "深度: {val:.1f} m", "en": "Depth: {val:.1f} m"},
    "status_sv": {"zh": "Sv: -- dB", "en": "Sv: -- dB"},
    "status_sv_fmt": {"zh": "Sv: {val:.1f} dB", "en": "Sv: {val:.1f} dB"},
    "status_zoom": {"zh": "缩放: 1.0x", "en": "Zoom: 1.0x"},
    "status_zoom_fmt": {"zh": "缩放: {val:.1f}x", "en": "Zoom: {val:.1f}x"},
    "status_coords": {"zh": "Ping: -- | 采样: --", "en": "Ping: -- | Sample: --"},
    "status_coords_fmt": {"zh": "Ping: {ping:.0f} | 采样: {sample:.0f}", "en": "Ping: {ping:.0f} | Sample: {sample:.0f}"},
    "status_gps": {"zh": "GPS: --", "en": "GPS: --"},

    # ── 左侧面板 ──
    "panel_frequency": {"zh": "频率选择", "en": "Frequency"},
    "panel_display_type": {"zh": "显示类型", "en": "Display Type"},
    "display_sv_raw": {"zh": "Sv (原始)", "en": "Sv (Raw)"},
    "display_sv_corrected": {"zh": "Sv (去噪)", "en": "Sv (Corrected)"},
    "display_noise": {"zh": "噪声", "en": "Noise"},
    "display_snr": {"zh": "SNR", "en": "SNR"},
    "panel_filters": {"zh": "滤波器", "en": "Filters"},
    "filter_noise": {"zh": "噪声去除", "en": "Noise Removal"},
    "filter_bottom": {"zh": "底部检测", "en": "Bottom Detection"},
    "filter_schools": {"zh": "鱼群显示", "en": "School Display"},
    "panel_variables": {"zh": "变量列表", "en": "Variables"},

    # ── 右侧属性面板 ──
    "tab_file_info": {"zh": "文件信息", "en": "File Info"},
    "tab_processing": {"zh": "处理参数", "en": "Parameters"},
    "tab_statistics": {"zh": "统计结果", "en": "Statistics"},

    # 文件信息
    "info_sonar_model": {"zh": "声呐型号", "en": "Sonar Model"},
    "info_frequency": {"zh": "频率", "en": "Frequency"},
    "info_pings": {"zh": "Ping 数", "en": "Ping Count"},
    "info_samples": {"zh": "采样点数", "en": "Sample Count"},
    "info_time_range": {"zh": "时间范围", "en": "Time Range"},
    "info_no_data": {"zh": "--", "en": "--"},

    # 预设配置
    "preset_group": {"zh": "预设配置", "en": "Preset Config"},
    "preset_load": {"zh": "加载", "en": "Load"},
    "preset_save": {"zh": "保存", "en": "Save"},
    "preset_loaded": {"zh": "预设已加载", "en": "Preset Loaded"},
    "preset_loaded_msg": {"zh": "已加载预设: {name}", "en": "Loaded preset: {name}"},
    "preset_saved": {"zh": "保存成功", "en": "Saved"},
    "preset_saved_msg": {"zh": "当前配置已保存为自定义预设", "en": "Current config saved as custom preset"},

    # 噪声去除
    "noise_group": {"zh": "噪声去除", "en": "Noise Removal"},
    "noise_ping_num": {"zh": "Ping 数:", "en": "Ping Count:"},
    "noise_range_num": {"zh": "Range 样本:", "en": "Range Samples:"},
    "noise_snr_threshold": {"zh": "SNR 阈值:", "en": "SNR Threshold:"},

    # 表线设置
    "surface_group": {"zh": "表线设置", "en": "Surface Line"},
    "surface_depth": {"zh": "表线深度:", "en": "Surface Depth:"},

    # 底部检测
    "bottom_group": {"zh": "底部检测", "en": "Bottom Detection"},
    "bottom_method": {"zh": "检测方法:", "en": "Method:"},
    "bottom_sv_threshold": {"zh": "Sv 阈值:", "en": "Sv Threshold:"},
    "bottom_peak_threshold": {"zh": "峰值阈值:", "en": "Peak Threshold:"},
    "bottom_disc_threshold": {"zh": "判别阈值:", "en": "Discrimination Threshold:"},
    "btn_detect_bottom": {"zh": "检测底部", "en": "Detect Bottom"},
    "btn_draw_bottom": {"zh": "绘制底线", "en": "Draw Bottom"},
    "btn_update_bottom": {"zh": "更新底线", "en": "Update Bottom"},

    # 鱼群检测
    "school_group": {"zh": "鱼群检测", "en": "School Detection"},
    "school_sv_threshold": {"zh": "Sv 阈值:", "en": "Sv Threshold:"},
    "btn_detect_schools": {"zh": "检测鱼群", "en": "Detect Schools"},

    # 密度估算
    "density_group": {"zh": "密度估算", "en": "Density Estimation"},
    "density_ts_default": {"zh": "TS 默认值:", "en": "TS Default:"},
    "density_avg_weight": {"zh": "平均体重:", "en": "Avg Weight:"},
    "btn_compute_density": {"zh": "计算密度", "en": "Compute Density"},

    # 网格分析
    "grid_group": {"zh": "网格分析", "en": "Grid Analysis"},
    "grid_vertical_interval": {"zh": "垂直间隔(m):", "en": "Vertical Interval(m):"},
    "grid_horizontal_interval": {"zh": "水平间隔:", "en": "Horizontal Interval:"},
    "grid_segment_method": {"zh": "分段方式:", "en": "Segment Method:"},
    "grid_method_ping": {"zh": "Ping", "en": "Ping"},
    "grid_method_distance": {"zh": "距离", "en": "Distance"},
    "grid_distance_unit": {"zh": "距离单位:", "en": "Distance Unit:"},
    "grid_stats_group": {"zh": "统计指标", "en": "Statistics"},
    "grid_stat_mean_sv": {"zh": "平均 Sv", "en": "Mean Sv"},
    "grid_stat_abc": {"zh": "ABC (面积背散射系数)", "en": "ABC (Area Backscattering Coeff.)"},
    "grid_stat_density": {"zh": "密度 (ind/ha)", "en": "Density (ind/ha)"},
    "grid_stat_biomass": {"zh": "生物量 (kg/ha)", "en": "Biomass (kg/ha)"},
    "grid_stat_valid_pixels": {"zh": "有效像素数", "en": "Valid Pixels"},
    "grid_output_group": {"zh": "输出设置", "en": "Output Settings"},
    "grid_output_format": {"zh": "输出格式:", "en": "Output Format:"},
    "grid_include_metadata": {"zh": "包含元数据", "en": "Include Metadata"},
    "grid_include_summary": {"zh": "包含摘要统计", "en": "Include Summary"},
    "btn_grid_analysis": {"zh": "网格分析", "en": "Grid Analysis"},
    "btn_statistics": {"zh": "统计结果", "en": "Statistics"},

    # 其他功能按钮
    "btn_quality_check": {"zh": "数据质量检查", "en": "Quality Check"},
    "btn_multifreq": {"zh": "多频分析", "en": "Multi-Freq Analysis"},
    "btn_single_target": {"zh": "单体目标检测", "en": "Single Target Detection"},
    "btn_sv_stats": {"zh": "Sv 统计摘要", "en": "Sv Statistics"},
    "btn_transect_split": {"zh": "Transect 分段", "en": "Transect Split"},
    "btn_apply_all": {"zh": "应用全部参数", "en": "Apply All Parameters"},

    # ── 回声积分 ──
    "menu_integration": {"zh": "回声积分", "en": "Echo Integration"},
    "integration_group": {"zh": "回声积分", "en": "Echo Integration"},
    "integration_esu_type": {"zh": "ESU 类型:", "en": "ESU Type:"},
    "integration_esu_pings": {"zh": "Ping 数", "en": "Pings"},
    "integration_esu_seconds": {"zh": "秒", "en": "Seconds"},
    "integration_esu_nmi": {"zh": "海里", "en": "Nautical Miles"},
    "integration_esu_size": {"zh": "ESU 大小:", "en": "ESU Size:"},
    "integration_layer_width": {"zh": "垂直层宽:", "en": "Layer Width:"},
    "integration_min_threshold": {"zh": "最小 Sv 阈值:", "en": "Min Sv Threshold:"},
    "integration_max_threshold": {"zh": "最大 Sv 阈值:", "en": "Max Sv Threshold:"},
    "btn_integration": {"zh": "回声积分", "en": "Echo Integration"},
    "msg_integration_running": {"zh": "回声积分中...", "en": "Echo integration..."},
    "msg_integration_done": {"zh": "回声积分完成: {n} 个单元", "en": "Echo integration done: {n} cells"},
    "stats_tab_integration": {"zh": "回声积分", "en": "Echo Integration"},
    "integration_info": {"zh": "回声积分: --", "en": "Integration: --"},
    "integration_info_fmt": {"zh": "回声积分: {n} 个单元", "en": "Integration: {n} cells"},
    "integration_headers": {
        "zh": ["ESU", "Ping 范围", "深度范围", "平均 Sv", "NASC", "最小 Sv", "最大 Sv", "有效样本"],
        "en": ["ESU", "Ping Range", "Depth Range", "Mean Sv", "NASC", "Min Sv", "Max Sv", "Good Samples"],
    },
    "stats_no_integration_data": {"zh": "没有回声积分数据可导出", "en": "No integration data to export"},

    # ── 单体目标检测 ──
    "menu_single_target": {"zh": "单体目标检测", "en": "Single Target Detection"},
    "single_target_group": {"zh": "单体目标检测", "en": "Single Target Detection"},
    "single_target_sv_threshold": {"zh": "Sv 阈值:", "en": "Sv Threshold:"},
    "single_target_min_area": {"zh": "最小面积:", "en": "Min Area:"},
    "single_target_max_area": {"zh": "最大面积:", "en": "Max Area:"},
    "single_target_area_px": {"zh": " 像素", "en": " px"},
    "stats_tab_single_target": {"zh": "单体目标", "en": "Single Targets"},
    "single_target_info": {"zh": "单体目标: --", "en": "Single Targets: --"},
    "single_target_info_fmt": {"zh": "单体目标: {n} 个", "en": "Single Targets: {n}"},
    "single_target_headers": {
        "zh": ["ID", "Ping", "深度", "Sv 峰值", "Sv 均值", "面积", "TS"],
        "en": ["ID", "Ping", "Depth", "Peak Sv", "Mean Sv", "Area", "TS"],
    },
    "stats_no_single_target_data": {"zh": "没有单体目标数据可导出", "en": "No single target data to export"},
    "msg_single_target_done": {"zh": "单体目标检测完成: {n} 个目标", "en": "Single target detection done: {n} targets"},
    "single_target_real_group": {"zh": "真实 SED（分裂波束）", "en": "Real SED (Split-beam)"},
    "st_real_ts_threshold": {"zh": "TS 阈值:", "en": "TS Threshold:"},
    "st_real_pldl": {"zh": "脉冲判定电平:", "en": "Pulse Length Level:"},
    "st_real_min_norm_pulse": {"zh": "最小归一化脉宽:", "en": "Min Norm Pulse:"},
    "st_real_max_norm_pulse": {"zh": "最大归一化脉宽:", "en": "Max Norm Pulse:"},
    "st_real_max_angle_std": {"zh": "最大角度标准差:", "en": "Max Angle Std Dev:"},
    "st_real_max_beam_comp": {"zh": "最大波束补偿:", "en": "Max Beam Comp:"},
    "st_real_min_depth": {"zh": "最小深度:", "en": "Min Depth:"},
    "st_real_max_depth": {"zh": "最大深度:", "en": "Max Depth:"},
    "btn_real_sed": {"zh": "真实 SED 检测", "en": "Real SED Detection"},
    "msg_real_sed_running": {"zh": "正在运行真实 SED...", "en": "Running real SED..."},
    "msg_real_sed_done": {"zh": "真实 SED 完成: {n} 个目标", "en": "Real SED done: {n} targets"},
    "msg_real_sed_none": {"zh": "未检测到单体目标\n尝试降低 TS 阈值", "en": "No single targets detected\nTry lowering TS threshold"},
    "stats_tab_real_sed": {"zh": "真实 SED", "en": "Real SED"},
    "real_sed_info": {"zh": "真实 SED: --", "en": "Real SED: --"},
    "real_sed_info_fmt": {"zh": "真实 SED: {n} 个目标", "en": "Real SED: {n} targets"},
    "real_sed_headers": {
        "zh": ["ID", "Ping", "深度", "TS", "TS(未补偿)", "沿船角", "横向角", "脉宽", "补偿"],
        "en": ["ID", "Ping", "Depth", "TS", "TS(raw)", "Alongship", "Athwartship", "Pulse", "Comp"],
    },
    "stats_no_real_sed_data": {"zh": "没有真实 SED 数据可导出", "en": "No real SED data to export"},

    # ── 底部区域表格 ──
    "region_headers": {
        "zh": ["ID", "名称", "类型", "Ping 范围", "深度范围", "面积", "平均 Sv"],
        "en": ["ID", "Name", "Type", "Ping Range", "Depth Range", "Area", "Mean Sv"],
    },
    "region_school": {"zh": "鱼群", "en": "School"},
    "region_noise": {"zh": "噪声", "en": "Noise"},
    "region_inspect": {"zh": "检查", "en": "Inspect"},
    "region_delete": {"zh": "删除区域", "en": "Delete Region"},
    "region_export_data": {"zh": "导出区域数据", "en": "Export Region Data"},

    # ── 统计对话框 ──
    "stats_title": {"zh": "统计结果", "en": "Statistics"},
    "stats_tab_summary": {"zh": "鱼群 / 密度", "en": "Schools / Density"},
    "stats_tab_grid": {"zh": "网格统计", "en": "Grid Statistics"},
    "stats_density_summary": {"zh": "密度摘要", "en": "Density Summary"},
    "stats_school_list": {"zh": "鱼群列表", "en": "School List"},
    "stats_grid_info": {"zh": "网格: --", "en": "Grid: --"},
    "stats_grid_info_fmt": {"zh": "网格: {n} 个单元", "en": "Grid: {n} cells"},
    "stats_filter": {"zh": "过滤:", "en": "Filter:"},
    "stats_filter_placeholder": {"zh": "输入过滤文本...", "en": "Enter filter text..."},
    "stats_refresh": {"zh": "刷新", "en": "Refresh"},
    "stats_copy_selected": {"zh": "复制选中行", "en": "Copy Selected"},
    "stats_copy_all": {"zh": "复制全部", "en": "Copy All"},
    "stats_export_selected": {"zh": "导出选中行", "en": "Export Selected"},
    "stats_btn_export": {"zh": "导出数据", "en": "Export Data"},
    "stats_btn_export_all": {"zh": "导出全部", "en": "Export All"},
    "stats_btn_copy": {"zh": "复制到剪贴板", "en": "Copy to Clipboard"},
    "stats_copy_success": {"zh": "复制成功", "en": "Copied"},
    "stats_copy_msg": {"zh": "已复制 {n} 行数据到剪贴板", "en": "Copied {n} rows to clipboard"},
    "stats_export_success": {"zh": "导出成功", "en": "Export Success"},
    "stats_export_failed": {"zh": "导出失败", "en": "Export Failed"},
    "stats_no_data_export": {"zh": "没有数据可导出", "en": "No data to export"},
    "stats_no_data_warn": {"zh": "没有 {name} 数据可导出", "en": "No {name} data to export"},
    "stats_select_rows_warn": {"zh": "请先选择要导出的行", "en": "Please select rows to export first"},
    "stats_no_school_data": {"zh": "没有鱼群数据可导出", "en": "No school data to export"},
    "stats_no_grid_data": {"zh": "没有网格数据可导出", "en": "No grid data to export"},

    # 网格统计表头
    "grid_headers": {
        "zh": ["单元", "Ping 范围", "深度范围", "平均 Sv", "ABC", "密度(ind/ha)", "生物量(kg/ha)", "有效像素"],
        "en": ["Cell", "Ping Range", "Depth Range", "Mean Sv", "ABC", "Density(ind/ha)", "Biomass(kg/ha)", "Valid Pixels"],
    },
    # 鱼群统计表头
    "school_headers": {
        "zh": ["ID", "Ping 范围", "深度范围", "面积", "平均 Sv", "中心深度"],
        "en": ["ID", "Ping Range", "Depth Range", "Area", "Mean Sv", "Centroid Depth"],
    },

    # ── 导出对话框 ──
    "export_title": {"zh": "导出设置", "en": "Export Settings"},
    "export_format_group": {"zh": "导出格式", "en": "Export Format"},
    "export_netcdf": {"zh": "netCDF (.nc) — 推荐大数据集", "en": "netCDF (.nc) — Recommended for large datasets"},
    "export_csv": {"zh": "CSV (.csv) — 通用格式", "en": "CSV (.csv) — Universal format"},
    "export_excel": {"zh": "Excel (.xlsx) — 多 sheet", "en": "Excel (.xlsx) — Multi-sheet"},
    "export_zarr": {"zh": "Zarr (.zarr) — 云优化", "en": "Zarr (.zarr) — Cloud optimized"},
    "export_content_group": {"zh": "导出内容", "en": "Export Content"},
    "export_sv_data": {"zh": "Sv 数据", "en": "Sv Data"},
    "export_school_list": {"zh": "鱼群清单", "en": "School List"},
    "export_density_est": {"zh": "密度估算", "en": "Density Estimation"},
    "export_grid_stats": {"zh": "网格统计", "en": "Grid Statistics"},
    "export_cancel": {"zh": "取消", "en": "Cancel"},
    "export_confirm": {"zh": "导出", "en": "Export"},

    # ── 质量检查对话框 ──
    "quality_title": {"zh": "数据质量检查", "en": "Data Quality Check"},
    "quality_waiting": {"zh": "等待检查...", "en": "Waiting..."},
    "quality_sv_group": {"zh": "Sv 数据质量", "en": "Sv Data Quality"},
    "quality_sv_range": {"zh": "Sv 值范围:", "en": "Sv Range:"},
    "quality_data_size": {"zh": "数据尺寸:", "en": "Data Size:"},
    "quality_nan_ratio": {"zh": "NaN 比例:", "en": "NaN Ratio:"},
    "quality_bottom_group": {"zh": "底线质量", "en": "Bottom Line Quality"},
    "quality_valid_pings": {"zh": "有效 Ping 数:", "en": "Valid Pings:"},
    "quality_warnings": {"zh": "警告列表", "en": "Warnings"},
    "quality_no_warnings": {"zh": "所有检查通过，无警告", "en": "All checks passed, no warnings"},
    "quality_close": {"zh": "关闭", "en": "Close"},
    "quality_failed": {"zh": "✕ 检查失败", "en": "✕ Check Failed"},
    "quality_warn": {"zh": "⚠ 存在警告", "en": "⚠ Warnings Found"},
    "quality_passed": {"zh": "✓ 检查通过", "en": "✓ Check Passed"},

    # ── 多频分析对话框 ──
    "multifreq_title": {"zh": "多频率分析", "en": "Multi-Frequency Analysis"},
    "multifreq_tab_summary": {"zh": "通道摘要", "en": "Channel Summary"},
    "multifreq_tab_compare": {"zh": "频率对比", "en": "Frequency Comparison"},
    "multifreq_summary_group": {"zh": "通道摘要", "en": "Channel Summary"},
    "multifreq_compare_group": {"zh": "多频率 ABC 对比", "en": "Multi-Frequency ABC Comparison"},
    "multifreq_need_2channels": {"zh": "需要至少 2 个通道才能进行频率对比", "en": "At least 2 channels required for comparison"},
    "multifreq_summary_headers": {
        "zh": ["通道", "频率 (Hz)", "Ping 数", "采样点数"],
        "en": ["Channel", "Frequency (Hz)", "Pings", "Samples"],
    },
    "multifreq_compare_headers": {
        "zh": ["通道", "频率 (Hz)", "平均 ABC", "标准差 ABC", "最大 ABC"],
        "en": ["Channel", "Frequency (Hz)", "Mean ABC", "Std ABC", "Max ABC"],
    },
    "multifreq_btn_csv": {"zh": "导出 CSV", "en": "Export CSV"},
    "multifreq_btn_all": {"zh": "导出全部", "en": "Export All"},
    "multifreq_btn_copy": {"zh": "复制到剪贴板", "en": "Copy to Clipboard"},

    # ── 文件集管理 ──
    "fileset_import_title": {"zh": "批量导入 Raw 文件", "en": "Batch Import Raw Files"},
    "fileset_source_group": {"zh": "文件来源", "en": "File Source"},
    "fileset_select_folder": {"zh": "选择文件夹...", "en": "Select Folder..."},
    "fileset_select_files": {"zh": "选择文件...", "en": "Select Files..."},
    "fileset_name_label": {"zh": "文件集名称:", "en": "Fileset Name:"},
    "fileset_default_name": {"zh": "新建文件集", "en": "New Fileset"},
    "fileset_probe": {"zh": "探测文件信息", "en": "Probe Files"},
    "fileset_create": {"zh": "创建文件集", "en": "Create Fileset"},
    "fileset_cancel": {"zh": "取消", "en": "Cancel"},
    "fileset_headers": {
        "zh": ["文件名", "大小", "通道", "Ping 数", "时间范围", "状态"],
        "en": ["Filename", "Size", "Channels", "Pings", "Time Range", "Status"],
    },
    "fileset_status_valid": {"zh": "✓ 有效", "en": "✓ Valid"},
    "fileset_status_invalid": {"zh": "✕ 无效", "en": "✕ Invalid"},
    "fileset_status_probing": {"zh": "探测中...", "en": "Probing..."},
    "fileset_ctrl_title": {"zh": "文件集 & 控制", "en": "Filesets & Controls"},
    "fileset_probe_start": {"zh": "开始探测 {n} 个文件...", "en": "Probing {n} files..."},
    "fileset_probe_done": {"zh": "探测完成: {valid}/{total} 个有效", "en": "Done: {valid}/{total} valid"},
    "fileset_probe_error": {"zh": "探测出错: {err}", "en": "Probe error: {err}"},
    "fileset_import": {"zh": "导入文件集", "en": "Import Fileset"},
    "fileset_import_tooltip": {"zh": "打开批量导入对话框，创建新的文件集", "en": "Open batch import dialog to create a new fileset"},
    "fileset_add_tooltip": {"zh": "向当前文件集添加更多文件", "en": "Add more files to the current fileset"},
    "fileset_delete_tooltip": {"zh": "删除当前选中的文件集", "en": "Delete the selected fileset"},
    "fileset_tree_header": {"zh": "文件集", "en": "Filesets"},
    "fileset_frequency_label": {"zh": "频率:", "en": "Freq:"},
    "fileset_all_channels": {"zh": "全部通道", "en": "All Channels"},
    "fileset_no_files": {"zh": "请先选择文件", "en": "Please select files first"},
    "fileset_select_first": {"zh": "请先选择一个文件集", "en": "Please select a fileset first"},
    "fileset_add_files_title": {"zh": "添加文件到文件集", "en": "Add Files to Fileset"},
    "fileset_delete_title": {"zh": "删除文件集", "en": "Delete Fileset"},
    "fileset_delete_confirm": {"zh": "确定删除文件集 \"{name}\" 吗？", "en": "Delete fileset \"{name}\"?"},
    "fileset_remove_selected": {"zh": "移除选中", "en": "Remove Selected"},
    "fileset_rename_title": {"zh": "重命名文件集", "en": "Rename Fileset"},
    "fileset_rename_label": {"zh": "新名称:", "en": "New Name:"},
    "fileset_ctx_rename": {"zh": "重命名", "en": "Rename"},
    "fileset_ctx_refresh": {"zh": "刷新", "en": "Refresh"},
    "fileset_ctx_remove": {"zh": "从列表移除", "en": "Remove from List"},
    "fileset_ctx_open_folder": {"zh": "打开所在文件夹", "en": "Open Containing Folder"},
    "fileset_stats": {"zh": "文件: {files} | 有效: {valid} | Ping: {pings}", "en": "Files: {files} | Valid: {valid} | Pings: {pings}"},

    # ── 对话框通用 ──
    "dialog_warning": {"zh": "警告", "en": "Warning"},
    "dialog_error": {"zh": "错误", "en": "Error"},
    "dialog_info": {"zh": "提示", "en": "Info"},
    "dialog_success": {"zh": "成功", "en": "Success"},
    "dialog_input_error": {"zh": "输入错误", "en": "Input Error"},
    "dialog_processing_error": {"zh": "处理错误", "en": "Processing Error"},

    # ── 主窗口消息 ──
    "msg_load_file_first": {"zh": "请先加载文件", "en": "Please load a file first"},
    "msg_load_data_first": {"zh": "请先加载数据", "en": "Please load data first"},
    "msg_import_first": {"zh": "请先导入文件", "en": "Please import files first"},
    "msg_detect_schools_first": {"zh": "请先检测鱼群", "en": "Please detect schools first"},
    "msg_bottom_manually_edited": {"zh": "底线已手动编辑，跳过自动检测", "en": "Bottom manually edited, skipping auto-detect"},
    "msg_surface_depth": {"zh": "表线深度: {val:.1f} m", "en": "Surface depth: {val:.1f} m"},
    "msg_mode": {"zh": "模式: {mode}", "en": "Mode: {mode}"},
    "msg_bottom_updated": {"zh": "底线已更新并保存", "en": "Bottom line updated and saved"},
    "msg_bottom_line_updated": {"zh": "底线已手动更新", "en": "Bottom line manually updated"},
    "msg_draw_bottom_mode": {"zh": "绘制底线模式：左键拖动绘制，右键完成", "en": "Draw bottom: left-drag to draw, right-click to finish"},
    "msg_analysis_region_on": {"zh": "分析区域限定已开启", "en": "Analysis region enabled"},
    "msg_analysis_region_off": {"zh": "分析区域限定已关闭", "en": "Analysis region disabled"},
    "msg_noise_cleared": {"zh": "已清除噪声区域", "en": "Noise regions cleared"},
    "msg_schools_cleared": {"zh": "已清除鱼群显示", "en": "School display cleared"},
    "msg_sv_computed": {"zh": "Sv 计算完成", "en": "Sv computed"},
    "msg_noise_removed": {"zh": "噪声去除完成（显示去噪数据，原始 Sv 已保留）", "en": "Noise removed (showing corrected, original Sv preserved)"},
    "msg_bottom_detected": {"zh": "底部检测完成 — 分析区域已启用，已进入绘制底线模式", "en": "Bottom detected — analysis region enabled, entered draw-bottom mode"},
    "msg_schools_detected": {"zh": "鱼群检测完成: {n} 个鱼群像素", "en": "School detection done: {n} pixels"},
    "msg_density_computed": {"zh": "密度计算完成", "en": "Density computed"},
    "msg_grid_done": {"zh": "网格分析完成: {n} 个单元", "en": "Grid analysis done: {n} cells"},
    "msg_export_done": {"zh": "导出完成: {n} 个文件 → {dir}", "en": "Export done: {n} files → {dir}"},
    "msg_batch_processing": {"zh": "批量处理 {n} 个文件...", "en": "Batch processing {n} files..."},
    "msg_batch_done": {"zh": "批量处理完成: 成功 {ok}, 失败 {fail}", "en": "Batch done: {ok} success, {fail} failed"},
    "msg_batch_result_title": {"zh": "批量处理完成", "en": "Batch Processing Complete"},
    "msg_batch_result": {"zh": "成功 {ok} 个文件，失败 {fail} 个文件", "en": "{ok} files succeeded, {fail} files failed"},
    "msg_config_loaded": {"zh": "配置已加载: {path}", "en": "Config loaded: {path}"},
    "msg_config_saved": {"zh": "配置已保存: {path}", "en": "Config saved: {path}"},
    "msg_no_config": {"zh": "无配置可保存", "en": "No config to save"},
    "msg_params_applied": {"zh": "参数已应用，开始处理...", "en": "Parameters applied, processing..."},
    "msg_processing": {"zh": "处理中...", "en": "Processing..."},
    "msg_channel_info": {"zh": "通道信息", "en": "Channel Info"},
    "msg_freq_comparison": {"zh": "频率对比 (ABC)", "en": "Frequency Comparison (ABC)"},
    "msg_ts_stats": {"zh": "TS 统计", "en": "TS Statistics"},
    "msg_mean": {"zh": "均值", "en": "Mean"},
    "msg_median": {"zh": "中位", "en": "Median"},
    "msg_range": {"zh": "范围", "en": "Range"},
    "msg_target_columns": {"zh": "目标列", "en": "Target Columns"},
    "msg_p5_p95": {"zh": "P5~P95", "en": "P5~P95"},
    "msg_computing_sv": {"zh": "计算 Sv...", "en": "Computing Sv..."},
    "msg_removing_noise": {"zh": "去除噪声...", "en": "Removing noise..."},
    "msg_detecting_bottom": {"zh": "检测底部...", "en": "Detecting bottom..."},
    "msg_bottom_detection": {"zh": "检测底部 (方法: {method})...", "en": "Detecting bottom (method: {method})..."},
    "msg_detecting_schools": {"zh": "检测鱼群...", "en": "Detecting schools..."},
    "msg_computing_density": {"zh": "计算密度...", "en": "Computing density..."},
    "msg_grid_analysis": {"zh": "网格分析...", "en": "Grid analysis..."},
    "msg_quality_checking": {"zh": "正在检查数据质量...", "en": "Checking data quality..."},
    "msg_multifreq_analyzing": {"zh": "正在分析多频率通道...", "en": "Analyzing multi-frequency channels..."},
    "msg_single_target": {"zh": "正在检测单体目标...", "en": "Detecting single targets..."},
    "msg_sv_stats": {"zh": "计算 Sv 统计...", "en": "Computing Sv statistics..."},
    "msg_transect_split": {"zh": "分段中...", "en": "Splitting transects..."},
    "msg_no_single_target": {"zh": "未检测到单体目标\n尝试降低 sv_threshold_db 参数", "en": "No single targets detected\nTry lowering sv_threshold_db"},
    "msg_single_target_result": {"zh": "单体目标检测结果", "en": "Single Target Detection Results"},
    "msg_no_sv_stats": {"zh": "无统计结果", "en": "No statistics available"},
    "msg_sv_stats_title": {"zh": "Sv 统计摘要", "en": "Sv Statistics Summary"},
    "msg_transect_split_done": {"zh": "分段完成：共 {n} 个 transect", "en": "Split done: {n} transects"},
    "msg_multifreq_title": {"zh": "多频率分析", "en": "Multi-Frequency Analysis"},
    "msg_multifreq_channels": {"zh": "通道数: {n}", "en": "Channels: {n}"},

    # ── 质量检查弹窗 ──
    "quality_report_title_pass": {"zh": "质量检查通过 ✓", "en": "Quality Check Passed ✓"},
    "quality_report_title_fail": {"zh": "质量检查发现问题 ⚠", "en": "Quality Issues Found ⚠"},
    "quality_report_sv_data": {"zh": "Sv 数据: {pings} pings × {samples} samples", "en": "Sv Data: {pings} pings × {samples} samples"},
    "quality_report_sv_range": {"zh": "Sv 范围: [{min:.1f}, {max:.1f}] dB", "en": "Sv Range: [{min:.1f}, {max:.1f}] dB"},
    "quality_report_nan": {"zh": "NaN 比例: {ratio:.1%}", "en": "NaN Ratio: {ratio:.1%}"},
    "quality_report_bottom": {"zh": "底线: {n} 个有效 ping", "en": "Bottom: {n} valid pings"},

    # ── 网格分析错误 ──
    "grid_error_vertical": {"zh": "垂直间隔必须大于0", "en": "Vertical interval must be > 0"},
    "grid_error_horizontal": {"zh": "水平间隔必须大于0", "en": "Horizontal interval must be > 0"},
    "grid_error_no_metrics": {"zh": "请至少选择一个统计指标", "en": "Please select at least one metric"},

    # ── 管线步骤名 ──
    "pipeline_sv": {"zh": "计算 Sv", "en": "Compute Sv"},
    "pipeline_noise": {"zh": "噪声去除", "en": "Noise Removal"},
    "pipeline_bottom": {"zh": "底部检测", "en": "Bottom Detection"},
    "pipeline_schools": {"zh": "鱼群检测", "en": "School Detection"},
    "pipeline_density": {"zh": "密度估算", "en": "Density Estimation"},

    # ── 密度/统计标签 ──
    "density_abc_fmt": {"zh": "ABC: {val:.6f} m²/m²", "en": "ABC: {val:.6f} m²/m²"},
    "density_val_fmt": {"zh": "密度: {val:.2f} ind/ha", "en": "Density: {val:.2f} ind/ha"},
    "density_biomass_fmt": {"zh": "生物量: {val:.2f} kg/ha", "en": "Biomass: {val:.2f} kg/ha"},

    # ── 右键菜单消息 ──
    "msg_no_loaded_files": {"zh": "没有已加载的文件，请先导入", "en": "No loaded files, please import first"},
    "msg_boundary_reached": {"zh": "已到达边界 (文件 {cur}/{total})", "en": "At boundary (file {cur}/{total})"},
    "msg_file_not_cached": {"zh": "{name} 尚未加载 (缓存: {cached}/{total})，请等待", "en": "{name} not loaded (cache: {cached}/{total}), please wait"},
    "msg_file_switched": {"zh": "文件 {cur}/{total}: {name}", "en": "File {cur}/{total}: {name}"},
    "msg_fileset_selected": {"zh": "文件集: {name} ({count} 个文件) — 自动加载中..", "en": "Fileset: {name} ({count} files) — Loading..."},
    "msg_fileset_empty": {"zh": "文件集: {name} (空)", "en": "Fileset: {name} (empty)"},
    "msg_all_cached": {"zh": "全部 {total} 个文件已缓存 — 右键 Echogram 翻页切换", "en": "All {total} files cached — right-click echogram to page through"},
    "msg_batch_in_progress": {"zh": "批量处理正在进行中", "en": "Batch processing in progress"},
    "msg_frequency": {"zh": "频率: {ch}", "en": "Frequency: {ch}"},
    "msg_region_sv_avg": {"zh": "区域 Sv 平均值: {val:.1f} dB", "en": "Region mean Sv: {val:.1f} dB"},

    # ── 质量警告 ──
    "quality_sv_all_nan": {"zh": "Sv 全部为 NaN，无有效数据", "en": "All Sv values are NaN, no valid data"},
    "quality_sv_range_warn": {"zh": "Sv 最小值 {val:.1f} dB 异常偏小（<-120 dB）", "en": "Sv min {val:.1f} dB abnormally low (<-120 dB)"},
    "quality_sv_range_high": {"zh": "Sv 最大值 {val:.1f} dB 异常偏大（>10 dB）", "en": "Sv max {val:.1f} dB abnormally high (>10 dB)"},
    "quality_nan_critical": {"zh": "[严重] NaN 比例 {ratio:.1%} 过高（>98%，数据几乎全空）", "en": "[CRITICAL] NaN ratio {ratio:.1%} too high (>98%, nearly empty)"},
    "quality_nan_warning": {"zh": "[警告] NaN 比例 {ratio:.1%} 偏高（>90%，大部分数据缺失）", "en": "[WARNING] NaN ratio {ratio:.1%} high (>90%, most data missing)"},
    "quality_nan_info": {"zh": "[提示] NaN 比例 {ratio:.1%} 较高（>80%），统计结果可能不稳定", "en": "[INFO] NaN ratio {ratio:.1%} elevated (>80%), stats may be unstable"},
    "quality_pings_low": {"zh": "Ping 数过少（{n}），统计结果可能不可靠", "en": "Too few pings ({n}), results may be unreliable"},
    "quality_bottom_all_nan": {"zh": "底线全部为 NaN，无法检测底部", "en": "All bottom values are NaN"},
    "quality_bottom_negative": {"zh": "底线异常负值: {val:.2f}", "en": "Abnormal negative bottom: {val:.2f}"},
    "quality_bottom_exceed": {"zh": "底线超出采样范围", "en": "Bottom exceeds sample range"},
    "quality_bottom_jump": {"zh": "底线跳变过大（最大 {val:.0f} samples）", "en": "Bottom jump too large (max {val:.0f} samples)"},
    "quality_bottom_nan_high": {"zh": "底线 NaN 比例 {ratio:.1%} 过高（>30%）", "en": "Bottom NaN ratio {ratio:.1%} too high (>30%)"},

    # ── 网格分析错误/进度 ──
    "grid_cancelled": {"zh": "网格分析已取消: {error}", "en": "Grid analysis cancelled: {error}"},
    "grid_import_error": {"zh": "缺少必要的模块: {error}\n请检查 echopype 和相关依赖是否正确安装", "en": "Missing required module: {error}\nPlease check echopype and dependencies are correctly installed"},
    "grid_key_error": {"zh": "配置参数错误: 缺少必要的参数 {error}\n请检查网格配置是否完整", "en": "Config error: missing required parameter {error}\nPlease check grid configuration"},
    "grid_value_error": {"zh": "参数值错误: {error}\n请检查输入参数是否有效", "en": "Parameter value error: {error}\nPlease check input parameters"},
    "grid_memory_error": {"zh": "内存不足：请尝试减小网格间隔或使用更小的数据集", "en": "Out of memory: try reducing grid interval or using a smaller dataset"},
    "grid_unexpected_error": {"zh": "网格分析过程中发生错误: {error}\n\n详细错误信息:\n{detail}", "en": "Grid analysis error: {error}\n\nDetail:\n{detail}"},
    "grid_validate_empty_ds": {"zh": "输入数据集为空", "en": "Input dataset is empty"},
    "grid_validate_negative_surface": {"zh": "表面深度不能为负数", "en": "Surface depth cannot be negative"},
    "grid_validate_missing_vertical": {"zh": "缺少垂直间隔参数 (vertical_interval_m)", "en": "Missing vertical interval parameter (vertical_interval_m)"},
    "grid_validate_missing_horizontal": {"zh": "缺少水平间隔参数 (horizontal_interval)", "en": "Missing horizontal interval parameter (horizontal_interval)"},
    "grid_validate_missing_method": {"zh": "缺少水平分段方法参数 (horizontal_method)", "en": "Missing horizontal method parameter (horizontal_method)"},
    "grid_validate_vertical_zero": {"zh": "垂直间隔必须大于0", "en": "Vertical interval must be > 0"},
    "grid_validate_horizontal_zero": {"zh": "水平间隔必须大于0", "en": "Horizontal interval must be > 0"},
    "grid_validate_method_invalid": {"zh": "水平分段方法必须是 'ping' 或 'distance'", "en": "Horizontal method must be 'ping' or 'distance'"},
    "grid_validate_missing_ts": {"zh": "缺少默认目标强度参数 (ts_default)", "en": "Missing default target strength parameter (ts_default)"},
    "grid_validate_missing_weight": {"zh": "缺少平均体重参数 (avg_weight_kg)", "en": "Missing average weight parameter (avg_weight_kg)"},
    "batch_file_fail": {"zh": "✗ 失败 [{done}/{total}]: {name}", "en": "✗ Fail [{done}/{total}]: {name}"},
    "batch_file_ok": {"zh": "✓ 完成 [{done}/{total}]: {name}", "en": "✓ Done [{done}/{total}]: {name}"},

    # ── 语言切换 ──
    "menu_language": {"zh": "语言(&L)", "en": "&Language"},
    "lang_zh": {"zh": "中文", "en": "中文"},
    "lang_en": {"zh": "English", "en": "English"},
    "lang_switch_prompt": {
        "zh": "语言已切换为中文，重启应用后生效",
        "en": "Language switched to English, restart to apply",
    },
}


def T(key: str, **kwargs) -> str:
    """获取当前语言的文本，支持格式化参数。

    Parameters
    ----------
    key : str
        文本键名
    **kwargs
        格式化参数

    Returns
    -------
    str
        当前语言的文本
    """
    entry = _TEXTS.get(key)
    if entry is None:
        return key  # fallback: 返回键名
    text = entry.get(_current_language, entry.get("zh", key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def set_language(lang: str):
    """设置当前语言。

    Parameters
    ----------
    lang : str
        语言代码: "zh" 或 "en"
    """
    global _current_language
    if lang in ("zh", "en"):
        _current_language = lang


def get_language() -> str:
    """获取当前语言代码。"""
    return _current_language


def get_supported_languages() -> list[str]:
    """获取支持的语言列表。"""
    return ["zh", "en"]
