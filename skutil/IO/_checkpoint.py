import hashlib
import inspect
import logging
import os
import re
from collections import OrderedDict

import joblib
import numpy as np
import pandas as pd


def _get_file_info(obj):
    filename = inspect.getfile(obj)
    ipython_filename_pattern = r"<ipython-input-\d+-(.{12})>"
    ipython_result = re.compile(ipython_filename_pattern).match(filename)
    if ipython_result:
        file_info = f"ipynb-{ipython_result.group(1)}"
    else:
        file_info, _ = os.path.splitext(os.path.basename(filename))

    return file_info


def _get_identify_str_for_cls_or_self(obj):
    identify_dict = {}
    for attr in dir(obj):
        if attr.startswith("__") and attr.endswith("__"):
            pass
        else:
            value = getattr(obj, attr)
            if inspect.ismethod(value) or inspect.isclass(value) or inspect.isfunction(value):
                pass
            else:
                if isinstance(value, (pd.DataFrame, pd.Series)):
                    identify_dict[attr] = _hash_pd_object(value)

                elif isinstance(value, np.ndarray):
                    identify_dict[attr] = _hash_np_array(value)

                else:
                    identify_dict[attr] = str(value) + str(type(value))

    return "-".join([k+":"+v for k, v in identify_dict.items()])


def _hash_pd_object(obj):
    if isinstance(obj, pd.DataFrame):
        if obj.shape[0] > obj.shape[1]:
            return pd.util.hash_pandas_object(
                obj.T).to_csv(index=True, header=True)
        else:
            return pd.util.hash_pandas_object(
                obj).to_csv(index=True, header=True)

    elif isinstance(obj, pd.Series):
        return pd.util.hash_pandas_object(
            pd.DataFrame(obj).T).to_csv(index=True, header=True)


def _hash_np_array(arr):
    if arr.flags['C_CONTIGUOUS']:
        return hashlib.md5(arr).hexdigest()
    else:
        return hashlib.md5(
            np.ascontiguousarray(arr)).hexdigest()


def _get_identify_str_for_value(value):
    if isinstance(value, (pd.DataFrame, pd.Series)):
        return _hash_pd_object(value)

    elif isinstance(value, np.ndarray):
        return _hash_np_array(value)

    else:
        return str(value) + str(type(value))


def _get_identify_str_for_func(func, applied_args, ignore=[]):
    file_info = _get_file_info(func)
    qualname = func.__qualname__

    identify_args = {}
    for key, value in applied_args.items():
        logging.debug(key)
        logging.debug(inspect.ismethod(func))
        logging.debug(func)
        if key in ignore:
            pass

        elif key in ("cls", "self"):
            identify_args[key] = _get_identify_str_for_cls_or_self(value)

        elif inspect.isclass(value):
            logging.warning(
                f"A class is used as the parameter of {str(value)}, it may cause mistake when detecting whether there is checkpoint for this call.")
            identify_args[key] = value.__qualname__

        elif inspect.ismethod(value) or inspect.isfunction(value):
            logging.warning(
                f"A function is used as the parameter of {str(value)}, it may cause mistake when detecting whether there is checkpoint for this call.")
            tmp_applied_args = _get_applied_args(value, (), {})
            identify_args[key] = _get_identify_str_for_func(
                value, tmp_applied_args)

        else:
            identify_args[key] = _get_identify_str_for_value(value)

    identify_args_str = "-".join([k+":"+v for k,
                                  v in identify_args.items()])

    full_str = f"{file_info}-{qualname}-{identify_args_str}"
    logging.debug(f"Identification String: {full_str}")
    return full_str


def _get_hash_of_str(str_):
    h = hashlib.md5()
    h.update(str_.encode("utf-8"))
    return h.hexdigest()


def _get_applied_args(func, args, kwargs):
    # Get default args and kwargs
    signature = inspect.signature(func)
    applied_args = OrderedDict({
        k: v.default
        for k, v in signature.parameters.items() if k != "__overwrite__"
    })

    # update call args into applied_args
    items = list(applied_args.items())
    for ix, arg in enumerate(args):
        applied_args[items[ix][0]] = arg
    for key, value in kwargs.items():
        applied_args[key] = value

    return applied_args


def checkpoint(ignore=[]):
    save_dir = ".skutil-checkpoint"

    if callable(ignore):
        param_is_callable = True
        func = ignore
        ignore = []
    elif isinstance(ignore, (list, tuple)):
        param_is_callable = False
    else:
        raise TypeError(f"Unsupported parameter type '{type(ignore)}'")

    def wrapper(func):
        def inner(*args, __overwrite__=False, **kwargs):
            if not os.path.exists(save_dir):
                os.mkdir(save_dir)

            if not isinstance(__overwrite__, bool):
                raise TypeError(
                    "'__overwrite__' parameter must be a boolean type")

            applied_args = _get_applied_args(func, args, kwargs)
            id_str = _get_identify_str_for_func(func, applied_args, ignore)
            hash_val = _get_hash_of_str(id_str)

            cache_path = os.path.join(save_dir, f"{hash_val}.pkl")
            if os.path.exists(cache_path) and not __overwrite__:
                return joblib.load(cache_path)
            else:
                res = func(*args, **kwargs)
                joblib.dump(res, cache_path)
                return res
        return inner

    if param_is_callable:
        return wrapper(func)
    else:
        return wrapper
