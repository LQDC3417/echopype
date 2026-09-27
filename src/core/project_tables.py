"""在 HDF5 项目中无损保存结果 DataFrame。"""

import json

import h5py
import numpy as np
import pandas as pd


def _label_to_json(value):
    if isinstance(value, tuple):
        return {"tuple": [_label_to_json(item) for item in value]}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"不支持的 DataFrame 标签类型: {type(value).__name__}")


def _label_from_json(value):
    if isinstance(value, dict) and set(value) == {"tuple"}:
        return tuple(_label_from_json(item) for item in value["tuple"])
    return value


def _dtype_name(dtype):
    return str(dtype)


def _classify(series: pd.Series) -> str:
    dtype = series.dtype
    if pd.api.types.is_bool_dtype(dtype):
        return "bool"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"
    if pd.api.types.is_numeric_dtype(dtype):
        return "numeric"
    if pd.api.types.is_string_dtype(dtype) and not pd.api.types.is_object_dtype(dtype):
        return "string"
    if pd.api.types.is_object_dtype(dtype):
        values = series[~series.isna()]
        if all(isinstance(value, (str, np.str_)) for value in values):
            return "string"
    raise TypeError(f"不支持的 DataFrame 列类型: {dtype}")


def _write_series(group: h5py.Group, series: pd.Series) -> None:
    kind = _classify(series)
    group.attrs["kind"] = kind
    group.attrs["dtype"] = _dtype_name(series.dtype)
    missing = series.isna().to_numpy(dtype=bool)
    group.create_dataset("missing", data=missing, compression="gzip" if len(missing) else None)

    if kind == "string":
        strings = ["" if is_missing else str(value) for value, is_missing in zip(series, missing)]
        if any("\x00" in value for value in strings):
            raise TypeError("DataFrame 字符串列不支持包含 NUL 字符")
        group.create_dataset(
            "values",
            data=np.asarray(strings, dtype=object),
            dtype=h5py.string_dtype(encoding="utf-8"),
        )
        return

    dtype = series.dtype
    if kind == "numeric" and hasattr(dtype, "numpy_dtype"):
        numpy_dtype = np.dtype(dtype.numpy_dtype)
    elif kind == "bool":
        numpy_dtype = np.dtype(bool)
    elif kind == "datetime":
        numpy_dtype = np.dtype("datetime64[ns]")
    else:
        numpy_dtype = np.dtype(dtype)

    if kind == "datetime":
        values = pd.to_datetime(series).to_numpy(dtype="datetime64[ns]").view("int64")
        fill = np.iinfo(np.int64).min
    else:
        fill = False if kind == "bool" else 0
        values = series.to_numpy(dtype=numpy_dtype, na_value=fill)
    group.create_dataset("values", data=values)


def _read_series(group: h5py.Group, name: str | None = None) -> pd.Series:
    kind = group.attrs["kind"]
    dtype = group.attrs["dtype"]
    missing = group["missing"][()].astype(bool)

    if kind == "string":
        values = group["values"].asstr(encoding="utf-8")[()].tolist()
        if dtype == "object":
            result = np.empty(len(values), dtype=object)
            for i, (value, is_missing) in enumerate(zip(values, missing)):
                result[i] = None if is_missing else value
            return pd.Series(result, name=name)
        values = [pd.NA if is_missing else value for value, is_missing in zip(values, missing)]
        return pd.Series(pd.array(values, dtype=dtype), name=name)

    values = group["values"][()]
    if kind == "datetime":
        values = values.view("datetime64[ns]")
        result = pd.Series(values, name=name)
        result.loc[missing] = pd.NaT
    else:
        if missing.any():
            if pd.api.types.is_extension_array_dtype(dtype):
                values = pd.array(values, dtype=dtype)
                values[missing] = pd.NA
            elif np.issubdtype(values.dtype, np.floating):
                values[missing] = np.nan
            else:
                raise ValueError(f"非浮点列 {name!r} 出现了不兼容的缺失值")
        if kind == "numeric" and pd.api.types.is_extension_array_dtype(dtype):
            return pd.Series(values, name=name)
        result = pd.Series(values, name=name)
    return result.astype(dtype)


def _write_index(group: h5py.Group, index: pd.Index) -> None:
    group.attrs["name"] = json.dumps(_label_to_json(index.name), ensure_ascii=False)
    if isinstance(index, pd.RangeIndex):
        group.attrs["kind"] = "range"
        group.attrs["start"] = index.start
        group.attrs["stop"] = index.stop
        group.attrs["step"] = index.step
        return
    group.attrs["kind"] = "values"
    _write_series(group.create_group("values"), pd.Series(index.array, dtype=index.dtype))


def _read_index(group: h5py.Group, row_count: int) -> pd.Index:
    name = _label_from_json(json.loads(group.attrs["name"]))
    if group.attrs["kind"] == "range":
        return pd.RangeIndex(
            int(group.attrs["start"]),
            int(group.attrs["stop"]),
            int(group.attrs["step"]),
            name=name,
        )
    values = _read_series(group["values"]).array
    index = pd.Index(values, name=name)
    if len(index) != row_count:
        raise ValueError("项目结果表索引长度与行数不一致")
    return index


def write_frame(parent: h5py.Group, name: str, frame: pd.DataFrame | None) -> None:
    """写入一个结果表；None 与空 DataFrame 使用不同状态保存。"""
    group = parent.create_group(name)
    if frame is None:
        group.attrs["state"] = "none"
        return

    columns = [_label_to_json(label) for label in frame.columns]
    group.attrs["state"] = "data"
    group.attrs["row_count"] = len(frame)
    group.attrs["columns"] = json.dumps(columns, ensure_ascii=False)
    group.attrs["columns_name"] = json.dumps(
        _label_to_json(frame.columns.name), ensure_ascii=False
    )
    _write_index(group.create_group("index"), frame.index)
    data_group = group.create_group("data")
    for i, label in enumerate(frame.columns):
        _write_series(data_group.create_group(str(i)), frame.iloc[:, i])


def read_frame(group: h5py.Group) -> pd.DataFrame | None:
    """读取由 :func:`write_frame` 保存的结果表。"""
    if group.attrs.get("state") == "none":
        return None
    row_count = int(group.attrs["row_count"])
    columns = [_label_from_json(item) for item in json.loads(group.attrs["columns"])]
    series = [
        _read_series(group["data"][str(i)], name=columns[i])
        for i in range(len(columns))
    ]
    frame = pd.concat(series, axis=1) if series else pd.DataFrame(index=_read_index(group["index"], row_count))
    frame.columns = pd.Index(columns, name=_label_from_json(json.loads(group.attrs["columns_name"])))
    if len(frame) != row_count:
        raise ValueError("项目结果表数据长度与行数不一致")
    if series:
        frame.index = _read_index(group["index"], row_count)
    return frame
