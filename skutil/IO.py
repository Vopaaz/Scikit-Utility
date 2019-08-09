import pandas as pd
import threading
import logging
import os
import operator
import chardet
import csv
import numpy as np
import pandas as pd
import re

from skutil._exceptions import SpeculationFailedError
from pandas.api.types import is_string_dtype, is_numeric_dtype
import joblib
import inspect
from collections import OrderedDict
import hashlib


class DataReader(object):
    _instances = {}
    _instances_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if "_id" not in kwargs:
            _id = 0
        else:
            _id = kwargs["_id"]

        with DataReader._instances_lock:
            if _id in DataReader._instances:
                return DataReader._instances[_id]
            else:
                new_instance = object.__new__(cls)
                DataReader._instances[_id] = new_instance
                return new_instance

    def __init__(self, train_path=None, test_path=None, val_path=None, *, _id="default", read_func=None, **read_kwargs):
        assert read_func is None or callable(read_func)
        if hasattr(self, "_id"):
            self.__init_existed__(train_path=train_path, test_path=test_path,
                                  val_path=val_path, _id=_id, read_func=read_func, **read_kwargs)
        else:
            self.__init_new__(train_path=train_path, test_path=test_path,
                              val_path=val_path, _id=_id, read_func=read_func, **read_kwargs)

    def __init_existed__(self, train_path=None, test_path=None, val_path=None, *, _id="default", read_func=None, **read_kwargs):
        assert(_id == self._id)
        if train_path is not None:
            self.train_path = train_path
        if test_path is not None:
            self.test_path = test_path
        if val_path is not None:
            self.val_path = val_path

        if read_kwargs:
            if operator.eq(read_kwargs, self.__read_kwargs):
                logging.info(
                    f"Data reading configuration is already set for {self.__class__} object, it's unnecessary to set it again.")
            else:
                raise ValueError(
                    "Newly set data reading configuration is different from the cached value. If you do want this, please specify '_id=N' as a parameter.")

        if read_func:
            if read_func is self.__read_func:
                logging.info(
                    f"Data reading function is already set for {self.__class__} object, it's unnecessary to set it again.")
            else:
                raise ValueError(
                    "Newly set data reading function is different from the cached value. If you do want this, please specify '_id=N' as a parameter.")

    def __init_new__(self, train_path=None, test_path=None, val_path=None, *, _id="default", read_func=None, **read_kwargs):
        try:
            if train_path is not None:
                assert os.path.exists(train_path)
            if test_path is not None:
                assert os.path.exists(test_path)
            if val_path is not None:
                assert os.path.exists(val_path)
        except Exception as e:
            raise ValueError("Some path is invalid or does not exist.", e)

        self._id = _id
        self.__read_kwargs = read_kwargs
        self.__read_func = read_func

        if self.__read_func is None:
            self.__read_func = pd.read_csv

        if train_path:
            self._train_path = train_path
        if test_path:
            self._test_path = test_path
        if val_path:
            self._val_path = val_path

    @property
    def train_path(self):
        if hasattr(self, "_train_path"):
            return self._train_path
        else:
            raise AttributeError(
                f"'{self.__class__}' object has no attribute 'train_path'.")

    @train_path.setter
    def train_path(self, value):
        if hasattr(self, "_train_path"):
            if self.train_path == value:
                logging.info(
                    f"'train_path' of {self.__class__} object is already set as {value}, it's unnecessary to set it again.")
            else:
                raise ValueError(
                    "Newly set train_path is different from the cached value. If you do want this, please specify '_id=N' as a parameter.")
        else:
            logging.warning(
                f"A train path is set after the first initialization of {self.__class__}.")
            self._train_path = value

    @property
    def test_path(self):
        if hasattr(self, "_test_path"):
            return self._test_path
        else:
            raise AttributeError(
                f"'{self.__class__}' object has no attribute 'test_path'.")

    @test_path.setter
    def test_path(self, value):
        if hasattr(self, "_test_path"):
            if self.test_path == value:
                logging.info(
                    f"'test_path' of {self.__class__} object is already set as {value}, it's unnecessary to set it again.")
            else:
                raise ValueError(
                    "Newly set test_path is different from the cached value. If you do want this, please specify '_id=N' as a parameter.")
        else:
            logging.warning(
                f"A test path is set after the first initialization of {self.__class__}.")
            self._test_path = value

    @property
    def val_path(self):
        if hasattr(self, "_val_path"):
            return self._val_path
        else:
            raise AttributeError(
                f"'{self.__class__}' object has no attribute 'val_path'.")

    @val_path.setter
    def val_path(self, value):
        if hasattr(self, "_val_path"):
            if self.val_path == value:
                logging.info(
                    f"'val_path' of {self.__class__} object is already set as {value}, it's unnecessary to set it again.")
            else:
                raise ValueError(
                    "Newly set val_path is different from the cached value. If you do want this, please specify '_id=N' as a parameter.")
        else:
            logging.warning(
                f"A val path is set after the first initialization of {self.__class__}.")
            self._val_path = value

    @property
    def train(self):
        return self.__read_func(self.train_path, **self.__read_kwargs)

    @train.setter
    def train(self, value):
        raise ValueError(
            f"Attibute 'train' of {self.__class__} object is read only.")

    @property
    def test(self):
        return self.__read_func(self.test_path, **self.__read_kwargs)

    @test.setter
    def test(self, value):
        raise ValueError(
            f"Attibute 'test' of {self.__class__} object is read only.")

    @property
    def val(self):
        return self.__read_func(self.val_path, **self.__read_kwargs)

    @val.setter
    def val(self, value):
        raise ValueError(
            f"Attibute 'val' of {self.__class__} object is read only.")


class AutoSaver(object):
    def __init__(self, save_dir="", example_path=None, **default_kwargs):
        if example_path and default_kwargs:
            raise ValueError(
                "You cannot set both 'example_path' and give other saving kwargs at the same time.")

        if save_dir and not os.path.exists(save_dir):
            os.mkdir(save_dir)

        self.save_dir = save_dir
        self.example_path = example_path
        self.default_kwargs = default_kwargs

    def __save_by_to_csv(self, X, filename):
        if self.example_path and self.__used_kwargs:
            raise ValueError(
                "You cannot set both 'example_path' and give other saving kwargs at the same time.")

        if self.example_path:
            return self.__save_by_to_csv_speculating(X, filename)
        else:
            if not isinstance(X, (pd.DataFrame, pd.Series)):
                raise TypeError(
                    f"When using 'to_csv', 'X' must be a pd.DataFrame or pd.Series, rather than {X.__class__} if you do not provide an example csv file, or are using self-defined keyword parameters.")
            return X.to_csv(os.path.join(self.save_dir, filename), **self.__used_kwargs)

    def __speculate_index(self, s):
        s = s.copy()
        if is_string_dtype(s):
            return (True, s.iloc[0])

        step = len(s)//100 + 1

        for i in range(0, len(s)-1, step):
            if s.iloc[i+step] - s.iloc[i] != step:
                return (False,)
        return (True, s.iloc[0])

    def __try_add_column(self, X, example_df):
        e = SpeculationFailedError(
            "The number of columns of 'X' is smaller than that in the example file.")
        col_ix = example_df.shape[1] - X.shape[1] - 1
        example_spec = self.__speculate_index(example_df.iloc[:, col_ix])
        if example_spec[0]:
            X = X.reset_index(level=0)
            try:
                X.iloc[:, 0] = X.iloc[:, 0].astype(int)
            except:
                pass
            X_spec = self.__speculate_index(X.iloc[:, 0])
            if X_spec[0] and X_spec[1] == example_spec[1]:
                pass  # Index addition OK
            else:
                if example_spec[1] == 0:
                    X.iloc[:, 0] = np.arange(X.shape[0])
                elif example_spec[1] == 1:
                    X.iloc[:, 1] = np.arange(1, X.shape[0]+1)
                else:
                    raise e
        else:
            raise e

        return X

    def __save_by_to_csv_speculating(self, X, filename):
        if not isinstance(X, (pd.DataFrame, pd.Series, np.ndarray)):
            raise TypeError(
                f"When using 'to_csv', 'X' must be either a pd.DataFrame, pd.Series or np.ndarray, rather than {X.__class__} if you provide an example csv file.")

        fullpath = os.path.join(self.save_dir, filename)

        with open(self.example_path, "rb") as f:
            buffer = f.read()
            enc = chardet.detect(buffer)["encoding"]

        with open(self.example_path, "r", encoding=enc) as f:
            df = pd.read_csv(f, header=None, nrows=1)

        has_header = is_string_dtype(df.iloc[0, :])

        with open(self.example_path, "r", encoding=enc) as f:
            sniffer = csv.Sniffer()
            content = f.read()
            try:
                dialect = sniffer.sniff(content)
                has_header = sniffer.has_header(content) or has_header

            except:
                fixed_content = "\n".join(
                    line+"," for line in content.split("\n"))
                dialect = sniffer.sniff(fixed_content)
                has_header = sniffer.has_header(fixed_content) or has_header

            dialect_kwargs = {
                "sep": dialect.delimiter,
                "line_terminator": dialect.lineterminator,
                "doublequote": dialect.doublequote,
                "quotechar": dialect.quotechar,
                "escapechar": dialect.escapechar,
                "quoting": dialect.quoting
            }

            f.seek(0, 0)
            example_df = pd.read_csv(
                f, dialect=dialect, index_col=False, header=0 if has_header else None)

        X = pd.DataFrame(X)

        while X.shape[1] > example_df.shape[1]:
            # Drop columns of X
            if self.__speculate_index(X.iloc[:, 0])[0]:
                X = X.drop(columns=[X.columns.values[0]])
            else:
                raise SpeculationFailedError(
                    "The number of columns of 'X' is larger than that in the example file.")

        while X.shape[1] < example_df.shape[1]:
            X = self.__try_add_column(X, example_df)

        for i in range(X.shape[1]):
            if self.__speculate_index(X.iloc[:, i])[0] and is_numeric_dtype(X.iloc[:, i]):
                X.iloc[:, i] = X.iloc[:, i].astype(int)
            else:
                break

        example_spec_res = self.__speculate_index(example_df.iloc[:, 0])
        if example_spec_res[0] and is_numeric_dtype(example_spec_res[1]):
            X.iloc[:, 0] = np.arange(
                example_spec_res[1], example_spec_res[1]+X.shape[0])

        if has_header:
            return X.to_csv(fullpath, header=example_df.columns, index=False, **dialect_kwargs)
        else:
            return X.to_csv(fullpath, header=False, index=False, **dialect_kwargs)

    def save(self, X, filename, memo=None, **kwargs):
        self.__used_kwargs = {**self.default_kwargs, **kwargs}

        res = self.__save_by_to_csv(X, filename)

        if memo:
            with open(os.path.join(self.save_dir, "memo.txt"), "a+", encoding="utf-8") as f:
                f.write(f"{filename}: {str(memo)}" + "\n")

        return res


def checkpoint(func):
    save_dir = ".skutil-checkpoint"

    def get_file_info(obj):
        filename = inspect.getfile(obj)
        ipython_filename_pattern = r"<ipython-input-\d+-(.{12})>"
        ipython_result = re.compile(ipython_filename_pattern).match(filename)
        if ipython_result:
            file_info = f"ipynb-{ipython_result.group(1)}"
        else:
            file_info, _ = os.path.splitext(os.path.basename(filename))

        return file_info

    def get_name(applied_args, func):
        file_info = get_file_info(func)
        qualname = func.__qualname__
        is_class_function = inspect.ismethod

        identify_args = {}
        for key, value in applied_args.items():
            if key == ("cls" if is_class_function(func) else "self"):
                pass
            elif inspect.isclass(value):
                logging.warning(
                    f"A class is used as the parameter of {str(value)}, it may cause mistake when detecting whether there is checkpoint for this call.")
                identify_args[key] = value.__qualname__
            elif inspect.ismethod(value) or inspect.isfunction(value):
                logging.warning(
                    f"A function is used as the parameter of {str(value)}, it may cause mistake when detecting whether there is checkpoint for this call.")
                tmp_applied_args = get_applied_args(value, (), {})
                identify_args[key] = get_name(tmp_applied_args, value)
            elif isinstance(value, pd.DataFrame):
                if value.shape[0] > value.shape[1]:
                    identify_args[key] = pd.util.hash_pandas_object(
                        value.T).to_json(orient='values')
                else:
                    identify_args[key] = pd.util.hash_pandas_object(
                        value).to_json(orient='values')
            elif isinstance(value, pd.Series):
                identify_args[key] = pd.util.hash_pandas_object(
                    pd.DataFrame(value).T).to_json(orient='values')
            elif isinstance(value, np.ndarray):
                if value.flags['C_CONTIGUOUS']:
                    identify_args[key] = hashlib.md5(value).hexdigest()
                else:
                    identify_args[key] = hashlib.md5(
                        np.ascontiguousarray(value)).hexdigest()
            else:
                identify_args[key] = str(value) + str(type(value))

        identify_args_str = "-".join([k+":"+v for k,
                                      v in identify_args.items()])

        full_str = f"{file_info}-{qualname}-{identify_args_str}"
        logging.debug(f"Identification String: {full_str}")
        return full_str

    def get_hash(str_):
        h = hashlib.md5()
        h.update(str_.encode("utf-8"))
        return h.hexdigest()

    def get_applied_args(func, args, kwargs):
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

    def inner(*args, __overwrite__=False, **kwargs):
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)

        if not isinstance(__overwrite__, bool):
            raise TypeError("'__overwrite__' parameter must be a boolean type")

        applied_args = get_applied_args(func, args, kwargs)
        name = get_name(applied_args, func)
        hash_val = get_hash(name)

        cache_path = os.path.join(save_dir, f"{hash_val}.pkl")
        if os.path.exists(cache_path) and not __overwrite__:
            return joblib.load(cache_path)
        else:
            res = func(*args, **kwargs)
            joblib.dump(res, cache_path)
            return res
    return inner
