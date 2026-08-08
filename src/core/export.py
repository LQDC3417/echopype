"""数据导出模块：将处理结果保存为 netCDF / CSV / Excel"""

import logging
import warnings
from pathlib import Path

import pandas as pd
import xarray as xr

logger = logging.getLogger("fish_acoustics")

_SV_CSV_SIZE_WARN_MB = 100  # 超过此大小发出警告


def export_to_netcdf(ds_Sv: xr.Dataset, output_path: str | Path) -> Path:
    """将 Sv 数据集导出为 netCDF 文件。

    Parameters
    ----------
    ds_Sv : xr.Dataset
        包含 Sv、Sv_corrected、depth 等变量的数据集
    output_path : str or Path
        输出文件路径（.nc）

    Returns
    -------
    Path
        实际写入的文件路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 选择要导出的变量（排除过大的中间变量）
    export_vars = []
    for var in ds_Sv.data_vars:
        if var in ("Sv", "Sv_corrected", "depth", "echo_range", "bottom_depth"):
            export_vars.append(var)

    ds_export = ds_Sv[export_vars] if export_vars else ds_Sv
    ds_export.to_netcdf(output_path)
    logger.info(f"已导出 netCDF: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")
    return output_path


def export_to_zarr(ds_Sv: xr.Dataset, output_path: str | Path) -> Path:
    """将 Sv 数据集导出为 Zarr 格式（云优化）。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    output_path : str or Path
        输出目录路径（.zarr）

    Returns
    -------
    Path
    """
    output_path = Path(output_path)
    if output_path.exists():
        import shutil
        shutil.rmtree(output_path)

    ds_Sv.to_zarr(output_path)
    logger.info(f"已导出 Zarr: {output_path}")
    return output_path


def export_schools_to_csv(schools_df: pd.DataFrame, output_path: str | Path) -> Path:
    """将鱼群清单导出为 CSV。

    Parameters
    ----------
    schools_df : pd.DataFrame
    output_path : str or Path

    Returns
    -------
    Path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schools_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"已导出鱼群清单: {output_path}")
    return output_path


def export_density_to_csv(density_df: pd.DataFrame, output_path: str | Path) -> Path:
    """将密度估算结果导出为 CSV。

    Parameters
    ----------
    density_df : pd.DataFrame
    output_path : str or Path

    Returns
    -------
    Path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    density_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"已导出密度结果: {output_path}")
    return output_path


def export_sv_to_csv(ds_Sv: xr.Dataset, output_path: str | Path) -> Path:
    """将 Sv 数据导出为 CSV（长格式：ping_time, depth, Sv）。

    大数据集会发出警告（超过 _SV_CSV_SIZE_WARN_MB）。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    output_path : str or Path

    Returns
    -------
    Path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    var = "Sv_corrected" if "Sv_corrected" in ds_Sv else "Sv"
    sv = ds_Sv[var]
    if "channel" in sv.dims:
        sv = sv.isel(channel=0)

    n_pings, n_samples = sv.shape
    est_rows = n_pings * n_samples
    est_mb = est_rows * 20 / (1024 * 1024)  # 粗估每行 ~20 bytes
    if est_mb > _SV_CSV_SIZE_WARN_MB:
        warnings.warn(
            f"Sv CSV 导出预估 {est_mb:.0f} MB（{est_rows:,} 行），建议改用 netCDF 格式",
            stacklevel=2,
        )

    df = sv.to_dataframe(name="Sv").reset_index()
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    logger.info(f"已导出 Sv CSV: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
    return output_path


def export_to_excel(
    schools_df: pd.DataFrame | None,
    density_df: pd.DataFrame | None,
    output_path: str | Path,
) -> Path:
    """将鱼群和密度结果导出为 Excel（多 sheet）。

    Parameters
    ----------
    schools_df : pd.DataFrame or None
    density_df : pd.DataFrame or None
    output_path : str or Path

    Returns
    -------
    Path
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        if schools_df is not None and not schools_df.empty:
            schools_df.to_excel(writer, sheet_name="鱼群", index=False)
        if density_df is not None and not density_df.empty:
            density_df.to_excel(writer, sheet_name="密度", index=False)

    logger.info(f"已导出 Excel: {output_path}")
    return output_path


def export_all(
    ds_Sv: xr.Dataset,
    schools_df: pd.DataFrame | None,
    density_df: pd.DataFrame | None,
    output_dir: str | Path,
    formats: list[str] | None = None,
) -> list[Path]:
    """批量导出所有结果。

    Parameters
    ----------
    ds_Sv : xr.Dataset
    schools_df : pd.DataFrame or None
    density_df : pd.DataFrame or None
    output_dir : str or Path
    formats : list[str], optional
        导出格式，默认 ["netcdf", "csv"]

    Returns
    -------
    list[Path]
        所有导出文件路径
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if formats is None:
        formats = ["netcdf", "csv"]

    exported = []

    if "netcdf" in formats:
        p = export_to_netcdf(ds_Sv, output_dir / "sv_data.nc")
        exported.append(p)

    if "zarr" in formats:
        p = export_to_zarr(ds_Sv, output_dir / "sv_data.zarr")
        exported.append(p)

    if "csv" in formats:
        p = export_sv_to_csv(ds_Sv, output_dir / "sv_data.csv")
        exported.append(p)

    if schools_df is not None and not schools_df.empty:
        p = export_schools_to_csv(schools_df, output_dir / "schools.csv")
        exported.append(p)

    if density_df is not None and not density_df.empty:
        p = export_density_to_csv(density_df, output_dir / "density.csv")
        exported.append(p)

    if "excel" in formats:
        p = export_to_excel(schools_df, density_df, output_dir / "results.xlsx")
        exported.append(p)

    logger.info(f"批量导出完成: {len(exported)} 个文件 → {output_dir}")
    return exported
